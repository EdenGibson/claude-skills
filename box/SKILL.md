---
name: box
description: Use when work needs a throwaway Linux VM from ascii.dev, or when driving one that already exists. Triggers include a sandbox for a build or stress test, a port exposed on an HTTPS URL, a remote desktop or browser, files copied to or from a rented box, and fork, stop, resume or delete of one. Also use before any box is created, to check the start budget first.
user_invocable: true
---

# box: drive an ascii.dev sandbox VM

Box rents a Linux VM for an hour, with root and 4 vCPU and 8GB by default.

What you can do with one:

- **Run anything.** `box exec` for a command, `box ssh` for a shell line, and
  `--detach` for a job that outlives the call.
- **Publish a port.** `box host <id> 3000` returns a stable HTTPS URL you can
  send to Eden. `box forward` brings a database port back to this devbox.
- **See a screen.** `box desktop` gives a full Linux desktop in a browser,
  `box browser` gives Chrome alone with a persistent profile.
- **Move files both ways.** `box scp`, or `box snapshot pull` for the whole disk.
- **Freeze a machine and rebuild it.** `box snapshot <id> <name>` makes a golden
  image, `box new --from <name>` starts there, `box fork` copies a live box.
- **Change your mind about size.** `box resume --type large` grows a stopped box
  without losing its disk.

Use it for a sandbox you drive yourself. Machine sizes: `small` at 2 vCPU and
4GB, `default` at 4 and 8, `large` at 8 and 16, `xlarge` at 16 and 32.

## The binary is not on your PATH

```bash
~/.ascii/bin/box list          # works
box list                       # "command not found"
```

`~/.bashrc` defines a `box()` function, and the file returns early for a
non-interactive shell. Claude's Bash tool is non-interactive, so the function
never loads. Measured 2026-09-11: `box --version` gives `command not found`,
`~/.ascii/bin/box --version` gives `0.1.228-ascii-prod1`.

That function also exports `BOX_CURRENT_ID` after `new` and `fork`. You do not
get it. Read the id out of the JSON yourself.

## Output is always JSON for you

No TTY means machine output, with no `--json` flag needed. The wrappers differ:
`box list` nests under `.boxes[]`, `box info` under `.box`. `jq` is installed.

```bash
B=~/.ascii/bin/box
$B list | jq -r '.boxes[] | "\(.id) \(.state) \(.name)"'   # verified
ID=$($B new --ttl 1800 | jq -r '.box.id // .id')           # shape unverified
```

Nobody has confirmed whether `box new` nests its result, so the `//` covers
both. Production does the same thing: `fleet-dispatch.py:1352` reads a fork
response as `(fork.get("box") or fork).get("id")`. Print the whole object once
and fix the path the first time you create a box.

## Check the start budget before you create anything

Starts are the scarce resource on this account, not credit.

```bash
~/.ascii/bin/box limits | jq -c '{day: .starts.day, active: .activeBoxes, maxActive: .maxActiveBoxes}'
# {"day":{"limit":420,"remaining":17,"used":403},"active":12,"maxActive":250}
```

`.starts.day` carries its own limit. `.activeBoxes` does not, so pair it with
`.maxActiveBoxes` or you read a count with no ceiling.

**Read the number live. Never quote one from this file.** Measured 2026-09-11:
394 used at 07:30, 403 used at 07:44. Fourteen minutes cost 9 starts. The
`plan-exec` fleet burns roughly 1.2 starts a minute through `fleet-dispatch`, so
the daily cap is the thing you will hit, hours before the credit runs low.
Monthly seconds moved 0.1% over the same window, from 9.01M of 10M remaining.

So, in order:

1. **Reuse a box you made.** `box exec` on an `idle` box costs zero starts.
2. **Resume a stopped one.** Same disk, same state.
3. **Create one** only when neither fits.

**Never touch an idle box you did not create.** Measured 2026-09-11 07:44: all
12 active boxes were `idle` and named only by a fork timestamp, such as
`Box 2026-09-11 04:29 fork`. Those belong to `fleet-dispatch`. Writing to one
corrupts a running job, and deleting one destroys work you cannot see. One
start out of the daily budget is the cheaper mistake.

`box list` defaults to `--filter r`, which already covers `provisioned`,
`cloning`, `ready`, `idle` and `running`. An `idle` box is live and billing.
`box new` has no `--name` flag, checked against `box new --help`, so track the
id you got back rather than expecting to recognise a name later.

## What a box can do

A box is a full Linux machine, not a container you hand one command to. Six
capabilities, each with the flag that unlocks it.

### 1. Run commands

```bash
box exec  <id> -- pnpm build          # one command, JSON result, real exit code
box exec  <id> --cwd derive-web -- pnpm test      # relative to /home/user
box exec  <id> --timeout 600 -- ./slow.sh         # 30s default, 600s ceiling
box exec  <id> --detach -- ./run.sh               # prints a pid, returns at once
box exec  <id> --status <pid>                     # status and logs of that pid
box ssh   <id> 'cmd | pipeline > out.txt'         # anything with shell syntax
box ssh   <id>                                    # interactive shell
```

`exec` accepts `current` or `self` in place of an id, so a script running on the
box can drive its own machine.

Measured 2026-09-11, the three response shapes are flat, with no `.box` wrapper:

| Call | Fields you want |
|---|---|
| `box exec <id> -- cmd` | `stdout`, `stderr`, `exitCode`, `timedOut`, `stdoutTruncated` |
| `box exec <id> --detach` | `pid`, `processId`, `logPath`, `errLogPath`, `startedAt` |
| `box exec <id> --status <pid>` | `running`, `known`, `status`, `exitCode`, `stdout`, `stderr` |

Read `stdoutTruncated` before you trust a long output, and read `timedOut`
rather than inferring a timeout from an empty `stdout`. Both fields exist on
every `exec` result, confirmed against a live call.

### 2. Reach it from outside

| Want | Command | What you get |
|---|---|---|
| A web service on the internet | `box host <id> 3000 --title api` | Stable HTTPS URL, token-gated |
| The same, no token | `box host <id> 3000 --public` | Open to anyone with the link |
| A database or non-HTTP port | `box forward <id> --remote 5432` | Local `127.0.0.1:5432` |
| A full Linux desktop | `box desktop <id>` | Browser URL, `--vnc` on a bad network |
| Chrome only | `box browser <id> --profile /home/user/.chrome` | Browser stream, profile persists |

`box forward` binds `127.0.0.1` by default. Leave `--bind` alone, because this
devbox has a public interface.

### 3. Move files

```bash
box scp -r ./derive-web <id>:/home/user/derive-web   # up
box scp -r <id>:/home/user/out ./out                 # down
box snapshot tree <id>                               # what the disk holds
box snapshot pull <id> -o ./recovered                # whole disk, no scp
```

`snapshot pull` takes a box id and grabs its latest snapshot, so you can recover
a box's files after it stopped.

### 4. Save a machine and rebuild it later

```bash
box snapshot <id> node22-ready     # name the current disk
box new --from node22-ready        # a fresh box that starts there
box snapshots                      # every snapshot you hold
box snapshot rm node22-ready       # drop the name
```

A named snapshot is a golden image. Build the toolchain once, then every later
box skips the install.

**`~/.cache` is excluded from every snapshot.** Measured 2026-09-11: a box with
932MB of Playwright browsers under `~/.cache/ms-playwright` snapshotted to
227MB, and `box new --from` produced a box with no browsers. The same disk with
the browsers moved to `~/.playwright` snapshotted to 1.20GB. Nothing warns you.
So install a toolchain somewhere other than `~/.cache`, then check the
`sizeBytes` on the `saved` event against `du -sh` before you trust the image.

Also: `box new --from <name>` streams NDJSON, so `.box.id` is null. Read the id
from the `created` event instead.

```bash
ID=$(box new --from playwright --ttl 900 | jq -rs '.[] | select(.event=="created") | .id')
```

### 5. Prepare a box at creation

```bash
box new --setup-file ./bootstrap.sh          # max 64KB, runs in the background
box info <id> | jq -r '.box.setupStatus, .box.setupError'   # poll until done
```

`--setup-file` returns before the script finishes, so read `setupStatus` rather
than assuming the box is ready. Add `-e KEY=VALUE` for per-box variables, and
`--environment <name>` to start from a different named environment.

### 6. Resize without losing the disk

```bash
box stop   <id>
box resume <id> --type large     # 4 vCPU/8GB becomes 8 vCPU/16GB
box fork   <id> --type small     # a half-rate copy
```

Growing always works. Shrinking is refused when the data does not fit.

### Read the state

`box info <id>` nests 28 fields under `.box`. The ones that answer a question:

| Field | Answers |
|---|---|
| `.box.state` | `provisioned`, `cloning`, `ready`, `idle`, `running`, then stopped or error |
| `.box.url` | the hosted HTTPS address |
| `.box.desktopUrl` | the desktop address |
| `.box.vcpu`, `.box.memoryGB` | what you actually got |
| `.box.billingMultiplier` | what the machine costs. `2` on a `large`, measured |
| `.box.setupStatus`, `.box.setupError` | did `--setup-file` finish |
| `.box.lastSnapshotStatus` | is a stop safe right now |
| `.box.environment`, `.box.environmentVersion` | which secrets it holds |

## A whole job, start to finish

```bash
B=~/.ascii/bin/box
$B limits | jq -c '.starts.day'                       # 1. can I afford a start
ID=$($B new --ttl 1800 --type large | jq -r '.box.id // .id')
git bundle create /tmp/repo.bundle --all              # 2. ship code, not a token
$B scp /tmp/repo.bundle $ID:/home/user/repo.bundle
$B ssh $ID 'git clone repo.bundle work && cd work && pnpm i'
PID=$($B exec $ID --cwd work --detach -- pnpm test | jq -r .pid)
$B exec $ID --status $PID                             # 3. poll until it ends
$B scp -r $ID:/home/user/work/coverage ./coverage     # 4. take the results home
$B delete $ID --yes | jq -r '.operationId // .id'     # 5. give the machine back
```

Step 2 is the rule from `~/CLAUDE.md`: a bundle carries the code, a token would
carry the whole GitHub account.

## Quick reference

| Need | Command |
|---|---|
| What is up | `box list \| jq -r '.boxes[] \| "\(.id) \(.state) \(.name)"'` |
| Include stopped ones | `box list --filter rs`, or `--all` for `rspte` |
| One box in full | `box info <id> \| jq .box` |
| New, 30 minutes | `box new --ttl 1800` |
| Bigger machine | `box new --type large`, 8 vCPU, 16GB, 2x rate |
| Cheapest machine | `box new --type small`, 2 vCPU, 4GB, half rate |
| One command, JSON result | `box exec <id> -- uname -r` |
| Any shell line | `box ssh <id> 'cmd \| pipeline > out'` |
| Long job | `box exec <id> --detach -- ./run.sh` |
| Check that job | `box exec <id> --status <pid>` |
| Interactive shell | `box ssh <id>` |
| Files in or out | `box scp -r ./src <id>:/home/user/src` |
| Whole disk, locally | `box snapshot pull <id> -o ./out` |
| Port on HTTPS | `box host <id> 3000 --title api` |
| Port on localhost | `box forward <id> --remote 5432` |
| Desktop in a browser | `box desktop <id>` |
| Chrome only | `box browser <id>` |
| Save a golden image | `box snapshot <id> <name>` |
| Start from that image | `box new --from <name>` |
| Keep it longer | `box extend <id> --hours 4` |
| Park it | `box stop <id>` |
| Bring it back, resized | `box resume <id> --type large` |
| Copy of its disk | `box fork <id> --ttl 3600` |
| Gone for good | `box delete <id> --yes` |
| Did the delete land | `box deletion status <bdop_id>` |

## exec takes an argv vector, ssh takes a shell line

`box exec` splits the command on whitespace. A quoted shell string does not
survive, and the failure is silent: exit code 0, wrong output, no error.

```bash
box exec bx_x -- echo hi                 # stdout 'hi\n'      correct
box exec bx_x -- bash -c 'echo A=$0'     # stdout '\n'        WRONG, exit 0
box ssh  bx_x 'echo hi; seq 1 3 | tr "\n" ","'   # hi / 1,2,3,   correct
```

Measured 2026-09-11, n=4 each. `bash -c` receives `echo` as its script and
`A=$0` as `$0`, so it prints a bare newline and reports success.

**Rule:** `exec` for one command and its arguments, when you want the exit code
as JSON. `ssh` for every pipe, redirect, semicolon, glob or quoted argument.

`exec` caps at `--timeout 30` by default, 600 maximum. Past that, detach. A
detached process writes two files on the box, and the detach response names
both: `/home/user/.ascii/processes/<pid>.log` for stdout, and the matching
`<pid>.err.log` for stderr. A silent failure usually sits in the second one.

### Retry a 502 once

The API returns `request failed (502): <empty response>` intermittently, on any
subcommand. Measured 2026-09-11: `box list` failed once in one window and 6 of
6 in the next, and `box list --all` failed twice in a row. A 502 says nothing
about your syntax. Retry before you change the command.

## Lifetime, and what a stop costs

A new box lives 3600 seconds and stops itself (cited, docs.ascii.dev). Pass
`--ttl <seconds>` up to 2592000, or `--no-auto-stop` for a box you will manage
by hand. A fork never inherits the source lifetime and always starts at one
hour, so `--no-auto-stop` does not propagate.

A TTL is a spend guard, not cleanup. The box stops and keeps its disk.

| Want | Command | Leaves behind |
|---|---|---|
| Pause, resume later | `box stop <id>` | Disk, resumable, no billing |
| Gone | `box delete <id> --yes` | Nothing, unrecoverable |

`box stop` snapshots first, then archives, so a failed snapshot refuses the
stop rather than losing work. **`box stop --force` overrides that refusal and
loses everything written since the last good snapshot.** Reach for `--force`
only after a plain stop has already failed. `box info <id> | jq -r
'.box.lastSnapshotStatus'` tells you whether a stop is safe right now.

`box resume` is free and hands the disk back, but the box reboots: systemd
units restart, anything you launched by hand does not. `box resume --no-env`
is one-way. The box stays no-env afterwards, so a later resume cannot give the
secrets back.

`box delete` returns before the box is gone. It prints a `bdop_` id, and the
delete then runs on its own. Confirm it:

```bash
box delete $ID --yes | jq -r '.operationId // .id'   # bdop_...
box deletion status <bdop_id>
box list | jq -r '.boxes[].id' | grep -c "$ID"       # expect 0
```

`box host <id> <port>` returns a token-gated URL by default. Two traps: the
service must bind `0.0.0.0` rather than loopback, and `--public` drops the
token entirely.

## Every box already carries Eden's credentials

The default environment is `base`. Checked 2026-09-11, it sets
`passGithub`, `passSecrets`, `passBoxCredentials` and `passAgentsCredentials`
all true, and injects a `FLEET_GH_TOKEN`. A fresh box therefore arrives with a
GitHub token and a `Derive` clone in `/home/user`, under the user `user`.

Two consequences:

- **Never treat a box URL, desktop or browser session as credential-free.**
  Anyone you hand it to reaches that token. Use `box new --no-env` for a box
  someone else will touch. `fleet-dispatch.py:1346` forks with `"noEnv": True`
  for exactly this reason, so the fleet's own boxes carry no secrets.
- **Never add a new secret to `base`.** `~/CLAUDE.md` forbids sending this
  box's credentials off-machine, and `base` sends whatever it holds to every
  VM you rent. Ask Eden per instance.

`box env list` shows the environments. `box env set-var` mints a new version
and leaves running boxes alone until `box env upgrade`.

## Playwright on a box

A fresh box carries Node and a `Derive` clone, and **no browsers at all**.
`npx playwright --version` answers, then `chromium.launch()` fails with
"Executable doesn't exist". Two ways to fix that, both using the same script:

```bash
S=~/.claude/skills/box/assets/setup-playwright.sh

box new --from playwright --ttl 1800     # already installed, ~15s to ready
box new --setup-file "$S" --ttl 1800     # a fresh install, ~4 minutes
```

The `playwright` snapshot is the one to reach for. Measured 2026-09-11 on a box
created from it: chromium 148.0.7778.96 launched in 293ms and webkit 26.4 in
676ms, n=1 each, headless, no `DISPLAY`.

The script installs to `$HOME/.playwright`, never `~/.cache`, because
snapshots drop `~/.cache`. It then points Playwright there three ways, all
outside `~/.cache`, because the three ways you reach a box differ:

| Reached by | Reads | Gets the variable |
|---|---|---|
| `box exec` | a login shell | yes, via `/etc/profile.d` |
| `box ssh` | neither profile nor bashrc | yes, via `/etc/environment` and pam_env |
| anything else | nothing | no, falls back to the symlink |

The third is `playwright-browsers.service`, a oneshot unit that links
`~/.cache/ms-playwright` to `$HOME/.playwright` at boot. It fires a few seconds
after a restored box first answers ssh, so a `systemctl is-active` check
immediately on connect can read `inactive` and be wrong.

Browser choice matters for the download. `derive-web/playwright.config.ts` runs
chromium only by default; `mobile-safari` and `ipad-safari` sit behind
`PLAYWRIGHT_IOS=1` (`pnpm test:e2e:ios`). So `pnpm test:e2e` needs chromium
alone, at 353MB. The script installs chromium and webkit, 932MB total. Pass a
browser list to cut that:

```bash
box ssh <id> 'bash ~/setup-playwright.sh "" chromium'   # skip webkit
```

`fleet-seed.py` solves the same problem its own way, chromium under
`~/repo/.playwright` with `PLAYWRIGHT_BROWSERS_PATH` exported. Do not merge the
two. `fleet-dispatch` owns its golden box.

## Three different things are called "box" here

| Name | Means |
|---|---|
| `box`, this skill | a rented ascii.dev VM |
| `loop-box-free.sh` | is **this devbox** calm enough to run something heavy |
| `fleet-box-cost.py` | the ascii.dev spend ledger, at `~/code/loop-architecture/bin/` |

`fleet-dispatch` already rents a box, ships the working tree and runs a build
on it. Do not rebuild that flow by hand. Reach for this skill when you want a
sandbox you drive yourself, not a faster `pnpm test`.

## Common mistakes

| Mistake | Fix |
|---|---|
| `box: command not found` | Use `~/.ascii/bin/box`, always |
| `.id` is null | `box list` nests in `.boxes[]`, `box info` in `.box` |
| `exec` exits 0 with empty output | You passed a shell line. Use `box ssh` |
| `request failed (502)` | Transient. Retry once before you edit the command |
| Created a box for a one-line check | `exec` against an `idle` box you made costs no start |
| Reused an idle box you did not create | Those are fleet forks. One start is cheaper than a corrupted job |
| Ran `delete`, called it gone | Delete is async. Check `box deletion status <bdop_id>` |
| Hosted port shows nothing | The service bound loopback, not `0.0.0.0` |
| `--setup-file` box looks empty | Setup runs in the background. Poll `.box.setupStatus` |
| Detached job produced nothing | Read `<pid>.err.log`, not just `<pid>.log` |
| Long output looks cut off | Check `stdoutTruncated` on the `exec` result |
| Reached for `stop --force` | Only after a plain stop failed. It discards unsnapshotted work |
| Installed the toolchain again | `box snapshot <id> <name>`, then `box new --from <name>` |
| A snapshot lost the toolchain | It lived in `~/.cache`, which snapshots exclude |
| `box new --from` gave a null id | That form streams NDJSON. Parse the `created` event |
| `chromium.launch()` says no executable | A fresh box has no browsers. See Playwright on a box |
| Set a TTL and called it cleanup | TTL stops the box. Only `delete` removes it |
| A fork outlived the night | Forks reset to 1 hour and ignore `--no-auto-stop` |
| Read `~/.config/ascii/token` | That one feeds the raw API. The CLI reads `~/.config/ascii/box/config.json` |
