---
name: worktree-cleanup
description: "Find and remove stale git worktrees and orphan directories"
user_invocable: true
---

# /worktree-cleanup

Identify and remove stale worktrees to reclaim disk space. A worktree is
stale if its branch has zero unique commits compared to main (meaning all
work was already merged or abandoned).

## Step 1: Inventory

Run from the repository root (NOT from inside a worktree):

```bash
git rev-parse --show-toplevel
git worktree list
```

If the current directory is inside a worktree, `cd` to the main worktree
first. The main worktree is always the first one listed.

## Step 2: Check each worktree branch

For each non-main worktree, run BOTH checks:

```bash
git log main..<branch> --oneline
git -C <worktree-path> status --porcelain
```

A worktree is **stale** ONLY if BOTH:
- `git log main..<branch>` produces zero output (no unique commits), AND
- `git status --porcelain` produces zero output (no uncommitted work)

If `git status` shows ANY output (modified, staged, or untracked files),
the worktree is **ACTIVE** — never classify as stale, regardless of
commit history. Uncommitted work is the most common cause of accidental
data loss.

## Step 3: Find orphan directories

List all directories in `.claude/worktrees/` and compare against the
`git worktree list` output. Any directory NOT in the git list is a
candidate orphan.

For each candidate, before treating it as removable:
- Check whether it contains a `.git` file/dir — if so, it may be a
  worktree whose metadata is broken, not a true orphan. Investigate
  rather than delete.
- Check for uncommitted work: `cd <path> && git status --porcelain`
  (if the dir still has a git link). Any output means the directory
  contains live work — classify as **ACTIVE-ORPHAN**, never auto-remove.
- Check for non-git files the user may have created (notes, scratch
  files, build artifacts they care about). When in doubt, ask.

Also check for stray worktrees outside `.claude/worktrees/` in the
`git worktree list` output.

## Step 4: Present findings

Show the user a table:

| Worktree | Branch | Status | Unique commits | Dirty files | Action |
|----------|--------|--------|----------------|-------------|--------|

Status values:
- **STALE** — zero unique commits AND zero dirty files. Safe to remove.
- **ACTIVE** — has unique commits OR uncommitted work. Never auto-remove.
- **ORPHAN** — directory only, no git tracking, no uncommitted work
  detected. Removable with confirmation.
- **ACTIVE-ORPHAN** — directory only but contains uncommitted work or
  user files. Never auto-remove; surface to user for manual review.

## Step 5: Confirm and remove

Ask the user which worktrees to remove. Default suggestion: all STALE
and ORPHAN ones. **Never** include ACTIVE or ACTIVE-ORPHAN in the
default suggestion — list them separately and require an explicit,
named confirmation per item before touching them.

For each confirmed removal:

1. **Git worktrees** (STALE): `git worktree remove <path>` (NO `--force`).
   Git will refuse if the worktree has uncommitted changes — this is
   the safety net. If it refuses, re-classify as ACTIVE and stop.
   Then `git branch -d <branch>` (safe delete — fails if not merged).
2. **Orphan directories**: confirm path is inside `.claude/worktrees/`
   or another known worktree storage area, then `rm -rf <path>`.
   Refuse to `rm -rf` any path outside that storage area without an
   explicit second confirmation.
3. **Stray worktrees** (outside .claude/worktrees/):
   `git worktree remove <path>` (NO `--force`) then `git branch -d <branch>`.

**`--force` is forbidden by default.** Only use `git worktree remove --force`
if the user has been shown the dirty file list and explicitly types
"force remove" (or equivalent unambiguous confirmation) for that
specific worktree. Never batch-force.

After all removals, run:
```bash
git worktree prune
```

## Step 6: Clean orphan branches

List branches with the `worktree-` or `agent-` prefix that have no
active worktree:

```bash
git branch --list 'worktree-*'
git branch --list 'agent-*'
```

For each such branch with zero unique commits vs main, delete it:
```bash
git branch -d <branch>
```

## Step 7: Report

Show: number of worktrees removed, branches deleted, and estimated disk
space recovered (count node_modules directories that were present).
