# attn — a list of things only Eden can do

**Date:** 2026-08-07
**Status:** approved, not implemented
**Port:** 4380 (free; 4321, 4340, 4350, 4360, 4370 and 4390 are taken)

## Purpose

Agents hit things they cannot finish. A PR needs a human approval. A schema
change needs a decision. A secret is missing. Today that fact dies with the
session that found it.

`attn` is a page at `http://devbox:4380` that holds those items, and only
those items. An item stays on the page while it is true and leaves the page
when it stops being true.

## The one hard requirement

The page must never show something that is already handled. A list that shows
handled work stops being read, and then the live items on it are lost too.

Two rules give that property, and neither one spends model tokens:

1. Every item carries a shell command that tests whether the item is still
   true. The server re-runs the command every 2 minutes.
2. An item with no such command expires 24 hours after it was last filed.

No agent reads the list to decide what to remove. A subprocess decides, from
the source of truth, on a timer.

## Not in scope

- Priority levels. Age and grouping are the only order.
- Notifications of any kind. Eden opens the URL.
- A sweeper agent that re-reads items with a model.
- Per-item TTL control. The 24-hour value is fixed.
- Any item that an agent could have finished by itself.

## Architecture

The worklog skill is the template, and `attn` copies its split:

| Part | File | Job |
|---|---|---|
| CLI | `attn.py` | write and read item files; never contacts the server |
| Server | `attn_server.py` | run the checks, serve the page, accept two actions |
| Unit | `attn.service` | systemd `--user`, tailnet bind, `Restart=always` |

The CLI never contacts the server, exactly as `worklog` does. Filing therefore
still works when the service is down, and the item appears when it comes back.

`attn_server.py` is a new file, not a third mode inside
`~/.claude/skills/html-design/server.py`. That file is 1169 lines and already
carries two modes. A checker thread, a POST handler and a different page
layout would make it a fourth job. The ~40 lines of `bind_host()` are copied
rather than imported, which is the same independence `worklog.py` documents in
its `STATES` comment.

Install: `~/.local/bin/attn` is a symlink to `~/.claude/skills/attn/attn.py`,
matching `~/.local/bin/worklog`.

## Storage

```
~/attn/
  open/<key>.json         one open item per file
  suppressed/<key>.json   dismissed keys, with an expiry
  closed.jsonl            append-only record; never served
  .lock                   one global lock file; never holds any data
```

All writes are atomic: write a temp file in the same directory, then
`os.replace`. Both the CLI and the server write items, so every
read-modify-write holds an `fcntl.flock`.

The lock is `~/attn/.lock`, a separate file that holds nothing, and never the
item file itself. `os.replace` swaps the inode, so two processes that locked
`open/<key>.json` would hold locks on two different files and block nothing.
`worklog.py` documents hitting exactly that bug. One global lock is used
rather than one per key, because contention is a handful of items every 2
minutes and a single lock cannot deadlock.

The lock is never held while a check command runs. Checks take up to 10
seconds; the lock is taken only for the microseconds around a write.

### Item schema

```json
{
  "key": "derive-pr-412",
  "title": "Approve the schema change on PR #412",
  "body": "Adds metrics_daily. Blocks the founder dashboard merge.",
  "project": "Derive",
  "url": "https://github.com/eden/derive/pull/412",
  "source": "mewt-audit",
  "alive": "gh pr view 412 --json state -q .state | grep -q OPEN",
  "cwd": "/home/eden/code/Derive",
  "filed": "2026-08-07T10:52:00Z",
  "refiled": "2026-08-07T11:20:00Z",
  "expires": null,
  "snoozed_until": null,
  "checked": "2026-08-07T11:22:00Z",
  "check_errors": 0,
  "last_error": null
}
```

`key` matches `[a-z0-9][a-z0-9._-]{0,63}` — the worklog slug rule, which
refuses `.`, `..` and any traversal by construction.

All timestamps are UTC, ISO 8601, with a trailing `Z`, as `worklog` writes
them.

Exactly one of `alive` and `expires` is set when an item is created. An item
with `alive` gains a fallback `expires` later only when its check breaks three
times running, which the check loop section describes. If a hand-edited file
has neither, the server sets `expires` to `filed + 24h` on its next sweep, so
there is no state in which an item lives forever unchecked.

## CLI

```
attn file <key> --title T [--alive CMD] [--cwd DIR] [--body B|-]
                          [--project P] [--url U] [--source S]
attn done <key>                  close it; the agent finished it after all
attn list [--json]               open items, for an agent to read
attn purge [<key>]               close one item, or every item
attn url                         print http://devbox:4380
```

`file` is idempotent on `<key>`. A second call on an existing key updates
`title`, `body`, `url`, `alive` and `cwd`, sets `refiled`, resets
`check_errors` to 0, and clears `snoozed_until`. It then sets `expires` to
`now + 24h` when there is no `alive`, and to `null` when there is one — so a
refile also clears a fallback expiry left by a broken check. It never creates
a duplicate. A loop can therefore call `attn file` on every cycle without
thinking.

`attn list` prints one line per open item as `key<TAB>title`, sorted by
`filed`. `--json` prints the full item array instead.

`--cwd` defaults to `$HOME`. `--source` defaults to `$ATTN_SOURCE` when set,
otherwise `unknown`. A loop exports `ATTN_SOURCE` once and every item it files
is labelled. A session id would be correct and useless, because no name on the
page would mean anything.

`--body` is plain text and is HTML-escaped when rendered. Items are short;
`worklog` is where HTML fragments belong.

Filing a suppressed key does not create an item. The CLI appends a
`suppressed` line to `closed.jsonl`, prints one line to stderr naming the
suppression expiry, and exits 0. Exit 0 is deliberate: a loop must not fail
because Eden dismissed something.

Exit codes: `0` ok · `2` unknown key · `4` bad input.

## The check loop

A daemon thread sweeps every 120 seconds, measured from the end of the
previous sweep. Items are checked through a `ThreadPoolExecutor` of 4, so
twenty 10-second checks take one sweep, not twenty.

Each command runs as `/bin/sh -c <alive>` in `cwd`, with a 10-second timeout,
in its own process group. On timeout the whole group is killed.

The exit code decides:

| Exit | Meaning | Action |
|---|---|---|
| 0 | still true | keep; `check_errors = 0`; clear any fallback `expires` |
| 1 | resolved | close with reason `resolved` |
| anything else, or timeout | the check is broken | keep; `check_errors += 1` |

The split between exit 1 and everything else is the important part. A `grep
-q` that finds nothing exits 1, which means the item is genuinely done. A `gh`
that lost its auth exits 127, and a missing binary exits 127 as well. Treating
those as "resolved" would silently empty the page, which is a worse failure
than showing something stale.

At `check_errors >= 3` the item sets `expires = now + 24h` and the page shows
"check failing". Checking continues, so a check that recovers clears the
counter and the fallback expiry. Neither broken-forever nor stale-forever is
reachable.

A check must not close an item that changed while the command ran. The command
runs outside the lock, because it takes up to 10 seconds. When it returns, the
sweep takes the lock, re-reads the item, and compares `refiled`. A changed
`refiled` means a loop refiled the item mid-check, so the result is discarded
and the item stays. The refile always wins.

Snoozed items are still checked. A snoozed item that resolves is removed
rather than reappearing tomorrow.

An item whose `expires` has passed is closed with reason `expired`.

Every close appends one line to `closed.jsonl` — the whole item, plus
`closed` and `reason`.

**Maximum staleness is one sweep: 120 seconds.**

## The page

`GET /` renders every open item that is not snoozed.

- Grouped by `project`; items with none fall under `unfiled`.
- Groups are ordered by name; items inside a group are oldest `filed` first.
- Each row shows: title (a link when `url` is set), body, `source`, age, and
  check state — "verified 40s ago", "check failing (3x)", or "expires in 18h".
- Age counts from `filed`, never from `refiled`. A loop that refiles every
  five minutes must not make a two-day-old item look new.
- Empty is the expected state and is styled as success, not as an error.

`GET /digest` returns a short hash over the sorted list of
`(key, title, snoozed_until, check_errors)` for every open item. A 20-line
inline script polls it every 15 seconds and calls `location.reload()` when the
value changes. No external dependency, and no reload while nothing has
changed. `checked` is deliberately outside the hash, or every sweep would
reload the page.

`GET /state.json` returns the open items, for debugging.

`POST /action` takes a form body of `key` and `action`:

- `dismiss` — close with reason `dismissed`, and write
  `~/attn/suppressed/<key>.json` with `until = now + 7d`.
- `snooze` — set `snoozed_until = now + 24h`.

The response is `303` back to `/`. Plain forms, so the page needs no
JavaScript to work.

Dismiss must suppress, because the loop that filed the item will file it again
within minutes. Without suppression the item cannot be cleared. Suppression
files older than their `until` are deleted at the start of each sweep.

## Server

Bind exactly as `worklog` does: `tailscale ip -4`, never `0.0.0.0`, fall back
to loopback only when overridden. `attn.service` copies worklog's
`ExecStartPre` loop, which refuses to start until `tailscale ip -4` answers.
That guard exists because binding loopback reports `active` while being
invisible from Eden's laptop.

`Environment=PATH` must include `/usr/bin` (for `gh` at `/usr/bin/gh`),
`%h/.local/bin`, and the fnm node bin directory, because item checks inherit
the service environment. A check that works in Eden's shell and fails under
systemd is the most likely early bug, and `check_errors` plus `last_error` on
the page is how it will be found.

## Risk

The server runs agent-authored shell as Eden, every 2 minutes, indefinitely.

Agents already have `Bash`, so this grants no new capability. It grants
persistence: a command filed once keeps running after the session that wrote
it is gone, and nothing in the loop asks again whether it should.

Accepted, with three limits: the 10-second timeout, `attn purge` to drop
everything at once, and `last_error` shown on the page so a misbehaving check
is visible rather than silent.

## Adoption

Nothing files anything today, and the list is worth exactly as much as the
loops that call it. Three writes make it real:

1. `SKILL.md` in this directory, so any session can find it.
2. One line in `~/CLAUDE.md` under the server table, naming port 4380.
3. One line in the automation-loop docs telling long-running loops to file
   instead of writing "needs Eden" into a report nobody opens.

## Tests

`test_cli.py`

- key validation, including `..` and `../escape`
- `file` creates; a second `file` updates and does not duplicate
- `file` on a suppressed key writes no item and exits 0
- `done`, `purge`, `purge <key>`
- unknown key exits 2, bad input exits 4
- an interrupted write leaves no partial file

`test_server.py`

- exit 0 keeps, exit 1 closes, exit 127 increments `check_errors`
- a timeout increments `check_errors` and kills the process group
- three errors set a 24h `expires`; a later exit 0 clears it
- an `expires` in the past closes the item with reason `expired`
- a snoozed item is hidden from `/` but still checked
- `dismiss` writes a suppression file with a 7-day expiry
- an expired suppression file is deleted on the next sweep
- an item with neither `alive` nor `expires` gains one on the first sweep
- `/digest` changes when the open set changes, and not otherwise
- bind never returns `0.0.0.0`

## Cost

Filing is one CLI call inside work a loop was already doing — roughly 50
tokens, estimated. Checking, closing and serving spend no model tokens at all.
Reading the page costs Eden nothing.
