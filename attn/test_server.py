#!/usr/bin/env python3
"""Behavioral tests for the attn server.

Run: python3 test_server.py

bind_host had no test at all. A reviewer replaced its whole body with
`return "0.0.0.0"` and every other suite still passed, so the one function
that decides whether this box answers on its public interface was unguarded.
"""
import http.client
import os
import stat
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

failures = []


def check(cond, msg):
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        failures.append(msg)


def fresh():
    root = tempfile.mkdtemp(prefix="attn-server-test-")
    os.environ["ATTN_DIR"] = root
    import store
    store.ensure_dirs()
    return root


class FakeRun:
    """Stand in for subprocess.run inside attn_server.

    stdout is what a `tailscale ip -4` would print. raises=True makes the
    call fail the way a missing binary does.
    """

    def __init__(self, stdout="", returncode=0, raises=None):
        self.stdout = stdout
        self.returncode = returncode
        self.raises = raises

    def __call__(self, *args, **kwargs):
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(args[0], self.returncode,
                                           self.stdout, "")


def with_tailscale(fake, fn):
    import attn_server
    real = attn_server.subprocess.run
    attn_server.subprocess.run = fake
    try:
        return fn()
    finally:
        attn_server.subprocess.run = real


def bind_host_in_subprocess(env_bind):
    """bind_host raises SystemExit on a bad ATTN_BIND, so run it apart."""
    proc = subprocess.run(
        [sys.executable, "-c",
         "import attn_server; print(attn_server.bind_host())"],
        capture_output=True, text=True, cwd=HERE,
        env={**os.environ, "ATTN_BIND": env_bind})
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def test_is_private_bind_accepts_loopback_and_the_tailnet():
    fresh()
    import attn_server as srv
    for address in ("127.0.0.1", "127.1.2.3", "::1",
                    "100.64.0.0", "100.123.184.91", "100.127.255.255"):
        check(srv.is_private_bind(address), f"{address} is a private bind")


def test_is_private_bind_refuses_every_public_address():
    fresh()
    import attn_server as srv
    # 0.0.0.0 and :: are the wildcards that would publish this box.
    # 172.31.6.202 is this box's own public interface.
    # 100.63.255.255 and 100.128.0.1 sit just outside 100.64.0.0/10, so
    # they catch a range written as 100.64.0.0/16 or as a string prefix.
    for address in ("0.0.0.0", "::", "172.31.6.202", "8.8.8.8",
                    "100.63.255.255", "100.128.0.1", "notanip", ""):
        check(not srv.is_private_bind(address), f"{address!r} is refused")


def test_bind_host_uses_the_tailnet_address_tailscale_prints():
    fresh()
    import attn_server as srv
    os.environ.pop("ATTN_BIND", None)
    got = with_tailscale(FakeRun(stdout="100.99.1.2\n"), srv.bind_host)
    check(got == "100.99.1.2", f"bind_host returned the tailnet IP ({got})")


def test_bind_host_ignores_a_public_address_from_tailscale():
    fresh()
    import attn_server as srv
    os.environ.pop("ATTN_BIND", None)
    # `tailscale` is resolved on PATH. A different binary earlier on PATH
    # can print anything, and before the check it was trusted verbatim.
    got = with_tailscale(FakeRun(stdout="0.0.0.0\n"), srv.bind_host)
    check(got == "127.0.0.1", f"a spoofed 0.0.0.0 fell back to loopback ({got})")


def test_bind_host_takes_the_first_private_line():
    fresh()
    import attn_server as srv
    os.environ.pop("ATTN_BIND", None)
    got = with_tailscale(FakeRun(stdout="0.0.0.0\n100.99.1.2\n"), srv.bind_host)
    check(got == "100.99.1.2", f"skipped the public line, took the tailnet one ({got})")


def test_bind_host_falls_back_to_loopback_without_tailscale():
    fresh()
    import attn_server as srv
    os.environ.pop("ATTN_BIND", None)
    got = with_tailscale(FakeRun(raises=FileNotFoundError("tailscale")),
                         srv.bind_host)
    check(got == "127.0.0.1", f"missing tailscale gave loopback ({got})")
    got = with_tailscale(FakeRun(stdout="", returncode=1), srv.bind_host)
    check(got == "127.0.0.1", f"a failing tailscale gave loopback ({got})")


def test_attn_bind_accepts_a_tailnet_override():
    fresh()
    code, out, _ = bind_host_in_subprocess("100.99.1.2")
    check(code == 0 and out == "100.99.1.2",
          f"ATTN_BIND=100.99.1.2 was honoured (rc={code}, out={out!r})")


def test_attn_bind_refuses_a_public_override_and_exits():
    fresh()
    for address in ("0.0.0.0", "::", "172.31.6.202"):
        code, out, err = bind_host_in_subprocess(address)
        check(code != 0, f"ATTN_BIND={address} exited non-zero (rc={code})")
        check(out == "", f"ATTN_BIND={address} returned no host to bind")
        check("refusing to bind" in err,
              f"ATTN_BIND={address} said why it refused")


# --- the two page actions -------------------------------------------------

def test_dismiss_closes_and_suppresses():
    fresh()
    import attn_server as srv
    import store
    store.upsert("k1", "title", source="test")
    check(srv.do_action("k1", "dismiss"), "dismiss reported success")
    check(store.read_item("k1") is None, "the item is gone from open/")
    check(store.suppressed_until("k1") is not None, "the key is suppressed")


def test_a_failed_dismiss_does_not_suppress_the_key():
    root = fresh()
    import attn_server as srv
    import store
    store.upsert("k1", "title", source="test")
    mode = os.stat(store.open_dir()).st_mode
    os.chmod(store.open_dir(), stat.S_IRUSR | stat.S_IXUSR)
    try:
        # close_item returns False when the unlink fails. The old code threw
        # that away, suppressed the key for seven days, and left the item on
        # the page, so Dismiss could never clear it.
        result = srv.do_action("k1", "dismiss")
    finally:
        os.chmod(store.open_dir(), mode)
    check(result is False, "a failed dismiss reported failure")
    check(store.suppressed_until("k1") is None,
          "a failed dismiss left the key un-suppressed")
    check(store.read_item("k1") is not None, "the item is still open")
    del root


def test_snooze_sets_a_future_time_and_keeps_the_item():
    fresh()
    import attn_server as srv
    import store
    store.upsert("k1", "title", source="test")
    check(srv.do_action("k1", "snooze"), "snooze reported success")
    item = store.read_item("k1")
    check(item is not None, "snooze kept the item open")
    check(store.epoch(item["snoozed_until"]) > store.now(),
          "snoozed_until is in the future")


def test_do_action_refuses_junk():
    fresh()
    import attn_server as srv
    import store
    store.upsert("k1", "title", source="test")
    check(not srv.do_action("k1", "delete"), "an unknown action is refused")
    check(not srv.do_action("../etc/passwd", "dismiss"),
          "a path-traversal key is refused")
    check(not srv.do_action("", "dismiss"), "an empty key is refused")
    check(not srv.do_action("no-such-key", "dismiss"),
          "an absent key is refused")


# --- over real HTTP -------------------------------------------------------

class Serving:
    def __init__(self):
        import attn_server
        self.httpd = attn_server.build_server("127.0.0.1", 0)
        self.port = self.httpd.server_address[1]

    def __enter__(self):
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()


def test_get_serves_the_page_the_digest_and_the_state():
    fresh()
    import store
    store.upsert("k1", "only-item", source="test")
    with Serving() as srv:
        code, body = srv.request("GET", "/")
        check(code == 200 and b"only-item" in body, "GET / shows the item")
        code, digest = srv.request("GET", "/digest")
        check(code == 200 and len(digest.strip()) == 16,
              f"GET /digest is a 16-char hash ({digest!r})")
        code, state = srv.request("GET", "/state.json")
        check(code == 200 and b"only-item" in state, "GET /state.json has it")
        code, _ = srv.request("GET", "/nope")
        check(code == 404, "an unknown path is 404")


def test_a_same_origin_post_dismisses():
    fresh()
    import store
    store.upsert("k1", "t", source="test")
    with Serving() as srv:
        host = f"127.0.0.1:{srv.port}"
        code, _ = srv.request(
            "POST", "/action", body="key=k1&action=dismiss",
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Origin": f"http://{host}", "Host": host})
        check(code == 303, f"a same-origin dismiss redirected ({code})")
    check(store.read_item("k1") is None, "the item was dismissed")


def test_a_cross_site_post_is_refused():
    fresh()
    import store
    store.upsert("k1", "t", source="test")
    with Serving() as srv:
        host = f"127.0.0.1:{srv.port}"
        # A form post is a simple request, so a page Eden opens can submit
        # it with no preflight and dismiss items by guessing short keys.
        code, _ = srv.request(
            "POST", "/action", body="key=k1&action=dismiss",
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Origin": "https://evil.example", "Host": host})
        check(code == 403, f"a cross-origin dismiss was refused ({code})")
        code, _ = srv.request(
            "POST", "/action", body="key=k1&action=dismiss",
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://evil.example/x", "Host": host})
        check(code == 403, f"a cross-site referer was refused ({code})")
    check(store.read_item("k1") is not None, "the item survived both")


def test_a_post_with_neither_header_still_works():
    fresh()
    import store
    store.upsert("k1", "t", source="test")
    with Serving() as srv:
        # curl and these tests send neither header. A browser always sends
        # Origin on a cross-site form post, so absent is not the attack shape.
        code, _ = srv.request(
            "POST", "/action", body="key=k1&action=snooze",
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        check(code == 303, f"a header-less post was allowed ({code})")


def test_a_non_utf8_body_is_a_400_not_a_dropped_connection():
    fresh()
    with Serving() as srv:
        # Uncaught, .decode("utf-8") raised inside the handler and the
        # connection closed with no response at all.
        code, _ = srv.request(
            "POST", "/action", body=b"\xff\xfe\xfd",
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        check(code == 400, f"a non-utf-8 body is 400 ({code})")


def test_a_bad_body_length_is_a_400():
    fresh()
    with Serving() as srv:
        code, _ = srv.request(
            "POST", "/action", body="",
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        check(code == 400, f"an empty body is 400 ({code})")
        code, _ = srv.request(
            "POST", "/action", body="k=" + "a" * 5000,
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        check(code == 400, f"an oversized body is 400 ({code})")
        code, _ = srv.request("POST", "/nope", body="x",
                              headers={"Content-Type": "text/plain"})
        check(code == 404, f"POST to an unknown path is 404 ({code})")


def main():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print()
    if failures:
        print(f"FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("all attn server checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
