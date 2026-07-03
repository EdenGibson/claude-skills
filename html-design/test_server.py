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
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.status, r.headers, r.read().decode("utf-8", "replace")


def wait_until_up(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            get("/", timeout=1)
            return True
        except Exception:
            time.sleep(0.15)
    return False


def main():
    tmp = tempfile.mkdtemp(prefix="design-test-")
    design = os.path.join(tmp, "current.html")
    with open(design, "w") as f:
        f.write("<!doctype html><html><body><h1>hello</h1></body></html>")

    proc = subprocess.Popen(
        [sys.executable, SERVER, tmp, str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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
    finally:
        # 4. stop subcommand terminates the server
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
