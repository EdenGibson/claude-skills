---
name: worktree-ship
description: "Commit, push, create PR, and squash-merge a worktree branch onto main"
user_invocable: true
---

# /worktree-ship

Ship the current worktree's work onto main in one step: commit → push → PR → green CI → squash merge.

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
   - Run the project's typecheck command — stop on type errors
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

## Step 5: Merge only on green CI

Never merge a red or stale branch. `gh` is not installed on Eden's Mac; there, run every `gh` command over `ssh devbox`.

### 5a. Bring the branch up to date

```bash
git fetch origin main && git merge origin/main
```

Merge, never rebase, so the push never needs force. Resolve any conflicts. If a conflict needs a product decision, stop and ask the user. Then `git push`.

### 5b. Wait for CI on the exact head sha

```bash
sha=$(git rev-parse HEAD)
gh pr view <n> --json headRefOid --jq .headRefOid   # must print $sha
gh pr checks <n>
```

Poll `gh pr checks <n>` until no check is pending. Checks for a fresh push can take a minute to appear, so an empty list is not green.

### 5c. If any check is red, fix the root cause

1. Read the failure: `gh run view <run> --log-failed`
2. Find the root cause and fix it.
   - A flaky test counts as a bug. Write a test that reproduces the flake on every run, then fix the cause.
   - Never rerun CI or retry a test to get green.
3. Commit the fix with one `CI-Fix-Of` trailer naming the failed sha, and one `CI-Failed-Test` trailer per failed test file (in Derive, the path is relative to `derive-web/`). Leave out `CI-Failed-Test` when only lint, typecheck or build failed. CI then runs only the failed tests and the tests the fix reaches. That works only when the failed sha is the fix commit's parent, so make one plain commit on it, not a merge. Add the trailers only when every CI job on the failed sha finished with success or failure. A cancelled, timed-out or missing test shard leaves tests unrun, so commit without trailers and let CI run the whole PR's selection.

   ```bash
   git commit -F - <<'EOF'
   fix(scope): message

   CI-Fix-Of: <failed sha, 40 chars>
   CI-Failed-Test: tests/lib/foo.test.ts
   EOF
   ```

4. Push, then go back to 5b.

At most 2 fix rounds. If CI is still red after the second, stop and report.

### 5d. Merge only green

```bash
gh pr merge <n> --squash --delete-branch --match-head-commit "$sha"
```

`--match-head-commit` refuses the merge if the branch moved after CI ran. This squash-merges onto main and deletes the remote branch.

## Step 6: Report

Show:
- What was committed (if anything new)
- PR URL
- Merge commit on main

## Error handling

- **Lint/typecheck fails**: Stop and report. Do not push broken code.
- **Push fails**: Fetch and merge `origin/main` as in 5a, then push again. Never rebase or force push.
- **PR creation fails**: Check if a PR already exists for this branch. If so, use it.
- **Merge from main conflicts**: Resolve it. Stop and ask the user if the conflict needs a product decision.
- **CI is red**: Fix the root cause as in 5c. Never rerun CI or retry a test. After 2 fix rounds, stop and report the failing checks.
- **Merge fails**: If the head moved, go back to 5b for the new sha. Otherwise report the error. Never merge without green CI on the head sha.
## Important

- Do NOT add co-author trailers to commits.
- Always squash merge to keep main history clean.
- Do NOT clean up the worktree after merging. The user will clean up manually or via `/worktree-cleanup`.
