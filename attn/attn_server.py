#!/usr/bin/env python3
"""The attn server: run the checks, serve the page, accept two actions.

    attn_server.py [port]        default 4380, or $ATTN_PORT

Bound to the tailnet IP, never 0.0.0.0. This box has a public interface, and
the page names internal work.
"""
import json
import ipaddress
import os
import signal
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checker  # noqa: E402
import page  # noqa: E402
import store  # noqa: E402

DEFAULT_PORT = 4380

# Favicon, so this tab is telling among the other devbox servers. Written by
# ~/.local/bin/make-server-icons.py; a missing folder costs the icon only.
ICON_DIR = os.path.expanduser("~/.local/share/server-icons")
ICONS = {
    "/favicon.ico": ("attn.ico", "image/x-icon"),
    "/favicon.png": ("attn-32.png", "image/png"),
}


def is_private_bind(address):
    """True when binding this address cannot expose the server publicly.

    Loopback and the tailnet range 100.64.0.0/10 only. Everything else is
    refused, including 0.0.0.0, :: and this box's own 172.31/16 address, which
    the public interface carries.
    """
    try:
        parsed = ipaddress.ip_address(address.strip())
    except ValueError:
        return False
    if parsed.is_loopback:
        return True
    return parsed in ipaddress.ip_network("100.64.0.0/10")


def bind_host():
    """Resolve the interface to bind.

    Never a publicly reachable address: this box has a public interface at
    172.31.6.202. Prefer the tailnet IP, which reaches Eden's laptop and
    nowhere else. Fall back to loopback when tailscale cannot answer.
    attn.service refuses to start in that case, so the fallback serves a
    hand-run server and the tests.

    Every candidate goes through is_private_bind, including the ATTN_BIND
    override and whatever `tailscale` prints. Measured before that check:
    ATTN_BIND=0.0.0.0 bound all interfaces and answered 200 on the public
    address, while the docstring promised it could not happen. `tailscale` is
    resolved on PATH, so a different binary earlier on PATH could print
    0.0.0.0 and be trusted verbatim.
    """
    override = os.environ.get("ATTN_BIND")
    if override:
        if is_private_bind(override):
            return override.strip()
        raise SystemExit(
            f"attn: refusing to bind {override!r}; it is neither loopback nor "
            f"in the tailnet range 100.64.0.0/10")
    try:
        proc = subprocess.run(["tailscale", "ip", "-4"], capture_output=True,
                              text=True, timeout=3)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                address = line.strip()
                if address and is_private_bind(address):
                    return address
    except (OSError, subprocess.SubprocessError):
        pass
    return "127.0.0.1"


def do_action(key, action):
    """Apply a page action. Returns True when it changed something."""
    if not store.valid_key(key) or action not in ("dismiss", "snooze"):
        return False
    with store.lock():
        item = store.read_item(key)
        if item is None:
            return False
        if action == "dismiss":
            # Suppress only when the close actually happened. close_item
            # returns False when the unlink fails, and the old code discarded
            # that. Measured with open/ at mode 555: the page reported
            # success, the item stayed visible, and the key was blocked for
            # seven days, so Dismiss could never clear it.
            if not store.close_item(key, "dismissed"):
                return False
            store.suppress(key)
            return True
        item["snoozed_until"] = store.iso(store.now() + store.SNOOZE_SECONDS)
        store.write_item(item)
        return True


class Handler(BaseHTTPRequestHandler):
    server_version = "attn/1.0"

    def _send(self, code, body, content_type="text/html; charset=utf-8"):
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_icon(self, stem, content_type):
        try:
            with open(os.path.join(ICON_DIR, stem), "rb") as fh:
                blob = fh.read()
        except OSError:
            self.send_error(404, "no icon")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ICONS:
            self._send_icon(*ICONS[path])
            return
        if path == "/":
            self._send(200, page.render(store.list_open()))
            return
        if path == "/digest":
            visible = page.visible(store.list_open())
            self._send(200, page.digest(visible), "text/plain; charset=utf-8")
            return
        if path == "/state.json":
            self._send(200, json.dumps(store.list_open(), indent=2,
                                       sort_keys=True),
                       "application/json; charset=utf-8")
            return
        self.send_error(404, "no such path")

    def _same_origin(self):
        """True when a POST came from the attn page itself.

        Origin decides when the browser sends it. A form post from another
        site always carries one, so a missing Origin is not the attack shape;
        curl and the tests send none. When Origin is absent, Referer decides
        if it is present, and a request with neither is allowed through.
        """
        expected = f"http://{self.headers.get('Host', '')}"
        origin = self.headers.get("Origin")
        if origin:
            return origin == expected
        referer = self.headers.get("Referer")
        if referer:
            parts = urllib.parse.urlparse(referer)
            return f"{parts.scheme}://{parts.netloc}" == expected
        return True

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/action":
            self.send_error(404, "no such path")
            return
        # Refuse a cross-site POST. A form post is a simple request, so the
        # browser sends it with no preflight. Without this check any page Eden
        # opens can dismiss items by guessing keys, which are short slugs like
        # "pr-42", and suppress each one for seven days. Binding to the
        # tailnet does not help, because his own browser makes the request.
        if not self._same_origin():
            self.send_error(403, "cross-site request refused")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 4096:
            self.send_error(400, "bad body")
            return
        try:
            raw = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError:
            # Uncaught, this dropped the connection with a traceback and no
            # response at all.
            self.send_error(400, "body is not utf-8")
            return
        fields = urllib.parse.parse_qs(raw)
        key = (fields.get("key") or [""])[0]
        action = (fields.get("action") or [""])[0]
        if not do_action(key, action):
            self.send_error(400, "bad key or action")
            return
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        # One line per action, nothing per page poll: the reload script hits
        # /digest every 15 seconds and would bury the journal.
        if self.command == "POST":
            sys.stderr.write(f"attn {self.command} {self.path}\n")


def build_server(host, port):
    return ThreadingHTTPServer((host, port), Handler)


def main(argv):
    port = int(argv[0]) if argv else int(os.environ.get("ATTN_PORT",
                                                        DEFAULT_PORT))
    store.ensure_dirs()
    host = bind_host()
    httpd = build_server(host, port)

    stop = threading.Event()
    thread = threading.Thread(target=checker.sweep_forever, args=(stop,),
                              daemon=True)
    thread.start()

    def shutdown(signum, frame):
        stop.set()
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print(f"attn serving http://{host}:{port} "
          f"(sweep every {checker.SWEEP_SECONDS}s)", flush=True)
    try:
        httpd.serve_forever()
    finally:
        stop.set()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
