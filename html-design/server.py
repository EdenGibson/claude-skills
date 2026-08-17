#!/usr/bin/env python3
"""Lightweight live-reload static server for iterating on HTML designs.

Pure Python standard library — no pip installs, no Node, ~20 MB RSS (one process).
Serves a folder of design files, injects a tiny SSE snippet into every HTML
response so a browser auto-refreshes the instant a file changes, and auto-builds
a gallery when the folder holds more than one design.

Usage:
    server.py [dir] [port]     start (default dir ~/design-lab, default port 4321)
    server.py stop [port]      stop the server running on <port> (default 4321)

Reuse: if <port> is already bound, start() assumes a server is already running
for this design lab and exits 0 without starting a second one.
"""
import os
import re
import sys
import socket
import subprocess
import tempfile
import time
import html as html_mod
import json
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 4321
DEFAULT_DIR = os.path.expanduser("~/design-lab")
POLL_SECONDS = 0.3

WORKLOG_PORT = 4370
WORKLOG_DIR = os.path.expanduser("~/worklog")
# Board order. `running` first because that is the only row you act on.
# The worklog CLI keeps its own STATES copy (skills/worklog/worklog.py) on
# purpose: the two skills stay independent, so nothing enforces agreement.
# Change one, change the other.
WORKLOG_STATES = ("running", "blocked", "failed", "done")

HERE = os.path.dirname(os.path.abspath(__file__))

# chart.py sits beside this file and renders worklog's live diagrams. The path
# insert is what makes the import work when a test loads server.py by path
# rather than running it, where sys.path[0] is the caller's directory.
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:
    import chart  # noqa: E402
except Exception:  # pragma: no cover - a broken chart.py must cost only charts
    # Unguarded, a syntax error in chart.py stops this process from starting,
    # which takes Design Lab on 4321 down with worklog on 4370. Charts are
    # decoration on top of a log that has to survive.
    class _NoCharts:
        @staticmethod
        def render_panel(_task_dir):
            return ""

    chart = _NoCharts()

KATEX_DIR = os.path.join(HERE, "vendor", "katex")
KATEX_VERSION = "0.16.45"  # matches vendor/katex/VERSION.txt
KATEX_ROUTE = "/__katex"
VENDOR_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
}

# Injected before </body> (or appended) into every served HTML page.
# __PAGE_QS__ becomes `?page=<file>` on a design page and `` on the gallery.
LIVERELOAD_SNIPPET = """
<script data-livereload>
(function () {
  // Browsers cap ~6 concurrent connections per origin, and an SSE stream holds
  // one open for as long as the page lives. Six backgrounded design tabs used to
  // exhaust the pool, after which EVERY new request to this origin queued
  // forever and pages simply spun. So only a *visible* tab keeps a stream open;
  // hidden tabs drop theirs and re-check the folder signature when you return.
  var es = null, sig = null;
  // One design folder is shared by every parallel agent session. A design page
  // therefore watches only itself, or another session's write would reload a
  // page nobody touched and throw away its scroll position. The gallery sends
  // no page and keeps watching the folder, so new designs still show up.
  var QS = '__PAGE_QS__';

  function readSig(cb) {
    try {
      fetch('/__sig' + QS, { cache: 'no-store' })
        .then(function (r) { return r.text(); })
        .then(cb)
        .catch(function () {});
    } catch (_) {}
  }

  function open() {
    if (es || document.hidden) return;
    try {
      es = new EventSource('/__livereload' + QS);
      es.onmessage = function (e) { if (e.data === 'reload') location.reload(); };
    } catch (_) { es = null; }
  }

  function close() {
    if (es) { try { es.close(); } catch (_) {} es = null; }
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { close(); return; }
    // Missed edits while we were disconnected? Catch up, else just reconnect.
    readSig(function (now) { if (sig !== null && now !== sig) location.reload(); else open(); });
  });
  window.addEventListener('pagehide', close);

  readSig(function (s) { sig = s; });
  open();
})();
</script>
""".strip()


# --- LaTeX (KaTeX) support ------------------------------------------------
#
# Math renders with zero boilerplate in the mockup: write $$…$$ or \(…\) and
# the server wires up KaTeX itself. Assets are vendored (this box has no
# outbound internet, and a mockup that needs a CDN breaks the moment the laptop
# is offline); the CDN is only a fallback if vendor/ is missing.
#
# Injection is conditional. KaTeX is ~600 KB of JS + fonts, and auto-render
# rewrites text nodes, so a landing page with no math must stay untouched.

# Regions whose contents are never math: auto-render skips them at runtime, so
# detection must skip them too, or a regex literal in a <script> pulls in KaTeX.
_NON_CONTENT = re.compile(
    r"<!--.*?-->|<(script|style|pre|code|textarea)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_OPT_OUT = re.compile(r"""data-latex\s*=\s*["']?\s*(off|false|none)""", re.IGNORECASE)
# A design that already wires up its own math engine gets left alone entirely:
# a second KaTeX would overwrite the global and auto-render would re-walk output
# the page had already rendered itself. (Real case: equation-ladder.html.)
_SELF_MANAGED = re.compile(
    r"katex(\.min)?\.(js|mjs|css)|katex\.render|renderMathInElement|mathjax",
    re.IGNORECASE,
)
_OPT_IN = re.compile(r"data-latex(?![\w-])", re.IGNORECASE)
_DOLLAR_MODE = re.compile(r"""data-latex\s*=\s*["']?[^"'>]*dollar""", re.IGNORECASE)
_CHEM = re.compile(r"\\(ce|pu)\s*\{")
_MATH_MARKERS = (
    re.compile(r"\$\$[^$]{1,4000}?\$\$", re.DOTALL),          # $$ … $$
    re.compile(r"\\\([\s\S]{1,4000}?\\\)"),                    # \( … \)
    re.compile(r"\\\[[\s\S]{1,4000}?\\\]"),                    # \[ … \]
    re.compile(r"\\begin\{[a-zA-Z]+\*?\}"),                    # \begin{align} …
    _CHEM,                                                     # \ce{H2O}
)


def _content_only(html_text):
    """Strip comments and the tags auto-render ignores, so detection sees only
    text that KaTeX would actually be allowed to rewrite."""
    return _NON_CONTENT.sub(" ", html_text)


def wants_katex(html_text):
    """True if this page should get KaTeX wired up.

    Precedence: explicit `data-latex="off"` wins, then the "page already has a
    math engine" guard, then a `data-latex` attribute anywhere in the markup
    (for math a script inserts later), then the delimiters themselves.

    Everything but the opt-out/self-managed checks looks at markup only —
    `data-latex` built inside a template literal is code, not a request."""
    if _OPT_OUT.search(html_text):
        return False
    if _SELF_MANAGED.search(html_text):
        return False
    body = _content_only(html_text)
    if _OPT_IN.search(body):
        return True
    return any(rx.search(body) for rx in _MATH_MARKERS)


def wants_dollar_math(html_text):
    """Single-`$` delimiters are opt-in via data-latex="dollars".

    Off by default on purpose: half the mockups in the lab are pricing pages,
    and `$29 … $49` would silently become math."""
    return bool(_DOLLAR_MODE.search(html_text))


def wants_mhchem(html_text):
    """Load the chemistry extension only for pages using \\ce{} / \\pu{}."""
    return bool(_CHEM.search(_content_only(html_text)))


def katex_base():
    """Where the browser fetches KaTeX from: this server if the assets are
    vendored, else jsDelivr so the skill still works on a box without them."""
    if os.path.isfile(os.path.join(KATEX_DIR, "katex.min.js")):
        return KATEX_ROUTE
    return f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist"


def katex_head(base):
    return f'<link rel="stylesheet" href="{base}/katex.min.css" data-katex>'


def katex_body(base, dollar=False, chem=False):
    """Deferred KaTeX + auto-render, then a bootstrap that renders the page.

    `defer` keeps the three external scripts in order and ahead of
    DOMContentLoaded; the inline bootstrap (inline scripts ignore `defer`)
    retries briefly in case it runs before they land."""
    dollar_pair = (
        "\n    {left: '$', right: '$', display: false},"  # AFTER $$: longest match first
        if dollar else ""
    )
    chem_tag = (
        f'\n<script defer src="{base}/contrib/mhchem.min.js" data-katex></script>'
        if chem else ""
    )
    return f"""
<script defer src="{base}/katex.min.js" data-katex></script>{chem_tag}
<script defer src="{base}/contrib/auto-render.min.js" data-katex></script>
<script data-katex-bootstrap>
(function () {{
  var OPTS = {{
    delimiters: [
      {{left: '$$', right: '$$', display: true}},{dollar_pair}
      {{left: '\\\\[', right: '\\\\]', display: true}},
      {{left: '\\\\(', right: '\\\\)', display: false}},
      {{left: '\\\\begin{{equation}}', right: '\\\\end{{equation}}', display: true}},
      {{left: '\\\\begin{{equation*}}', right: '\\\\end{{equation*}}', display: true}},
      {{left: '\\\\begin{{align}}', right: '\\\\end{{align}}', display: true}},
      {{left: '\\\\begin{{align*}}', right: '\\\\end{{align*}}', display: true}},
      {{left: '\\\\begin{{gather}}', right: '\\\\end{{gather}}', display: true}},
      {{left: '\\\\begin{{alignat}}', right: '\\\\end{{alignat}}', display: true}},
      {{left: '\\\\begin{{CD}}', right: '\\\\end{{CD}}', display: true}}
    ],
    throwOnError: false,
    errorColor: '#e5484d',
    strict: false,
    ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option'],
    ignoredClasses: ['no-katex']
  }};
  function render(el) {{
    if (!window.renderMathInElement) return false;
    try {{ window.renderMathInElement(el || document.body, OPTS); }} catch (e) {{}}
    return true;
  }}
  // Call window.renderMath(el) after inserting math with JS.
  window.renderMath = render;
  window.katexOptions = OPTS;
  var tries = 0;
  function go() {{ if (!render() && ++tries < 60) setTimeout(go, 50); }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', go);
  }} else {{
    go();
  }}
}})();
</script>
""".strip()


def pidfile_for(port):
    return os.path.join(tempfile.gettempdir(), f"design-lab-{port}.pid")


def design_files(directory):
    """Top-level .html files (excluding the generated index), newest first.

    Ordered by mtime descending, not by name: the lab accumulates months of
    mockups, and what you almost always want is whatever you just edited — an
    alphabetical list buries it behind whatever happens to start with 'a'.
    Equal mtimes tie-break by name so the order stays stable.
    """
    try:
        names = [
            n for n in os.listdir(directory)
            if n.lower().endswith(".html") and n.lower() != "index.html"
            and os.path.isfile(os.path.join(directory, n))
        ]
    except OSError:
        return []

    def mtime(n):
        try:
            return os.stat(os.path.join(directory, n)).st_mtime
        except OSError:
            return 0.0  # unreadable: sort last, still listed

    return sorted(names, key=lambda n: (-mtime(n), n))


def age_label(mtime, now=None):
    """Short, human 'when was this touched' string for a gallery card."""
    now = time.time() if now is None else now
    delta = now - mtime
    if delta < 90:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    if delta < 7 * 86400:
        return f"{int(delta // 86400)}d ago"
    return time.strftime("%b %-d", time.localtime(mtime))


def watch_signature(directory, only=None):
    """A cheap fingerprint of the design folder: changes when any html/css/js
    file is edited, added, or removed. Used to decide when to push a reload.

    `only=<name>` narrows it to that one page plus the shared top-level css/js.
    The folder is shared by every parallel agent session, so a folder-wide
    fingerprint made one session's write reload every other session's tab. An
    unknown name falls back to the folder-wide fingerprint, which is both the
    safe answer for a deleted page and the reason a traversal attempt reads
    nothing outside the folder."""
    if only is not None:
        only = os.path.basename(only)
        if not only or not os.path.isfile(os.path.join(directory, only)):
            only = None
    sig = []
    try:
        for n in sorted(os.listdir(directory)):
            if not n.lower().endswith((".html", ".css", ".js")):
                continue
            if only is not None and n != only and n.lower().endswith(".html"):
                continue
            p = os.path.join(directory, n)
            try:
                st = os.stat(p)
            except OSError:
                continue
            sig.append((n, st.st_mtime, st.st_size))
    except OSError:
        pass
    return tuple(sig)


def _insert_before(text, tag, snippet):
    """Insert snippet before the last `tag` (e.g. </body>), else append."""
    idx = text.lower().rfind(tag)
    if idx == -1:
        return text + "\n" + snippet
    return text[:idx] + snippet + "\n" + text[idx:]


def inject(html_bytes, live=True, page=None):
    """Wire up the page: KaTeX if it contains math, live-reload if requested.

    `live=False` is for gallery-preview iframes — they still render math, but
    must not open an SSE stream (browsers cap ~6 connections per origin).
    `page=<name>` scopes the reload stream to that file; None watches the
    whole folder and is what the gallery wants."""
    text = html_bytes.decode("utf-8", "replace")
    if wants_katex(text):
        base = katex_base()
        # Stylesheet as early as possible so glyphs never flash unstyled;
        # fall back through </head> -> <body> -> top of document.
        lower = text.lower()
        if "</head>" in lower:
            text = _insert_before(text, "</head>", katex_head(base))
        elif "<body" in lower:
            at = lower.find("<body")
            text = text[:at] + katex_head(base) + "\n" + text[at:]
        else:
            text = katex_head(base) + "\n" + text
        text = _insert_before(
            text, "</body>",
            katex_body(base, dollar=wants_dollar_math(text), chem=wants_mhchem(text)),
        )
    if live:
        qs = f"?page={urllib.parse.quote(page)}" if page else ""
        text = _insert_before(text, "</body>",
                              LIVERELOAD_SNIPPET.replace("__PAGE_QS__", qs))
    return text.encode("utf-8")


def gallery_page(directory):
    cards = []
    names = design_files(directory)
    for name in names:
        safe = html_mod.escape(name)
        try:
            when = age_label(os.stat(os.path.join(directory, name)).st_mtime)
        except OSError:
            when = ""
        cards.append(
            f'<a class="card" href="/{safe}">'
            # ?embed=1 keeps the live-reload EventSource out of preview iframes:
            # browsers cap ~6 connections per origin, so with many designs the
            # iframes' SSE streams would exhaust the pool and clicks would hang.
            f'<div class="frame"><iframe src="/{safe}?embed=1" loading="lazy" '
            f'tabindex="-1" scrolling="no"></iframe></div>'
            f'<span class="name">{safe}<time>{html_mod.escape(when)}</time></span></a>'
        )
    body = "\n".join(cards) or '<p class="empty">No designs yet.</p>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Design lab</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; font:15px/1.5 system-ui,sans-serif; background:#0f1115; color:#e7e9ee; }}
  header {{ padding:20px 28px; border-bottom:1px solid #232734; }}
  header h1 {{ margin:0; font-size:16px; font-weight:600; letter-spacing:.02em; }}
  header p {{ margin:4px 0 0; color:#8b90a0; font-size:13px; }}
  .grid {{ display:grid; gap:18px; padding:28px;
           grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); }}
  .card {{ display:block; text-decoration:none; color:inherit;
           border:1px solid #232734; border-radius:12px; overflow:hidden;
           background:#161922; transition:border-color .15s,transform .15s; }}
  .card:hover {{ border-color:#3b82f6; transform:translateY(-2px); }}
  .frame {{ height:200px; overflow:hidden; background:#fff; }}
  .frame iframe {{ width:1280px; height:800px; border:0;
                   transform:scale(.3125); transform-origin:0 0; pointer-events:none; }}
  .name {{ display:flex; gap:12px; align-items:baseline; justify-content:space-between;
           padding:10px 14px; font-size:13px; border-top:1px solid #232734; }}
  .name time {{ color:#8b90a0; font-size:12px; font-variant-numeric:tabular-nums;
                white-space:nowrap; flex:none; }}
  .empty {{ padding:40px; color:#8b90a0; }}
</style></head>
<body>
<header><h1>Design lab</h1><p>{len(names)} design(s) · newest first · live-reloads on change</p></header>
<div class="grid">
{body}
</div>
{LIVERELOAD_SNIPPET}
</body></html>"""


def worklog_slug(slug):
    """The one safe form of a slug, or None when it is not a task name.

    os.path.basename strips any directory part, but basename("..") is "..",
    which then reaches os.walk(<root>/..) and os.path.isdir(<root>/..). On the
    live service that parent is $HOME. "." is the worklog root itself. Both are
    refused here rather than at each call site, so a new caller cannot forget.

    "../../etc" was never the dangerous string — its basename is "etc".
    """
    slug = os.path.basename(slug or "")
    if not slug or slug in (".", ".."):
        return None
    return slug


def worklog_read_meta(directory, slug):
    """Parse <slug>/meta.json into a dict with every field filled in.

    Returns None when the directory or the file is missing, or the JSON is
    unreadable. Callers skip such a task rather than failing: an agent killed
    midway through `worklog start` leaves exactly this state, and one broken
    task must never take the whole board down.
    """
    slug = worklog_slug(slug)
    if not slug:
        return None
    try:
        with open(os.path.join(directory, slug, "meta.json"),
                  encoding="utf-8") as f:
            meta = json.load(f)
    # Deliberately every exception, not (OSError, ValueError). json.load raises
    # RecursionError on deeply nested JSON, which is neither, and one such file
    # used to kill the handler thread and blank the whole board. The contract
    # of this function is that a bad meta.json is skipped, never fatal.
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None
    meta["slug"] = slug
    # Coerce, do not trust. json.load happily yields ints, lists and dicts,
    # and html.escape() calls .replace() on whatever it is given — one task
    # with `"title": 42` used to kill the handler thread and blank the whole
    # board, not just its own row.
    for key, fallback in (("title", slug), ("summary", ""),
                          ("created", ""), ("updated", "")):
        value = meta.get(key)
        if isinstance(value, str):
            meta[key] = value
        elif value is None:
            meta[key] = ""
        else:
            meta[key] = str(value)
    if not meta["title"]:
        meta["title"] = slug
    if meta.get("state") not in WORKLOG_STATES:
        meta["state"] = "running"
    return meta


def worklog_tasks(directory):
    """Every readable task, in board order.

    Order is state rank, then most recently touched first, then slug. Recency
    reads the mtime of log.html and meta.json rather than the directory's own,
    because appending to a file does not update the parent directory's mtime.
    """
    try:
        entries = sorted(os.listdir(directory))
    except OSError:
        return []

    tasks = []
    for slug in entries:
        if slug.startswith("."):
            continue
        if not os.path.isdir(os.path.join(directory, slug)):
            continue
        meta = worklog_read_meta(directory, slug)
        if meta is None:
            continue
        mtime = 0.0
        for name in ("log.html", "meta.json"):
            try:
                mtime = max(mtime,
                            os.stat(os.path.join(directory, slug, name)).st_mtime)
            except OSError:
                pass
        meta["_mtime"] = mtime
        tasks.append(meta)

    rank = {s: i for i, s in enumerate(WORKLOG_STATES)}
    return sorted(tasks, key=lambda t: (rank[t["state"]], -t["_mtime"], t["slug"]))


def worklog_signature(directory, slug=None):
    """Fingerprint of one task tree, or of the board when slug is None.

    A task page must notice a new chart under assets/, so a given slug walks
    its whole tree recursively. The board shows only title, state, summary
    and age, none of which comes from assets/, so the board fingerprint stats
    just meta.json and log.html per task rather than walking everything.

    Kept separate from watch_signature(): that one takes a top-level file
    name and validates it with os.path.isfile, so teaching it about
    directories would tangle both modes.

    An unknown or traversing slug falls back to the board fingerprint. That
    is the safe answer for a deleted task. worklog_slug() is what keeps a
    traversal out: a bare `..` would otherwise walk the parent of the worklog
    root, which on the live service is $HOME, on every 0.3s poll.
    """
    if slug is not None:
        slug = worklog_slug(slug)
        candidate = os.path.join(directory, slug or "")
        if slug and os.path.isdir(candidate):
            # A task page must notice a new chart under assets/, so walk it all.
            sig = []
            for dirpath, dirnames, filenames in os.walk(candidate):
                dirnames.sort()
                for name in sorted(filenames):
                    p = os.path.join(dirpath, name)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    sig.append((os.path.relpath(p, directory),
                                st.st_mtime, st.st_size))
            return tuple(sig)

    # Board fingerprint. Only the two files the board actually reads, so cost
    # is 2 stats per task rather than a full walk. Measured before this bound:
    # 7320 files took 415ms per call against a 300ms poll, so the SSE loop
    # never slept.
    try:
        slugs = sorted(n for n in os.listdir(directory)
                       if not n.startswith(".")
                       and os.path.isdir(os.path.join(directory, n)))
    except OSError:
        return ()
    sig = []
    for name in slugs:
        for fname in ("meta.json", "log.html"):
            p = os.path.join(directory, name, fname)
            try:
                st = os.stat(p)
            except OSError:
                continue
            sig.append((os.path.relpath(p, directory), st.st_mtime, st.st_size))
    return tuple(sig)


WORKLOG_CSS = """
  :root { color-scheme: dark; }
  body { margin:0; font:15px/1.5 system-ui,sans-serif; background:#0f1115; color:#e7e9ee; }
  header { padding:20px 28px; border-bottom:1px solid #232734; }
  header h1 { margin:0; font-size:16px; font-weight:600; letter-spacing:.02em; }
  header p { margin:4px 0 0; color:#8b90a0; font-size:13px; }
  .rows { padding:16px 28px 40px; }
  .row { display:grid; grid-template-columns:88px 1fr auto; gap:16px; align-items:baseline;
         padding:14px 16px; margin-bottom:8px; text-decoration:none; color:inherit;
         border:1px solid #232734; border-radius:10px; background:#161922;
         transition:border-color .15s, transform .15s; }
  .row:hover { border-color:#3b82f6; transform:translateY(-1px); }
  .chip { font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
          padding:3px 8px; border-radius:999px; text-align:center; }
  .chip.running { background:#12324d; color:#7cc4ff; }
  .chip.blocked { background:#4a3a12; color:#ffd479; }
  .chip.failed  { background:#4d1f1f; color:#ff9d9d; }
  .chip.done    { background:#173d2a; color:#7ee2a8; }
  .title { font-weight:500; }
  .summary { display:block; color:#8b90a0; font-size:13px; font-weight:400; }
  time { color:#8b90a0; font-size:12px; font-variant-numeric:tabular-nums; white-space:nowrap; }
  .empty { padding:40px 28px; color:#8b90a0; }
  main { padding:24px 28px 60px; max-width:1000px; }
  .wl-entry { border-left:2px solid #232734; padding:2px 0 2px 16px; margin:0 0 18px; }
  .wl-entry:first-of-type { border-left-color:#3b82f6; }
  time.wl-when { display:block; margin:0 0 8px; color:#8b90a0; font-size:12px;
                 font-variant-numeric:tabular-nums; letter-spacing:.02em; }
  .wl-entry > :first-child { margin-top:0; }
  .wl-entry > :last-child { margin-bottom:0; }
  .wl-entry img, .wl-entry svg { max-width:100%; height:auto; }
  .wl-entry pre { overflow-x:auto; background:#161922; padding:12px; border-radius:8px; }
  .wl-entry table { border-collapse:collapse; }
  .wl-entry th, .wl-entry td { border:1px solid #232734; padding:6px 10px; text-align:left; }
  .wl-charts { margin:0 0 22px; }
  .wl-chart { margin:0 0 14px; padding:10px 14px 6px; border:1px solid #232734;
              border-radius:10px; background:#161922; }
  .wl-chart:last-child { margin-bottom:0; }
  a.back { color:#8b90a0; text-decoration:none; font-size:13px; }
  a.back:hover { color:#e7e9ee; }
""".strip()


def worklog_board(directory):
    """The front page: one row per task, most actionable first.

    Carries no live-reload script of its own. LIVERELOAD_SNIPPET holds a
    __PAGE_QS__ placeholder that only inject() substitutes, so a template copy
    would ship `var QS = '__PAGE_QS__'` to the browser. The caller sends this
    through inject(live=True, page=None), exactly as a task page goes.
    """
    tasks = worklog_tasks(directory)
    rows = []
    for t in tasks:
        href = html_mod.escape(urllib.parse.quote(t["slug"]), quote=True)
        title = html_mod.escape(t["title"])
        state = html_mod.escape(t["state"])
        summary = html_mod.escape(t["summary"])
        when = html_mod.escape(age_label(t["_mtime"])) if t["_mtime"] else ""
        summary_html = f'<span class="summary">{summary}</span>' if summary else ""
        rows.append(
            f'<a class="row" href="/{href}/">'
            f'<span class="chip {state}">{state}</span>'
            f'<span class="title">{title}{summary_html}</span>'
            f'<time>{when}</time></a>'
        )
    body = "\n".join(rows) or '<p class="empty">No tasks yet.</p>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Worklog</title>
<style>
{WORKLOG_CSS}
</style></head>
<body>
<header><h1>Worklog</h1><p>{len(tasks)} task(s) · live-reloads on change</p></header>
<div class="rows">
{body}
</div>
</body></html>"""


ENTRY_SPLIT_RE = re.compile(r'(?m)^(?=<section class="wl-entry")')
ENTRY_OPEN_RE = re.compile(r'^<section class="wl-entry" data-ts="([^"]*)">')


def worklog_newest_first(log):
    """Reverse the appended entries, and give each one a time label.

    log.html is append-only, so the oldest entry is first on disk. The page
    Eden leaves open reloads on every append. Oldest-first made him scroll to
    the bottom after every reload to find what changed, so the page now puts
    the newest entry at the top. The file on disk does not change.

    The split matches the opening tag only, never the closing one, so a
    fragment that nests its own </section> stays in one piece. Any text before
    the first entry stays at the top.
    """
    parts = ENTRY_SPLIT_RE.split(log)
    if len(parts) < 2:
        return log
    head, entries = parts[0], parts[1:]
    labelled = []
    for entry in entries:
        m = ENTRY_OPEN_RE.match(entry)
        if m:
            ts = html_mod.escape(m.group(1), quote=True)
            # One <time> per entry, formatted in the browser. The stamp is UTC
            # and Eden is not, so a server-rendered label reads hours wrong for
            # him. With no JS the raw stamp still shows.
            entry = (f'{entry[:m.end()]}'
                     f'<time class="wl-when" datetime="{ts}">{ts}</time>'
                     f'{entry[m.end():]}')
        labelled.append(entry)
    return head + "".join(reversed(labelled))


WORKLOG_TIME_SCRIPT = """
<script>
document.querySelectorAll('time.wl-when[datetime]').forEach(function (el) {
  var d = new Date(el.getAttribute('datetime'));
  if (!isNaN(d.getTime())) el.textContent = d.toLocaleString(undefined,
    { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
});
</script>
""".strip()


def worklog_page(directory, slug):
    """Compose one task page: shell + meta header + every appended fragment.

    Returns None when the task directory does not exist, so the caller can 404.
    Composition happens per request, with no cache: a fragment appended a
    moment ago must be visible on the very next reload.
    """
    slug = worklog_slug(slug)
    if not slug:
        return None
    task_dir = os.path.join(directory, slug)
    if not os.path.isdir(task_dir):
        return None

    meta = worklog_read_meta(directory, slug) or {
        "slug": slug, "title": slug, "state": "running",
        "summary": "", "updated": "",
    }
    try:
        # errors="replace", matching inject() on the design path. A fragment
        # pasted from a latin-1 tool raises UnicodeDecodeError otherwise, which
        # is not an OSError, so it killed the handler thread and the task page
        # served nothing at all.
        with open(os.path.join(task_dir, "log.html"),
                  encoding="utf-8", errors="replace") as f:
            log = f.read()
    except OSError:
        log = ""
    if not log.strip():
        log = '<p class="empty">Nothing appended yet.</p>'
    else:
        log = worklog_newest_first(log)

    # Charts are pinned above the log, never inside it. The log is append-only
    # and reads newest first, so a chart appended into it would scroll away
    # exactly as the work it describes gets interesting.
    try:
        charts = chart.render_panel(task_dir)
    except Exception:
        charts = ""

    title = html_mod.escape(meta["title"])
    state = html_mod.escape(meta["state"])
    summary = html_mod.escape(meta["summary"])
    updated = html_mod.escape(meta.get("updated", ""))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Worklog</title>
<style>
{WORKLOG_CSS}
</style></head>
<body>
<header>
  <a class="back" href="/">&larr; all tasks</a>
  <h1>{title} <span class="chip {state}">{state}</span></h1>
  <p>{summary}{' · ' if summary and updated else ''}{updated}</p>
</header>
<main>
{charts}
{log}
</main>
{WORKLOG_TIME_SCRIPT}
</body></html>"""


RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
RANGE_CHUNK = 256 * 1024


def byte_range(header, size):
    """Resolve a Range header to one inclusive (start, end) pair.

    Returns None when the header is absent, malformed, or asks for more than
    one range. Each of those may fall back to a plain 200 with the whole file.
    Returns False when the range parses but cannot be satisfied. That case
    must be answered 416, never 200: a player that asks for the tail and gets
    the head decodes the wrong bytes silently.
    """
    if not header:
        return None
    m = RANGE_RE.match(header.strip())
    if not m:
        return None
    first, last = m.group(1), m.group(2)
    if first == "":
        # Suffix form, `bytes=-500` -- the last 500 bytes. Players use it to
        # read a trailing index before they seek.
        if last == "":
            return None
        want = int(last)
        if want == 0 or size == 0:
            return False
        return (max(0, size - want), size - 1)
    start = int(first)
    end = int(last) if last else size - 1
    if end >= size:
        end = size - 1  # an end past EOF is legal and clamps
    if start > end or start >= size:
        return False
    return (start, end)


class Handler(SimpleHTTPRequestHandler):
    # `directory` is bound per-server below via a subclass.
    mode = "design"  # "design" | "worklog"; bound per-server in make_handler
    _advertise_ranges = False

    def log_message(self, *args):
        pass  # quiet

    def send_response(self, code, message=None):
        # Recorded so end_headers() can tell a served file from a 404 or 301.
        self._status = code
        super().send_response(code, message)

    def end_headers(self):
        if self._advertise_ranges and getattr(self, "_status", None) == 200:
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def _send_html(self, body_bytes, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body_bytes)

    def _send_worklog_board(self):
        """Serve the board through inject(), never _send_html directly.

        LIVERELOAD_SNIPPET carries a __PAGE_QS__ placeholder and inject() is
        the only thing that substitutes it. Sent raw, the board shipped
        `var QS = '__PAGE_QS__'`, the browser asked for
        /__livereload__PAGE_QS__, that 404'd, and the board never reloaded --
        which is the one thing a board has to do. page=None keeps it watching
        the whole folder rather than a single task.
        """
        self._send_html(inject(worklog_board(self.directory).encode("utf-8"),
                               live=True, page=None))

    def _signature(self, only=None):
        if self.mode == "worklog":
            return worklog_signature(self.directory, slug=only)
        return watch_signature(self.directory, only=only)

    def do_HEAD(self):
        """Answer HEAD with the same headers GET would send.

        The parent's do_HEAD calls send_head() and never enters do_GET, so
        every `self.command != "HEAD"` guard in this class was unreachable and
        HEAD on a design page reported the raw file's length, not the injected
        page's. Routing through do_GET makes those guards do their job.
        """
        if self.path.partition("?")[0] == "/__livereload":
            # Never open the poll loop for a HEAD: it has no end.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        return self.do_GET()

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/__livereload":
            return self._serve_sse(
                urllib.parse.parse_qs(query).get("page", [None])[0])
        if path.startswith(KATEX_ROUTE + "/"):
            return self._serve_vendor(path[len(KATEX_ROUTE) + 1:])
        embed = "embed=1" in query
        watched = urllib.parse.parse_qs(query).get("page", [None])[0]

        root = self.directory

        if path == "/__sig":
            # Cheap, connection-free way for a tab that dropped its SSE stream
            # (see LIVERELOAD_SNIPPET) to tell whether it went stale meanwhile.
            # repr, not hash(): str hashing is PYTHONHASHSEED-randomised, so a
            # hash would change across restarts and force spurious reloads.
            body = repr(self._signature(only=watched)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return

        if path == "/":
            if self.mode == "worklog":
                return self._send_worklog_board()
            files = design_files(root)
            if len(files) == 1:
                return self._serve_injected_html(os.path.join(root, files[0]))
            return self._send_html(gallery_page(root).encode("utf-8"))

        if self.mode == "worklog":
            return self._serve_worklog(path, embed)

        # Map URL path to a file; inject into .html, otherwise serve normally.
        local = self.translate_path(self.path)
        if local.lower().endswith(".html") and os.path.isfile(local):
            # Scope the page's reload stream to itself, so a parallel session
            # writing a different design cannot reload this tab.
            return self._serve_injected_html(
                local, live=not embed, page=os.path.basename(local))
        return self._serve_static()

    def _serve_static(self):
        """Serve a file from disk, honouring one byte range.

        SimpleHTTPRequestHandler ignores Range and always answers 200 with the
        whole file. Chrome opens a <video> with `Range: bytes=0-`. A 200 tells
        it the file cannot be seeked, so the scrub bar goes dead and the clip
        only plays forward at 1x while it downloads. Screen recordings dropped
        next to a design are the reason this exists.
        """
        local = self.translate_path(self.path)
        rng = None
        size = 0
        if os.path.isfile(local):
            try:
                size = os.path.getsize(local)
                rng = byte_range(self.headers.get("Range"), size)
            except OSError:
                rng = None
        if rng is None:
            # No range asked for, or one this server declines to split. Let the
            # parent serve it, with Accept-Ranges added so the client knows a
            # later seek is worth trying.
            self._advertise_ranges = True
            try:
                if self.command == "HEAD":
                    return super().do_HEAD()
                return super().do_GET()
            finally:
                self._advertise_ranges = False
        if rng is False:
            self.send_response(416)
            self.send_header("Content-Range", "bytes */%d" % size)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start, end = rng
        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(local))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(length))
        self.send_header("Last-Modified",
                         self.date_time_string(os.path.getmtime(local)))
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            with open(local, "rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(RANGE_CHUNK, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            # Every seek cancels the range still in flight. That is normal
            # player behaviour, not a fault worth a traceback.
            return

    def _serve_injected_html(self, local_path, live=True, page=None):
        try:
            with open(local_path, "rb") as f:
                raw = f.read()
        except OSError:
            self.send_error(404)
            return
        self._send_html(inject(raw, live=live, page=page))

    def _serve_worklog(self, path, embed):
        """Route /<slug>/ to a composed page and /<slug>/... to a static file."""
        # self.path is still percent-encoded here. translate_path unquotes for
        # the asset leg, but the slug match against a real directory name does
        # not, so `/my%20task/` would never find `my task`.
        parts = [urllib.parse.unquote(p)
                 for p in path.strip("/").split("/") if p]
        if not parts:
            return self._send_worklog_board()
        # `..` and `.` survive os.path.basename, so they are refused here
        # before any leg of this router can stat or walk the parent folder.
        # %2e%2e arrives decoded, which is why the guard sits after unquote.
        slug = worklog_slug(parts[0])
        if slug is None:
            self.send_error(404)
            return
        if len(parts) == 1:
            if not path.endswith("/"):
                if not os.path.isdir(os.path.join(self.directory, slug)):
                    # Most no-trailing-slash hits here are /favicon.ico, which
                    # is never a task directory. Redirecting it anyway cost two
                    # round trips (a 301 that itself 404s) on every board load.
                    self.send_error(404)
                    return
                # Redirect so relative asset URLs inside a fragment resolve
                # against /<slug>/ rather than against the root.
                self.send_response(301)
                self.send_header("Location", "/" + urllib.parse.quote(slug) + "/")
                self.end_headers()
                return
            page = worklog_page(self.directory, slug)
            if page is None:
                self.send_error(404)
                return
            return self._send_html(
                inject(page.encode("utf-8"), live=not embed, page=slug))
        # Anything deeper is an asset, served by translate_path. That drops
        # `..` components, so this asset leg alone cannot climb out of
        # self.directory. It says nothing about the slug leg above, which
        # reaches os.walk and os.path.isdir directly -- worklog_slug() is what
        # holds that one. translate_path also does NOT resolve symlinks: a
        # symlink written inside a task directory still resolves to its target.
        # Design mode has the same property and the bind is tailnet-only, so
        # this is accepted, not overlooked.
        return self._serve_static()

    def _serve_vendor(self, rel):
        """Serve the vendored KaTeX assets (css, js, woff2 fonts).

        Confined to KATEX_DIR: the request path is unquoted, so `..%2f` would
        otherwise walk out of the vendor dir and read arbitrary files."""
        rel = urllib.parse.unquote(rel)
        target = os.path.normpath(os.path.join(KATEX_DIR, rel))
        if not target.startswith(KATEX_DIR + os.sep) or not os.path.isfile(target):
            self.send_error(404)
            return
        ctype = VENDOR_TYPES.get(os.path.splitext(target)[1].lower(),
                                 "application/octet-stream")
        try:
            with open(target, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        # Pinned version, immutable content — no reason to refetch fonts on
        # every live-reload (a design iteration reloads the page constantly).
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _serve_sse(self, page=None):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last = self._signature(only=page)
        ticks = 0
        try:
            while True:
                time.sleep(POLL_SECONDS)
                sig = self._signature(only=page)
                if sig != last:
                    last = sig
                    self.wfile.write(b"data: reload\n\n")
                    self.wfile.flush()
                else:
                    ticks += 1
                    if ticks % 30 == 0:  # ~9s heartbeat to detect disconnects
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def make_handler(directory, mode="design"):
    class BoundHandler(Handler):
        def __init__(self, *a, **kw):
            # Set mode BEFORE super().__init__: BaseHTTPRequestHandler handles
            # the whole request inside __init__, so anything set afterwards is
            # too late to affect routing.
            self.mode = mode
            # Pass directory through SimpleHTTPRequestHandler.__init__ so it sets
            # self.directory before handling the request. A class attribute alone
            # is shadowed because __init__ defaults self.directory to os.getcwd().
            super().__init__(*a, directory=directory, **kw)
    return BoundHandler


def bind_host():
    """Resolve the interface to bind.

    Never 0.0.0.0: this box has a public interface, so binding all interfaces
    would publish design mockups to the open internet. Prefer the tailnet IP
    (reachable from Eden's laptop, nowhere else); fall back to loopback.
    Override with HTML_DESIGN_BIND if you really mean something else.
    """
    override = os.environ.get("HTML_DESIGN_BIND")
    if override:
        return override
    try:
        proc = subprocess.run(
            ["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                ip = line.strip()
                if ip:
                    return ip
    except (OSError, subprocess.SubprocessError):
        pass
    return "127.0.0.1"


def port_in_use(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def start(directory, port, mode="design"):
    directory = os.path.abspath(os.path.expanduser(directory))
    os.makedirs(directory, exist_ok=True)
    host = bind_host()
    # Probe the address we would actually bind, else a running tailnet-bound
    # instance looks free on loopback and we double-bind.
    if port_in_use(port, host) or port_in_use(port):
        print(f"Server already running on port {port} (reusing).")
        return 0

    handler_cls = make_handler(directory, mode=mode)
    server = ThreadingHTTPServer((host, port), handler_cls)
    server.daemon_threads = True  # don't let lingering SSE threads block shutdown
    with open(pidfile_for(port), "w") as f:
        f.write(str(os.getpid()))
    print(f"Serving {directory} on http://{host}:{port}  (live-reload on)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            os.remove(pidfile_for(port))
        except OSError:
            pass
    return 0


def stop(port):
    pf = pidfile_for(port)
    try:
        with open(pf) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        print(f"No pidfile for port {port}; nothing to stop.")
        return 0
    try:
        os.kill(pid, 15)
        print(f"Stopped server (pid {pid}) on port {port}.")
    except ProcessLookupError:
        print(f"Process {pid} not running.")
    except OSError as e:
        print(f"Could not stop pid {pid}: {e}")
        return 1
    try:
        os.remove(pf)
    except OSError:
        pass
    return 0


def parse_mode(argv):
    """Strip the --mode flag from argv.

    Returns (mode, remaining_argv), or None when the arguments are invalid.
    Accepts `--mode worklog` and `--mode=worklog`. Any other leading `--`
    argument is an error rather than a directory name: `--mode=worklog` used
    to fall through to the positional reader and silently start design mode
    while creating a directory literally named `--mode=worklog`.
    """
    argv = list(argv)
    mode = "design"
    out = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--mode":
            if i + 1 >= len(argv):
                return None
            mode = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]
            i += 1
            continue
        if arg.startswith("--"):
            return None
        out.append(arg)
        i += 1
    if mode not in ("design", "worklog"):
        return None
    return mode, out


def main(argv):
    """server.py [--mode design|worklog] [dir] [port]  |  server.py stop [port]

    --mode is stripped before the positional arguments are read, so the
    original positional form keeps working unchanged.
    """
    parsed = parse_mode(argv)
    if parsed is None:
        print("usage: server.py [--mode design|worklog] [dir] [port]",
              file=sys.stderr)
        return 2
    mode, rest = parsed

    if rest and rest[0] == "stop":
        port = int(rest[1]) if len(rest) > 1 else (
            WORKLOG_PORT if mode == "worklog" else DEFAULT_PORT)
        return stop(port)

    default_dir = WORKLOG_DIR if mode == "worklog" else DEFAULT_DIR
    default_port = WORKLOG_PORT if mode == "worklog" else DEFAULT_PORT
    directory = rest[0] if len(rest) > 0 else default_dir
    port = int(rest[1]) if len(rest) > 1 else default_port
    return start(directory, port, mode=mode)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
