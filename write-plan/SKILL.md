---
name: write-plan
description: Use when you've already decided on a discrete piece of work and want to file it as one self-contained plan in a repo's plans/ for a separate zero-context executor (e.g. the plan-executor loop) to implement. Triggers — "/write-plan", "write a plan", "save/capture this as a plan", "file this for the executor", "hand this off", "turn this into a plan". Not for discovering what to do (use improve) or plans this same session will execute itself (use writing-plans).
---

# Write Plan

## Overview

Turn **one already-decided piece of work** into **one self-contained plan file** at `plans/NNN-slug.md` in the repo root, formatted so a separate, zero-context, possibly cheaper executor agent (the `plan-executor` loop, or any fresh agent) can implement it without seeing this conversation.

You already did the understanding — **the plan is the product**; its quality decides whether the executor succeeds. This is the *writing* half of the `improve` skill **without the audit**: the thinking is done; you are crystallizing it, not discovering it.

## When to Use

Use when the work is **already settled** in this session and you just need to capture it for handoff: "write a plan for that fix", "save this as a plan", "file this for the executor", "hand this off".

**Pick the right tool:**

| Situation | Use |
|---|---|
| You need to **discover** what to do (audit a codebase → batch of plans) | `improve` |
| **This session** executes the work, with TDD checkpoints | `superpowers:writing-plans` (→ `docs/superpowers/plans/`) |
| You **already know** the one thing to do; file it for a zero-context executor | **this skill** |

**Do NOT use** when nothing is decided yet (brainstorm or `improve` first), or to write more than one plan (that's `improve`'s batch job).

**If the task is so trivial a plan is overkill** (a one-line fix): say so and *offer to just do it directly* (a plain edit, or another tool) instead of ceremony. But while running this skill you **never edit source** — write the plan or hand the decision back; don't quietly switch to implementing.

## Workflow

1. **Identify the task** from this session — what we decided, which files, which approach. Don't re-derive it. If several threads are live, confirm which one. An optional `/write-plan <hint>` arg can disambiguate or title it.
2. **Locate the destination.** `git rev-parse --show-toplevel` → repo root; find/create `plans/`; next number = max existing `plans/NNN-*.md` + 1 (zero-padded to 3); pick a short kebab slug → `plans/NNN-slug.md`.
3. **Light verification (targeted, not an audit).** Read the in-scope files for **real `file:line` excerpts**. Read `package.json` / `Makefile` / CI for the **exact** test/lint/build/typecheck commands (never guess). Stamp `git rev-parse --short HEAD` + today's date into **Planned at**.
   - **You do not run those commands and do not need a working local toolchain** — they run in the *executor's* environment. Copy them verbatim; a missing local toolchain is expected and fine. **Never invent a substitute verification harness** to work around it. "Verify" only that the excerpts and commands are real.
4. **Write the plan** in the canonical template (below): every section present; every step ends in a runnable `Verify:` command with its expected result.
5. **Update `plans/README.md`** — add the index row (status `TODO`). If a README exists, **match its existing columns/format** (don't reformat); only generate from the template's index block when creating it fresh.
6. **Self-review** against the quality bar (below); fix inline.
7. **Report and stop.** State the path written. **Don't** execute the plan, and **don't** `git commit`/`push`/open a PR.
   - **Handoff reality:** the `plan-executor` loop only runs plans **committed and pushed to `origin/main`** with a `TODO` row in `plans/README.md` — it `reset --hard`s to `origin/main` and never reads uncommitted files. So the plan you just wrote sits **inert** until committed+pushed. If it's destined for that loop, say so and **offer to commit+push** it — don't do it silently (that's the user's call per the repo's git rules). If a human or this-session agent will pick it up instead, the file alone is enough.

## Plan format

**REQUIRED REFERENCE:** read the canonical template before writing — `~/.claude/skills/improve/references/plan-template.md` (the exact format `plan-executor` consumes; don't invent another).

Three properties make a plan executable by a weaker, zero-context model — all three are mandatory:

1. **Self-contained** — every path, excerpt, convention, and command is in the file. Never "as we discussed" or "see above."
2. **Verification gates** — each step ends with a command and its expected result, so the executor never has to *judge* success. These run in the **executor's** environment; you record them, you don't execute them.
3. **Hard boundaries + escape hatches** — explicit in/out-of-scope lists and "STOP and report" conditions instead of improvising.

Required sections: title • executor instructions + drift check • Status (priority/effort/risk/depends/category/planned-at) • Why this matters • Current state (with excerpts) • Commands you will need • Scope (in / out) • Git workflow • Steps (each with `Verify`) • Test plan • Done criteria (machine-checkable) • STOP conditions • Maintenance notes.

## Quality bar — check before finishing

- Could an agent that never saw this repo execute it from **only the file + the repo**? Inline anything that fails this.
- Every verification a **command with an expected result**, not "make sure it works"?
- Every step names **exact files/symbols**, not "the relevant module"?
- **STOP conditions** specific to this plan's real risks, not boilerplate?
- **No secret values anywhere** — credential *type* + `file:line` only.
- **Planned at** SHA filled, drift-check paths match Scope.
- Exactly **one** plan; `plans/README.md` row added.

## Hard rules

- **Only ever create/modify files under `plans/`.** Never edit source — this skill plans, it does not implement.
- **Never reproduce a secret value** — type + `file:line` only; recommend rotation if found.
- **Write-only.** Never run the plan, never `git commit`/`push`/`gh pr create`. Leave committing to the user (see step 7's handoff note).
- **One plan per invocation.** Batches are `improve`'s job.

## Red flags — STOP

Catch yourself thinking any of these → re-read the rule:

| Thought | Reality |
|---|---|
| "User said *get it moving tonight* — so commit & push it" | Write-only. The skill never commits; surface the handoff and let the user decide (step 7). |
| "It's a 2-line change / too trivial for a plan — I'll just fix it" | This skill never edits source. Write the plan, or offer to fix it directly — don't silently implement. |
| "To be self-contained, paste the exact secret so the executor can grep it" | Never. Type + `file:line` only; executor greps by variable name; recommend rotation. |
| "The test/lint won't run here, so I'll write my own verify harness" | You don't run them and don't need a toolchain. Record the repo's real commands; the executor runs them. |
| "I'll reference what we decided earlier" | The executor has zero context. Inline it or it doesn't exist. |
| "I'll re-audit the codebase first to be safe" | The decision is made — crystallize it. Use `improve` when you actually need to discover. |
| "Close enough — I'll guess the command / say *the relevant module*" | Real `file:line` from reading the file; exact commands from `package.json`. |
| "I'll write plans for all of it" | One plan per invocation. Use `improve` for batches. |
