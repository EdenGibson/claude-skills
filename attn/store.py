#!/usr/bin/env python3
"""Shared storage for attn: paths, locking, atomic writes, the item schema.

Both attn.py (the CLI) and attn_server.py (the checker and the page) import
this module, so the item schema is defined exactly once.

Every path helper reads ATTN_DIR on each call rather than caching it at import
time. Tests set the variable and call in-process; caching would pin the first
value and make them share state.
"""
import calendar
import contextlib
import fcntl
import json
import os
import re
import tempfile
import time

KEY_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")

TTL_SECONDS = 24 * 3600
SNOOZE_SECONDS = 24 * 3600
SUPPRESS_SECONDS = 7 * 24 * 3600
MAX_CHECK_ERRORS = 3


def root():
    return os.path.abspath(os.path.expanduser(
        os.environ.get("ATTN_DIR", "~/attn")))


def base_url():
    return os.environ.get("ATTN_URL", "http://devbox:4380").rstrip("/")


def open_dir():
    return os.path.join(root(), "open")


def suppress_dir():
    return os.path.join(root(), "suppressed")


def closed_path():
    return os.path.join(root(), "closed.jsonl")


def lock_path():
    """A separate file that holds nothing.

    Never lock an item file. write_json swaps the inode with os.replace, so two
    processes that locked open/<key>.json would hold locks on two different
    files and block nothing at all. worklog.py documents hitting exactly this.
    """
    return os.path.join(root(), ".lock")


def open_path(key):
    return os.path.join(open_dir(), f"{key}.json")


def suppress_path(key):
    return os.path.join(suppress_dir(), f"{key}.json")


def ensure_dirs():
    os.makedirs(open_dir(), exist_ok=True)
    os.makedirs(suppress_dir(), exist_ok=True)


def valid_key(key):
    """Lowercase, bounded. Refuses '.', '..' and traversal by construction,
    because the pattern demands [a-z0-9] first and allows no '/'."""
    return bool(key) and bool(KEY_RE.match(key))


def now():
    return time.time()


def iso(epoch_seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))


def now_iso():
    return iso(now())


def epoch(iso_str):
    """Parse an ISO stamp back to epoch seconds. None on anything unparseable.

    calendar.timegm, not time.mktime: the stamps are UTC and mktime reads local
    time, which would shift every comparison by the box's offset.
    """
    if not iso_str:
        return None
    try:
        return calendar.timegm(time.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return None


@contextlib.contextmanager
def lock():
    """Serialise one read-modify-write across the CLI and the server.

    Never held while a check command runs. Checks take up to 10 seconds; this
    is taken only for the microseconds around a write.

    Not reentrant: a second `with lock():` in the same process, nested inside
    the first, blocks on itself forever. Every function below that documents
    "the caller must hold lock()" or "takes the lock itself" exists so a
    caller never has to guess which one applies.
    """
    fd = None
    try:
        ensure_dirs()
        fd = os.open(lock_path(), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError:
        # A vanished or read-only root. Running unlocked is bad; a traceback is
        # worse, because the CLI's exit codes are documented and callers read
        # them.
        if fd is not None:
            os.close(fd)
            fd = None
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)  # closing the descriptor releases the flock


def write_json(path, obj):
    """Write atomically, so a reader never sees a half-written file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_item(key):
    return read_json(open_path(key))


def write_item(item):
    write_json(open_path(item["key"]), item)


def list_open():
    """Every open item, oldest filed first. Unreadable files are skipped."""
    ensure_dirs()
    items = []
    try:
        names = os.listdir(open_dir())
    except OSError:
        return []
    for name in names:
        if name.startswith(".") or not name.endswith(".json"):
            continue
        item = read_json(os.path.join(open_dir(), name))
        if item and item.get("key"):
            items.append(item)
    # str(): a hand-edited file can carry a non-string filed (an int epoch,
    # say). Comparing that against another item's ISO string would raise
    # TypeError and take the whole sweep and page down with it.
    items.sort(key=lambda i: (str(i.get("filed") or ""), i["key"]))
    return items


def default_source():
    return os.environ.get("ATTN_SOURCE") or "unknown"


def upsert(key, title, body=None, project=None, url=None, source=None,
           alive=None, cwd=None):
    """Create or replace one item's fields. The caller must hold lock().

    Idempotent on `key`: a loop calls this every cycle and gets one item, with
    `filed` preserved so the page can show a true age. Every other field is
    replaced wholesale, not merged: a refile that omits --alive erases a
    previously stored check command rather than leaving it in place.
    """
    stamp = now_iso()
    item = read_item(key)
    if item is None:
        item = {"key": key, "filed": stamp, "checked": None}
    item.update({
        "title": title,
        "body": body,
        "project": project,
        "url": url,
        "source": source or default_source(),
        "alive": alive,
        "cwd": cwd or os.path.expanduser("~"),
        "refiled": stamp,
        "check_errors": 0,
        "last_error": None,
        "snoozed_until": None,
    })
    # A checked item is judged by its command, never by a clock. Setting this
    # to None on every refile also clears a fallback expiry that a broken check
    # left behind.
    item["expires"] = None if alive else iso(now() + TTL_SECONDS)
    item.setdefault("checked", None)
    write_item(item)
    return item


def append_closed(record):
    """Append one line to closed.jsonl. A record, never served to the page."""
    ensure_dirs()
    with open(closed_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def close_item(key, reason):
    """Remove the item from open/ and record it. The caller must hold lock().

    Removes before logging, not after: a failed unlink (a read-only open/,
    say) then returns False with nothing written to closed.jsonl, so a caller
    that retries never produces a second, duplicate record for one close.
    """
    item = read_item(key)
    if item is None:
        return False
    try:
        os.remove(open_path(key))
    except OSError:
        return False
    item["closed"] = now_iso()
    item["reason"] = reason
    append_closed(item)
    return True


def suppress(key):
    """Block refiles of this key. The caller must hold lock().

    Dismiss without suppression cannot work: the loop that filed the item files
    it again within minutes, and the item is unclearable.
    """
    write_json(suppress_path(key),
               {"key": key, "until": iso(now() + SUPPRESS_SECONDS)})


def suppressed_until(key):
    """The ISO expiry while the key is suppressed, else None."""
    record = read_json(suppress_path(key))
    if not record:
        return None
    until = epoch(record.get("until"))
    if until is None or until <= now():
        return None
    return record["until"]


def purge_expired_suppressions():
    """Delete suppression files that have expired. Returns how many went.

    Takes the lock itself — never call this from inside a `with lock():`
    block; lock() is not reentrant and the nested acquisition would block
    forever. Holding the lock for the whole read-decide-delete pass is the
    fix for a real race: unlocked, a `suppress()` landing between this
    function's read and its os.remove() got its fresh file deleted, silently
    undoing a concurrent dismiss.

    suppress() does NOT take the lock; its own docstring says the caller must
    hold it. The two serialise through that caller's lock, not through one
    inside suppress(). An earlier version of this sentence named the wrong
    mechanism, which would mislead anyone adding a third writer.
    """
    ensure_dirs()
    removed = 0
    with lock():
        try:
            names = os.listdir(suppress_dir())
        except OSError:
            return 0
        for name in names:
            if name.startswith(".") or not name.endswith(".json"):
                continue
            path = os.path.join(suppress_dir(), name)
            record = read_json(path)
            if record is None:
                # Absent, corrupt, or a transient read error read the same
                # way. Deleting on that ambiguity would destroy a live 7-day
                # dismiss on nothing more than bad luck; skip it instead and
                # let the next sweep re-read it.
                continue
            until = epoch(record.get("until"))
            if until is None or until <= now():
                try:
                    os.remove(path)
                except OSError:
                    continue  # a failed removal is not a removal
                removed += 1
    return removed
