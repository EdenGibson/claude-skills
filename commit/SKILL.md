---
name: commit
description: "Verify (lint + typecheck), then generate a conventional commit"
user_invocable: true
---

# /commit

Smart commit workflow that verifies code quality before committing. Follow these steps:

## Step 1: Understand the changes

1. `git status` — see all modified, staged, and untracked files
2. `git diff` and `git diff --staged` — see what changed
3. `git log --oneline -10` — understand recent commit message style

## Step 2: Lint

Run the project's lint command (e.g., `npm run lint`, `pnpm lint`, or whatever is configured in `package.json`). Run from the project root or the appropriate subdirectory.

- If there are auto-fixable lint errors, fix them and re-stage the affected files
- If there are non-fixable lint errors, report them clearly and stop

## Step 3: Typecheck

Run the project's typecheck command if one exists (e.g., `npm run typecheck`, `pnpm typecheck`).

- If there are type errors, report them clearly and stop
- Do not proceed to commit if typecheck fails
- If the project has no typecheck script, skip this step

## Step 2.5 / 3.5: Skip checks if already run this session

Before running lint or typecheck, scan back through the current conversation for recent runs of these commands. If they have already been run on the same set of changes and passed, skip re-running them and note that checks were already verified. Only re-run if:
- New files were modified after the last check
- The previous run produced errors that needed fixing

## Step 4: Generate commit message

If all checks pass, analyze the diff to determine:

- **Type**: One of `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`
- **Scope**: Derived from changed file paths (e.g., `auth`, `api`, `ui`, `config`)
- **Message**: Concise description focusing on the "why", not the "what"

Format: `type(scope): message`

Examples:
- `fix(auth): handle expired refresh tokens on silent renew`
- `refactor(storage): extract sync retry logic into shared utility`
- `perf(canvas): cache 2D context ref instead of re-acquiring per frame`

## Step 5: Stage and commit

1. Stage the relevant files by name (do NOT use `git add -A` or `git add .`)
2. Commit with the generated message using a HEREDOC — do NOT add a co-author trailer
3. Run `git status` to verify the commit succeeded

## Important

- Do NOT push to the remote — only commit locally
- If there are no changes to commit, report that and stop
- Do not include unrelated files in the commit
