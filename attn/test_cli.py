#!/usr/bin/env python3
"""Behavioral tests for the attn CLI.

Run: python3 test_cli.py
Exits 0 on success, non-zero (with a FAIL line) otherwise.
Every run points ATTN_DIR at a temp folder, so no test touches the real ~/attn.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, "attn.py")

failures = []


def check(cond, msg):
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        failures.append(msg)


def run(root, *args, stdin=None):
    env = dict(os.environ, ATTN_DIR=root, ATTN_URL="http://devbox:4380")
    env.pop("ATTN_SOURCE", None)
    proc = subprocess.run([sys.executable, CLI, *args], capture_output=True,
                          text=True, env=env, input=stdin)
    return proc.returncode, proc.stdout, proc.stderr


def fresh():
    return tempfile.mkdtemp(prefix="attn-cli-test-")


def item(root, key):
    with open(os.path.join(root, "open", f"{key}.json"), encoding="utf-8") as f:
        return json.load(f)


def test_file_creates_an_item():
    root = fresh()
    rc, out, err = run(root, "file", "pr-412", "--title", "Approve PR 412",
                       "--alive", "true", "--project", "Derive")
    check(rc == 0, f"exit 0 (got {rc}, stderr={err.strip()!r})")
    got = item(root, "pr-412")
    check(got["title"] == "Approve PR 412", "title stored")
    check(got["alive"] == "true", "alive stored")
    check(got["project"] == "Derive", "project stored")


def test_file_is_idempotent():
    root = fresh()
    run(root, "file", "k", "--title", "One", "--alive", "true")
    run(root, "file", "k", "--title", "Two", "--alive", "true")
    names = sorted(os.listdir(os.path.join(root, "open")))
    check(names == ["k.json"], f"one file only (got {names})")
    check(item(root, "k")["title"] == "Two", "the second call wins")


def test_file_rejects_a_bad_key():
    root = fresh()
    for bad in ("../escape", "Derive", "a b"):
        rc, _, _ = run(root, "file", bad, "--title", "T", "--alive", "true")
        check(rc == 4, f"{bad!r} exits 4 (got {rc})")


def test_file_requires_a_title():
    root = fresh()
    rc, _, _ = run(root, "file", "k", "--alive", "true")
    check(rc == 4, f"a missing title exits 4 (got {rc})")


def test_body_from_stdin():
    root = fresh()
    rc, _, _ = run(root, "file", "k", "--title", "T", "--alive", "true",
                   "--body", "-", stdin="line one\nline two\n")
    check(rc == 0, f"exit 0 (got {rc})")
    check(item(root, "k")["body"] == "line one\nline two", "stdin body stored")


def test_done_closes_and_unknown_key_exits_2():
    root = fresh()
    run(root, "file", "k", "--title", "T", "--alive", "true")
    rc, _, _ = run(root, "done", "k")
    check(rc == 0, f"done exits 0 (got {rc})")
    check(not os.path.exists(os.path.join(root, "open", "k.json")),
          "the open file is gone")
    rc, _, _ = run(root, "done", "k")
    check(rc == 2, f"a second done exits 2 (got {rc})")


def test_file_on_a_suppressed_key_writes_nothing_and_exits_0():
    root = fresh()
    os.makedirs(os.path.join(root, "suppressed"), exist_ok=True)
    import time
    until = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                          time.gmtime(time.time() + 86400))
    with open(os.path.join(root, "suppressed", "k.json"), "w",
              encoding="utf-8") as f:
        json.dump({"key": "k", "until": until}, f)
    rc, _, err = run(root, "file", "k", "--title", "T", "--alive", "true")
    check(rc == 0, f"a suppressed file exits 0 (got {rc})")
    check(not os.path.exists(os.path.join(root, "open", "k.json")),
          "no item is created")
    check("suppressed" in err.lower(), f"stderr says why (got {err.strip()!r})")
    with open(os.path.join(root, "closed.jsonl"), encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    check(lines[-1]["reason"] == "suppressed", "the attempt is recorded")


def test_list_plain_and_json():
    root = fresh()
    run(root, "file", "b", "--title", "Bee", "--alive", "true")
    run(root, "file", "a", "--title", "Ay", "--alive", "true")
    rc, out, _ = run(root, "list")
    check(rc == 0, f"list exits 0 (got {rc})")
    check("b\tBee" in out, f"plain output is key<TAB>title (got {out!r})")
    rc, out, _ = run(root, "list", "--json")
    parsed = json.loads(out)
    check(len(parsed) == 2, f"json lists both (got {len(parsed)})")


def test_purge_all_and_one():
    root = fresh()
    run(root, "file", "a", "--title", "A", "--alive", "true")
    run(root, "file", "b", "--title", "B", "--alive", "true")
    rc, _, _ = run(root, "purge", "a")
    check(rc == 0, f"purge one exits 0 (got {rc})")
    check(os.path.exists(os.path.join(root, "open", "b.json")), "b survives")
    rc, _, _ = run(root, "purge")
    check(rc == 0, f"purge all exits 0 (got {rc})")
    check(os.listdir(os.path.join(root, "open")) == [], "open/ is empty")


def test_url():
    root = fresh()
    rc, out, _ = run(root, "url")
    check(rc == 0 and out.strip() == "http://devbox:4380",
          f"url prints the base (got {out.strip()!r})")


def main():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print()
    if failures:
        print(f"FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("all attn CLI checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
