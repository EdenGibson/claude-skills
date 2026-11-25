#!/usr/bin/env python3
"""Render the attn page.

Empty is the expected state, so it is styled as success rather than as an
error. A page that usually shows nothing is the goal, not a failure.
"""
import hashlib
import json
import html as html_mod
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402

CSS = """
:root { color-scheme: light dark; --bg:#fff; --fg:#111; --dim:#666;
        --line:#e5e5e5; --card:#fafafa; --warn:#b45309; --ok:#15803d; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0f0f0f; --fg:#ededed; --dim:#8b8b8b;
          --line:#262626; --card:#171717; --warn:#f59e0b; --ok:#4ade80; }
}
* { box-sizing: border-box; }
body { margin:0; padding:2.5rem 1.25rem; background:var(--bg); color:var(--fg);
       font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; }
main { max-width: 44rem; margin: 0 auto; }
h1 { font-size:1.05rem; font-weight:600; letter-spacing:.01em; margin:0 0 .35rem; }
.sub { color:var(--dim); font-size:.85rem; margin:0 0 2rem; }
h2 { font-size:.75rem; font-weight:600; text-transform:uppercase;
     letter-spacing:.08em; color:var(--dim); margin:2rem 0 .6rem; }
.item { border:1px solid var(--line); background:var(--card);
        border-radius:10px; padding:.85rem 1rem; margin-bottom:.6rem; }
.title { font-weight:550; }
.title a { color:inherit; }
.body { color:var(--dim); font-size:.88rem; margin-top:.3rem;
        white-space:pre-wrap; }
.meta { display:flex; flex-wrap:wrap; gap:.75rem; align-items:center;
        margin-top:.6rem; color:var(--dim); font-size:.78rem; }
.meta .warn { color:var(--warn); }
form { display:inline; margin:0; }
button { font:inherit; font-size:.78rem; color:var(--dim); background:none;
         border:1px solid var(--line); border-radius:6px;
         padding:.15rem .5rem; cursor:pointer; }
button:hover { color:var(--fg); border-color:var(--dim); }
.empty { color:var(--ok); font-size:.95rem; padding:2rem 0; }
.err { font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
       font-size:.72rem; color:var(--warn); margin-top:.35rem;
       overflow-x:auto; white-space:pre; }
""".strip()

RELOAD_SNIPPET = """
<script>
(function () {
  var current = document.body.getAttribute('data-digest');
  setInterval(function () {
    fetch('/digest', {cache: 'no-store'})
      .then(function (r) { return r.text(); })
      .then(function (d) { if (d.trim() !== current) location.reload(); })
      .catch(function () {});
  }, 15000);
})();
</script>
""".strip()


def visible(items, now=None):
    """Open items that are not currently snoozed."""
    moment = store.now() if now is None else now
    out = []
    for item in items:
        until = store.epoch(item.get("snoozed_until"))
        if until is not None and until > moment:
            continue
        out.append(item)
    return out


def digest(items):
    """A short hash of the open set.

    `checked` is deliberately outside the hash. Including it would change the
    digest on every sweep and reload the page under Eden every 2 minutes.

    Every other rendered field is inside it. Hand-picking four fields meant a
    refile that changed the body, the project, the url or last_error moved the
    page but not the digest, so Eden kept reading the first version. Measured:
    a refile into a different project regrouped the page with no digest change.

    json.dumps supplies the separators. Joining with "|" and "\\n" let one
    crafted title collide with two real items, because neither separator was
    escaped and `attn file` only strips the ends of a title. Measured: a
    title of "x||0\\nb|y" produced the digest of the two-item set.
    """
    fields = ("key", "title", "body", "project", "url", "source", "alive",
              "filed", "expires", "snoozed_until", "check_errors", "last_error")
    parts = [
        {name: item.get(name) for name in fields}
        for item in sorted(items, key=lambda i: str(i.get("key") or ""))
    ]
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def humanize(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def check_state(item, now):
    """One short phrase describing how this item is being kept honest."""
    errors = int(item.get("check_errors") or 0)
    if errors >= 1:
        return f"check failing ({errors}x)", True
    if item.get("alive"):
        checked = store.epoch(item.get("checked"))
        if checked is None:
            return "not checked yet", False
        return f"verified {humanize(now - checked)} ago", False
    expires = store.epoch(item.get("expires"))
    if expires is None:
        return "no check", True
    return f"expires in {humanize(expires - now)}", False


def esc(value):
    return html_mod.escape(str(value)) if value is not None else ""


# C0 controls plus space (0x00-0x20), the run of characters a browser skips
# at the front of a URL before it looks at the scheme.
_URL_STRIP_CHARS = "".join(chr(c) for c in range(0x21))


def safe_href(url):
    """An href-safe URL, or None when the scheme is not http or https.

    A strict allowlist, not a blocklist: script-executing schemes are many
    (javascript:, data:, vbscript:, blob:, ...) and a blocklist would always
    be missing one. Browsers delete tab, newline and carriage return from
    anywhere in a URL before they parse its scheme, so `java\tscript:` reaches
    the browser as `javascript:`; those three characters are removed from the
    whole string here too, not just the front. Leading C0 control characters
    and spaces are stripped next, because a browser accepts ` javascript:`
    just as readily. The scheme check is case-insensitive on a lowercased
    copy, but the returned value keeps the original case, since URL paths can
    be case-sensitive.
    """
    if not url:
        return None
    cleaned = url.replace("\t", "").replace("\n", "").replace("\r", "")
    cleaned = cleaned.lstrip(_URL_STRIP_CHARS)
    if cleaned.lower().startswith(("http://", "https://")):
        return cleaned
    return None


def render_item(item, now):
    filed = store.epoch(item.get("filed")) or now
    age = humanize(now - filed)
    phrase, warn = check_state(item, now)
    title = esc(item.get("title"))
    href = safe_href(item.get("url"))
    if href:
        title = f'<a href="{esc(href)}">{title}</a>'

    rows = [f'<div class="item"><div class="title">{title}</div>']
    if item.get("body"):
        rows.append(f'<div class="body">{esc(item["body"])}</div>')
    if item.get("last_error"):
        rows.append(f'<div class="err">{esc(item["last_error"])}</div>')
    rows.append('<div class="meta">')
    rows.append(f'<span>{esc(item.get("source") or "unknown")}</span>')
    rows.append(f'<span>{age} old</span>')
    rows.append(f'<span class="{"warn" if warn else ""}">{esc(phrase)}</span>')
    for action, label in (("dismiss", "Dismiss"), ("snooze", "Snooze 1 day")):
        rows.append(
            f'<form method="post" action="/action">'
            f'<input type="hidden" name="key" value="{esc(item["key"])}">'
            f'<input type="hidden" name="action" value="{action}">'
            f'<button type="submit">{label}</button></form>'
        )
    rows.append("</div></div>")
    return "".join(rows)


def render(items, now=None):
    moment = store.now() if now is None else now
    shown = visible(items, moment)

    groups = {}
    for item in shown:
        groups.setdefault(item.get("project") or "unfiled", []).append(item)

    body = []
    if not shown:
        body.append('<p class="empty">Nothing needs you.</p>')
    else:
        for name in sorted(groups):
            body.append(f"<h2>{esc(name)}</h2>")
            for item in sorted(groups[name],
                               key=lambda i: (i.get("filed") or "", i["key"])):
                body.append(render_item(item, moment))

    count = len(shown)
    sub = "nothing open" if count == 0 else f"{count} open"
    return (
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>attn</title>"
        "<link rel=\"icon\" type=\"image/png\" href=\"/favicon.png\">"
        f"<style>{CSS}</style></head>"
        f'<body data-digest="{digest(shown)}">'
        f"<main><h1>attn</h1><p class=\"sub\">{sub}</p>"
        + "".join(body) +
        f"</main>{RELOAD_SNIPPET}</body></html>"
    )
