---
name: boat
description: Use when work needs a throwaway Linux VM from Boat (boat.dev, by ascii.dev, formerly "Box"), or when driving one that already exists. Triggers include a sandbox for a build or stress test, a port exposed on an HTTPS URL, a remote desktop or browser, files copied to or from a rented sandbox, and fork, stop, resume or delete of one. Also use before any sandbox is created, to check the start budget first.
user_invocable: true
---

# boat: drive a Boat sandbox VM

Boat rents a Linux VM for an hour, with root and 4 vCPU and 8GB by default.
Boat is the product ascii.dev used to call Box. Same account, same sandbox ids
(`bx_...`), same SSH key, new binary and new JSON field names.

What you can do with one:

- **Run anything.** `boat exec` for a command, `boat ssh` for a shell line, and
  `--detach` for a job that outlives the call.
- **Publish a port.** `boat host <id> 3000` returns a stable HTTPS URL you can
  send to Eden. `boat forward` brings a database port back to this devbox.
- **See a screen.** `boat desktop` gives a full Linux desktop in a browser,
  `boat browser` gives Chrome alone with a persistent profile.
- **Move files both ways.** `boat scp`, or `boat snapshot pull` for the whole disk.
- **Freeze a machine and rebuild it.** `boat snapshot <id> <name>` makes a golden
  image, `boat new --from <name>` starts there, `boat fork` copies a live sandbox.
- **Change your mind about size.** `boat resume --type large` grows a stopped
  sandbox without losing its disk.

Use it for a sandbox you drive yourself. Machine sizes: `small` at 2 vCPU and
4GB at half rate, `default` at 4 and 8, `large` at 8 and 16 at 2x, `xlarge` at
16 and 32 at $0.20 an hour on a $100+ plan. Measured 2026-09-17: a `small`
reports `vcpu 2, memoryGB 4, billingMultiplier 0.5`.

## The binary is not on your PATH

```bash
~/.ascii/bin/boat list         # works
boat list                      # "command not found" inside Claude's Bash tool
```

The installer prepends a PATH block to `~/.bashrc` and `~/.profile`. Claude's
Bash tool reads neither, so `command -v boat` finds nothing there. Measured
2026-09-17: `boat --version` inside the tool gives `command not found`,
`~/.ascii/bin/boat --version` gives `boat 1.0.9`, and `bash -lc 'command -v
boat'` finds it. A login shell has it. Your tool shell does not.

`~/.bashrc` also defines a `boat()` function that exports `BOAT_CURRENT_ID`
after `new` and `fork`. You do not get it. Read the id out of the JSON yourself.

**The old `~/.ascii/bin/box` binary still exists and still works.** It updated
itself to `boat 0.1.259-ascii-prod1` on 2026-09-17, prints `Box is now Boat`
on stderr, and will not update again. Its `list` output already changed to
`.sandboxes[]`. Do not write new scripts against it. The fleet scripts in
`~/code/loop-architecture/bin/` use neither binary: they call
`https://ascii.dev/api/box/v1` directly with `~/.config/ascii/token`.

## Output is always JSON for you

No TTY means machine output, with no `--json` flag needed. `boat new` streams
JSONL events, one object per line. `list` and `info` return one object each.

```bash
B=~/.ascii/bin/boat
$B list | jq -r '.sandboxes[] | "\(.id) \(.state) \(.name)"'         # measured
$B info <id> | jq '.sandbox.state'                                     # measured
ID=$($B new --ttl 1800 | jq -rs '.[] | select(.event=="created") | .id')  # measured
```

Measured 2026-09-17, a plain `boat new --type small --ttl 900` printed four
lines in 3.95s: `created`, `state cloning`, `state ready`, `ready`. Every line
carries `.id`. There is no `.sandbox.id` and no `.box.id` on a `new`.

The old names are gone: `list` nested under `.boxes[]` and `info` under
`.box`. Now `.sandboxes[]` and `.sandbox`. The 28 fields inside are unchanged.

## Check the start budget before you create anything

Starts are the scarce resource on this account, not credit.

```bash
~/.ascii/bin/boat limits | jq -c '{day: .starts.day, hour: .starts.hour, active: .activeSandboxes, maxActive: .maxActiveSandboxes}'
# {"day":{"limit":840,"remaining":807,"used":33},"hour":{"limit":210,...},"active":2,"maxActive":300}
```

Each of `.starts.minute`, `.starts.hour` and `.starts.day` carries its own
limit. `.activeSandboxes` does not, so pair it with `.maxActiveSandboxes`.

**Read the number live. Never quote one from this file.** Measured 2026-09-17
13:09: day limit 840, hour 210, minute 30, max active 300. On 2026-09-11 the
day limit was 420 and the fleet sat at 403 used by 07:44. The `plan-exec`
fleet burns starts through `fleet-dispatch` whenever load is high, so the
daily cap is the thing you will hit, hours before the credit runs low.

So, in order:

1. **Reuse a sandbox you made.** `boat exec` on an `idle` one costs zero starts.
2. **Resume a stopped one.** Same disk, same state.
3. **Create one** only when neither fits.

**Never touch an idle sandbox you did not create.** Every active one on this
account is named by a fork timestamp, such as `Box 2026-09-17 04:32 fork`, and
belongs to `fleet-dispatch`. Writing to one corrupts a running job, and
deleting one destroys work you cannot see. One start out of the daily budget
is the cheaper mistake.

`boat list` defaults to `--filter r`, which covers `ready`, `cloning`, `idle`
and `running`. An `idle` sandbox is live and billing. `boat new` has no
`--name` flag, checked against `boat new --help` on 1.0.9, so track the id you
got back rather than expecting to recognise a name later.

## What a sandbox can do

A sandbox is a full Linux machine, not a container you hand one command to.
Six capabilities, each with the flag that unlocks it.

### 1. Run commands

```bash
boat exec  <id> "pnpm build"                       # one shell line, JSON result, real exit code
boat exec  <id> --cwd derive-web "pnpm test"       # relative to /home/user
boat exec  <id> --timeout 600 "./slow.sh"          # 30s default, 600s ceiling
boat exec  <id> --detach "./run.sh"                # prints a pid, returns at once
boat exec  <id> --status <pid>                     # status and logs of that pid
boat ssh   <id> 'cmd | pipeline > out.txt'         # anything with shell syntax
boat ssh   <id>                                    # interactive shell
```

`exec` accepts `current` or `self` in place of an id, so a script running on
the sandbox can drive its own machine. `exec` now exits with the remote exit
code: `boat exec <id> -- false; echo $?` prints 1, measured 2026-09-17.

Measured 2026-09-17, the three response shapes are flat, with no wrapper:

| Call | Fields you want |
|---|---|
| `boat exec <id> "cmd"` | `stdout`, `stderr`, `exitCode`, `success`, `timedOut`, `stdoutTruncated`, `launcherFailed` |
| `boat exec <id> --detach` | `pid`, `processId`, `logPath`, `errLogPath`, `command`, `startedAt` |
| `boat exec <id> --status <pid>` | `running`, `known`, `status`, `exitCode`, `stdout`, `stderr` |

Read `stdoutTruncated` before you trust a long output, and read `timedOut`
rather than inferring a timeout from an empty `stdout`.

### 2. Reach it from outside

| Want | Command | What you get |
|---|---|---|
| A web service on the internet | `boat host <id> 3000 --title api` | Stable HTTPS URL, token-gated |
| The same, no token | `boat host <id> 3000 --public` | Open to anyone with the link |
| A database or non-HTTP port | `boat forward <id> --remote 5432` | Local `127.0.0.1:5432` |
| This devbox, from inside the sandbox | `boat forward <id> --reverse --local 7777` | `127.0.0.1:7777` on the sandbox |
| A full Linux desktop | `boat desktop <id>` | Browser URL, `--vnc` on a bad network |
| Chrome only | `boat browser <id> --profile /data/chrome` | Browser stream, profile persists |

`boat forward` binds `127.0.0.1` by default. Leave `--bind` alone, because this
devbox has a public interface. A `--profile` path must sit outside
`/home/user`, which the browser sandbox masks (cited, docs.boat.dev).

### 3. Move files

```bash
boat scp -r ./derive-web <id>:/home/user/derive-web   # up
boat scp -r <id>:/home/user/out ./out                 # down
boat snapshot tree <id>                               # what the disk holds
boat snapshot pull <id> -o ./recovered                # whole disk, no scp
```

`snapshot tree` and `snapshot pull` take a snapshot id, or a sandbox id for
its latest snapshot. `pull` writes `home_user/` and `docker/`. Works while the
sandbox is stopped, so you can recover files after it stopped.

### 4. Save a machine and rebuild it later

```bash
boat snapshot <id> node22-ready     # name the current disk
boat new --from node22-ready        # a fresh sandbox that starts there
boat snapshots                      # .named[] you hold, then .snapshots[] history
boat snapshot rm node22-ready       # drop the name
```

A named snapshot is a golden image. Build the toolchain once, then every later
sandbox skips the install. You can hold 10 names (cited, docs.boat.dev).

**`~/.cache` is excluded from every snapshot.** Measured 2026-09-11 on Box: a
machine with 932MB of Playwright browsers under `~/.cache/ms-playwright`
snapshotted to 227MB, and `new --from` produced a machine with no browsers.
The same disk with the browsers moved to `~/.playwright` snapshotted to
1.20GB. Nothing warns you. So install a toolchain somewhere other than
`~/.cache`, then check `sizeBytes` on the `saved` event against `du -sh`
before you trust the image. A `.boxignore` file adds more exclusions, in
gitignore syntax (cited, docs.boat.dev).

### 5. Prepare a sandbox at creation

```bash
boat new --setup-file ./bootstrap.sh          # max 64KB, runs in the background
boat info <id> | jq -r '.sandbox.setupStatus, .sandbox.setupError'   # poll until done
```

`--setup-file` returns before the script finishes, so read `setupStatus`
rather than assuming the sandbox is ready. Add `-e KEY=VALUE` for per-sandbox
variables, and `--environment <name>` to start from a different named
environment.

### 6. Resize without losing the disk

```bash
boat stop   <id>
boat resume <id> --type large     # 4 vCPU/8GB becomes 8 vCPU/16GB
boat fork   <id> --type small     # a half-rate copy
```

Growing always works. Shrinking is refused when the data does not fit.

### Read the state

`boat info <id>` nests 28 fields under `.sandbox`. The ones that answer a
question:

| Field | Answers |
|---|---|
| `.sandbox.state` | `provisioned`, `cloning`, `ready`, `idle`, `running`, then stopped or error |
| `.sandbox.url` | the hosted HTTPS address, on `on.boat.dev` |
| `.sandbox.desktopUrl` | the desktop address |
| `.sandbox.vcpu`, `.sandbox.memoryGB` | what you actually got |
| `.sandbox.billingMultiplier` | what the machine costs. `0.5` on a `small`, measured |
| `.sandbox.setupStatus`, `.sandbox.setupError` | did `--setup-file` finish |
| `.sandbox.lastSnapshotStatus` | is a stop safe right now. `in_progress` on a fresh machine |
| `.sandbox.environment`, `.sandbox.environmentVersion` | which secrets it holds |

`boat usage <id>` prices one sandbox: `seconds`, `dollars`,
`billingMultiplier`, `running`. Measured 2026-09-17: 25s on a `small` cost
$0.00025.

## A whole job, start to finish

```bash
B=~/.ascii/bin/boat
$B limits | jq -c '.starts.day'                       # 1. can I afford a start
ID=$($B new --ttl 1800 --type large | jq -rs '.[] | select(.event=="created") | .id')
git bundle create /tmp/repo.bundle --all              # 2. ship code, not a token
$B scp /tmp/repo.bundle $ID:/home/user/repo.bundle
$B ssh $ID 'git clone repo.bundle work && cd work && pnpm i'
PID=$($B exec $ID --cwd work --detach "pnpm test" | jq -r .pid)
$B exec $ID --status $PID                             # 3. poll until it ends
$B scp -r $ID:/home/user/work/coverage ./coverage     # 4. take the results home
$B delete $ID --yes | jq -r '.operation.id'           # 5. give the machine back
```

Step 2 is the rule from `~/CLAUDE.md`: a bundle carries the code, a token would
carry the whole GitHub account.

## Quick reference

| Need | Command |
|---|---|
| What is up | `boat list \| jq -r '.sandboxes[] \| "\(.id) \(.state) \(.name)"'` |
| Include stopped ones | `boat list --filter rs`, or `--all` for `rspte` |
| One sandbox in full | `boat info <id> \| jq .sandbox` |
| New, 30 minutes | `boat new --ttl 1800` |
| Bigger machine | `boat new --type large`, 8 vCPU, 16GB, 2x rate |
| Cheapest machine | `boat new --type small`, 2 vCPU, 4GB, half rate |
| One shell line, JSON result | `boat exec <id> "uname -r"` |
| Any shell line, raw output | `boat ssh <id> 'cmd \| pipeline > out'` |
| Long job | `boat exec <id> --detach "./run.sh"` |
| Check that job | `boat exec <id> --status <pid>` |
| Interactive shell | `boat ssh <id>` |
| Files in or out | `boat scp -r ./src <id>:/home/user/src` |
| Whole disk, locally | `boat snapshot pull <id> -o ./out` |
| Port on HTTPS | `boat host <id> 3000 --title api` |
| Port on localhost | `boat forward <id> --remote 5432` |
| Desktop in a browser | `boat desktop <id>` |
| Chrome only | `boat browser <id>` |
| Save a golden image | `boat snapshot <id> <name>` |
| Start from that image | `boat new --from <name>` |
| Keep it longer | `boat extend <id> --hours 4` |
| Park it | `boat stop <id>` |
| Bring it back, resized | `boat resume <id> --type large` |
| Copy of its disk | `boat fork <id> --ttl 3600` |
| What it cost | `boat usage <id>` |
| Gone for good | `boat delete <id> --yes` |
| Did the delete land | `boat deletion status <bdop_id>` |
| Am I signed in | `boat status \| jq .account` |

## exec joins its arguments into one shell line

`boat exec` takes every argument after the id, joins them with single spaces,
and hands that one string to a shell on the sandbox. Quoting boundaries do not
survive the join, and the failure is silent: exit code 0, wrong output.

```bash
boat exec bx_x "echo a | tr a-z A-Z"        # stdout 'A\n'      correct, one string
boat exec bx_x -- echo 'a  b'               # stdout 'a b\n'    two spaces became one
boat exec bx_x -- printf '%s|' x 'y z'      # stdout ''         exit 0, WRONG
boat exec bx_x -- bash -c 'echo A=$0'       # stdout '\n'       exit 0, WRONG
boat ssh  bx_x -- printf '%s|' x 'y z'      # x|y z|            ssh keeps argv
```

Measured 2026-09-17, n=1 each, on `boat 1.0.9`. In the `bash -c` case the
shell sees `bash -c echo A=$0`, so `echo` is the script and `A=$0` is `$0`.

**Rule:** give `exec` exactly one quoted string, and put the whole shell line
in it. Use `ssh` when you need argv boundaries kept, or raw output rather
than JSON.

`exec` caps at `--timeout 30` by default, 600 maximum. Past that, detach. A
detached process writes two files on the sandbox, and the detach response
names both: `/home/user/.ascii/processes/<pid>.log` for stdout, and the
matching `<pid>.err.log` for stderr. A silent failure usually sits in the
second one.

### Retry a 502 once

The Box API returned `request failed (502): <empty response>` intermittently,
on any subcommand. Measured 2026-09-11 on Box: `list` failed once in one
window and 6 of 6 in the next. Not seen on Boat yet, 14 calls on 2026-09-17.
A 502 says nothing about your syntax. Retry before you change the command.

## Lifetime, and what a stop costs

A new sandbox lives 3600 seconds and stops itself (cited, docs.boat.dev). Pass
`--ttl <seconds>` up to 2592000, or `--no-auto-stop` for one you will manage
by hand. A fork never inherits the source lifetime and always starts at one
hour, so `--no-auto-stop` does not propagate.

A TTL is a spend guard, not cleanup. The sandbox stops and keeps its disk.

| Want | Command | Leaves behind |
|---|---|---|
| Pause, resume later | `boat stop <id>` | Disk, resumable, no billing |
| Gone | `boat delete <id> --yes` | Nothing, unrecoverable |

`boat stop` snapshots first, then archives, so a failed snapshot refuses the
stop rather than losing work. **`boat stop --force` overrides that refusal and
loses everything written since the last good snapshot.** Reach for `--force`
only after a plain stop has already failed. `boat info <id> | jq -r
'.sandbox.lastSnapshotStatus'` tells you whether a stop is safe right now.

`boat resume` is free and hands the disk back, but the machine reboots:
systemd units restart, anything you launched by hand does not. `boat resume
--no-env` is one-way. The sandbox stays no-env afterwards, so a later resume
cannot give the secrets back.

`boat delete` returns before the machine is gone. It prints an operation
under `.operation`, and the delete then runs on its own. Confirm it:

```bash
boat delete $ID --yes | jq -r '.operation.id'       # bdop_..., measured
boat deletion status <bdop_id>
boat list --all | jq -r '.sandboxes[].id' | grep -c "$ID"   # expect 0
```

Measured 2026-09-17: the deleted id was gone from `list --all` on the next
call, while the operation still said `pending`.

`boat host <id> <port>` returns a token-gated URL by default. Two traps: the
service must bind `0.0.0.0` rather than loopback, and `--public` drops the
token entirely.

## Every sandbox may carry Eden's credentials

The default environment is `base`. Checked 2026-09-17 with `boat env list`:
`passGithub`, `passSecrets`, `passSandboxCredentials` and
`passAgentsCredentials` all true, `safeForThirdParties` also true, and one
variable named `FLEET_GH_TOKEN` in `envContents`. The docs say
`safeForThirdParties` overrides the other flags and injects nothing. The
listing still shows the token. Do not resolve that by experiment. Assume the
token arrives.

Three consequences:

- **Never treat a sandbox URL, desktop or browser session as credential-free.**
  Anyone you hand it to may reach that token. Use `boat new --no-env` for one
  someone else will touch. `fleet-dispatch.py` forks with `"noEnv": True` for
  exactly this reason, so the fleet's own machines carry no secrets.
- **Never add a new secret to `base`.** `~/CLAUDE.md` forbids sending this
  box's credentials off-machine, and `base` sends whatever it holds to every
  VM you rent. Ask Eden per instance.
- **`boat env list` prints every variable value in clear text.** Measured
  2026-09-17: `envContents` carried the full `FLEET_GH_TOKEN`. Never paste
  that output into a transcript, a log or a file. Strip it first:
  `boat env list | jq 'del(.environments[].envContents)'`.

  **Only ever strip it recursively:**

  ```bash
  boat env new NAME  | jq 'del(.. | .envContents?)'    # any shape, any depth
  boat env set  NAME | jq 'del(.. | .envContents?)'
  boat env list      | jq 'del(.. | .envContents?)'
  ```

  Two different mistakes on 2026-09-22 each printed a live token into a session
  transcript, and each cost a rotation:

  1. A jq guard that handled an array or an object and fell back to `.`.
     `envContents` is a plain string, `FLEET_GH_TOKEN=gho_...\n`, so the
     fallback branch printed it.
  2. `del(.environment.envContents?)` on `boat env new`, which answers with
     `.environments[]` rather than `.environment`. The path did not match, so
     `del` removed nothing and every environment printed in full.

  The lesson is the same both times: **never name the path**. Every `env`
  subcommand has its own response shape, and a path-specific `del` silently
  removes nothing when it guesses wrong. `del(.. | .envContents?)` cannot miss.

  To prove a value changed without reading it, hash it:
  `boat env list | jq -r '.environments[]|select(.name=="base")|.envContents' | sha256sum`.

`boat env set-var` mints a new version and leaves running sandboxes alone
until `boat env upgrade`.

## Signing in

The CLI reads `~/.config/ascii/boat/config.json`. Boat's installer writes
only `api_url` and `channel` there, then wants a browser sign-in. On this box
the old Box token signed Boat in with no browser, measured 2026-09-17:

```bash
jq -r .token ~/.config/ascii/box/config.json | ~/.ascii/bin/boat login --key-stdin --json
# {"event":"login_complete", ...}
~/.ascii/bin/boat status | jq -c .account    # loginState "active", plan "Standard"
```

That token stays on this box. `~/.config/ascii/token` is a different file. It
feeds the raw API for `fleet-dispatch.py`, `fleet-seed.py` and
`fleet-box-cost.py`, and the CLI never reads it. `boat ssh` reuses
`~/.ssh/ascii_box_ed25519`, so nothing needed re-authorising.

## Playwright on a sandbox

A fresh sandbox carries Node and a `Derive` clone, and **no browsers at all**.
`npx playwright --version` answers, then `chromium.launch()` fails with
"Executable doesn't exist". Two ways to fix that, both using the same script:

```bash
S=~/.claude/skills/boat/assets/setup-playwright.sh

boat new --from playwright --ttl 1800     # already installed, ~15s to ready
boat new --setup-file "$S" --ttl 1800     # a fresh install, ~4 minutes
```

The `playwright` snapshot is the one to reach for. Checked 2026-09-17 with
`boat snapshots`: `.named[]` still lists it, `status ready`, 1.20GB.
Measured 2026-09-11 on a machine created from it: chromium 148.0.7778.96
launched in 293ms and webkit 26.4 in 676ms, n=1 each, headless, no `DISPLAY`.

The script installs to `$HOME/.playwright`, never `~/.cache`, because
snapshots drop `~/.cache`. It then points Playwright there three ways, all
outside `~/.cache`, because the three ways you reach a sandbox differ:

| Reached by | Reads | Gets the variable |
|---|---|---|
| `boat exec` | a login shell | yes, via `/etc/profile.d` |
| `boat ssh` | neither profile nor bashrc | yes, via `/etc/environment` and pam_env |
| anything else | nothing | no, falls back to the symlink |

The third is `playwright-browsers.service`, a oneshot unit that links
`~/.cache/ms-playwright` to `$HOME/.playwright` at boot. It fires a few seconds
after a restored machine first answers ssh, so a `systemctl is-active` check
immediately on connect can read `inactive` and be wrong.

Browser choice matters for the download. `derive-web/playwright.config.ts` runs
chromium only by default; `mobile-safari` and `ipad-safari` sit behind
`PLAYWRIGHT_IOS=1` (`pnpm test:e2e:ios`). So `pnpm test:e2e` needs chromium
alone, at 353MB. The script installs chromium and webkit, 932MB total. Pass a
browser list to cut that:

```bash
boat ssh <id> 'bash ~/setup-playwright.sh "" chromium'   # skip webkit
```

`fleet-seed.py` solves the same problem its own way, chromium under
`~/repo/.playwright` with `PLAYWRIGHT_BROWSERS_PATH` exported. Do not merge the
two. `fleet-dispatch` owns its golden machine.

## Four different things are called "box" here

| Name | Means |
|---|---|
| `boat`, this skill | a rented Boat VM, the product ascii.dev called Box until 2026-09 |
| `~/.ascii/bin/box` | the legacy CLI, frozen at `boat 0.1.259-ascii-prod1`. Do not write new scripts against it |
| `loop-box-free.sh` | is **this devbox** calm enough to run something heavy |
| `fleet-box-cost.py` | the Boat spend ledger, at `~/code/loop-architecture/bin/` |

`fleet-dispatch` already rents a sandbox, ships the working tree and runs a
build on it. Do not rebuild that flow by hand. Reach for this skill when you
want a sandbox you drive yourself, not a faster `pnpm test`.

## Common mistakes

| Mistake | Fix |
|---|---|
| `boat: command not found` | Use `~/.ascii/bin/boat`, always |
| `.boxes[]` or `.box.id` is null | The names changed. `list` nests in `.sandboxes[]`, `info` in `.sandbox` |
| `boat new` gave a null id | It streams JSONL. Parse the `created` event |
| `exec` exits 0 with wrong output | Argv was joined and re-split. Pass one quoted string, or use `ssh` |
| `request failed (502)` | Transient. Retry once before you edit the command |
| Created a sandbox for a one-line check | `exec` against an `idle` one you made costs no start |
| Reused an idle sandbox you did not create | Those are fleet forks. One start is cheaper than a corrupted job |
| Ran `delete`, called it gone | Delete is async. `jq -r .operation.id`, then `boat deletion status` |
| Hosted port shows nothing | The service bound loopback, not `0.0.0.0` |
| `--setup-file` machine looks empty | Setup runs in the background. Poll `.sandbox.setupStatus` |
| Detached job produced nothing | Read `<pid>.err.log`, not just `<pid>.log` |
| Long output looks cut off | Check `stdoutTruncated` on the `exec` result |
| Reached for `stop --force` | Only after a plain stop failed. It discards unsnapshotted work |
| Installed the toolchain again | `boat snapshot <id> <name>`, then `boat new --from <name>` |
| A snapshot lost the toolchain | It lived in `~/.cache`, which snapshots exclude |
| `chromium.launch()` says no executable | A fresh machine has no browsers. See Playwright on a sandbox |
| Set a TTL and called it cleanup | TTL stops the machine. Only `delete` removes it |
| A fork outlived the night | Forks reset to 1 hour and ignore `--no-auto-stop` |
| Pasted `boat env list` output | It holds every secret value. `jq 'del(.environments[].envContents)'` |
| Wrote a jq guard around `envContents` | It is a plain string, so the fallback branch prints the token. Use `del`, never a type check |
| Named the path in `del` | `env new` answers `.environments[]`, `env set` answers `.environment`. A wrong path removes nothing. Always `del(.. \| .envContents?)` |
| Rented a sandbox for someone else to touch | `boat new --no-env`. The default environment passes GitHub and secrets |
| Read `~/.config/ascii/token` | That one feeds the raw API. The CLI reads `~/.config/ascii/boat/config.json` |
| Wrote a script against `~/.ascii/bin/box` | Frozen legacy binary. Use `boat` |
