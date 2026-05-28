---
name: worktree-ship
description: "Commit, push, create PR, and squash-merge a worktree branch onto main"
user_invocable: true
---

# /worktree-ship

Ship the current worktree's work onto main in one step: commit → push → PR → squash merge.

## Step 0: Verify context

```bash
git rev-parse --show-toplevel
git branch --show-current
```

- Confirm we are in a worktree (NOT on main). If on main, tell the user this skill is for worktrees only.
- Store the current branch name and worktree path for later cleanup.

## Step 1: Commit (reuse /commit logic)

1. `git status` — check for uncommitted changes
2. If there are changes to commit:
   - `git diff` and `git diff --staged` — understand what changed
   - Run the project's lint command — fix auto-fixable errors, stop on unfixable
   - Run the project's typecheck command if available — stop on type errors
   - Stage relevant files by name (NOT `git add -A`)
   - Generate a conventional commit message (`type(scope): message`)
   - Commit using HEREDOC, no co-author trailer
3. If there are no uncommitted changes, continue (prior commits will be shipped)

## Step 2: Verify there's work to ship

```bash
git log main..<branch> --oneline
```

If zero commits ahead of main, tell the user there's nothing to ship and stop.

## Step 3: Push

```bash
git push -u origin <branch>
```

If the branch already exists on the remote, just `git push`.

## Step 4: Create PR

Generate a PR title and body from the branch commits:

- **Title**: If single commit, use its message. If multiple, write a summary under 70 chars.
- **Body**: List all commits as bullet points.

```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Changes

<bullet list of commits>

EOF
)"
```

## Step 5: Squash merge

Immediately squash merge the PR:

```bash
gh pr merge --squash --delete-branch
```

This squash-merges onto main and deletes the remote branch.

## Step 6: Report

Show:
- What was committed (if anything new)
- PR URL
- Merge commit on main

## Error handling

- **Lint/typecheck fails**: Stop and report. Do not push broken code.
- **Push fails**: Report the error. Likely needs `git pull --rebase` or force push.
- **PR creation fails**: Check if a PR already exists for this branch. If so, use it.
- **Merge fails**: Report the error (likely merge conflicts). Tell the user to resolve manually.
## Important

- Do NOT add co-author trailers to commits.
- Always squash merge to keep main history clean.
- Do NOT clean up the worktree after merging. The user will clean up manually or via `/worktree-cleanup`.
