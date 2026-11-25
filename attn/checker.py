#!/usr/bin/env python3
"""The attn check loop: decide whether each item is still true.

The exit code decides, and the split between 1 and everything else is the
whole design:

    0                       still true    keep the item
    1                       resolved      close the item
    anything else, timeout  broken check  keep it and count the failure

A `grep -q` that finds nothing exits 1, which means the item is genuinely
done. A `gh` that lost its auth exits 127, and so does a missing binary.
Treating those as resolved would silently empty the page, which is a worse
failure than showing something stale.
"""
import collections
import concurrent.futures
import contextlib
import os
import select
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402

CHECK_TIMEOUT = 10
SWEEP_SECONDS = 120
POOL_SIZE = 4

_STDERR_CHUNK = 4096
_STDERR_CHUNKS = 2      # at most 8 KB of a check's stderr is ever held


def _drain(stream, sink, deadline):
    """Read a stream until it ends or the deadline passes.

    The deque bounds memory: older chunks fall out as new ones arrive, so a
    check that writes without limit costs 8 KB rather than its whole output.

    The deadline bounds the thread. A grandchild that called setsid survives
    the group kill and holds the write end open, so a plain blocking read
    would never return. Measured with no deadline: 10 such timeouts leaked 10
    threads and 10 descriptors, freed only when the grandchild finally died.

    The thread owns the stream and closes it here. Never close it from the
    caller — close() blocks on the same lock a blocked read() holds, and the
    two deadlock. Measured: the whole run hung past 300s.
    """
    fd = stream.fileno()
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            ready, _, _ = select.select([fd], [], [], min(remaining, 0.5))
            if not ready:
                continue
            chunk = os.read(fd, _STDERR_CHUNK)
            if not chunk:
                return
            sink.append(chunk)
    except (OSError, ValueError):
        return
    finally:
        with contextlib.suppress(Exception):
            stream.close()


def _alive_cmd(item):
    """The item's check command, or None when it has nothing runnable.

    A whitespace-only string is not a check. /bin/sh runs it, exits 0, and the
    item stays "alive" forever with no expiry. A non-string reaches here only
    from a hand-edited file, and Popen raises TypeError on one.
    """
    alive = item.get("alive")
    if not isinstance(alive, str) or not alive.strip():
        return None
    return alive


def run_check(alive, cwd, timeout=CHECK_TIMEOUT):
    """Run one alive command. Returns (verdict, detail).

    verdict is "alive", "resolved" or "error". The command runs in its own
    session, so a timeout can kill the whole process group rather than leaving
    orphaned children behind.
    """
    if not isinstance(alive, str):
        return "error", f"alive is {type(alive).__name__}, not a string"

    try:
        proc = subprocess.Popen(
            ["/bin/sh", "-c", alive],
            cwd=cwd or os.path.expanduser("~"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        return "error", f"could not start: {exc}"

    # Drain stderr in a thread that keeps only the last few chunks.
    # communicate() buffers the whole stream, and only the last 200 characters
    # are ever shown. Measured with `yes >&2` and no cap: 2712 MB RSS after
    # 1s, 5000 MB after 4s, then the kernel killed the process. One chatty
    # check would take down the server that serves the page.
    tail = collections.deque(maxlen=_STDERR_CHUNKS)
    reader = threading.Thread(
        target=_drain,
        args=(proc.stderr, tail, time.monotonic() + timeout + 2),
        daemon=True,
    )
    reader.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError, ProcessLookupError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        # Wait on the process, never on the pipe. A grandchild that called
        # setsid survives the group kill and holds stderr open. Reading the
        # pipe here cost 7.04s against a 2s timeout, measured.
        with contextlib.suppress(Exception):
            proc.wait(timeout=2)
        # The drain thread stops itself at its own deadline and closes the
        # stream. Do not close it here; see _drain for the deadlock.
        return "error", f"timeout after {timeout}s"

    reader.join(timeout=1)
    err = b"".join(tail).decode("utf-8", "replace")
    code = proc.returncode
    if code == 0:
        return "alive", ""
    if code == 1:
        return "resolved", ""
    lines = (err or "").strip().splitlines()
    tail = lines[-1][:200] if lines else "no stderr"
    return "error", f"exit {code}: {tail}"


def apply_result(key, verdict, detail, refiled_at):
    """Write one check result back. Returns what happened, for the log.

    The command ran outside the lock, because it takes up to 10 seconds. A loop
    can refile the item during that window, so the item is re-read here and
    `refiled` compared. A changed stamp means the verdict describes an older
    version of the item, and the refile wins.
    """
    with store.lock():
        item = store.read_item(key)
        if item is None:
            return "gone"
        if item.get("refiled") != refiled_at:
            return "refiled"

        if verdict == "resolved":
            store.close_item(key, "resolved")
            return "resolved"

        item["checked"] = store.now_iso()
        if verdict == "alive":
            item["check_errors"] = 0
            item["last_error"] = None
            if item.get("alive"):
                item["expires"] = None
            store.write_item(item)
            return "alive"

        item["check_errors"] = int(item.get("check_errors") or 0) + 1
        item["last_error"] = detail
        if (item["check_errors"] >= store.MAX_CHECK_ERRORS
                and not item.get("expires")):
            item["expires"] = store.iso(store.now() + store.TTL_SECONDS)
        store.write_item(item)
        return "error"


def _close_if_expired(item):
    """True when the item was expired and has now been closed.

    The caller passes a snapshot from list_open(). The snapshot goes stale
    while the sweep waits, because this function blocks on store.lock()
    exactly while a writer holds it. A refile very often lands in that window.
    Re-read under the lock and re-check, or a refiled item is closed as
    "expired" while carrying an expiry 24 hours in the future.

    Measured without the re-read, over 30 sweeps of 200 expired items against
    a concurrent refiler: 644 of 6000 closes destroyed live items, and 10 of
    30 sweeps lost work. The worst single sweep destroyed 171 of 200.

    Both skips are deliberately conservative. A snapshot that looks live but
    is really expired waits for the next sweep, 120s later. A missed close
    costs one sweep of staleness. A wrong close destroys the item.
    """
    expires = store.epoch(item.get("expires"))
    if expires is None or expires > store.now():
        return False
    with store.lock():
        fresh = store.read_item(item["key"])
        if fresh is None:
            return False
        fresh_expires = store.epoch(fresh.get("expires"))
        if fresh_expires is None or fresh_expires > store.now():
            return False
        return store.close_item(item["key"], "expired")


def _backfill_expiry(key):
    """Give an item with neither a check nor an expiry a 24h clock.

    Only a hand-edited file reaches this. Without it the item would live
    forever unchecked, which is the exact failure this whole tool exists to
    prevent.
    """
    with store.lock():
        item = store.read_item(key)
        if item is None or item.get("expires"):
            return
        if _alive_cmd(item) is not None:
            return
        base = store.epoch(item.get("filed")) or store.now()
        item["expires"] = store.iso(base + store.TTL_SECONDS)
        store.write_item(item)


def sweep():
    """One pass over every open item. Returns a count dict for the log."""
    store.ensure_dirs()
    counts = {"checked": 0, "resolved": 0, "expired": 0,
              "errors": 0, "refiled": 0}
    store.purge_expired_suppressions()

    # Every item is isolated. One bad item must not stop the pass, or the
    # page silently stops clearing. Measured before this guard: one item with
    # a list-valued `alive` raised out of sweep(), and 6 of 6 resolved items
    # stayed open. Every later sweep died at the same item.
    pending = []
    for item in store.list_open():
        try:
            if _close_if_expired(item):
                counts["expired"] += 1
                continue
            if _alive_cmd(item) is None:
                if not item.get("expires"):
                    _backfill_expiry(item["key"])
                continue
            pending.append(item)
        except Exception as exc:                       # noqa: BLE001
            counts["errors"] += 1
            print(f"attn: item {item.get('key')!r} failed: {exc}",
                  file=sys.stderr, flush=True)

    if not pending:
        return counts

    with concurrent.futures.ThreadPoolExecutor(max_workers=POOL_SIZE) as pool:
        futures = {
            pool.submit(run_check, _alive_cmd(item), item.get("cwd")): item
            for item in pending
        }
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try:
                verdict, detail = future.result()
                outcome = apply_result(item["key"], verdict, detail,
                                       item.get("refiled"))
            except Exception as exc:                   # noqa: BLE001
                counts["errors"] += 1
                print(f"attn: check for {item.get('key')!r} failed: {exc}",
                      file=sys.stderr, flush=True)
                continue
            counts["checked"] += 1
            if outcome in counts:
                counts[outcome] += 1
            elif outcome == "error":
                counts["errors"] += 1
    return counts


def sweep_forever(stop_event):
    """Sweep, wait, repeat. The wait starts after the sweep finishes, so a slow
    sweep never stacks up behind itself."""
    while not stop_event.is_set():
        try:
            counts = sweep()
            if any(counts[k] for k in ("resolved", "expired", "errors")):
                print(f"attn sweep: {counts}", flush=True)
        except Exception as exc:            # never let the thread die
            print(f"attn sweep failed: {exc!r}", file=sys.stderr, flush=True)
        stop_event.wait(SWEEP_SECONDS)
