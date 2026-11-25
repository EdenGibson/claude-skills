#!/usr/bin/env python3
"""Behavioral tests for the html-design live-reload server.

Starts server.py as a subprocess against a temp dir and asserts the four
behaviors that are easy to get subtly wrong:
  1. A single .html file is served at "/" with the live-reload script injected.
  2. /__livereload is an SSE stream that emits `data: reload` when a file changes.
  3. With >1 .html file, "/" serves an auto-built gallery linking each file.
  4. `server.py stop <port>` terminates the running server.

Run: python3 test_server.py
Exits 0 on success, non-zero (with a FAIL line) otherwise.
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "server.py")
PORT = 4399  # test port, unlikely to clash with the default 4321
BASE = f"http://127.0.0.1:{PORT}"

failures = []


def check(cond, msg):
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        failures.append(msg)


def get(path, timeout=5):
    status, headers, raw = get_raw(path, timeout=timeout)
    return status, headers, raw.decode("utf-8", "replace")


def get_raw(path, timeout=5):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.status, r.headers, r.read()


def get_range(path, rng, timeout=5):
    """GET with a Range header. Returns (status, headers, body_bytes)."""
    req = urllib.request.Request(BASE + path, headers={"Range": rng})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def status_of(path, timeout=5):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


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
    spec.loader.exec_module(mod)  # __main__ guard keeps this from starting a server
    return mod


def test_bind_host_is_never_all_interfaces():
    """This box has a public interface, so 0.0.0.0 would publish mockups to it."""
    mod = load_server_module()
    saved = os.environ.pop("HTML_DESIGN_BIND", None)
    try:
        host = mod.bind_host()
        check(host != "0.0.0.0", f"default bind is never 0.0.0.0 (got {host})")
        # 100.64.0.0/10 is the tailnet (CGNAT) range tailscale hands out.
        check(host == "127.0.0.1" or host.startswith("100."),
              f"default bind is loopback or tailnet (got {host})")
        os.environ["HTML_DESIGN_BIND"] = "127.0.0.1"
        check(mod.bind_host() == "127.0.0.1", "HTML_DESIGN_BIND overrides the default")
    finally:
        os.environ.pop("HTML_DESIGN_BIND", None)
        if saved is not None:
            os.environ["HTML_DESIGN_BIND"] = saved


def test_latex_detection():
    """KaTeX is injected only into pages that actually contain math.

    Non-math mockups must stay untouched: the assets are ~600 KB of JS+fonts,
    and a pricing page full of `$` must never be mistaken for TeX.
    """
    mod = load_server_module()
    should_fire = {
        "display dollars": "<p>$$E = mc^2$$</p>",
        "inline paren": r"<p>the value \(x_i\) here</p>",
        "display bracket": r"<p>\[\int_0^1 f\]</p>",
        "equation env": r"<p>\begin{equation}a=b\end{equation}</p>",
        "explicit opt-in": '<body data-latex><div id="math-goes-here"></div></body>',
    }
    for label, snippet in should_fire.items():
        check(mod.wants_katex(snippet), f"detects LaTeX: {label}")

    should_not_fire = {
        "plain page": "<h1>Pricing</h1><p>Simple and fair.</p>",
        "currency": "<p>$29/mo</p><p>$290/yr</p>",
        "regex in script": r"<script>s.replace(/\(a\)/g, '')</script>",
        "tex inside code": r"<pre><code>\(not math\)</code></pre>",
        "explicit opt-out": r'<body data-latex="off"><p>$$x$$</p></body>',
        # An attribute built inside a template literal is code, not markup.
        "data-latex inside script":
            '<script>el.innerHTML = `<span data-latex="${x}">`;</script>',
        # Designs that wire up their own math engine must be left alone: a
        # second KaTeX would clobber the global and re-walk rendered output.
        "page ships its own katex":
            '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js">'
            '</script><p>$$x^2$$</p>',
        "page ships its own mathjax":
            '<script id="MathJax-script" src="/mathjax/tex-svg.js"></script><p>$$x$$</p>',
    }
    for label, snippet in should_not_fire.items():
        check(not mod.wants_katex(snippet), f"leaves alone: {label}")

    # Single-`$` delimiters are opt-in only, precisely because of the currency case.
    check(not mod.wants_dollar_math("<p>$$x$$</p>"), "single-$ math is off by default")
    check(mod.wants_dollar_math('<body data-latex="dollars">$x$</body>'),
          'data-latex="dollars" turns single-$ math on')


def test_design_files_are_newest_first():
    """The gallery is a work log, not a directory listing: whatever was touched
    last must lead, regardless of filename."""
    mod = load_server_module()
    d = tempfile.mkdtemp(prefix="design-order-")
    # Alphabetical order (a, b, c) is deliberately the REVERSE of mtime order.
    for name, age in (("a-oldest.html", 300), ("b-middle.html", 200), ("c-newest.html", 100)):
        p = os.path.join(d, name)
        with open(p, "w") as f:
            f.write("<!doctype html><html><body>x</body></html>")
        stamp = time.time() - age
        os.utime(p, (stamp, stamp))
    got = mod.design_files(d)
    check(got == ["c-newest.html", "b-middle.html", "a-oldest.html"],
          f"design_files() orders newest-mtime first (got {got})")

    # Same mtime -> stable, name-ordered tie-break rather than filesystem order.
    tie = tempfile.mkdtemp(prefix="design-tie-")
    for name in ("zeta.html", "alpha.html"):
        p = os.path.join(tie, name)
        with open(p, "w") as f:
            f.write("<!doctype html><html><body>x</body></html>")
        os.utime(p, (1_700_000_000, 1_700_000_000))
    got_tie = mod.design_files(tie)
    check(got_tie == ["alpha.html", "zeta.html"],
          f"equal mtimes tie-break by name (got {got_tie})")


def test_watch_signature_is_scoped_to_one_page():
    """Parallel agents share one design folder, so a folder-wide reload signal
    means every session's write yanks every open tab. A tab watching one page
    must only react to that page (plus shared top-level css/js)."""
    mod = load_server_module()
    d = tempfile.mkdtemp(prefix="design-scope-")
    mine = os.path.join(d, "mine.html")
    theirs = os.path.join(d, "theirs.html")
    for p in (mine, theirs):
        with open(p, "w") as f:
            f.write("<!doctype html><html><body>x</body></html>")

    scoped_before = mod.watch_signature(d, only="mine.html")
    folder_before = mod.watch_signature(d)

    with open(theirs, "w") as f:  # another session's design
        f.write("<!doctype html><html><body>they edited</body></html>")
    os.utime(theirs, (time.time() + 5, time.time() + 5))

    check(mod.watch_signature(d, only="mine.html") == scoped_before,
          "scoped signature ignores another session's page")
    check(mod.watch_signature(d) != folder_before,
          "folder-wide signature still reacts to any page (gallery tabs)")

    with open(mine, "w") as f:
        f.write("<!doctype html><html><body>I edited</body></html>")
    os.utime(mine, (time.time() + 9, time.time() + 9))
    check(mod.watch_signature(d, only="mine.html") != scoped_before,
          "scoped signature reacts to its own page")

    # Shared assets still count: a design that pulls in a sibling stylesheet
    # must reload when the stylesheet changes.
    css = os.path.join(d, "shared.css")
    with open(css, "w") as f:
        f.write("body{color:red}")
    sig_with_css = mod.watch_signature(d, only="mine.html")
    with open(css, "w") as f:
        f.write("body{color:blue}")
    os.utime(css, (time.time() + 12, time.time() + 12))
    check(mod.watch_signature(d, only="mine.html") != sig_with_css,
          "scoped signature still reacts to top-level css/js")

    # A page name is attacker-controlled input on a tailnet-exposed server.
    traversal = mod.watch_signature(d, only="../../etc/passwd")
    check(traversal == mod.watch_signature(d),
          "unknown/traversal page name falls back to folder-wide, never escapes")


def main():
    test_bind_host_is_never_all_interfaces()
    test_design_files_are_newest_first()
    test_watch_signature_is_scoped_to_one_page()
    test_latex_detection()
    tmp = tempfile.mkdtemp(prefix="design-test-")
    design = os.path.join(tmp, "current.html")
    with open(design, "w") as f:
        f.write("<!doctype html><html><body><h1>hello</h1></body></html>")

    # These cases exercise serving mechanics, so pin the bind to loopback; the
    # real default is the tailnet IP, which this harness cannot reach via BASE.
    # Bind policy itself is covered by test_bind_host_is_never_all_interfaces.
    child_env = dict(os.environ, HTML_DESIGN_BIND="127.0.0.1")
    proc = subprocess.Popen(
        [sys.executable, SERVER, tmp, str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=child_env,
    )
    try:
        if not wait_until_up():
            out = b""
            try:
                proc.terminate()
                out = proc.stdout.read() if proc.stdout else b""
            except Exception:
                pass
            print("  FAIL: server did not come up")
            print(out.decode("utf-8", "replace"))
            failures.append("server did not come up")
            return

        # 1. single file served at "/" with injected live-reload script
        status, _, body = get("/")
        check(status == 200, "GET / returns 200")
        check("<h1>hello</h1>" in body, "GET / serves the original html content")
        check("/__livereload" in body and "EventSource" in body,
              "GET / injects the live-reload (EventSource) script")

        # 2. SSE stream emits `reload` after a file changes
        sse_ok = False
        try:
            stream = urllib.request.urlopen(BASE + "/__livereload", timeout=8)
            ctype = stream.headers.get("Content-Type", "")
            check("text/event-stream" in ctype,
                  "/__livereload Content-Type is text/event-stream")
            # change the file AFTER connecting so the server detects a new signature
            time.sleep(0.4)
            with open(design, "w") as f:
                f.write("<!doctype html><html><body><h1>changed</h1></body></html>")
            deadline = time.time() + 5
            while time.time() < deadline:
                line = stream.readline()
                if not line:
                    break
                if b"reload" in line:
                    sse_ok = True
                    break
            stream.close()
        except Exception as e:
            print(f"  (sse error: {e})")
        check(sse_ok, "SSE emits `reload` within 5s of a file change")

        # 3. multiple html files -> "/" is an auto-built gallery linking each
        with open(os.path.join(tmp, "v2.html"), "w") as f:
            f.write("<!doctype html><html><body>v2</body></html>")
        status, _, body = get("/")
        check(status == 200, "GET / (gallery) returns 200")
        check("current.html" in body and "v2.html" in body,
              "gallery lists both current.html and v2.html")

        # 3b. A page tells the reload stream which file it is showing, so a
        #     parallel session editing a different design leaves it alone.
        _, _, page = get("/current.html")
        check("page=current.html" in page,
              "a design page scopes its reload stream to its own filename")
        _, _, gallery = get("/")
        check("__livereload" in gallery and "page=" not in gallery,
              "the gallery watches the whole folder, so new designs appear")

        no_crosstalk = None
        try:
            stream = urllib.request.urlopen(
                BASE + "/__livereload?page=current.html", timeout=2)
            time.sleep(0.4)
            with open(os.path.join(tmp, "v2.html"), "w") as f:  # another session
                f.write("<!doctype html><html><body>v2 edited</body></html>")
            try:
                deadline = time.time() + 1.6
                no_crosstalk = True
                while time.time() < deadline:
                    line = stream.readline()
                    if b"reload" in line:
                        no_crosstalk = False
                        break
            except (TimeoutError, OSError):
                no_crosstalk = True  # nothing sent: exactly what we want
            stream.close()
        except Exception as e:
            print(f"  (scoped sse error: {e})")
        check(no_crosstalk is True,
              "a scoped stream stays quiet when another design is edited")

        # 4. LaTeX: math pages get KaTeX wired up, plain pages stay clean,
        #    and the assets come from this server (the devbox has no internet).
        with open(os.path.join(tmp, "math.html"), "w") as f:
            f.write("<!doctype html><html><head></head><body>"
                    "<p>$$E = mc^2$$</p></body></html>")
        _, _, mathpage = get("/math.html")
        check("/__katex/katex.min.css" in mathpage,
              "math page links the locally-served KaTeX stylesheet")
        check("renderMathInElement" in mathpage,
              "math page gets the auto-render bootstrap")
        _, _, plainpage = get("/current.html")
        check("__katex" not in plainpage, "plain page is not burdened with KaTeX")

        st, hdr, css = get_raw("/__katex/katex.min.css")
        check(st == 200 and b"KaTeX_Main" in css,
              "GET /__katex/katex.min.css serves the vendored stylesheet")
        check("text/css" in hdr.get("Content-Type", ""), "KaTeX CSS has a css Content-Type")
        # Fonts must resolve relative to the CSS URL or every glyph silently
        # falls back to a system font and the math looks wrong but not broken.
        st, hdr, font = get_raw("/__katex/fonts/KaTeX_Main-Regular.woff2")
        check(st == 200 and len(font) > 1000, "KaTeX woff2 fonts are served")
        check("font/woff2" in hdr.get("Content-Type", ""), "fonts have a woff2 Content-Type")
        check(status_of("/__katex/..%2f..%2fSKILL.md") != 200,
              "/__katex/ refuses path traversal outside the vendor dir")

        # Gallery previews should render math, but must not open an SSE stream
        # (browsers cap ~6 connections per origin; iframes would exhaust it).
        _, _, embedded = get("/math.html?embed=1")
        check("__katex" in embedded, "embedded (gallery iframe) math still renders")
        check("EventSource" not in embedded, "embedded math page opens no SSE stream")

        # 4b. Static files must be revalidated. With only Last-Modified, Chrome
        #     caches a file for 10% of its age, so a script untouched for 4 days
        #     stays cached ~10 hours. A reload then pairs new html with old
        #     modules, and the page breaks with no visible cause.
        os.makedirs(os.path.join(tmp, "src"), exist_ok=True)
        with open(os.path.join(tmp, "src", "app.js"), "w") as f:
            f.write("export const v = 1;\n")
        st, hdr, _ = get_raw("/src/app.js")
        check(st == 200 and hdr.get("Cache-Control") == "no-cache",
              f"static js is sent with Cache-Control: no-cache (got {hdr.get('Cache-Control')})")
        req = urllib.request.Request(BASE + "/src/app.js",
                                     headers={"If-Modified-Since": hdr.get("Last-Modified")})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                revalidated = r.status
        except urllib.error.HTTPError as e:
            revalidated = e.code
        check(revalidated == 304, f"an unchanged file revalidates as 304 (got {revalidated})")

        # 5. Byte ranges. Without them a <video> cannot seek: Chrome asks for a
        #    range, gets the whole file back, and the scrub bar does nothing --
        #    you can only watch forward at 1x as the file downloads.
        clip = os.path.join(tmp, "clip.webm")
        payload = bytes(range(256)) * 400  # 102400 bytes, position-checkable
        with open(clip, "wb") as f:
            f.write(payload)

        st, hdr, body = get_raw("/clip.webm")
        check(st == 200 and body == payload, "GET /clip.webm serves the whole file")
        check(hdr.get("Accept-Ranges") == "bytes",
              "a plain GET advertises Accept-Ranges: bytes")
        check("video/webm" in hdr.get("Content-Type", ""),
              "webm gets a video Content-Type")

        st, hdr, body = get_range("/clip.webm", "bytes=1000-1999")
        check(st == 206, "a Range request returns 206, not 200")
        check(body == payload[1000:2000], "206 body is exactly the bytes asked for")
        check(hdr.get("Content-Range") == "bytes 1000-1999/102400",
              "206 carries a correct Content-Range")
        check(hdr.get("Content-Length") == "1000", "206 Content-Length is the slice")

        # Chrome's opening probe on a <video> is an open-ended range.
        st, hdr, body = get_range("/clip.webm", "bytes=0-")
        check(st == 206 and len(body) == 102400,
              "open-ended `bytes=0-` returns 206 with the rest of the file")

        # Seeking near the end sends a suffix range.
        st, hdr, body = get_range("/clip.webm", "bytes=-500")
        check(st == 206 and body == payload[-500:],
              "suffix range `bytes=-500` returns the last 500 bytes")

        # An end past EOF is legal and clamps; a start past EOF is not.
        st, _, body = get_range("/clip.webm", "bytes=102300-999999")
        check(st == 206 and body == payload[102300:],
              "an end past EOF clamps to the last byte")
        st, hdr, _ = get_range("/clip.webm", "bytes=200000-200100")
        check(st == 416, "a start past EOF returns 416")
        check(hdr.get("Content-Range") == "bytes */102400",
              "416 reports the real file size")

        # A malformed or multi-part range must not corrupt the response.
        st, _, body = get_range("/clip.webm", "bytes=abc")
        check(st == 200 and body == payload,
              "an unparseable Range falls back to the whole file")
        st, _, body = get_range("/clip.webm", "bytes=0-99,200-299")
        check(st == 200 and body == payload,
              "a multi-part Range falls back to the whole file")

        # HEAD must report the same 206 headers and carry no body, or a client
        # that probes with HEAD before playing desyncs the connection.
        req = urllib.request.Request(BASE + "/clip.webm", method="HEAD",
                                     headers={"Range": "bytes=0-99"})
        with urllib.request.urlopen(req, timeout=5) as r:
            check(r.status == 206 and r.read() == b"",
                  "HEAD with a Range returns 206 headers and no body")
    finally:
        # 5. stop subcommand terminates the server
        rc = subprocess.call([sys.executable, SERVER, "stop", str(PORT)])
        check(rc == 0, "`server.py stop <port>` exits 0")
        time.sleep(0.5)
        down = False
        try:
            get("/", timeout=1)
        except Exception:
            down = True
        check(down, "server is no longer reachable after stop")
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()

    if failures:
        print(f"\n{len(failures)} FAILURE(S)")
        sys.exit(1)
    print("\nALL PASSED")


if __name__ == "__main__":
    main()
