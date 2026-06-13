# Review-tracker Statusline Segment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Claude Code statusline segment `rev: CR 3/5 TN 1/3` showing, per code review (CR = built-in `/code-review`, TN = the `thermo-nuclear-code-quality-review` skill), whether it ran this session and how many of its findings have been fixed.

**Architecture:** A single node helper (`review-track`) is the sole writer of a per-session JSON state file keyed by `CLAUDE_CODE_SESSION_ID`. A hook auto-marks "ran". Counts are recorded by Claude via a CLAUDE.md convention (for CR) and an appended step in the TN skill (for TN). The existing `status-line.sh` reads the state file and renders the segment.

**Tech Stack:** node v24 (`node:test` for unit tests), bash hooks, Claude Code `settings.json` hooks + `statusLine`.

**Spec:** `~/docs/superpowers/specs/2026-06-13-review-tracker-statusline-design.md`

---

## Conventions for this plan

- **No git repo at `$HOME`.** "Commit" steps are replaced by **Checkpoint** steps (a verification you must see pass). If you want history, optionally `git init ~/.claude` before starting; otherwise skip.
- **Session id** is read from `CLAUDE_CODE_SESSION_ID` (confirmed present in the Bash environment). `review-track` also accepts `--session <id>` and falls back to `CLAUDE_SESSION_ID`.
- All paths are absolute. `~` means `/home/eden`.

## File structure

| File | Responsibility | Action |
|---|---|---|
| `~/.claude/bin/review-track` | Sole writer/reader of state file; verbs `ran`/`review`/`fixed`/`reset`/`show` | Create |
| `~/.claude/bin/review-track.test.mjs` | Unit tests for the helper | Create |
| `~/.claude/hooks/review-detect.sh` | Auto-mark `ran` from hook events | Create |
| `~/.claude/hooks/status-line.sh` | Render `rev:` segment | Modify |
| `~/.claude/settings.json` | Wire the detection hook + prune | Modify |
| `~/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md` | Append "record count" step | Modify |
| `~/.claude/CLAUDE.md` | CR count + applied-ticking convention | Modify |
| `~/.claude/skill-state/` | Runtime state dir | Auto-created |

---

## Task 1: `review-track` helper (TDD)

**Files:**
- Create: `~/.claude/bin/review-track`
- Test: `~/.claude/bin/review-track.test.mjs`

- [ ] **Step 1: Write the failing tests**

Create `~/.claude/bin/review-track.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = fileURLToPath(new URL('./review-track', import.meta.url));

function run(args, { home, session = 'sess1' } = {}) {
  return execFileSync('node', [SCRIPT, ...args], {
    env: { ...process.env, HOME: home, CLAUDE_CODE_SESSION_ID: session, CLAUDE_SESSION_ID: '' },
    encoding: 'utf8',
  });
}
const statePath = (home, session = 'sess1') =>
  join(home, '.claude', 'skill-state', `${session}.json`);
const readState = (home, session = 'sess1') =>
  JSON.parse(readFileSync(statePath(home, session), 'utf8'));
const freshHome = () => mkdtempSync(join(tmpdir(), 'rt-'));

test('ran creates key with ran=true', () => {
  const home = freshHome();
  run(['ran', 'cr'], { home });
  assert.deepStrictEqual(readState(home).cr, { ran: true, total: 0, applied: 0 });
});

test('review sets total and resets applied', () => {
  const home = freshHome();
  run(['fixed', 'cr', '2'], { home });
  run(['review', 'cr', '5'], { home });
  assert.deepStrictEqual(readState(home).cr, { ran: true, total: 5, applied: 0 });
});

test('fixed increments by 1 by default and clamps to total', () => {
  const home = freshHome();
  run(['review', 'cr', '2'], { home });
  run(['fixed', 'cr'], { home });
  assert.strictEqual(readState(home).cr.applied, 1);
  run(['fixed', 'cr', '5'], { home });
  assert.strictEqual(readState(home).cr.applied, 2);
});

test('fixed before review increments from zero, ran=true, no clamp when total=0', () => {
  const home = freshHome();
  run(['fixed', 'tn', '3'], { home });
  assert.deepStrictEqual(readState(home).tn, { ran: true, total: 0, applied: 3 });
});

test('reset removes the session file', () => {
  const home = freshHome();
  run(['ran', 'cr'], { home });
  assert.ok(existsSync(statePath(home)));
  run(['reset'], { home });
  assert.ok(!existsSync(statePath(home)));
});

test('no session id is a silent no-op (exit 0, no file written)', () => {
  const home = freshHome();
  execFileSync('node', [SCRIPT, 'ran', 'cr'], {
    env: { ...process.env, HOME: home, CLAUDE_CODE_SESSION_ID: '', CLAUDE_SESSION_ID: '' },
    encoding: 'utf8',
  });
  const dir = join(home, '.claude', 'skill-state');
  assert.ok(!existsSync(dir) || readdirSync(dir).length === 0);
});

test('unknown key exits non-zero', () => {
  const home = freshHome();
  assert.throws(() => run(['ran', 'xx'], { home }));
});

test('cr and tn are independent', () => {
  const home = freshHome();
  run(['review', 'cr', '5'], { home });
  run(['review', 'tn', '3'], { home });
  run(['fixed', 'cr', '2'], { home });
  const st = readState(home);
  assert.strictEqual(st.cr.applied, 2);
  assert.strictEqual(st.tn.applied, 0);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test /home/eden/.claude/bin/review-track.test.mjs`
Expected: FAIL — every test errors because `~/.claude/bin/review-track` does not exist (spawn ENOENT / module not found).

- [ ] **Step 3: Write the helper**

Create `~/.claude/bin/review-track`:

```js
#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');

const STATE_DIR = path.join(os.homedir(), '.claude', 'skill-state');
const VALID_KEYS = new Set(['cr', 'tn']);
const USAGE =
  'usage: review-track <ran|review|fixed|reset|show> [cr|tn] [N] [--session ID]\n';

function getSessionId(argv) {
  const i = argv.indexOf('--session');
  if (i !== -1 && argv[i + 1]) return argv[i + 1];
  return process.env.CLAUDE_CODE_SESSION_ID || process.env.CLAUDE_SESSION_ID || '';
}
function stateFile(sid) {
  return path.join(STATE_DIR, `${sid}.json`);
}
function readState(sid) {
  try { return JSON.parse(fs.readFileSync(stateFile(sid), 'utf8')); }
  catch { return {}; }
}
function writeState(sid, state) {
  fs.mkdirSync(STATE_DIR, { recursive: true });
  const file = stateFile(sid);
  const tmp = `${file}.tmp.${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(state));
  fs.renameSync(tmp, file);
}
function ensureKey(state, key) {
  if (!state[key]) state[key] = { ran: false, total: 0, applied: 0 };
  return state[key];
}

function main() {
  const argv = process.argv.slice(2);
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--session') { i++; continue; }
    positional.push(argv[i]);
  }
  const [verb, key, n] = positional;
  const sid = getSessionId(argv);

  if (verb === 'show') {
    process.stdout.write(sid ? JSON.stringify(readState(sid), null, 2) + '\n' : '{}\n');
    return 0;
  }
  if (verb === 'reset') {
    if (sid) { try { fs.unlinkSync(stateFile(sid)); } catch {} }
    return 0;
  }
  if (!['ran', 'review', 'fixed'].includes(verb)) {
    process.stderr.write(`review-track: unknown verb "${verb}"\n${USAGE}`);
    return 2;
  }
  if (!VALID_KEYS.has(key)) {
    process.stderr.write(`review-track: unknown key "${key}" (expected cr|tn)\n`);
    return 2;
  }
  // Mutating verbs with no session id: silent no-op success (never break a hook/prompt).
  if (!sid) return 0;

  const state = readState(sid);
  const entry = ensureKey(state, key);

  if (verb === 'ran') {
    entry.ran = true;
  } else if (verb === 'review') {
    const total = parseInt(n, 10);
    if (Number.isNaN(total) || total < 0) {
      process.stderr.write('review-track: review requires a non-negative integer N\n');
      return 2;
    }
    entry.ran = true;
    entry.total = total;
    entry.applied = 0;
  } else if (verb === 'fixed') {
    const k = n === undefined ? 1 : parseInt(n, 10);
    if (Number.isNaN(k)) {
      process.stderr.write('review-track: fixed requires an integer k\n');
      return 2;
    }
    entry.ran = true;
    entry.applied += k;
    if (entry.total > 0 && entry.applied > entry.total) entry.applied = entry.total;
    if (entry.applied < 0) entry.applied = 0;
  }

  writeState(sid, state);
  return 0;
}

process.exit(main());
```

- [ ] **Step 4: Make it executable**

Run: `chmod +x /home/eden/.claude/bin/review-track`
Expected: no output, exit 0.

- [ ] **Step 5: Run tests to verify they pass**

Run: `node --test /home/eden/.claude/bin/review-track.test.mjs`
Expected: PASS — `# pass 8`, `# fail 0`.

- [ ] **Step 6: Checkpoint**

Run: `CLAUDE_CODE_SESSION_ID=demo /home/eden/.claude/bin/review-track review cr 5 && CLAUDE_CODE_SESSION_ID=demo /home/eden/.claude/bin/review-track fixed cr && CLAUDE_CODE_SESSION_ID=demo /home/eden/.claude/bin/review-track show && CLAUDE_CODE_SESSION_ID=demo /home/eden/.claude/bin/review-track reset`
Expected: prints JSON `{ "cr": { "ran": true, "total": 5, "applied": 1 } }`, then cleans up.

---

## Task 2: Statusline rendering

**Files:**
- Modify: `~/.claude/hooks/status-line.sh` (insert a `REV_SEGMENT` block before the final `PARTS` assembly)

- [ ] **Step 1: Seed a known state file for manual verification**

Run:
```bash
CLAUDE_CODE_SESSION_ID=slt /home/eden/.claude/bin/review-track review cr 5
CLAUDE_CODE_SESSION_ID=slt /home/eden/.claude/bin/review-track fixed cr 3
CLAUDE_CODE_SESSION_ID=slt /home/eden/.claude/bin/review-track review tn 3
CLAUDE_CODE_SESSION_ID=slt /home/eden/.claude/bin/review-track fixed tn 1
```
Expected: state file `~/.claude/skill-state/slt.json` exists with `cr 3/5`, `tn 1/3`.

- [ ] **Step 2: Add the rendering block**

In `~/.claude/hooks/status-line.sh`, immediately **after** the `CTX_SEGMENT` `fi` (the line that closes the context-meter `if` block) and **before** the `# Build the output line` comment, insert:

```bash
# --- Review tracker segment ---
# Reads ~/.claude/skill-state/$SESSION_ID.json (written by review-track).
# Renders e.g. "rev: CR 3/5 TN 1/3". Shown only if a review ran this session.
REV_SEGMENT=""
if [ -n "$SESSION_ID" ]; then
  REV_SEGMENT=$(SESSION_ID="$SESSION_ID" node -e '
    (() => {
      const fs = require("fs"), os = require("os"), path = require("path");
      const sid = process.env.SESSION_ID;
      let st = {};
      try {
        st = JSON.parse(fs.readFileSync(
          path.join(os.homedir(), ".claude", "skill-state", sid + ".json"), "utf8"));
      } catch { return; }
      const parts = [];
      for (const [key, label] of [["cr", "CR"], ["tn", "TN"]]) {
        const e = st[key];
        if (!e || !e.ran) continue;
        if (e.total > 0) {
          const done = e.applied >= e.total;
          const color = done ? "\x1b[32m" : "\x1b[33m";
          parts.push(`${color}${label} ${e.applied}/${e.total}\x1b[0m`);
        } else {
          parts.push(`\x1b[2m${label} ·\x1b[0m`);
        }
      }
      if (parts.length) process.stdout.write("rev: " + parts.join(" "));
    })();
  ' 2>/dev/null)
fi
```

- [ ] **Step 3: Append the segment to the output line**

In the same file, in the "Build the output line" block, **after** the existing `[ -n "$TASK" ] && PARTS="$PARTS | $TASK"` line, add:

```bash
[ -n "$REV_SEGMENT" ] && PARTS="$PARTS | $REV_SEGMENT"
```

- [ ] **Step 4: Verify rendering with the seeded state**

Run:
```bash
printf '{"cwd":"/home/eden/code/Derive","session_id":"slt","transcript_path":""}' \
  | bash /home/eden/.claude/hooks/status-line.sh
```
Expected: output ends with ` | rev: CR 3/5 TN 1/3` (CR yellow, TN yellow via ANSI codes).

- [ ] **Step 5: Verify the not-run case is clean**

Run:
```bash
printf '{"cwd":"/home/eden/code/Derive","session_id":"no-such-session","transcript_path":""}' \
  | bash /home/eden/.claude/hooks/status-line.sh
```
Expected: normal statusline with **no** `rev:` segment.

- [ ] **Step 6: Verify complete + clean states**

Run:
```bash
CLAUDE_CODE_SESSION_ID=slt /home/eden/.claude/bin/review-track fixed cr 2   # -> 5/5 (green)
CLAUDE_CODE_SESSION_ID=slt /home/eden/.claude/bin/review-track review tn 0  # -> TN · (dim)
printf '{"cwd":"/x","session_id":"slt","transcript_path":""}' \
  | bash /home/eden/.claude/hooks/status-line.sh
CLAUDE_CODE_SESSION_ID=slt /home/eden/.claude/bin/review-track reset
```
Expected: segment shows `rev: CR 5/5 TN ·` (CR green, TN dim).

- [ ] **Step 7: Checkpoint** — all six render cases above behaved as described.

---

## Task 3: Append count-recording step to the TN skill

**Files:**
- Modify: `~/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md` (append a new section at end of file)

- [ ] **Step 1: Append the section**

Append to the **end** of `~/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`:

```markdown

## Statusline tracking (count only)

After the review above is complete, record the finding count for the statusline tracker.
Run exactly once:

    ~/.claude/bin/review-track review tn <N>

where `<N>` is the number of distinct findings you raised (use `0` if you raised none).
This writes only a count to a small per-session file; it does **not** alter the free-prose
review, which remains the deliverable, and it introduces **no** structured finding schema.
If the user later asks you to apply fixes, run `~/.claude/bin/review-track fixed tn` once
per finding you resolve.
```

- [ ] **Step 2: Verify the skill still parses (frontmatter intact, file readable)**

Run: `head -5 /home/eden/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md && tail -12 /home/eden/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`
Expected: original `---`/`name:` frontmatter at top unchanged; new "Statusline tracking" section at the bottom.

- [ ] **Step 3: Checkpoint** — section appended, frontmatter untouched.

---

## Task 4: CLAUDE.md convention (CR count + applied-ticking)

**Files:**
- Modify: `~/.claude/CLAUDE.md` (append a new section)

- [ ] **Step 1: Append the convention**

Append to the **end** of `~/.claude/CLAUDE.md`:

```markdown

## Review tracking (statusline)

A statusline segment (`rev: CR a/b TN a/b`) tracks two code reviews via the helper
`~/.claude/bin/review-track`. Keep it current with these best-effort commands (they only
update a small per-session JSON file; if missed, the count is merely stale, never wrong):

- **After running `/code-review`:** run `~/.claude/bin/review-track review cr <N>` once,
  where `<N>` is the number of findings it surfaced (`0` if none).
- **The thermo-nuclear skill records its own `tn` count** — do not duplicate it.
- **When you apply a fix the user prompted for** in response to either review, run
  `~/.claude/bin/review-track fixed cr` (or `fixed tn`) once per finding you resolve.
```

- [ ] **Step 2: Verify**

Run: `tail -15 /home/eden/CLAUDE.md`
Expected: the new "Review tracking (statusline)" section is present at the end.

- [ ] **Step 3: Checkpoint** — convention appended.

---

## Task 5: Detection probe (collaborative — confirms hook wiring)

> This task needs the **user's real interactive session** because `/code-review` and the
> TN skill are user-triggered slash commands. It installs a temporary logging hook, asks
> the user to run each review once, then inspects the log. No production wiring yet.

**Files:**
- Create (temporary): `~/.claude/hooks/_probe.sh`
- Modify (temporary): `~/.claude/settings.json` (add `_probe.sh` to `UserPromptSubmit` and `PostToolUse`)

- [ ] **Step 1: Create the probe logger**

Create `~/.claude/hooks/_probe.sh`:

```bash
#!/bin/bash
INPUT=$(cat)
LOG="$HOME/.claude/skill-state/_probe.log"
mkdir -p "$(dirname "$LOG")"
{
  printf '=== %s ===\n' "${1:-event}"
  printf '%s\n' "$INPUT" | node -e 'let d="";process.stdin.on("data",c=>d+=c);process.stdin.on("end",()=>{let j={};try{j=JSON.parse(d)}catch{};console.log(JSON.stringify({hook_event_name:j.hook_event_name,session_id:j.session_id,tool_name:j.tool_name,prompt:(j.prompt||"").slice(0,60),tool_input_keys:Object.keys(j.tool_input||{})}))})' 2>/dev/null
} >> "$LOG"
exit 0
```

Run: `chmod +x /home/eden/.claude/hooks/_probe.sh`

- [ ] **Step 2: Temporarily wire the probe**

In `~/.claude/settings.json`, add to the `UserPromptSubmit` hooks array a new object, and to the `PostToolUse` hooks array a new object with `"matcher": ""` (match-all, temporary):

```json
{ "hooks": [ { "type": "command", "command": "bash /home/eden/.claude/hooks/_probe.sh UserPromptSubmit" } ] }
```
```json
{ "matcher": "", "hooks": [ { "type": "command", "command": "bash /home/eden/.claude/hooks/_probe.sh PostToolUse" } ] }
```

Validate JSON: `node -e 'JSON.parse(require("fs").readFileSync("/home/eden/.claude/settings.json","utf8"));console.log("ok")'`
Expected: `ok`.

- [ ] **Step 3: Ask the user to exercise both reviews (NEW session)**

Tell the user: start a fresh Claude Code session, then (a) run `/code-review`, and (b) run `/thermo-nuclear-code-quality-review`. Also, in that session, run a Bash command: `echo "SID=$CLAUDE_CODE_SESSION_ID"`.

- [ ] **Step 4: Inspect the probe log**

Run: `cat /home/eden/.claude/skill-state/_probe.log`
Record, for **each** review:
- Which `hook_event_name` carried the signal (`UserPromptSubmit` vs `PostToolUse`).
- For `UserPromptSubmit`: does `prompt` begin with `/code-review` / `/thermo-nuclear`?
- For `PostToolUse`: what is `tool_name` when the TN skill ran (e.g. `Skill`, or the skill name)?
- Confirm the `session_id` in the log equals the `SID=` printed by the Bash echo (proves `CLAUDE_CODE_SESSION_ID` == statusline `session_id`).

- [ ] **Step 5: Remove the temporary probe wiring**

Delete the two probe objects added in Step 2 from `~/.claude/settings.json`, then:
Run: `rm /home/eden/.claude/hooks/_probe.sh && node -e 'JSON.parse(require("fs").readFileSync("/home/eden/.claude/settings.json","utf8"));console.log("ok")'`
Expected: `ok` (settings still valid; probe removed).

- [ ] **Step 6: Checkpoint** — write the findings (events, prompt prefixes, tool_name, session-id match) into the top of Task 6 before wiring production hooks.

---

## Task 6: Production detection hook + settings wiring

> The hook below handles **both** likely signal shapes (a `prompt` field, or a `tool_name`/`tool_input` referencing a review), so it is correct regardless of Task 5's outcome. Task 5 only decides **which hook arrays** to register it in and the **PostToolUse matcher**.

**Files:**
- Create: `~/.claude/hooks/review-detect.sh`
- Modify: `~/.claude/settings.json`

- [ ] **Step 1: Create the detection hook**

Create `~/.claude/hooks/review-detect.sh`:

```bash
#!/bin/bash
# Auto-mark that a tracked review ran. Inspects the hook payload for either a /command
# prompt or a tool invocation naming a review. Never blocks (always exit 0).
INPUT=$(cat)
RT="$HOME/.claude/bin/review-track"

# Parse "session_id<TAB>lowercased-blob-of-relevant-fields".
PARSED=$(printf '%s' "$INPUT" | node -e '
  let d="";process.stdin.on("data",c=>d+=c);process.stdin.on("end",()=>{
    let j={};try{j=JSON.parse(d)}catch{}
    const sid=j.session_id||"";
    const blob=[j.prompt,j.tool_name,JSON.stringify(j.tool_input||"")]
      .join(" ").toLowerCase().replace(/\s+/g," ");
    process.stdout.write(sid+"\t"+blob);
  });' 2>/dev/null)
SID="${PARSED%%$'\t'*}"
BLOB="${PARSED#*$'\t'}"

emit() {
  [ -x "$RT" ] || return 0
  if [ -n "$SID" ]; then "$RT" "$@" --session "$SID" >/dev/null 2>&1 || true
  else "$RT" "$@" >/dev/null 2>&1 || true; fi
}

case "$BLOB" in
  *"/code-review"*|*'"code-review"'*|*"code_review"*) emit ran cr ;;
esac
case "$BLOB" in
  *"thermo-nuclear"*|*"thermo_nuclear"*|*"thermonuclear"*) emit ran tn ;;
esac
exit 0
```

Run: `chmod +x /home/eden/.claude/hooks/review-detect.sh`

- [ ] **Step 2: Unit-test the hook against synthetic payloads**

Run:
```bash
printf '{"session_id":"hooktest","prompt":"/code-review"}' | bash /home/eden/.claude/hooks/review-detect.sh
printf '{"session_id":"hooktest","tool_name":"Skill","tool_input":{"name":"thermo-nuclear-code-quality-review"}}' | bash /home/eden/.claude/hooks/review-detect.sh
CLAUDE_CODE_SESSION_ID=hooktest /home/eden/.claude/bin/review-track show
CLAUDE_CODE_SESSION_ID=hooktest /home/eden/.claude/bin/review-track reset
```
Expected: `show` prints `{ "cr": { "ran": true, ... }, "tn": { "ran": true, ... } }`.

- [ ] **Step 3: Wire into settings.json (using Task 5 findings)**

In `~/.claude/settings.json`:
- Add to the **`UserPromptSubmit`** hooks array (alongside `update-task.sh`):
```json
{ "hooks": [ { "type": "command", "command": "bash /home/eden/.claude/hooks/review-detect.sh" } ] }
```
- **Only if** Task 5 showed the TN skill fires via `PostToolUse` (not `UserPromptSubmit`), add to the **`PostToolUse`** array, using the `tool_name` observed in Task 5 as the matcher (commonly `Skill`):
```json
{ "matcher": "Skill", "hooks": [ { "type": "command", "command": "bash /home/eden/.claude/hooks/review-detect.sh" } ] }
```
  If Task 5 showed both reviews appear in `UserPromptSubmit` (the user types both slash commands), **skip** the PostToolUse entry — the UserPromptSubmit hook already covers both.

Validate JSON: `node -e 'JSON.parse(require("fs").readFileSync("/home/eden/.claude/settings.json","utf8"));console.log("ok")'`
Expected: `ok`.

- [ ] **Step 4: Checkpoint** — synthetic payloads mark `ran`, settings.json is valid JSON.

---

## Task 7: SessionStart pruning (housekeeping)

**Files:**
- Create: `~/.claude/hooks/prune-skill-state.sh`
- Modify: `~/.claude/settings.json` (add to existing `SessionStart` hooks array)

- [ ] **Step 1: Create the prune script**

Create `~/.claude/hooks/prune-skill-state.sh`:

```bash
#!/bin/bash
# Delete per-session review-track state files older than 7 days. Never blocks.
DIR="$HOME/.claude/skill-state"
[ -d "$DIR" ] && find "$DIR" -maxdepth 1 -type f -name '*.json' -mtime +7 -delete 2>/dev/null
exit 0
```

Run: `chmod +x /home/eden/.claude/hooks/prune-skill-state.sh`

- [ ] **Step 2: Wire into the existing SessionStart array**

In `~/.claude/settings.json`, add to the `SessionStart` hooks array (alongside `set-tab-title.sh`):
```json
{ "type": "command", "command": "bash /home/eden/.claude/hooks/prune-skill-state.sh" }
```
(Add this object inside the existing `SessionStart[0].hooks` array.)

Validate JSON: `node -e 'JSON.parse(require("fs").readFileSync("/home/eden/.claude/settings.json","utf8"));console.log("ok")'`
Expected: `ok`.

- [ ] **Step 3: Verify prune is safe on a fresh dir**

Run: `bash /home/eden/.claude/hooks/prune-skill-state.sh && echo "prune-ok"`
Expected: `prune-ok` (no error even if dir empty/absent).

- [ ] **Step 4: Checkpoint** — prune wired, runs cleanly.

---

## Task 8: End-to-end verification (live session)

- [ ] **Step 1: Re-run helper unit tests**

Run: `node --test /home/eden/.claude/bin/review-track.test.mjs`
Expected: `# pass 8  # fail 0`.

- [ ] **Step 2: Live walkthrough in a new session**

Ask the user (or do it, if executing interactively in a real session):
1. Start a fresh session → statusline shows **no** `rev:` segment.
2. Run `/code-review` → segment appears as `rev: CR ·` (ran, count pending) within a refresh.
3. Confirm Claude then ran `review-track review cr <N>` → segment becomes `rev: CR 0/N` (or `CR ·` if N=0).
4. Prompt Claude to fix one finding → after it applies, segment increments (`CR 1/N`).
5. Run `/thermo-nuclear-code-quality-review` → `TN` appears once it records its count.

- [ ] **Step 3: Confirm cross-session isolation**

Run: `ls /home/eden/.claude/skill-state/*.json`
Expected: one file per active session id; the live session's file reflects the walkthrough counts.

- [ ] **Step 4: Final checkpoint** — segment renders live, counts move on review + fix, sessions are isolated.

---

## Self-review notes (addressed)

- **Spec coverage:** data model (Task 1), helper verbs (Task 1), detection hook + probe (Tasks 5–6), statusline render incl. color/not-run/clean (Task 2), TN append (Task 3), CR + applied convention (Task 4), prune (Task 7), testing (Tasks 1, 2, 8). All spec sections mapped.
- **Session-id source:** confirmed `CLAUDE_CODE_SESSION_ID` (helper reads it; statusline uses stdin `session_id`; Task 5 step 4 verifies they match).
- **Naming consistency:** verbs `ran` / `review` / `fixed` / `reset` / `show` and keys `cr` / `tn` used identically across helper, tests, hook, statusline, skill, and CLAUDE.md.
- **`total=0` rendering:** rendered as dim `·` (covers both "ran, count pending" and "clean review"); never false-green.
