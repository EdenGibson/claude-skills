#!/usr/bin/env python3
"""Behavioral tests for attn storage.

Run: python3 test_store.py
Every test points ATTN_DIR at a temp folder, so none touches the real ~/attn.
"""
import json
import os
import sys
import tempfile
import time

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
    """Point ATTN_DIR at a new temp dir and return it."""
    root = tempfile.mkdtemp(prefix="attn-test-")
    os.environ["ATTN_DIR"] = root
    return root


def test_key_validation():
    import store
    for good in ("a", "derive-pr-412", "a.b_c-9", "x" * 64):
        check(store.valid_key(good), f"accepts {good!r}")
    for bad in ("", ".", "..", "../escape", "Derive", "a b", "-lead", "x" * 65):
        check(not store.valid_key(bad), f"refuses {bad!r}")


def test_root_follows_the_env():
    import store
    root = fresh()
    check(store.root() == root, "root() reads ATTN_DIR on every call")
    check(store.open_dir() == os.path.join(root, "open"), "open_dir under root")
    check(store.lock_path() == os.path.join(root, ".lock"), "lock_path is root/.lock")
    # The property that actually matters: the lock can never collide with an
    # item file. write_json swaps the inode via os.replace, so a lock taken
    # on an item path would guard nothing.
    check(store.lock_path() not in (store.open_path("k"), store.suppress_path("k")),
          "the lock path never coincides with an item path")


def test_atomic_write_leaves_no_partial():
    import store
    root = fresh()
    store.ensure_dirs()
    path = os.path.join(store.open_dir(), "k.json")
    store.write_json(path, {"key": "k"})
    check(store.read_json(path) == {"key": "k"}, "round-trips json")
    leftovers = [n for n in os.listdir(store.open_dir()) if n.startswith(".tmp-")]
    check(leftovers == [], "no temp file left behind")


def test_read_json_of_garbage_returns_none():
    import store
    root = fresh()
    store.ensure_dirs()
    path = os.path.join(store.open_dir(), "bad.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not json")
    check(store.read_json(path) is None, "unparseable file reads as None")
    check(store.read_json(os.path.join(root, "nope.json")) is None,
          "missing file reads as None")


def test_lock_serialises_two_processes():
    """The lock must make a second acquirer wait, not just eventually succeed.

    A child acquires the lock, tells the parent through a pipe that it holds
    it, and only then sleeps for HOLD seconds. The parent starts its timer on
    that signal, so the measurement never depends on how long the fork takes
    to be scheduled. If lock() actually excludes, the parent blocks for close
    to HOLD; if lock() were a no-op, it returns at once and this assertion is
    what catches that.

    The pass condition is an ordering fact, not a duration. The child writes a
    marker file immediately before it releases. If the lock excludes, the
    parent cannot enter until after that release, so the marker is always
    there. If lock() were a no-op, the parent enters at once and the marker is
    absent. Nothing depends on how loaded the box is.

    Two earlier versions were worse. The first asserted check(True, ...), a
    constant, and passed against a no-op lock. The second timed the parent's
    wait against a threshold: with a real lock it measured 0.47-0.94s, but
    with a no-op it still measured 0.24s against a 0.25s bound, so a loaded
    box could have let a broken lock through.
    """
    import store
    fresh()
    HOLD = 0.3
    marker = os.path.join(store.root(), "released")
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        with store.lock():
            os.write(write_fd, b"1")   # the parent may try to acquire now
            time.sleep(HOLD)
            open(marker, "w").close()  # written while still holding the lock
        os.close(write_fd)
        os._exit(0)
    os.close(write_fd)
    try:
        os.read(read_fd, 1)            # blocks until the child holds the lock
        start = time.time()
        with store.lock():
            entered_after_release = os.path.exists(marker)
        elapsed = time.time() - start
    finally:
        os.close(read_fd)
        os.waitpid(pid, 0)
    check(entered_after_release,
          f"the parent entered only after the child released "
          f"(waited {elapsed:.2f}s of the child's {HOLD}s hold)")


def test_lock_survives_a_read_only_root():
    """A root the process cannot create in (a read-only ~/attn, say) must not
    turn lock() into an uncaught traceback: the CLI's exit codes are
    documented and a caller reads them, so this has to run unlocked instead.
    """
    import store
    fresh()
    orig_ensure_dirs = store.ensure_dirs
    store.ensure_dirs = lambda: (_ for _ in ()).throw(OSError("read-only root"))
    try:
        with store.lock():
            pass
        check(True, "lock() swallows a failing ensure_dirs instead of raising")
    except OSError:
        check(False, "lock() raised instead of running unlocked")
    finally:
        store.ensure_dirs = orig_ensure_dirs


def test_time_helpers_round_trip_utc():
    import store
    t = 1770000000
    check(store.epoch(store.iso(t)) == t, "iso/epoch round-trip in UTC")
    check(store.epoch(None) is None, "epoch(None) is None")
    check(store.epoch("garbage") is None, "epoch of garbage is None")


def test_upsert_creates_with_a_ttl_when_there_is_no_check():
    import store
    fresh()
    with store.lock():
        item = store.upsert("k", title="Decide the pricing")
    check(item["title"] == "Decide the pricing", "title stored")
    check(item["alive"] is None, "no alive command")
    check(item["expires"] is not None, "unverifiable item gets an expiry")
    gap = store.epoch(item["expires"]) - store.now()
    check(23 * 3600 < gap <= 24 * 3600, f"expiry is ~24h away (got {gap:.0f}s)")
    check(item["cwd"] == os.path.expanduser("~"), "cwd defaults to home")
    check(item["source"] == "unknown", "source defaults to unknown")


def test_upsert_with_a_check_has_no_expiry():
    import store
    fresh()
    with store.lock():
        item = store.upsert("k", title="Approve PR", alive="true")
    check(item["expires"] is None, "a checked item never expires on a clock")
    check(item["alive"] == "true", "alive command stored")


def test_upsert_is_idempotent_and_updates():
    import store
    fresh()
    with store.lock():
        first = store.upsert("k", title="Old", alive="true")
    with store.lock():
        second = store.upsert("k", title="New", alive="false", project="Derive")
    check(second["filed"] == first["filed"], "filed is preserved across refiles")
    check(second["title"] == "New", "title is updated")
    check(second["project"] == "Derive", "project is updated")
    names = sorted(os.listdir(store.open_dir()))
    check(names == ["k.json"], f"exactly one item file (got {names})")


def test_refile_clears_a_fallback_expiry_and_a_snooze():
    import store
    fresh()
    with store.lock():
        store.upsert("k", title="T", alive="true")
        item = store.read_item("k")
        item["expires"] = store.iso(store.now() + 60)
        item["snoozed_until"] = store.iso(store.now() + 60)
        item["check_errors"] = 3
        item["last_error"] = "exit 127"
        store.write_item(item)
    with store.lock():
        after = store.upsert("k", title="T", alive="true")
    check(after["expires"] is None, "refile clears a fallback expiry")
    check(after["snoozed_until"] is None, "refile clears a snooze")
    check(after["check_errors"] == 0, "refile resets the error counter")
    check(after["last_error"] is None, "refile clears the last error")


def test_list_open_sorts_by_filed():
    import store
    fresh()
    with store.lock():
        store.upsert("b", title="B", alive="true")
        older = store.read_item("b")
        older["filed"] = store.iso(store.now() - 900)
        store.write_item(older)
        store.upsert("a", title="A", alive="true")
    keys = [i["key"] for i in store.list_open()]
    check(keys == ["b", "a"], f"oldest filed first (got {keys})")


def test_source_falls_back_to_the_env():
    import store
    fresh()
    os.environ["ATTN_SOURCE"] = "mewt-audit"
    try:
        with store.lock():
            item = store.upsert("k", title="T", alive="true")
        check(item["source"] == "mewt-audit", "source read from ATTN_SOURCE")
    finally:
        del os.environ["ATTN_SOURCE"]


def test_close_moves_the_item_to_the_log():
    import store
    fresh()
    with store.lock():
        store.upsert("k", title="T", alive="true")
        closed = store.close_item("k", "resolved")
    check(closed is True, "close_item reports success")
    check(store.read_item("k") is None, "the open file is gone")
    with open(store.closed_path(), encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    check(len(lines) == 1, "one line appended to closed.jsonl")
    check(lines[0]["reason"] == "resolved", "the reason is recorded")
    check(lines[0]["key"] == "k", "the whole item is recorded")


def test_close_of_an_unknown_key_reports_false():
    import store
    fresh()
    with store.lock():
        check(store.close_item("nope", "resolved") is False,
              "closing an unknown key returns False")


def test_close_item_reports_failure_when_unlink_fails():
    """A close_item that cannot unlink must not claim success, and must not
    leave a duplicate closed.jsonl record behind when the caller retries."""
    import store
    fresh()
    with store.lock():
        store.upsert("k", title="T", alive="true")

    orig_remove = store.os.remove
    store.os.remove = lambda path: (_ for _ in ()).throw(OSError("read-only"))
    try:
        with store.lock():
            result = store.close_item("k", "resolved")
    finally:
        store.os.remove = orig_remove
    check(result is False, "close_item reports failure when unlink fails")
    check(store.read_item("k") is not None, "the item stays open")
    check(not os.path.exists(store.closed_path()),
          "nothing is written to closed.jsonl on a failed removal")

    with store.lock():
        retried = store.close_item("k", "resolved")
    check(retried is True, "a retry after the transient failure succeeds")
    with open(store.closed_path(), encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    check(len(lines) == 1,
          f"exactly one closed record, no duplicate (got {len(lines)})")


def test_suppress_blocks_for_seven_days():
    import store
    fresh()
    with store.lock():
        store.suppress("k")
    until = store.suppressed_until("k")
    check(until is not None, "the key reads as suppressed")
    gap = store.epoch(until) - store.now()
    check(6.9 * 86400 < gap <= 7 * 86400, f"suppressed ~7d (got {gap:.0f}s)")
    check(store.suppressed_until("other") is None, "other keys are unaffected")


def test_an_expired_suppression_does_not_block():
    import store
    fresh()
    store.ensure_dirs()
    store.write_json(store.suppress_path("k"),
                     {"key": "k", "until": store.iso(store.now() - 60)})
    check(store.suppressed_until("k") is None, "a past expiry does not block")


def test_purge_expired_suppressions_removes_only_the_dead():
    import store
    fresh()
    store.ensure_dirs()
    store.write_json(store.suppress_path("dead"),
                     {"key": "dead", "until": store.iso(store.now() - 60)})
    store.write_json(store.suppress_path("live"),
                     {"key": "live", "until": store.iso(store.now() + 600)})
    removed = store.purge_expired_suppressions()
    names = sorted(os.listdir(store.suppress_dir()))
    check(removed == 1, f"one suppression removed (got {removed})")
    check(names == ["live.json"], f"the live one survives (got {names})")


def test_purge_skips_an_unreadable_suppression_file():
    """read_json returns None for absent, corrupt and transiently-unreadable
    files alike. Deleting on that ambiguity would destroy a live 7-day dismiss
    on nothing more than a bad read; a corrupt file must be left in place."""
    import store
    fresh()
    store.ensure_dirs()
    path = store.suppress_path("k")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not json")
    removed = store.purge_expired_suppressions()
    check(removed == 0, f"an unreadable file is not counted as removed (got {removed})")
    check(os.path.exists(path), "an unreadable file is left in place, not deleted")


def test_purge_does_not_count_a_failed_removal():
    import store
    fresh()
    store.ensure_dirs()
    store.write_json(store.suppress_path("k"),
                     {"key": "k", "until": store.iso(store.now() - 60)})
    orig_remove = store.os.remove
    store.os.remove = lambda path: (_ for _ in ()).throw(OSError("locked"))
    try:
        removed = store.purge_expired_suppressions()
    finally:
        store.os.remove = orig_remove
    check(removed == 0, f"a failed removal is not counted (got {removed})")


def test_list_open_survives_a_non_string_filed():
    """A hand-edited item can carry a non-string filed (an int epoch, say).
    The sort must coerce rather than compare str to int and raise."""
    import store
    fresh()
    store.ensure_dirs()
    store.write_json(store.open_path("k"), {"key": "k", "filed": 12345})
    keys = [i["key"] for i in store.list_open()]
    check(keys == ["k"], f"an integer filed does not raise (got {keys})")


def main():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print()
    if failures:
        print(f"FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("all attn store checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
