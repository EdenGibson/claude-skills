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
import sys
import socket
import tempfile
import time
import html as html_mod
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 4321
DEFAULT_DIR = os.path.expanduser("~/design-lab")
POLL_SECONDS = 0.3

# Injected before </body> (or appended) into every served HTML page.
LIVERELOAD_SNIPPET = """
<script data-livereload>
(function () {
  try {
    var es = new EventSource('/__livereload');
    es.onmessage = function (e) { if (e.data === 'reload') location.reload(); };
  } catch (_) {}
})();
</script>
""".strip()


def pidfile_for(port):
    return os.path.join(tempfile.gettempdir(), f"design-lab-{port}.pid")


def design_files(directory):
    """Top-level .html files (excluding the generated index), sorted by name."""
    try:
        names = [
            n for n in os.listdir(directory)
            if n.lower().endswith(".html") and n.lower() != "index.html"
            and os.path.isfile(os.path.join(directory, n))
        ]
    except OSError:
        return []
    return sorted(names)


def watch_signature(directory):
    """A cheap fingerprint of the design folder: changes when any html/css/js
    file is edited, added, or removed. Used to decide when to push a reload."""
    sig = []
    try:
        for n in sorted(os.listdir(directory)):
            if not n.lower().endswith((".html", ".css", ".js")):
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


def inject(html_bytes):
    """Insert the live-reload snippet before </body>, else append it."""
    text = html_bytes.decode("utf-8", "replace")
    lower = text.lower()
    idx = lower.rfind("</body>")
    if idx != -1:
        text = text[:idx] + LIVERELOAD_SNIPPET + "\n" + text[idx:]
    else:
        text = text + "\n" + LIVERELOAD_SNIPPET
    return text.encode("utf-8")


def gallery_page(directory):
    cards = []
    for name in design_files(directory):
        safe = html_mod.escape(name)
        cards.append(
            f'<a class="card" href="/{safe}">'
            # ?embed=1 keeps the live-reload EventSource out of preview iframes:
            # browsers cap ~6 connections per origin, so with many designs the
            # iframes' SSE streams would exhaust the pool and clicks would hang.
            f'<div class="frame"><iframe src="/{safe}?embed=1" loading="lazy" '
            f'tabindex="-1" scrolling="no"></iframe></div>'
            f'<span class="name">{safe}</span></a>'
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
  .name {{ display:block; padding:10px 14px; font-size:13px;
           border-top:1px solid #232734; }}
  .empty {{ padding:40px; color:#8b90a0; }}
</style></head>
<body>
<header><h1>Design lab</h1><p>{len(design_files(directory))} design(s) · live-reloads on change</p></header>
<div class="grid">
{body}
</div>
{LIVERELOAD_SNIPPET}
</body></html>"""


class Handler(SimpleHTTPRequestHandler):
    # `directory` is bound per-server below via a subclass.
    def log_message(self, *args):
        pass  # quiet

    def _send_html(self, body_bytes, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body_bytes)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/__livereload":
            return self._serve_sse()
        embed = "embed=1" in query

        root = self.directory

        if path == "/":
            files = design_files(root)
            if len(files) == 1:
                return self._serve_injected_html(os.path.join(root, files[0]))
            return self._send_html(gallery_page(root).encode("utf-8"))

        # Map URL path to a file; inject into .html, otherwise serve normally.
        local = self.translate_path(self.path)
        if local.lower().endswith(".html") and os.path.isfile(local):
            return self._serve_injected_html(local, live=not embed)
        return super().do_GET()

    def _serve_injected_html(self, local_path, live=True):
        try:
            with open(local_path, "rb") as f:
                raw = f.read()
        except OSError:
            self.send_error(404)
            return
        self._send_html(inject(raw) if live else raw)

    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last = watch_signature(self.directory)
        ticks = 0
        try:
            while True:
                time.sleep(POLL_SECONDS)
                sig = watch_signature(self.directory)
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


def make_handler(directory):
    class BoundHandler(Handler):
        def __init__(self, *a, **kw):
            # Pass directory through SimpleHTTPRequestHandler.__init__ so it sets
            # self.directory before handling the request. A class attribute alone
            # is shadowed because __init__ defaults self.directory to os.getcwd().
            super().__init__(*a, directory=directory, **kw)
    return BoundHandler


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start(directory, port):
    directory = os.path.abspath(os.path.expanduser(directory))
    os.makedirs(directory, exist_ok=True)
    if port_in_use(port):
        print(f"Design server already running on port {port} (reusing).")
        return 0

    handler_cls = make_handler(directory)
    server = ThreadingHTTPServer(("0.0.0.0", port), handler_cls)
    server.daemon_threads = True  # don't let lingering SSE threads block shutdown
    with open(pidfile_for(port), "w") as f:
        f.write(str(os.getpid()))
    print(f"Serving {directory} on http://0.0.0.0:{port}  (live-reload on)")
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
        print(f"Stopped design server (pid {pid}) on port {port}.")
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


def main(argv):
    if argv and argv[0] == "stop":
        port = int(argv[1]) if len(argv) > 1 else DEFAULT_PORT
        return stop(port)
    directory = argv[0] if len(argv) > 0 else DEFAULT_DIR
    port = int(argv[1]) if len(argv) > 1 else DEFAULT_PORT
    return start(directory, port)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
