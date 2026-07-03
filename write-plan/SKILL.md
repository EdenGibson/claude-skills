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
   - **For a bugfix, reproduce the issue first — before writing the plan.** Actually trigger the bug (run the failing test, the repro command, the relevant script/page) to observe its *real* behavior: exact error text, stack trace, the wrong-vs-expected values, which line throws. Reproduction is the one thing you *do* run here — it's information-gathering, not the executor's verify-suite — and it routinely sharpens or **changes** the diagnosis (the obvious cause is often wrong). Fold what you learn into the plan's **Current state** (the real symptom, not a guess), the exact repro command/test the executor will use, and a grounded root-cause. If you genuinely can't run it locally, gather the next-best evidence (the report's stack trace, CI logs, Sentry) and **state in the plan that the symptom is reported, not reproduced**.
4. **Research online — deeply (after local recon, before writing).** Local facts gathered? Now search the web — for most plans this is where the biggest wins come from, and your own recollection drifts, so **treat current authoritative sources as ground truth** (per the global research rule) and cite them. This is also where you confirm the **best way to implement** the decided approach, not only where you verify facts.
   - **Validate the decided approach — don't silently re-decide it.** The *what* and *how* were chosen this session; use research to confirm that *how* is still current best practice (idiomatic, not deprecated / superseded / insecure), to pin down its implementation details, and to find a **reference implementation** to model. If research shows the decided approach is wrong, deprecated, or clearly worse than an alternative, **STOP and surface it to the user** — that's their decision, not a quiet swap buried in the plan. Record the confirmed approach (plus any caveat found) in **Why this matters**, and put reference docs/URLs in **Suggested executor toolkit**.
   - Run **several** targeted queries, not one: the **verbatim error string**, the exact package/API/symbol name **+ version**, "how to `<task>` in `<framework>`", "is `<chosen-lib>` still recommended/maintained", "`<lib>` deprecated / breaking change", "`<approach>` best practice", any relevant CVE/advisory.
   - **Follow into primary sources** — official docs *for the version in use*, release notes/changelogs, the actual GitHub issue/PR/commit, security advisories — not just blog summaries. Cross-check ≥2 sources and note the version + date (this stuff drifts).
   - For a bug, check whether it's **already known or fixed upstream** (issue tracker, changelog) — that can change the entire fix.
   - **Fold findings + URLs into the plan**: Current state, the chosen approach/root-cause, the *Suggested executor toolkit* (reference docs/URLs), and inline citations — so the zero-context executor inherits the references instead of re-deriving them.
   - For broad multi-source digging, dispatch a research subagent / the `deep-research` skill to keep this context lean. Skip only when the change is **purely internal logic with no external surface** (no library/API/version/security/best-practice/error-message angle) — and say so.
5. **Write the plan** in the canonical template (below): every section present; every step ends in a runnable `Verify:` command with its expected result.
6. **Update `plans/README.md`** — add the index row (status `TODO`). If a README exists, **match its existing columns/format** (don't reformat); only generate from the template's index block when creating it fresh.
7. **Self-review** against the quality bar (below); fix inline.
8. **Report and stop.** State the path written. **Don't** execute the plan, and **don't** `git commit`/`push`/open a PR.
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
- **Bugfix?** Did you **reproduce it before writing** and inline the *real* observed symptom (exact error / wrong value / stack trace) into Current state — not a guess? (If it couldn't be reproduced locally, the plan says so.)
- **Searched online deeply and cited it?** Any library/API/version/security/best-practice/error-string fact grounded in *current authoritative sources* (cross-checked, URLs inlined) — not recollection? (Or a note that the change has no external surface.)
- **Decided approach validated, not silently swapped?** Research confirms the chosen *how* is current best practice (not deprecated/superseded); any conflict was surfaced to the user, not quietly replaced.
- **STOP conditions** specific to this plan's real risks, not boilerplate?
- **No secret values anywhere** — credential *type* + `file:line` only.
- **Planned at** SHA filled, drift-check paths match Scope.
- Exactly **one** plan; `plans/README.md` row added.

## Hard rules

- **Only ever create/modify files under `plans/`.** Never edit source — this skill plans, it does not implement.
- **Never reproduce a secret value** — type + `file:line` only; recommend rotation if found.
- **Write-only.** Never run the plan, never `git commit`/`push`/`gh pr create`. Leave committing to the user (see step 8's handoff note).
- **One plan per invocation.** Batches are `improve`'s job.

## Red flags — STOP

Catch yourself thinking any of these → re-read the rule:

| Thought | Reality |
|---|---|
| "User said *get it moving tonight* — so commit & push it" | Write-only. The skill never commits; surface the handoff and let the user decide (step 8). |
| "It's a 2-line change / too trivial for a plan — I'll just fix it" | This skill never edits source. Write the plan, or offer to fix it directly — don't silently implement. |
| "It's a bugfix — I'll describe the symptom from the report and write the plan" | Reproduce it *first* to get real information (exact error, stack trace, wrong value); a plan built on a guessed symptom misdiagnoses the fix. If you truly can't repro locally, say so in the plan. |
| "I know this library / API well enough — I'll write it from memory" | Recollection drifts. Search current authoritative sources deeply, cross-check, cite URLs in the plan — versions, APIs, and best practices change. |
| "Research turned up a better approach than we decided — I'll just put that in the plan" | `write-plan` crystallizes the decision; it doesn't make a new one. Surface the conflict to the user and let them choose. |
| "To be self-contained, paste the exact secret so the executor can grep it" | Never. Type + `file:line` only; executor greps by variable name; recommend rotation. |
| "The test/lint won't run here, so I'll write my own verify harness" | You don't run them and don't need a toolchain. Record the repo's real commands; the executor runs them. |
| "I'll reference what we decided earlier" | The executor has zero context. Inline it or it doesn't exist. |
| "I'll re-audit the codebase first to be safe" | The decision is made — crystallize it. Use `improve` when you actually need to discover. |
| "Close enough — I'll guess the command / say *the relevant module*" | Real `file:line` from reading the file; exact commands from `package.json`. |
| "I'll write plans for all of it" | One plan per invocation. Use `improve` for batches. |
