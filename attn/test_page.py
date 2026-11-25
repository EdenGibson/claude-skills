#!/usr/bin/env python3
"""Behavioral tests for the attn page.

Run: python3 test_page.py
"""
import os
import sys
import tempfile

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
    root = tempfile.mkdtemp(prefix="attn-page-test-")
    os.environ["ATTN_DIR"] = root
    return root


def make(key, **kwargs):
    import store
    item = {
        "key": key, "title": key, "body": None, "project": None, "url": None,
        "source": "test", "alive": "true", "cwd": None,
        "filed": store.now_iso(), "refiled": store.now_iso(),
        "expires": None, "snoozed_until": None, "checked": store.now_iso(),
        "check_errors": 0, "last_error": None,
    }
    item.update(kwargs)
    return item


def test_visible_hides_a_snoozed_item():
    import page, store
    fresh()
    live = make("a")
    snoozed = make("b", snoozed_until=store.iso(store.now() + 3600))
    past = make("c", snoozed_until=store.iso(store.now() - 3600))
    keys = [i["key"] for i in page.visible([live, snoozed, past])]
    check(keys == ["a", "c"], f"a live snooze hides, a past one does not (got {keys})")


def test_digest_changes_with_the_open_set():
    import page
    fresh()
    one = page.digest([make("a")])
    two = page.digest([make("a"), make("b")])
    check(one != two, "adding an item changes the digest")
    retitled = page.digest([make("a", title="different")])
    check(one != retitled, "changing a title changes the digest")


def test_digest_ignores_the_checked_stamp():
    import page, store
    fresh()
    a = make("a", checked="2026-01-01T00:00:00Z")
    b = make("a", checked="2026-06-06T06:06:06Z")
    check(page.digest([a]) == page.digest([b]),
          "a new checked stamp must not reload the page")


def test_digest_ignores_item_order():
    import page
    fresh()
    forward = page.digest([make("a"), make("b")])
    backward = page.digest([make("b"), make("a")])
    check(forward == backward, "the digest is order-independent")


def test_render_escapes_html():
    import page
    fresh()
    html = page.render([make("a", title="<script>alert(1)</script>")])
    check("<script>alert(1)</script>" not in html, "the title is escaped")
    check("&lt;script&gt;" in html, "the escaped form is present")


def test_render_groups_by_project():
    import page
    fresh()
    html = page.render([make("a", project="Derive"), make("b")])
    check("Derive" in html, "the project name is a heading")
    check("unfiled" in html, "items with no project fall under unfiled")


def test_render_shows_an_empty_state():
    import page
    fresh()
    html = page.render([])
    check("Nothing needs you" in html, "empty reads as success")
    check("<form" not in html, "no action forms on an empty page")


def test_render_marks_a_failing_check():
    import page
    fresh()
    html = page.render([make("a", check_errors=3, last_error="exit 127: gh: not found")])
    check("check failing" in html, "a broken check is called out")
    check("gh: not found" in html, "the last error is shown")


def test_humanize():
    import page
    check(page.humanize(40) == "40s", f"40s (got {page.humanize(40)})")
    check(page.humanize(1800) == "30m", f"30m (got {page.humanize(1800)})")
    check(page.humanize(7200) == "2h", f"2h (got {page.humanize(7200)})")
    check(page.humanize(172800) == "2d", f"2d (got {page.humanize(172800)})")


def test_age_counts_from_filed_not_refiled():
    import page, store
    fresh()
    item = make("a", filed=store.iso(store.now() - 2 * 86400),
                refiled=store.now_iso())
    html = page.render([item])
    check("2d" in html, "a refiled item still shows its true age")


def test_javascript_url_is_not_a_link():
    import page
    fresh()
    html = page.render([make("a", url="javascript:alert(1)")])
    check("href" not in html, f"no href is rendered (got {html!r})")
    check(">a</a" not in html, "the title is not wrapped in a link")


def test_javascript_url_mixed_case_is_not_a_link():
    import page
    fresh()
    html = page.render([make("a", url="JaVaScRiPt:alert(1)")])
    check("href" not in html, f"a mixed-case scheme is still blocked (got {html!r})")


def test_javascript_url_with_leading_space_is_not_a_link():
    import page
    fresh()
    html = page.render([make("a", url="  javascript:alert(1)")])
    check("href" not in html, f"leading whitespace does not bypass the block (got {html!r})")


def test_data_url_is_not_a_link():
    import page
    fresh()
    html = page.render(
        [make("a", url="data:text/html,<script>alert(1)</script>")])
    check("href" not in html, f"a data: url is blocked (got {html!r})")


def test_https_url_renders_as_a_link():
    import page
    fresh()
    html = page.render([make("a", url="https://github.com/x/y/pull/1")])
    check('href="https://github.com/x/y/pull/1"' in html,
          f"an https url is a working href (got {html!r})")


def test_http_url_renders_as_a_link():
    import page
    fresh()
    html = page.render([make("a", url="http://devbox:4380/")])
    check('href="http://devbox:4380/"' in html,
          f"an http url is a working href (got {html!r})")


def serve_in_thread():
    """Start the server on an ephemeral port. Returns (base_url, shutdown)."""
    import threading
    import attn_server
    os.environ["ATTN_BIND"] = "127.0.0.1"
    httpd = attn_server.build_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    return f"http://127.0.0.1:{port}", httpd.shutdown


def test_bind_never_returns_all_interfaces():
    import attn_server
    os.environ.pop("ATTN_BIND", None)
    host = attn_server.bind_host()
    check(host != "0.0.0.0", f"never binds every interface (got {host})")


def test_bind_honours_the_override():
    import attn_server
    os.environ["ATTN_BIND"] = "127.0.0.1"
    check(attn_server.bind_host() == "127.0.0.1", "ATTN_BIND wins")
    os.environ.pop("ATTN_BIND", None)


def test_get_root_and_digest_and_state():
    import json as json_mod
    import urllib.request
    import store
    fresh()
    with store.lock():
        store.upsert("k", title="Approve the thing", alive="true")
    base, shutdown = serve_in_thread()
    try:
        body = urllib.request.urlopen(base + "/").read().decode()
        check("Approve the thing" in body, "the page lists the item")
        digest_value = urllib.request.urlopen(base + "/digest").read().decode()
        check(len(digest_value.strip()) == 16,
              f"digest is 16 chars (got {digest_value.strip()!r})")
        state = json_mod.loads(
            urllib.request.urlopen(base + "/state.json").read().decode())
        check(len(state) == 1 and state[0]["key"] == "k", "state.json lists it")
    finally:
        shutdown()


def test_post_dismiss_closes_and_suppresses():
    import urllib.parse
    import urllib.request
    import store
    fresh()
    with store.lock():
        store.upsert("k", title="T", alive="true")
    base, shutdown = serve_in_thread()
    try:
        data = urllib.parse.urlencode({"key": "k", "action": "dismiss"}).encode()
        request = urllib.request.Request(base + "/action", data=data)
        with urllib.request.urlopen(request) as response:
            check(response.status == 200, "the redirect is followed to the page")
        check(store.read_item("k") is None, "the item is closed")
        check(store.suppressed_until("k") is not None, "the key is suppressed")
    finally:
        shutdown()


def test_post_snooze_hides_but_keeps_the_item():
    import urllib.parse
    import urllib.request
    import store
    fresh()
    with store.lock():
        store.upsert("k", title="Snoozy", alive="true")
    base, shutdown = serve_in_thread()
    try:
        data = urllib.parse.urlencode({"key": "k", "action": "snooze"}).encode()
        urllib.request.urlopen(urllib.request.Request(base + "/action", data=data))
        item = store.read_item("k")
        check(item is not None, "the item still exists")
        check(item["snoozed_until"] is not None, "it is snoozed")
        body = urllib.request.urlopen(base + "/").read().decode()
        check("Snoozy" not in body, "it is hidden from the page")
    finally:
        shutdown()


def test_post_with_a_bad_key_is_refused():
    import urllib.error
    import urllib.parse
    import urllib.request
    fresh()
    base, shutdown = serve_in_thread()
    try:
        data = urllib.parse.urlencode(
            {"key": "../escape", "action": "dismiss"}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(base + "/action", data=data))
            check(False, "a traversal key must not succeed")
        except urllib.error.HTTPError as exc:
            check(exc.code == 400, f"a bad key is 400 (got {exc.code})")
    finally:
        shutdown()


def test_unknown_path_is_404():
    import urllib.error
    import urllib.request
    fresh()
    base, shutdown = serve_in_thread()
    try:
        try:
            urllib.request.urlopen(base + "/nope")
            check(False, "an unknown path must not succeed")
        except urllib.error.HTTPError as exc:
            check(exc.code == 404, f"unknown path is 404 (got {exc.code})")
    finally:
        shutdown()


def main():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print()
    if failures:
        print(f"FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("all attn page checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
