---
name: attn
description: File something that only Eden can do, at http://devbox:4380. Use when work stops on a decision, an approval, a credential, or an access grant that no agent can give itself — a PR needing review, a schema change needing a call, a missing secret, a failing check nobody has triaged. Every item carries a shell command that proves it is still real, so the list removes itself. Not for progress on a long task (that is worklog, port 4370) and not for anything an agent could finish itself.
user_invocable: true
---

# attn — the list of things only Eden can do

An agent that hits a wall writes the fact into a report nobody opens, and the
fact dies with the session. `attn` is where that fact goes instead.

## The one rule

**File an item only when Eden must act himself.** Something you could finish,
retry, or work around is not an item. The list is worth reading only while
every line on it is genuinely his.

## File it with a check

```bash
attn file derive-pr-412 \
  --title "Approve the schema change on PR #412" \
  --alive 'gh pr view 412 --repo eden/derive --json state -q .state | grep -q OPEN' \
  --cwd ~/code/Derive \
  --project Derive \
  --url https://github.com/eden/derive/pull/412 \
  --source mewt-audit
```

The `--alive` command is re-run every 2 minutes:

| Exit | Meaning |
|---|---|
| 0 | still true — the item stays |
| 1 | resolved — the item is removed |
| anything else | the check is broken — the item stays and is marked |

So the item disappears by itself the moment Eden merges that PR. Nobody has to
remember to close it.

That split is why a check must never be written as `[ ... ] && exit 0 || exit
2`. Exit 1 is the only code that closes an item. Every other non-zero code
means "my check broke", and the item stays on the page marked as failing.

**Write a check that reads the source of truth**, not one that reads your own
output. Good: `gh pr view`, `test -f`, `grep -q` over a live file, a `psql -c`
that counts rows. Bad: anything testing a file you wrote yourself.

`--cwd` matters for any check that needs a repo. It defaults to `$HOME`.

### The check runs under systemd, not in your shell

Item checks inherit the service environment, not yours. Two traps, both
measured on this box:

- `node` resolves interactively through a per-shell fnm path that does not
  exist for the service. The service PATH names the stable
  `~/.local/share/fnm/node-versions/v24.15.0/installation/bin` instead.
- `pnpm` is a shell function interactively and a plain binary at
  `/usr/bin/pnpm` under the service. A check depending on the wrapper's
  behaviour will not behave the same.

A check that works in your shell and fails here shows as "check failing" on
the page with its `last_error`. That is the designed behaviour, not a bug —
but fix the check rather than leaving it.

## Filing without a check

Some items no command can test — "decide whether we ship the new pricing".
Omit `--alive` and the item expires 24 hours later.

```bash
attn file pricing-call --title "Decide whether the new pricing ships this week"
```

If a loop still cares tomorrow, it files again and the clock resets. A one-off
session's item is simply gone by the next day, which is correct: nobody is
left asserting it.

## Refile freely

`attn file` is idempotent on the key. A loop calls it on every cycle and gets
one item, with its original age preserved. Never invent a per-run key.

A refile replaces **every** field. Pass the same arguments each cycle; omitting
`--alive` on a later call erases the check and puts the item on a 24-hour
clock.

## The rest of the commands

```
attn done  <key>       you finished it after all; close it
attn list  [--json]    what is open
attn purge [<key>]     close one item, or every item
attn url               print http://devbox:4380
```

Exit codes: `0` ok · `2` unknown key · `4` bad input.

Filing a key Eden dismissed prints a line to stderr and exits 0 without
creating anything. A dismiss suppresses the key for 7 days, so your loop
cannot force it back.

## Which server

| What you have | Use | Port |
|---|---|---|
| Something only Eden can do | **attn** | 4380 |
| Progress on one long task | `worklog` | 4370 |
| HTML you are designing | `html-design` | 4321 |
| A finished artifact | `preview` | 4340 |

## Rules

- **Claim a key from the thing, not the session.** `derive-pr-412`, not
  `task1`. Lowercase, digits, `-`, `.`, `_`, 64 characters at most.
- **Set `--project`** so the page groups usefully.
- **Set `--source`** to the loop's name, or export `ATTN_SOURCE` once.
- **Do not pass a URL you did not construct.** `--url` becomes a link Eden
  clicks. Only `http://` and `https://` render as links; anything else shows
  as text. Never forward a URL lifted from a Sentry payload, an issue body or
  a PR description without reading it.
- **Never file something you could do.** That is the whole rule.

## When it breaks

```bash
systemctl --user status attn
journalctl --user -u attn.service -n 50
systemctl --user restart attn
```

A check that works in your shell but fails under systemd is the usual cause.
The page shows `last_error` for exactly this.

The CLI never contacts the server, so filing still lands on disk while the
service is down.

## Tests

```bash
cd ~/.claude/skills/attn
for t in test_store.py test_cli.py test_checker.py test_page.py; do python3 "$t"; done
```
