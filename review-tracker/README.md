# review-tracker

A Claude Code **statusline segment** that shows, per code review, whether it ran this
session and how many of its findings have been fixed:

```
PS Derive (main) | ████░░░░░░ 142k | rev: CR ✓ TN 3/4 | <task>
```

- **`CR ✓`** — `/code-review` (built-in command) **ran** this session. Run-state only
  (no count), set automatically by a hook. `/code-review` is compiled into the CLI and
  can't be instrumented for counts, so it's intentionally ran-only.
- **`TN a/b`** — the `thermo-nuclear-code-quality-review` skill: `b` findings raised,
  `a` fixed. Green `TN ✓` when complete (or a clean 0-finding review).
- Not-run reviews are omitted entirely.

> Not a model-invoked skill — this folder is a **versioned package** (no `SKILL.md`, so
> the skill loader ignores it). The live feature lives in `~/.claude/`; this is its source
> of truth for restore.

## How it works

| Piece | Lives at | Role |
|---|---|---|
| `bin/review-track` | `~/.claude/bin/review-track` | Sole writer of per-session state `~/.claude/skill-state/<session_id>.json`. Verbs: `ran` / `review <N>` / `fixed [k]` / `reset` / `show`. Resolves the session from `$CLAUDE_CODE_SESSION_ID` (or `--session`). |
| `hooks/review-detect.sh` | `~/.claude/hooks/` | On `UserPromptSubmit` + `PostToolUse(Skill)`, marks `cr`/`tn` as **ran** when it sees `/code-review` or the thermo-nuclear skill. |
| `hooks/prune-skill-state.sh` | `~/.claude/hooks/` | `SessionStart` housekeeping: deletes state files older than 7 days. |
| statusline patch | `~/.claude/hooks/status-line.sh` | Renders the `rev:` segment (placed *before* the task title so it can't be truncated off). See `snippets/status-line.snippet.sh`. |
| settings wiring | `~/.claude/settings.json` | Registers the two hooks + `statusLine`. See `snippets/settings.hooks.json`. |
| CR convention | `~/.claude/CLAUDE.md` | Tells Claude not to record CR counts, and to tick `review-track fixed tn` when applying thermo-nuclear fixes. See `snippets/CLAUDE.md.snippet`. |
| TN recording | `thermo-nuclear-code-quality-review/SKILL.md` | Appended step: the skill records its own `review tn <N>` count. |

**State shape:** `{ "cr": {"ran":true,"total":0,"applied":0}, "tn": {"ran":true,"total":4,"applied":4} }`
Keyed by `session_id`, so every new session starts clean.

## Reliability

- **Fully automatic:** the `ran` detection, rendering, and pruning (hooks + helper + script).
- **Best-effort:** the `TN a/b` counts depend on Claude following the convention / skill
  step. If missed, the number is **stale, never wrong**. (`/code-review` is ran-only
  precisely because its count couldn't be made reliable — it's a built-in.)

## Install / restore

```bash
~/.claude/skills/review-tracker/install.sh
```

Auto-deploys the helper, hooks, and CLAUDE.md convention. For the two **shared** files
(`status-line.sh`, `settings.json`) the installer detects whether the change is already
present and otherwise points you at the snippet in `snippets/` (it won't risk an
auto-patch). `snippets/status-line.sh.reference` is a full snapshot of a working
`status-line.sh` if you need to rebuild from scratch.

Hooks load at session start, so changes take effect in the **next** session. The
statusline re-reads `status-line.sh` on every refresh (no restart needed for render tweaks).

## Test

```bash
node --test ~/.claude/bin/review-track.test.mjs   # 8 tests
```

## Manual use

```bash
review-track show                 # inspect current session state
review-track review tn 5          # a review surfaced 5 findings (resets applied=0)
review-track fixed tn 2           # +2 applied  ->  TN 2/5
review-track ran cr               # mark /code-review as ran  ->  CR ✓
review-track reset                # clear this session
```

## Provenance

Design spec and implementation plan are in `docs/` (`spec.md`, `plan.md`).
