---
name: glow-pane
description: Use when the user asks to view, preview, open, render, or "show me" a markdown file (plan, spec, findings doc, README, etc.) — opens it with glow in a new tmux split pane next to Claude Code so they can read it in-place without leaving the session. Triggers include "open that plan", "show me docs/X", "preview that", "view in glow", "pop it open", "render the markdown", "let me see it", "pull it up".
---

# glow-pane

Render a markdown file with `glow` in a fresh tmux split pane to the right of Claude Code. Replaces the manual "leave Claude Code → `cd` → `glow file.md` → come back" loop.

## When to use

- A plan, spec, findings doc, or any markdown file is the thing the user wants to *read*, not edit
- The user has just generated/written a doc and would obviously want to look at it
- They say "show me", "open", "preview", "render", "let me see it", "pop it up", "view it in glow", "pull it up"

**Don't use when:**
- The file isn't markdown — `glow` is markdown-only (use `bat`/`less` instead, or just Read it)
- The user wants to *edit* the doc (route to an editor instead)
- No tmux session is running (the script will tell you; fall back to summarising)

## How to invoke

Run the helper script via Bash. It handles path quoting, session detection, and error reporting:

```bash
~/.claude/skills/glow-pane/glow-pane.sh <path-to-file.md>
```

Accepts multiple files — glow will page through them in order:

```bash
~/.claude/skills/glow-pane/glow-pane.sh docs/plans/foo.md docs/plans/bar.md
```

Paths can be relative to cwd or absolute; the script calls `realpath` internally.

## Critical: don't read it back

**After opening the pane, do NOT use the `Read` tool on that file.** The whole point is to keep the document out of Claude Code's context window — the user reads it with their eyes. Just confirm the pane opened and what file is in it.

## Quick reference

| Situation | What to do |
|-----------|-----------|
| User says "show me the plan" right after you wrote one | Open it without asking — the path is obvious |
| Multiple recent docs, ambiguous reference | Ask which one (one-liner) before opening |
| File doesn't exist | Script returns exit 66; tell the user the path was wrong |
| No tmux running | Script returns exit 69; mention they need a tmux session, fall back to a short summary |
| User wants a permanent reference open while iterating | Mention they can keep the pane open; rerun on next file |

## Exit codes

- `0` — pane opened
- `64` — no file argument given
- `66` — file not found
- `69` — no tmux session available

## Notes on the tmux mechanics

- Uses `tmux split-window -h` (horizontal split = new pane on the right)
- Auto-detects target session: uses `$TMUX` if Claude Code is inside tmux, otherwise picks the first session from `tmux list-sessions`
- New pane's working directory is the file's parent dir, so if a shell drops out after glow exits the user lands somewhere useful
- The pane closes automatically when the user presses `q` in glow
- **Pane is auto-named** with the file's basename (e.g. `"foo-plan.md"`), or `"foo.md (+N more)"` for multi-file invocations. The script also enables `pane-border-status top` at window scope (not global), so the title is visible above the pane. Other tmux windows are unaffected.
