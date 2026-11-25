#!/usr/bin/env python3
"""Behavioral tests for the attn check loop.

Run: python3 test_checker.py
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
    root = tempfile.mkdtemp(prefix="attn-checker-test-")
    os.environ["ATTN_DIR"] = root
    return root


def test_exit_0_is_alive():
    import checker
    verdict, detail = checker.run_check("exit 0", None)
    check(verdict == "alive", f"exit 0 is alive (got {verdict})")


def test_exit_1_is_resolved():
    import checker
    verdict, detail = checker.run_check("exit 1", None)
    check(verdict == "resolved", f"exit 1 is resolved (got {verdict})")


def test_exit_127_is_an_error_not_resolved():
    import checker
    verdict, detail = checker.run_check("no-such-binary-anywhere", None)
    check(verdict == "error", f"127 is an error (got {verdict})")
    check("127" in detail, f"the detail names the code (got {detail!r})")


def test_a_timeout_is_an_error_and_kills_the_group():
    import checker
    start = time.time()
    verdict, detail = checker.run_check("sleep 30", None, timeout=1)
    elapsed = time.time() - start
    check(verdict == "error", f"a timeout is an error (got {verdict})")
    check("timeout" in detail, f"the detail says timeout (got {detail!r})")
    check(elapsed < 5, f"it returns promptly (took {elapsed:.1f}s)")


def test_a_missing_cwd_is_an_error():
    import checker
    verdict, detail = checker.run_check("true", "/no/such/directory")
    check(verdict == "error", f"a bad cwd is an error (got {verdict})")


def file_item(key, **kwargs):
    import store
    kwargs.setdefault("title", key)
    with store.lock():
        return store.upsert(key, **kwargs)


def test_sweep_keeps_a_live_item():
    import checker, store
    fresh()
    file_item("k", alive="exit 0")
    checker.sweep()
    item = store.read_item("k")
    check(item is not None, "a live item stays")
    check(item["checked"] is not None, "checked is stamped")
    check(item["check_errors"] == 0, "no errors counted")


def test_sweep_closes_a_resolved_item():
    import checker, store
    fresh()
    file_item("k", alive="exit 1")
    checker.sweep()
    check(store.read_item("k") is None, "a resolved item is removed")
    with open(store.closed_path(), encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    check(lines[-1]["reason"] == "resolved", "closed with reason resolved")


def test_three_broken_checks_set_a_fallback_expiry():
    import checker, store
    fresh()
    file_item("k", alive="no-such-binary-anywhere")
    for expected in (1, 2, 3):
        checker.sweep()
        item = store.read_item("k")
        check(item is not None, f"the item survives error {expected}")
        check(item["check_errors"] == expected,
              f"error count is {expected} (got {item['check_errors']})")
    check(item["expires"] is not None, "a third failure sets a 24h expiry")
    check(item["last_error"] and "127" in item["last_error"],
          f"last_error is recorded (got {item.get('last_error')!r})")


def test_a_recovered_check_clears_the_counter_and_the_expiry():
    import checker, store
    fresh()
    file_item("k", alive="no-such-binary-anywhere")
    for _ in range(3):
        checker.sweep()
    check(store.read_item("k")["expires"] is not None, "expiry was set")
    with store.lock():
        item = store.read_item("k")
        item["alive"] = "exit 0"
        store.write_item(item)
    checker.sweep()
    item = store.read_item("k")
    check(item["check_errors"] == 0, "the counter resets")
    check(item["expires"] is None, "the fallback expiry clears")
    check(item["last_error"] is None, "last_error clears")


def test_sweep_closes_an_expired_item():
    import store, checker
    fresh()
    file_item("k", title="Decide")           # no alive: gets a 24h expiry
    with store.lock():
        item = store.read_item("k")
        item["expires"] = store.iso(store.now() - 1)
        store.write_item(item)
    checker.sweep()
    check(store.read_item("k") is None, "an expired item is removed")
    with open(store.closed_path(), encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    check(lines[-1]["reason"] == "expired", "closed with reason expired")


def test_an_item_with_neither_check_nor_expiry_gains_one():
    import store, checker
    fresh()
    file_item("k", title="Hand edited")
    with store.lock():
        item = store.read_item("k")
        item["expires"] = None
        item["alive"] = None
        store.write_item(item)
    checker.sweep()
    item = store.read_item("k")
    check(item is not None, "the item survives one sweep")
    check(item["expires"] is not None, "the sweep gives it an expiry")


def test_a_refile_during_a_check_wins():
    """apply_result must discard a verdict computed against an older refile."""
    import store, checker
    fresh()
    file_item("k", alive="exit 0")
    stale_refiled = store.read_item("k")["refiled"]
    time.sleep(1.1)                     # the stamp has one-second resolution
    file_item("k", alive="exit 0")      # refile: a new `refiled` stamp
    outcome = checker.apply_result("k", "resolved", "", stale_refiled)
    check(outcome == "refiled", f"the stale verdict is discarded (got {outcome})")
    check(store.read_item("k") is not None, "the refiled item survives")


def test_sweep_purges_expired_suppressions():
    import store, checker
    fresh()
    store.ensure_dirs()
    store.write_json(store.suppress_path("dead"),
                     {"key": "dead", "until": store.iso(store.now() - 60)})
    checker.sweep()
    check(os.listdir(store.suppress_dir()) == [],
          "the sweep clears expired suppressions")


def test_a_snoozed_item_is_still_checked():
    import store, checker
    fresh()
    file_item("k", alive="exit 1")
    with store.lock():
        item = store.read_item("k")
        item["snoozed_until"] = store.iso(store.now() + 3600)
        store.write_item(item)
    checker.sweep()
    check(store.read_item("k") is None,
          "a snoozed item that resolves is removed, not deferred")


def test_expiry_close_re_reads_before_it_closes():
    """A refile during the sweep must beat a stale "expired" verdict.

    _close_if_expired blocks on store.lock() exactly while a writer holds it,
    so its snapshot is very often out of date by the time it can act. Measured
    without the re-read: 644 of 6000 closes destroyed live items over 30
    sweeps, worst case 171 of 200 in one sweep.
    """
    import checker
    import store
    fresh()
    store.upsert("k", title="original")
    item = store.read_item("k")
    item["expires"] = store.iso(store.now() - 60)
    store.write_item(item)
    stale = store.read_item("k")          # what the sweep would carry
    time.sleep(1.1)                       # force a different refile stamp
    store.upsert("k", title="refiled and live", alive="true")

    check(checker._close_if_expired(stale) is False,
          "a stale expired snapshot does not close a refiled item")
    survivor = store.read_item("k")
    check(survivor is not None, "the refiled item is still open")
    check(survivor is None or survivor["title"] == "refiled and live",
          "and it kept the refiled title")


def test_a_genuinely_expired_item_still_closes():
    import checker
    import store
    fresh()
    store.upsert("k", title="really expired")
    item = store.read_item("k")
    item["expires"] = store.iso(store.now() - 60)
    store.write_item(item)
    check(checker._close_if_expired(store.read_item("k")) is True,
          "an expired item with no refile still closes")
    check(store.read_item("k") is None, "and leaves open/")


def test_a_chatty_check_does_not_buffer_its_whole_stderr():
    """Measured with communicate(): 2712 MB RSS at 1s, 5000 MB at 4s."""
    import resource
    import checker
    fresh()
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    verdict, detail = checker.run_check("yes hello >&2", None, timeout=3)
    grew = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024) - before
    check(grew < 100, f"a 3s `yes >&2` grew peak RSS by {grew} MB, not GBs")
    check(verdict == "error", f"and times out as an error (got {verdict})")


def test_short_stderr_still_reaches_last_error():
    import checker
    fresh()
    verdict, detail = checker.run_check("echo boom >&2; exit 3", None)
    check(verdict == "error" and "boom" in detail,
          f"a normal failure still reports its stderr (got {detail!r})")


def test_one_malformed_item_does_not_stop_the_sweep():
    """A hand-edited file with a list `alive` used to kill every later sweep."""
    import checker
    import store
    fresh()
    store.upsert("good", title="good", alive="exit 1")
    store.upsert("bad", title="hand edited", alive="exit 1")
    bad = store.read_item("bad")
    bad["alive"] = ["gh", "pr", "view"]
    store.write_item(bad)

    raised = None
    try:
        checker.sweep()
    except Exception as exc:                      # noqa: BLE001
        raised = exc
    check(raised is None, f"sweep survives a malformed item (raised {raised!r})")
    check(store.read_item("good") is None,
          "and the healthy item beside it still resolved")


def test_a_blank_alive_is_not_a_check():
    """`"   "` runs through /bin/sh, exits 0, and would never expire."""
    import checker
    import store
    fresh()
    store.upsert("k", title="blank", alive="   ")
    checker.sweep()
    item = store.read_item("k")
    check(item is not None and item.get("expires") is not None,
          "a whitespace-only alive gets a 24h expiry instead of living forever")


def main():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print()
    if failures:
        print(f"FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("all attn checker checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
