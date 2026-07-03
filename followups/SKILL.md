---
name: followups
description: Use at the end of a work session or when handing off to the next one. Triggers - "/followups", "wrap up", "wrap it up", "what's left", "where did we land", "summarize what we did", "recap", or just before /clear or ending a session. Do not use mid-task with active in-progress todos, or when the user wants a persisted plan file (use plans/ or the improve skill instead).
user_invocable: true
---

# /followups

An end-of-task wrap-up. Produces a short **Done / Open / Next** summary of the current session, **printed in chat only** — write no files.

**Core principle: ground every line in evidence, not memory.** A wrap-up is worthless if "Done" lists things that were never verified or "Next" invents work nobody discussed. Check git, todos, and the actual conversation before writing a single bullet.

## When to use

- Closing out a session: "wrap up", "what's left", "where did we land", "recap"
- Handing off to the next session or before `/clear`
- The user explicitly types `/followups`

**Do NOT use when:** you're mid-task with active in-progress todos (keep working), or the user wants a durable plan another agent will execute (use `plans/` or the `improve` skill — this skill writes nothing to disk).

## Step 1 — Gather evidence (batch these in parallel)

- `git log --oneline` for commits made this session + `git status` for uncommitted/untracked changes
- TodoWrite state — which todos are `completed` vs `pending`/`in_progress`
- Scan the conversation for explicit deferrals: "later", "out of scope", "punt", "skip for now", "follow-up", "TODO", "next session", "we should also"
- Whether verification (lint / test / build) was actually **run and passed this session** — not just attempted or assumed

## Step 2 — Classify honestly

| Bucket | Goes here | Evidence required |
|---|---|---|
| **Done** | Work that is committed, or changed + verified passing this turn | a commit SHA, or a green check you ran this session |
| **Open** | Uncommitted WIP, pending todos, failing/un-run checks, things deferred in conversation | the artifact exists but isn't finished/verified |
| **Next** | Concrete, self-contained actions for the next session | drawn from Open + explicit deferrals |

If something was done but **not verified**, it goes under Done with `(unverified)` — never silently promote it. This matches the repo rule: don't call anything done/passing without confirming it this turn.

## Step 3 — Print the summary (in chat, no files)

Terse and scannable. One line per item. Skip empty sections.

```
Done
- rename input focus ring → flat chrome parity (678f04c9)
- removed decorative drop-shadows (8be5a85e)
- coverage ratchet plan drafted: plans/021 (unverified — not yet wired to CI)

Open
- plans/021 floors not enforced in pnpm test:coverage
- 1 pending todo: backfill element-drawing tests (plan 022)

Next
- wire the coverage floors from plan 021 into the CI gate
- start plan 022: add the element-drawing test cases
```

## Rules

- **Write no files.** The deliverable is the chat message. Don't "save it" to `FOLLOWUPS.md`, a plan, or anywhere — the user chose in-chat output deliberately. If they later want it persisted, that's a separate ask.
- **No padding.** A two-line wrap-up is fine. Don't manufacture "Next" items to look thorough.
- **Each Next item stands alone** — actionable by a fresh session without re-reading this one.

## Common mistakes

| Mistake | Fix |
|---|---|
| "Done: fixed the bug" with no commit/test | Check git + whether the test ran. Unverified → mark it `(unverified)` or move to Open. |
| Inventing next steps from vibes | Pull Next only from real Open items and things actually deferred in the conversation. |
| Writing a file anyway | This skill prints to chat. Writing files is a different task. |
| Restating the whole session narratively | It's a scannable list, not a story. One line per item. |
