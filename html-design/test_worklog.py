#!/usr/bin/env python3
"""Behavioral tests for worklog mode of the html-design server.

Run: python3 test_worklog.py
Exits 0 on success, non-zero (with a FAIL line) otherwise.

Port 4398, chosen so this suite and test_server.py (4399) can run at once.
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "server.py")
PORT = 4398
BASE = f"http://127.0.0.1:{PORT}"

failures = []


def check(cond, msg):
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        failures.append(msg)


def get(path, timeout=5):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.status, r.headers, r.read().decode("utf-8", "replace")


def status_of(path, timeout=5):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def raw_get(path, timeout=8):
    """Send one request line verbatim. Returns (status, body).

    curl collapses `/..` before the request leaves the machine unless you pass
    --path-as-is, and a client library may do the same. A traversal test that
    lets the client normalise the path proves nothing, so this writes the bytes
    itself.
    """
    s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
    try:
        s.sendall(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                  f"Connection: close\r\n\r\n".encode("utf-8"))
        chunks = []
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
    finally:
        s.close()
    raw = b"".join(chunks).decode("utf-8", "replace")
    head, _, body = raw.partition("\r\n\r\n")
    parts = head.split(None, 2)
    return (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0), body


def wait_until_up(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            get("/", timeout=1)
            return True
        except Exception:
            time.sleep(0.15)
    return False


def load_server_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("design_server", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_task(root, slug, title="A task", state="running", summary="",
              log="<p>hello</p>", updated="2026-08-06T05:00:00Z"):
    """Write a task directory by hand, the way the CLI will."""
    d = os.path.join(root, slug)
    os.makedirs(os.path.join(d, "assets"), exist_ok=True)
    meta = {"v": 1, "slug": slug, "title": title, "state": state,
            "summary": summary, "created": "2026-08-06T04:00:00Z",
            "updated": updated}
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    with open(os.path.join(d, "log.html"), "w", encoding="utf-8") as f:
        f.write(f'<section class="wl-entry" data-ts="{updated}">{log}</section>\n')
    return d


def make_escape_root(prefix):
    """A worklog root with a decoy file in its parent. Returns (base, root).

    Traversal must be tested against a parent we control, never against /tmp
    or $HOME. Walking such a parent IS the denial of service under test: on the
    live service the parent is $HOME, where a bounded probe read 126,685 files
    in 1.4s and a full walk did not finish in 300s.
    """
    base = tempfile.mkdtemp(prefix=prefix)
    with open(os.path.join(base, "secret-file.txt"), "w", encoding="utf-8") as f:
        f.write("must never be served")
    root = os.path.join(base, "board")
    os.makedirs(root)
    return base, root


def start_server(root):
    """Start server.py in worklog mode against root. Returns the process."""
    env = dict(os.environ, HTML_DESIGN_BIND="127.0.0.1")
    proc = subprocess.Popen(
        [sys.executable, SERVER, "--mode", "worklog", root, str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    return proc


def test_mode_flag_parsing():
    """--mode must not disturb the positional `server.py [dir] [port]` form."""
    mod = load_server_module()
    check(mod.WORKLOG_PORT == 4370, "WORKLOG_PORT is 4370")
    check(hasattr(mod, "worklog_board"), "worklog_board exists")

    check(mod.parse_mode(["--mode", "worklog", "/tmp/x", "4398"])
          == ("worklog", ["/tmp/x", "4398"]), "space form parses")
    check(mod.parse_mode(["--mode=worklog", "/tmp/x"])
          == ("worklog", ["/tmp/x"]), "equals form parses")
    check(mod.parse_mode(["/tmp/x", "4321"]) == ("design", ["/tmp/x", "4321"]),
          "positional-only form is unchanged and defaults to design")
    check(mod.parse_mode(["stop", "4321"]) == ("design", ["stop", "4321"]),
          "stop survives parsing")
    check(mod.parse_mode([]) == ("design", []), "no arguments is design mode")
    check(mod.parse_mode(["--mode"]) is None, "--mode with no value is refused")
    check(mod.parse_mode(["--mode", "sideways"]) is None,
          "an unknown mode is refused")
    check(mod.parse_mode(["--bogus", "/tmp/x"]) is None,
          "an unknown flag is refused, not treated as a directory")


def test_board_served_at_root():
    """Task 2 only proves the routing. Board content is Task 4's job."""
    root = tempfile.mkdtemp(prefix="worklog-test-")
    make_task(root, "alpha", title="Alpha task")
    proc = start_server(root)
    try:
        check(wait_until_up(), "worklog server starts and answers")
        status, _, body = get("/")
        check(status == 200, "board returns 200")
        check("Worklog" in body, "root serves the worklog board")
        check("iframe" not in body, "board is not the design gallery")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_worklog_tasks_ordering_and_resilience():
    """Board order is running, blocked, failed, done; then most recent first.

    A directory with no or corrupt meta.json is skipped rather than fatal: an
    agent killed midway through `worklog start` must not blank the board.
    """
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-order-")
    make_task(root, "old-run", state="running", updated="2026-08-06T01:00:00Z")
    make_task(root, "new-run", state="running", updated="2026-08-06T09:00:00Z")
    make_task(root, "a-done", state="done")
    make_task(root, "a-blocked", state="blocked")
    make_task(root, "a-failed", state="failed")

    # A directory with no meta.json at all.
    os.makedirs(os.path.join(root, "half-made"), exist_ok=True)
    # A directory whose meta.json is not valid JSON.
    corrupt = os.path.join(root, "corrupt")
    os.makedirs(corrupt, exist_ok=True)
    with open(os.path.join(corrupt, "meta.json"), "w") as f:
        f.write("{not json")

    # Force distinct mtimes so recency ordering is deterministic.
    os.utime(os.path.join(root, "old-run", "log.html"), (1000, 1000))
    os.utime(os.path.join(root, "new-run", "log.html"), (9000, 9000))

    tasks = mod.worklog_tasks(root)
    slugs = [t["slug"] for t in tasks]

    check("half-made" not in slugs, "task with no meta.json is skipped")
    check("corrupt" not in slugs, "task with corrupt meta.json is skipped")
    check(len(slugs) == 5, f"five valid tasks listed (got {len(slugs)}: {slugs})")
    check(slugs[:2] == ["new-run", "old-run"],
          f"running tasks first, newest first (got {slugs[:2]})")
    check(slugs.index("a-blocked") < slugs.index("a-failed") < slugs.index("a-done"),
          f"state order is running, blocked, failed, done (got {slugs})")

    meta = mod.worklog_read_meta(root, "a-done")
    check(meta["state"] == "done", "read_meta returns the state")
    check(mod.worklog_read_meta(root, "nope") is None,
          "read_meta returns None for an unknown slug")


def test_worklog_meta_defaults():
    """A meta.json missing fields must not crash the board."""
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-defaults-")
    d = os.path.join(root, "sparse")
    os.makedirs(d)
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump({"v": 1}, f)
    meta = mod.worklog_read_meta(root, "sparse")
    check(meta is not None, "sparse meta.json still parses")
    check(meta["title"] == "sparse", "title falls back to the slug")
    check(meta["state"] == "running", "unknown state falls back to running")
    check(meta["summary"] == "", "summary falls back to empty")


def test_board_survives_wrong_typed_meta():
    """A non-string meta value must not take the board down.

    An agent writing meta.json by hand is likelier to emit a number than to
    emit invalid JSON, and the board is shared by every task.
    """
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-badtype-")
    make_task(root, "healthy", title="Healthy task")
    for slug, bad in (("badtitle", {"title": 42, "state": "running"}),
                      ("badsummary", {"title": "x", "summary": ["a", "b"]}),
                      ("badupdated", {"title": "x", "updated": {"a": 1}})):
        d = os.path.join(root, slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "meta.json"), "w") as f:
            json.dump(bad, f)

    html = mod.worklog_board(root)
    check("Healthy task" in html, "board still lists the healthy task")
    check("42" in html, "a numeric title is coerced and shown, not dropped")

    for slug in ("badtitle", "badsummary", "badupdated"):
        page = mod.worklog_page(root, slug)
        check(page is not None, f"{slug} page still renders")


def test_board_rendering():
    """The board shows one row per task with title, state, age and summary."""
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-board-")
    make_task(root, "gate-rerun", title="Tutor gate rerun",
              state="running", summary="24 of 45 rows scored")
    make_task(root, "pr-sweep", title="PR sweep", state="done",
              summary="9 PRs, 2 blocked")

    html = mod.worklog_board(root)
    check("Tutor gate rerun" in html, "board shows a title")
    check("24 of 45 rows scored" in html, "board shows the summary")
    check('href="/gate-rerun/"' in html, "board links to the task page")
    check("running" in html and "done" in html, "board shows both states")
    check(html.index("gate-rerun") < html.index("pr-sweep"),
          "running row sorts above done row")
    # LIVERELOAD_SNIPPET is a template. Only inject() substitutes __PAGE_QS__,
    # so a board sent straight to _send_html shipped `var QS = '__PAGE_QS__'`
    # and the browser asked for /__livereload__PAGE_QS__, which 404s. The board
    # then never reloaded at all, which is its one job. The template therefore
    # carries no copy of its own; inject() is the single source.
    check("data-livereload" not in html,
          "the board template leaves the live-reload script to inject()")

    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        _, _, served = get("/")
        check(served.count("data-livereload") == 1,
              "the served board carries exactly one live-reload script")
        check("__PAGE_QS__" not in served,
              "the served board has no unsubstituted __PAGE_QS__ placeholder")
        m = re.search(r"var QS = '([^']*)'", served)
        check(m is not None, "the served board declares a live-reload query")
        qs = m.group(1) if m else "__PAGE_QS__"
        check(qs == "", f"the board watches the whole folder (QS={qs!r})")
        check(status_of("/__livereload" + qs) == 200,
              f"the stream the board references answers (/__livereload{qs})")
        check(status_of("/__sig" + qs) == 200,
              f"the signature the board references answers (/__sig{qs})")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_board_escapes_titles():
    """A title is agent-supplied text and must never inject markup."""
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-escape-")
    make_task(root, "xss", title="<script>alert(1)</script>", summary="a & b")
    html = mod.worklog_board(root)
    check("<script>alert(1)</script>" not in html, "title markup is escaped")
    check("&lt;script&gt;" in html, "title is escaped, not dropped")
    check("a &amp; b" in html, "summary ampersand is escaped")


def test_empty_board():
    """An empty worklog folder still renders."""
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-empty-")
    html = mod.worklog_board(root)
    check("<!doctype html>" in html.lower(), "empty board is a real document")
    check("No tasks" in html, "empty board says so")


def test_task_page_and_assets():
    root = tempfile.mkdtemp(prefix="worklog-page-")
    d = make_task(root, "alpha", title="Alpha task", summary="halfway",
                  log="<p>first entry</p>")
    with open(os.path.join(d, "log.html"), "a", encoding="utf-8") as f:
        f.write('<section class="wl-entry"><p>second entry</p></section>\n')
    with open(os.path.join(d, "assets", "note.txt"), "w") as f:
        f.write("evidence")

    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        status, _, body = get("/alpha/")
        check(status == 200, "task page returns 200")
        check("Alpha task" in body, "task page shows the title")
        check("first entry" in body and "second entry" in body,
              "task page shows every appended fragment")
        check(body.index("second entry") < body.index("first entry"),
              "the newest fragment renders first")
        check("data-livereload" in body, "task page carries live-reload")
        check("page=alpha" in body, "reload stream is scoped to this task")

        status, _, asset = get("/alpha/assets/note.txt")
        check(status == 200 and "evidence" in asset, "assets are served")

        check(status_of("/nope/") == 404, "unknown slug is 404")
        check(status_of("/alpha/assets/../../../etc/passwd") in (404, 400, 301),
              "path traversal out of the worklog folder is refused")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_slug_with_space_is_reachable():
    """A slug with a space or non-ASCII must survive the URL round trip."""
    root = tempfile.mkdtemp(prefix="worklog-encoded-")
    make_task(root, "my task", title="Spaced task")
    make_task(root, "café", title="Accented task")
    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        _, _, board = get("/")
        check("/my%20task/" in board, "board percent-encodes the slug in href")
        status, _, body = get("/my%20task/")
        check(status == 200 and "Spaced task" in body,
              "an encoded slug serves its page")
        status, _, body = get("/caf%C3%A9/")
        check(status == 200 and "Accented task" in body,
              "a non-ASCII slug serves its page")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_task_page_renders_latex():
    """A fragment with math gets KaTeX, exactly as a design page would."""
    root = tempfile.mkdtemp(prefix="worklog-latex-")
    make_task(root, "mathy", log=r"<p>error is \(\epsilon < 0.01\)</p>")
    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        _, _, body = get("/mathy/")
        check("__katex" in body, "KaTeX is injected into a task page with math")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_worklog_signature_scoping():
    """A task watches its own tree. The board watches everything."""
    mod = load_server_module()
    # A controlled parent: the traversal checks below walk it when the guard is
    # missing, and a mkdtemp straight under /tmp would walk all of /tmp.
    base, root = make_escape_root("worklog-sig-")
    make_task(root, "alpha")
    make_task(root, "beta")

    alpha_before = mod.worklog_signature(root, slug="alpha")
    board_before = mod.worklog_signature(root)

    time.sleep(0.01)
    with open(os.path.join(root, "beta", "log.html"), "a", encoding="utf-8") as f:
        f.write("<section>appended to beta</section>\n")

    check(mod.worklog_signature(root, slug="alpha") == alpha_before,
          "writing beta does NOT change alpha's signature")
    check(mod.worklog_signature(root) != board_before,
          "writing beta DOES change the board signature")

    # An asset two levels down must still be seen.
    asset_before = mod.worklog_signature(root, slug="alpha")
    with open(os.path.join(root, "alpha", "assets", "chart.svg"), "w") as f:
        f.write("<svg/>")
    check(mod.worklog_signature(root, slug="alpha") != asset_before,
          "a new nested asset changes the task signature")

    # A traversal attempt must not read outside the folder. "../../etc" is the
    # one traversal string that is safe by accident: its basename is "etc".
    # The dangerous strings are "." and "..", whose basename is themselves.
    board_sig = mod.worklog_signature(root)
    for bad in ("../../etc", "..", ".", "../..", "%2e%2e"):
        sig = mod.worklog_signature(root, slug=bad)
        check(isinstance(sig, tuple), f"slug {bad!r} is handled without raising")
        check(sig == board_sig,
              f"slug {bad!r} falls back to the board signature")
        check(not any(str(p).startswith("..") for p, *_ in sig),
              f"slug {bad!r} reads nothing above the worklog root")


def test_sse_reloads_on_append():
    """An append pushes `data: reload` down the task's stream."""
    root = tempfile.mkdtemp(prefix="worklog-sse-")
    make_task(root, "alpha")
    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        stream = urllib.request.urlopen(BASE + "/__livereload?page=alpha",
                                        timeout=10)
        time.sleep(0.5)
        with open(os.path.join(root, "alpha", "log.html"), "a",
                  encoding="utf-8") as f:
            f.write("<section>new work</section>\n")
        line = stream.readline().decode("utf-8", "replace")
        deadline = time.time() + 6
        while "reload" not in line and time.time() < deadline:
            line = stream.readline().decode("utf-8", "replace")
        check("reload" in line, f"SSE pushed a reload after an append (got {line!r})")
        stream.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_dotdot_slug_cannot_escape_over_http():
    """A bare `..` must 404 and must never list a file above the root.

    os.path.basename("..") == "..", so the basename guard passed it straight
    through to os.walk(<root>/..) and to the composed page. GET /__livereload
    ?page=.. then re-walked that tree every 0.3s for as long as the tab lived.
    """
    base, root = make_escape_root("worklog-escape-http-")
    make_task(root, "alpha", title="Alpha task")
    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        for path in ("/../", "/..", "/%2e%2e/", "/%2e%2e", "/./"):
            status, _ = raw_get(path)
            check(status == 404, f"{path} is refused with 404 (got {status})")

        status, body = raw_get("/__sig?page=..")
        check(status == 200, f"__sig still answers (got {status})")
        check("../" not in body,
              f"__sig?page=.. lists no path above the root (got {body[:200]!r})")
        check("secret-file.txt" not in body,
              "__sig?page=.. does not leak a file outside the root")

        status, board = raw_get("/")
        check(status == 200 and "Alpha task" in board,
              "the real board is unaffected")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_board_survives_unparseable_meta():
    """A meta.json json.load cannot parse must not take the whole board down.

    Deeply nested JSON raises RecursionError, which is neither OSError nor
    ValueError. It escaped worklog_read_meta and killed the handler thread, so
    every board request returned nothing while the file existed.
    """
    root = tempfile.mkdtemp(prefix="worklog-deep-")
    make_task(root, "healthy", title="Healthy task")
    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        d = os.path.join(root, "deep")
        os.makedirs(d)
        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            f.write("[" * 40000 + "]" * 40000)

        status, body = raw_get("/")
        check(status == 200, f"board still returns 200 (got {status})")
        check("Healthy task" in body, "board still lists the healthy task")
        check('href="/deep/"' not in body, "the unreadable task is skipped")

        status, _ = raw_get("/healthy/")
        check(status == 200, f"the healthy task page still serves (got {status})")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_task_page_survives_non_utf8_log():
    """A log.html holding latin-1 bytes must still render.

    UnicodeDecodeError is not an OSError, so it escaped the reader and killed
    the handler thread. inject() on the design path already decodes with
    errors="replace" — the worklog reader was stricter than the code it feeds.
    """
    root = tempfile.mkdtemp(prefix="worklog-badlog-")
    make_task(root, "badlog", title="Bad log")
    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        with open(os.path.join(root, "badlog", "log.html"), "wb") as f:
            f.write(b"<p>caf\xe9 latin-1</p>")

        status, body = raw_get("/badlog/")
        check(status == 200, f"a non-UTF-8 log.html still serves (got {status})")
        check("Bad log" in body, "the page still renders its title")
        check("latin-1" in body, "the readable part of the log survives")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_newest_entry_renders_first():
    """Order is a render-time reversal; log.html itself stays append-only."""
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-order-")
    d = make_task(root, "order", log="<p>oldest</p>",
                  updated="2026-08-06T05:00:00Z")
    path = os.path.join(d, "log.html")
    with open(path, "a", encoding="utf-8") as f:
        # The middle entry nests its own </section>. Splitting on the closing
        # tag would tear it in half, so the split must use the opening tag.
        f.write('<section class="wl-entry" data-ts="2026-08-06T06:00:00Z">\n'
                '<section><p>middle nested</p></section>\n</section>\n')
        f.write('<section class="wl-entry" data-ts="2026-08-06T07:00:00Z">\n'
                '<p>newest</p>\n</section>\n')

    on_disk = open(path, encoding="utf-8").read()
    check(on_disk.index("oldest") < on_disk.index("newest"),
          "log.html on disk keeps append order")

    page = mod.worklog_page(root, "order")
    check(page.index("newest") < page.index("middle nested") < page.index("oldest"),
          "the page renders newest first")
    check("<section><p>middle nested</p></section>" in page,
          "a nested </section> survives the reversal")
    labels = page.count('time class="wl-when"')
    check(labels == 3, f"every entry carries a time label (got {labels})")
    check('datetime="2026-08-06T07:00:00Z"' in page,
          "the time label carries the machine-readable stamp")


def test_single_entry_and_empty_log_are_untouched():
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-order-one-")
    make_task(root, "one", log="<p>only</p>")
    page = mod.worklog_page(root, "one")
    check("only" in page, "a one-entry log still renders")

    d = make_task(root, "blank", log="<p>x</p>")
    open(os.path.join(d, "log.html"), "w").close()
    page = mod.worklog_page(root, "blank")
    check("Nothing appended yet" in page, "an empty log still says so")


def make_chart(task_dir, chart_id, cfg=None, points=(), raw_cfg=None,
               raw_points=None):
    """Write a chart the way the CLI will: <id>.json plus <id>.jsonl."""
    charts = os.path.join(task_dir, "charts")
    os.makedirs(charts, exist_ok=True)
    with open(os.path.join(charts, chart_id + ".json"), "w",
              encoding="utf-8") as f:
        if raw_cfg is not None:
            f.write(raw_cfg)
        else:
            body = {"v": 1, "id": chart_id, "type": "progress",
                    "goal": "higher", "title": chart_id, "order": 1.0}
            body.update(cfg or {})
            json.dump(body, f)
    with open(os.path.join(charts, chart_id + ".jsonl"), "w",
              encoding="utf-8") as f:
        if raw_points is not None:
            f.write(raw_points)
        else:
            for p in points:
                f.write(json.dumps(p) + "\n")


def test_chart_panel_renders_above_the_log():
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-chart-")
    d = make_task(root, "vc-f1", log="<p>hypothesis 49 landed</p>")
    make_chart(d, "f1", cfg={"title": "Test F1", "y_label": "F1"},
               points=[{"x": 0, "y": 0.90, "s": "kept", "l": "H1"},
                       {"x": 1, "y": 0.88},
                       {"x": 2, "y": 0.93, "s": "kept"}])
    page = mod.worklog_page(root, "vc-f1")
    # The marker is the div, not the string: WORKLOG_CSS also names wl-charts,
    # and a page carrying only the rule would pass a substring check.
    check('<div class="wl-charts"' in page,
          "a task with a chart renders the chart strip")
    check("<svg" in page and "Test F1" in page, "the chart renders inline SVG")
    check(page.index('<div class="wl-charts"') < page.index("hypothesis 49 landed"),
          "the chart strip sits above the log")
    check(page.count("<circle") == 3, "every point renders")


def test_a_task_without_charts_is_unchanged():
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-nochart-")
    make_task(root, "plain")
    page = mod.worklog_page(root, "plain")
    check('<div class="wl-charts"' not in page,
          "a task with no charts renders no strip")
    check("hello" in page, "a task with no charts still renders its log")


def test_a_broken_chart_never_takes_the_page_down():
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-badchart-")
    d = make_task(root, "broken", log="<p>the log survives</p>")
    make_chart(d, "junk", raw_cfg="{not json at all")
    make_chart(d, "listy", raw_cfg='["a list, not an object"]')
    make_chart(d, "good", cfg={"title": "Still fine", "order": 9.0},
               points=[{"y": 1}])
    page = mod.worklog_page(root, "broken")
    check("the log survives" in page, "a broken chart leaves the log readable")
    check("Still fine" in page, "a broken chart does not stop its neighbours")


def test_a_torn_point_line_is_skipped():
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-torn-")
    d = make_task(root, "torn")
    # A half-written last line is normal: the CLI appends while the server reads.
    make_chart(d, "f1", raw_points='{"y": 1}\n{"y": 2}\n{"y": 3, "l": "cut')
    page = mod.worklog_page(root, "torn")
    check(page.count("<circle") == 2, "the two whole points render")
    check("cut" not in page, "the half-written point contributes nothing")
    check('<div class="wl-charts"' in page and "</html>" in page,
          "the page still composes around the torn line")


def test_a_broken_chart_module_never_stops_the_server():
    """charts are decoration; the server also serves Design Lab on 4321."""
    sandbox = tempfile.mkdtemp(prefix="worklog-badmodule-")
    with open(os.path.join(HERE, "server.py"), encoding="utf-8") as f:
        source = f.read()
    with open(os.path.join(sandbox, "server.py"), "w", encoding="utf-8") as f:
        f.write(source)
    with open(os.path.join(sandbox, "chart.py"), "w", encoding="utf-8") as f:
        f.write("def render_panel(  # unbalanced, a SyntaxError on import\n")
    proc = subprocess.run(
        [sys.executable, "-c",
         "import importlib.util, sys;"
         f"spec = importlib.util.spec_from_file_location('s', {os.path.join(sandbox, 'server.py')!r});"
         "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
         "print('imported', m.chart.render_panel('/nowhere') == '')"],
        capture_output=True, text=True, timeout=30)
    check(proc.returncode == 0,
          f"a broken chart.py still lets server.py import (stderr={proc.stderr[-300:]!r})")
    check("imported True" in proc.stdout,
          f"the fallback renders no charts rather than raising (got {proc.stdout!r})")


def test_charts_render_in_declared_order():
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-order-")
    d = make_task(root, "two")
    make_chart(d, "zebra", cfg={"title": "Declared first", "order": 1.0},
               points=[{"y": 1}])
    make_chart(d, "alpha", cfg={"title": "Declared second", "order": 2.0},
               points=[{"y": 1}])
    page = mod.worklog_page(root, "two")
    check(page.index("Declared first") < page.index("Declared second"),
          "order beats alphabetical")


def test_an_empty_chart_says_so():
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-emptychart-")
    d = make_task(root, "fresh")
    make_chart(d, "f1", points=[])
    page = mod.worklog_page(root, "fresh")
    check("No points yet" in page, "a declared chart with no points says so")


def test_signature_moves_when_a_point_lands():
    mod = load_server_module()
    root = tempfile.mkdtemp(prefix="worklog-sig-")
    d = make_task(root, "live")
    make_chart(d, "f1", points=[{"y": 1}])
    before = mod.worklog_signature(root, slug="live")
    with open(os.path.join(d, "charts", "f1.jsonl"), "a",
              encoding="utf-8") as f:
        f.write('{"y": 2}\n')
    check(mod.worklog_signature(root, slug="live") != before,
          "a new point changes the fingerprint, so the open tab reloads")


def test_chart_over_http_reaches_the_browser():
    root = tempfile.mkdtemp(prefix="worklog-http-")
    d = make_task(root, "served", log="<p>log body</p>")
    make_chart(d, "f1", cfg={"title": "Served chart"},
               points=[{"x": 0, "y": 0.9, "s": "kept", "l": "H1"}])
    proc = start_server(root)
    try:
        check(wait_until_up(), "server up")
        status, _, body = get("/served/")
        check(status == 200, f"the task page serves 200 (got {status})")
        check("Served chart" in body and "<svg" in body,
              "the chart reaches the browser as inline SVG")
        check("log body" in body, "the log still reaches the browser")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def main():
    # Auto-discovers every test_* in definition order, so later tasks add a
    # function and nothing else. Dicts preserve insertion order.
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print()
    if failures:
        print(f"FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("all worklog checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
