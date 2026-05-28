---
name: worktree-sync
description: "Fetch origin and rebase the current worktree branch onto main"
user_invocable: true
---

# /worktree-sync

Bring the current worktree branch up to date with main. This is useful
when the worktree has fallen behind and needs the latest changes.

## Step 1: Verify context

```bash
git rev-parse --show-toplevel
git branch --show-current
```

Confirm we are in a worktree (not main). If on main, tell the user
to run `git pull` instead.

## Step 2: Check for uncommitted changes

```bash
git status --porcelain
```

If there are uncommitted changes, warn the user and ask whether to
stash them first. If yes:

```bash
git stash push -m "worktree-sync: auto-stash before rebase"
```

## Step 3: Fetch and rebase

```bash
git fetch origin main
git rebase origin/main
```

If the rebase has conflicts:
1. Show the conflicting files
2. Ask the user how to proceed (fix conflicts or abort)
3. If abort: `git rebase --abort` and restore stash if applicable

## Step 4: Restore stash

If changes were stashed in Step 2:

```bash
git stash pop
```

If pop fails due to conflicts, warn the user.

## Step 5: Report

Show:
- How many commits the branch was behind
- Whether rebase succeeded
- Current branch status after sync
