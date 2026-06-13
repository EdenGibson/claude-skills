# Review-tracker statusline segment — Design

**Date:** 2026-06-13
**Status:** Approved (design)
**Scope:** Personal Claude Code config (`~/.claude/`), not any project repo.

## Problem

When working in Claude Code, Eden runs two code reviews and wants the statusline to
show, per review: **(a) has it run this session, and (b) how many of its findings have
been fixed** — e.g. `rev: CR 3/5 TN 1/3`.

- **CR** = `/code-review` — the **built-in** Claude Code command (reviews the *current
  diff*, `--fix`/effort levels). Compiled into the CLI → **no file to edit/append to.**
- **TN** = `/thermo-nuclear-code-quality-review` — a **personal skill** at
  `~/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md` → **editable.**

Both are **review-only** (neither auto-links a finding to the edit that fixes it). Eden's
workflow: run a review, then **prompt Claude to apply the fixes in the same session.**

## Why this is non-trivial

- "A review ran" is reliably detectable via hooks.
- "Total findings (N)" must be captured at review time (Claude has them in context).
- "Applied (M)" ticks up *later*, when Eden prompts fixes — a **separate turn, outside
  the skill's execution**. Cross-turn behavior cannot live inside a skill body.
- `/code-review` is built-in → cannot be instrumented at the source.

Net: detection + rendering are rock-solid; the **counts depend on Claude following a
convention**. When the convention is missed the number goes **stale, never silently
wrong**. That is the accepted reliability floor.

## Data model

One JSON file per session: `~/.claude/skill-state/<session_id>.json`

```json
{ "cr": { "ran": true, "total": 5, "applied": 3 },
  "tn": { "ran": true, "total": 3, "applied": 1 } }
```

Keyed by `session_id`, so each new session starts empty automatically — no reset logic.
SessionStart only **prunes** files older than ~7 days (housekeeping).

Keys: `cr`, `tn`. Per key: `ran` (bool), `total` (int, findings surfaced by the latest
review), `applied` (int, fixes applied since that review). Missing key ⇒ not run.

## Components

### 1. `review-track` helper — `~/.claude/bin/review-track`

The **only** writer of the state file. Node script (node v24 available). Resolves the
session id from `$CLAUDE_SESSION_ID` (env) or a `--session <id>` flag; if neither is
available it is a no-op that exits 0 (never breaks a hook or a prompt). Atomic write
(write temp + rename). Auto-creates `~/.claude/skill-state/`.

Verbs:
- `review-track ran <cr|tn>` — set `ran=true` (leaves total/applied untouched; creates
  the key with `total=0, applied=0` if absent). Used by the detection hook.
- `review-track review <cr|tn> <N>` — a review just produced N findings → `ran=true`,
  `total=N`, `applied=0` (starts a fresh fix cycle).
- `review-track fixed <cr|tn> [k]` — `applied += k` (default 1), clamped to ≤ `total`
  when `total>0`.
- `review-track reset` — clear the current session's file.
- `review-track show` — print the current JSON (debugging).

Unknown key/verb ⇒ exit non-zero with a usage message, but never throw uncaught.

### 2. Detection hook — auto-set `ran=true`

Makes the segment appear as soon as a review runs, before counts exist. **The exact
hook event is the one genuine unknown** and is resolved by the first implementation step
(see Implementation step 1). Expected wiring:
- `/code-review` (built-in slash command) → most likely a `UserPromptSubmit` hook
  matching a prompt that begins with `/code-review` → `review-track ran cr`.
- `thermo-nuclear` (skill) → most likely a `PostToolUse` hook on the `Skill` tool whose
  payload names the skill → `review-track ran tn`.

A **dedicated** hook script (`~/.claude/hooks/review-detect.sh`) — not entangled with the
existing `update-task.sh` / `set-tab-title.sh`. Added as an additional entry in the
relevant hook arrays in `~/.claude/settings.json`.

### 3. Statusline patch — `~/.claude/hooks/status-line.sh`

Append a segment after the existing context/task segments. Reuses the script's existing
node-based JSON parsing. Reads `~/.claude/skill-state/$SESSION_ID.json`.

- Render only if ≥1 review ran this session (no clutter otherwise).
- Format per review: `CR <applied>/<total>` (and `TN …`), joined as `rev: CR 3/5 TN 1/3`.
- Not-run review ⇒ omitted, or shown dim as `CR –` only if the *other* ran (keep simple:
  omit not-run keys).
- Color: dim `–`/not-run; yellow when `applied < total`; green when `applied == total`
  and `total > 0`; for `total == 0` (ran, no findings) show `CR ✓` green.

### 4. The counts (split by what's possible)

- **TN total** → **append to the skill file**: a short post-review step instructing the
  reviewer to run `review-track review tn <N>` with the finding count. Scoped + reliable.
  Recording a *count* as a side-channel keeps the skill's "free-prose, no schema"
  deliverable intact.
- **CR total** → **`~/.claude/CLAUDE.md` convention** (built-in, cannot append): "after
  `/code-review`, run `review-track review cr <N>`."
- **Applied (both)** → **`~/.claude/CLAUDE.md` convention**: "as you apply each fix the
  user prompts for, run `review-track fixed <cr|tn>`."

## Testing

- **Unit (`review-track`):** each verb mutates JSON correctly; atomic write; missing-file
  and missing-session safe (no-op exit 0); `fixed` clamps to `total`; `review` resets
  `applied`. Run via node directly with a temp `--session`/temp HOME.
- **Statusline:** manually render each state — none, ran-no-findings, partial, complete —
  by seeding a state file and piping representative JSON to `status-line.sh`.
- **Detection probe (implementation step 1):** log `UserPromptSubmit` + `Pre/PostToolUse`,
  run each review once, confirm which event fires with what payload before wiring.

## Out of scope (YAGNI)

- Transcript-parsing to auto-derive counts (fragile; rejected).
- A manual `/fixdone` command (Eden prompts Claude to fix → Claude ticks; no hand-ticking).
- Tracking any review other than CR and TN.
- tmux status-bar rendering (Claude's own statusline only, per decision).

## Files touched

- **New:** `~/.claude/bin/review-track`, `~/.claude/hooks/review-detect.sh`,
  `~/.claude/skill-state/` (dir, runtime).
- **Edited:** `~/.claude/hooks/status-line.sh`, `~/.claude/settings.json` (hook wiring),
  `~/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md` (append step),
  `~/.claude/CLAUDE.md` (convention lines), `~/.claude/hooks/set-tab-title.sh` or a
  SessionStart entry (prune old state files).
