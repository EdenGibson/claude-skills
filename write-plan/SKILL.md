---
name: write-plan
description: Use when you've already decided on a discrete piece of work and want to file it as one self-contained plan in a repo's plans/ for a separate zero-context executor (e.g. the plan-executor loop) to implement. Triggers — "/write-plan", "write a plan", "save/capture this as a plan", "file this for the executor", "hand this off", "turn this into a plan". Not for discovering what to do (use improve) or plans this same session will execute itself (use writing-plans).
---

# Write Plan

## Overview

Turn **one already-decided piece of work** into **one self-contained plan file** at `plans/NNN-slug.md` in the repo root, formatted so a separate, zero-context, possibly cheaper executor (the `plan-executor` loop, or any fresh agent) can implement it without seeing this conversation.

The thinking is already done — **the plan is the product**, and its quality decides whether the executor succeeds. This is `improve`'s writing half without the audit: you are crystallizing a decision, not discovering one.

**Paths, defined once:** `plan-number` = `~/.claude/skills/write-plan/bin/plan-number` · `references/` = `~/.claude/skills/write-plan/references/`

## When to Use

Use when the work is **already settled** in this session and you just need to capture it for handoff.

| Situation | Use |
|---|---|
| You need to **discover** what to do (audit a codebase → batch of plans) | `improve` |
| **This session** executes the work, with TDD checkpoints | `superpowers:writing-plans` (→ `docs/superpowers/plans/`) |
| You **already know** the one thing to do; file it for a zero-context executor | **this skill** |

**Do NOT use** when nothing is decided yet (brainstorm or `improve` first), or to write more than one plan.

**If a plan is overkill** (a one-line fix): say so and *offer to do it directly*. But while running this skill you **never edit source** — write the plan or hand the decision back; don't quietly switch to implementing.

## Workflow

1. **Identify the task** from this session — what we decided, which files, which approach. Don't re-derive it. If several threads are live, confirm which one. Syntax: `/write-plan [--local] [<hint>]`. The optional `<hint>` disambiguates or titles it. **`--local` changes step 8 only**: the plan and its README row stay uncommitted in this checkout, for the operator to commit by hand. Steps 2 to 7 run in full either way.

2. **Locate the destination — and check nobody got there first.** `git rev-parse --show-toplevel` → repo root; find/create `plans/`. Then, in order:
   - **Take the number from the tool, never by eye — `plan-number next`.** It returns the first number free across `origin/main`, every fetched ref, numbers retired by a rename, and untracked local plans, ignoring reserved bands (Derive's `900`/`901`/`902` make naive max+1 hand out `903`). Reading `origin/main` yourself is stale the moment another session pushes, and blind to your own uncommitted plans. Measured: **14% of plans claimed a number another already held; 4 slugs were silently dropped** — zero commits, zero files, anywhere. **The number stays provisional until step 8 claims it at push time.**
   - **Clear ghosts first — `plan-number ghosts`.** Untracked local plans whose slug already landed upstream under a *different* number: stale copies of shipped work. They inflate numbering and make the duplicate check fire on your own past self. Surface them; never delete unprompted. (Derive carried **11**.)
   - **Check for the same work.** Search `plans/` with `rg -l -F -- "<primary in-scope path>" plans/`. Search PRs with `gh pr list --search "<task terms>" --state all`. Treat matches as candidates to inspect. A shared path, component, or topic does not establish a duplicate.
     Compare plausible matches against the requested outcome, scope, and acceptance criteria. Read the relevant plan sections or PR details. Check current source before concluding merged work satisfies the request.
     - Different outcome: continue with the requested plan. Mention related work only where it affects execution.
     - Partial coverage: record what existing work covers and plan the unmet criteria. Add a dependency when execution requires the earlier work.
     - Full coverage: reuse the active plan or PR and report the exact matching criteria. If current source already satisfies the request, report that evidence without another plan. Respect an explicit request for a separate follow-up.
     - Uncertain coverage or unavailable search: record the limitation and continue. Ask only when a concrete conflict requires a user decision. Cite the conflicting requirements when that happens.
     Do not ask permission to proceed solely because a search returned matches. Keep this check targeted to the decided task.
   - Pick a short kebab slug → `plans/NNN-slug.md`.
   - **Sandbox with no network?** When `plan-number` prints `git fetch failed (offline?)` or `gh cannot resolve origin`, the number is a placeholder and the PR duplicate check did not run. Say both in your report. `ship` fixes the number later; nothing fixes the missed duplicate, so the caller must check coverage itself. *Measured 2026-11-14: all 34 issue-proposer runs hit this, and three pairs drew the same number (873, 889, 926).*

3. **Light verification (targeted, not an audit).** Read the in-scope files for **real `file:line` excerpts**. Read `package.json` / `Makefile` / CI for the **exact** test/lint/build/typecheck commands (never guess). Stamp `git rev-parse --short HEAD` + today's date into **Planned at**.
   - **You don't run those commands and don't need a local toolchain** — they run in the *executor's* environment. Copy them verbatim; a missing toolchain is expected. **Never invent a substitute verification harness.** Verify only that the excerpts and commands are real.
   - **Design recon — mandatory once the change is user-visible** (component, stylesheet, layout, colour, spacing, type, icon, motion, copy). Find the design system *before* writing: root `DESIGN.md`; `docs/design/` (or `design/`, `.design/`); the token/theme source (`globals.css` `:root`, `tokens.*`, Tailwind/theme config); the icon convention; `CLAUDE.md`/`AGENTS.md` design rules. Read only what governs *this* surface.
     Then **inline the decision, not the pointer**: exact token variable names + the file defining them, one exemplar component (`file:line`) that already does it right, and only the non-negotiables this change could violate. A pointer ("follow the design system") is worthless to an executor that won't read 2,700 lines; a named token is not. **You choose the visual values — the executor must never have to.** If the tokens don't cover it, say so and make it a STOP condition rather than licensing an ad-hoc value. No design system → `No design system found — <what you checked>` plus the closest component to imitate. Nothing user-visible → the literal line `No visual surface — <reason>`.
     *Measured (Derive, 2026-08-01): 201 of 324 plans touch `components/` or a stylesheet, but only 27% mention the design system — and 214 hard-coded hex literals sit in 31 of 118 `*.module.css` files.*
   - **From a GitHub issue? Put the issue in the front matter, one key only.** `closes_issue: "N"` when *nothing in the issue remains open after this plan ships*; `issue: "N"` when it is related, partial, or one of several plans. **Choose `issue:` when unsure**: a wrong `issue:` leaves a report open, which is recoverable; a wrong `closes_issue:` closes a live report on the person who filed it the moment the PR merges, with nobody looking. Same-repo issues only, never a PR number, never an upstream URL (plan 246 cites `mozilla/pdf.js#20899`; a bare number lifted from that would target a Derive issue). Keep the `- **Issue**: <url>` bullet in `## Status` too. `plan-number issue plans/NNN-slug.md` shows what `ship` will resolve it to. A bullet without either key is incomplete: `ship` will print the issue and refuse to commit until the author passes `--closes` or `--related`. *Measured 2026-09-12: 0 of 672 Derive plans carried `closes_issue:` and only 5 carried `issue:`, so the executor never emitted `Closes #N` from a plan.*
   - **Excluding an operator-gated area? Prove the change does not need it.** When Scope puts a path out of bounds for permission reasons (`supabase/functions/**`, `supabase/migrations/**`, native shells), trace the data path end to end and record the grep or test that shows nothing there must change. A claim like "the twin does not need the key" with no command behind it is a guess. If the area might need a change, write that change as an explicit operator-gated step and say so in `- **State**:`, rather than leaving it for a STOP condition to find. *Measured 2026-11-14: plans 923 and 927 both asserted an Edge Function exemption without checking, and both executors stopped on the same one-word `CONTENT_META_KEYS` edit, 2 of the 3 executor blocks in plans 916–974.*
   - **Dependencies match the State line.** If `- **State**:` names an unmerged branch or plan, `depends_on:` names it too, never `"none"` (plan 945).
   - **Bugfix? Reproduce it before writing the plan.** Trigger it (the failing test, the repro command, the relevant page) to observe *real* behavior: exact error text, stack trace, wrong-vs-expected values, which line throws. This is the one thing you *do* run here, and it routinely sharpens or **changes** the diagnosis — the obvious cause is often wrong. Fold it into **Current state** (the real symptom, not a guess) with the exact repro command the executor will use and a grounded root-cause. Can't run it → gather next-best evidence (stack trace, CI logs, Sentry) and **state in the plan that the symptom is reported, not reproduced**.

4. **Research online — every plan you are actually writing (after local recon, before writing).** Skip research if full coverage resolves the request or a concrete blocker requires user input. A search match alone does not stop this workflow.

   **A current authoritative source beats your own recollection roughly 9 times out of 10.** Your weights are a *lead*; a page you actually opened is a *fact*. Memory drifts, versions move, best practice turns over — and the zero-context executor inherits whatever you got wrong with no way to catch it. So this step is **not** sized by how confident you feel: confidence is the symptom, not the exemption.
   - **The deliverable is a complete `## Research` block — not a particular method.** Fastest path is the dispatch (`references/research-dispatch.md`), a copy-paste subagent prompt that returns one already formatted; use `deep-research` when the territory is broad or unfamiliar. Researching directly is fine — but **every field below is required**, so "how much is enough" is never yours to decide:
     **(a)** the installed version, read from `package.json`/lockfile *before* searching — research the version in use, never "latest"; **(b)** **≥2 independent sources** for any fact that decides the approach, primary over blog; **(c)** every citation carrying URL + version + date checked; **(d)** an explicit `**Approach verdict**: CURRENT | SUPERSEDED | DEPRECATED | INSECURE` with the URL establishing it; **(e)** a reference implementation to model, or "none found". `plan-number research` checks (d) mechanically.
     *Measured 2026-08-01: **12 of 318** Derive plans carried a single citation — the step fails because "how much is enough?" is a decision, and decisions get skipped when you're trying to finish. Both agents observed under test researched inline rather than dispatching, which is why the requirement is the block, not the method.*
   - **Validate the decided approach — don't silently re-decide it.** Research confirms the chosen *how* is still idiomatic and not deprecated/superseded/insecure, pins its details, and finds a reference implementation. Any verdict other than `CURRENT` → **STOP and surface it to the user**; that's their call, not a quiet swap buried in the plan. Record the confirmed approach and caveats in **Why this matters**; reference URLs in **Suggested executor toolkit**.
   - **The only way to skip is on the record.** There is no "obviously internal, no research needed" branch you take on your own authority — that judgment is exactly what the dispatch makes, *with sources open*. If the honest answer is no external surface, write the literal line `No external surface — <reason>` into `## Research`, the reason **naming what you checked and found absent** ("no library, API, version, security, best-practice or error-string angle"), not just "it's internal".
   - **Fold findings + URLs into the plan** — Current state, the approach/root-cause, *Suggested executor toolkit*, and inline citations where a fact decides something. A citation stranded in one section is one the executor won't connect to the work.
   - **Never cite a URL you didn't open.** An inferred link is a fabrication, and worse than no citation because it reads as verified.

5. **Write the plan** in the canonical template (below): every section present; every step ends in a runnable `Verify:` command with its expected result.

6. **Do not hand-edit `plans/README.md`.** The index is generated from each plan's front matter plus its `- **State**:` bullet: `ship` writes the row itself when none exists, and `.github/workflows/plans-index.yml` regenerates the whole index on every push to `main`. Get the front matter and State line right; that is the row. (A repo with no generator: add one row matching the existing columns.) *Measured 2026-11-14: 4 of 6 interactive runs grepped the `plan-number` source to resolve the old "add a row" vs "never edit README" conflict.*

7. **Self-review** against the quality bar (below); fix inline. **Run `plan-number research plans/NNN-slug.md`** — it must print `cited` or `declared`. `empty` or `missing` means step 4 didn't happen; go back and run the dispatch. Last point where fixing it is free.

8. **Land the plan, then report and stop.** **Don't** execute the plan and **don't** open a PR — but **do** commit+push the plan file itself, unless `--local` was passed. State the path written and the commit.
   - **`--local` passed: skip the ship, leave the files.** Do not run `plan-number ship`, do not commit, do not push, do not delete the local copy. `plans/NNN-slug.md` stays as an uncommitted file in the current checkout, where the operator can read them in place. The number stays provisional and no issue label flips. Report the path and the provisional number, then say the plan is inert until the operator lands it: `plan-number ship plans/NNN-slug.md` re-fetches and renumbers when they are ready. Then stop. Every bullet below describes the default path.
   - **Handoff reality:** `plan-executor` only runs plans **committed and pushed to `origin/main`** with a `TODO` row in `plans/README.md` — it `reset --hard`s and never reads uncommitted files. An uncommitted plan is **inert and invisible**; that is how 4 plans were lost outright.
   - **Ship it with the tool — `plan-number ship plans/NNN-slug.md`. Do not hand-roll the commit.** It re-fetches and, if your number was claimed while you were writing, renumbers the file, its `# Plan NNN:` heading and its README row; stages **only** those two paths; commits as `plan(NNN): <title>`; pushes to `origin/main` from a **throwaway worktree**, then removes it. Retries the fetch→renumber→push loop up to 3×. When a plan names its issue only in the Status bullet, pass exactly one choice: `--closes` or `--related`. `ship` prints the issue title and report, then blocks before the commit when the choice is absent.
     **Report the number it prints — it may not be the one you wrote.**
     **When the plan cites an issue, `ship` also marks it as spoken for**: `+planned`, `-needs-triage`, and a comment on the issue carrying `<!-- plan: NNN -->`. `--closes` writes `closes_issue: "N"`; `--related` writes `issue: "N"`. An explicit front-matter key needs no flag. A contradictory flag blocks before the commit. Label and comment writes remain idempotent and warn-only: a failed flip prints a `⚠` line and the plan is still on `main`. Repeat any such line to the user. This is the only place in the fleet that edits issue labels; no loop has that authority, and the `issue-work` skill that once did was removed 2026-08-03.
     **`ship` also re-runs the research check and prints a `⚠ RESEARCH MISSING` banner when the plan has no citations and no opt-out line. Warn-only — the push still succeeds — so the banner is the entire mechanism. If it fires, repeat it to the user verbatim and say the plan shipped unresearched.** Reporting "shipped ✓" while it fired is a false report. (Warn-only is deliberate: the `plan-executor` loops ship unattended and a hard gate would strand them.)
   - **This is what makes a dirty checkout or a feature branch safe** — the throwaway worktree means your tree is never touched, stashed, rebased or checked out, so "I'm on a branch / the checkout is dirty" stops being a reason a plan gets stranded off `main`. After a successful push the tool deletes the local copy (a lingering copy is how the 11 ghosts were born); `git pull` to get the landed version.
   - **Standing grant (Eden, 2026-07-31): commit and push the plan yourself, by default.** Scope is exactly `plans/NNN-slug.md` plus its `plans/README.md` row, on `main`. Never source, never a PR, never anything else in the same commit. A deliberate, measured exception to the repo's "don't commit without asking" posture — Eden typed the ship command himself in **9 of 17** hand-offs. `plan-number ship` enforces this scope mechanically, which is the point. `--local` is the per-invocation opt-out from this grant.
   - Say what you committed. `--local`, or being told *not* to commit this session, means the same thing: honour it and say the plan is inert until they commit it.

## Plan format

**REQUIRED REFERENCE:** read `references/plan-template.md` before writing. It is the format `plan-executor` consumes; don't invent another. (Editing the template itself? Its header carries the sync rules against `improve`'s copy — read them first.)

Three properties make a plan executable by a weaker, zero-context model — all mandatory:

1. **Self-contained** — every path, excerpt, convention and command is in the file. Never "as we discussed" or "see above."
2. **Verification gates** — each step ends with a command and its expected result, so the executor never has to *judge* success. These run in the **executor's** environment; you record them, you don't execute them.
3. **Hard boundaries + escape hatches** — explicit in/out-of-scope lists and "STOP and report" conditions instead of improvising.

Required sections: title • executor instructions + drift check • Status (priority/effort/risk/depends/category/planned-at **plus the `- **State**:` bullet — it is the ONLY line that reaches the index's Status column; omit it and `pnpm plans:index` silently files the plan as bare `TODO`, which is how plans 408–413 lost their real "NOT STARTED, needs a human decision" status) • Why this matters • Current state (with excerpts) • **Research (≥1 cited URL, or the literal line `No external surface — <reason>`)** • **Design constraints (named tokens + exemplar `file:line` + applicable non-negotiables, or the literal line `No visual surface — <reason>`)** • Commands you will need • Scope (in / out) • Git workflow • Steps (each with `Verify`) • Test plan • Done criteria (machine-checkable) • STOP conditions • Maintenance notes.

Optional marker: a line `evidence: motion` anywhere forces the executor to attach motion evidence (25fps GIF + raw webm of the probe run) to its draft PR — for animations/transitions, canvas/stylus interaction, drag, or multi-step flows a still screenshot can't prove (loop-architecture PR-report spec §3.6).

## Quality bar — check before finishing

- Could an agent that never saw this repo execute it from **only the file + the repo**? Inline anything that fails this.
- Every verification a **command with an expected result**, not "make sure it works"?
- Every step names **exact files/symbols**, not "the relevant module"?
- **Bugfix?** Reproduced **before writing**, with the *real* symptom (exact error / wrong value / stack trace) inlined into Current state — not a guess? (Or the plan says it couldn't be reproduced locally.)
- **Did `plan-number research plans/NNN-slug.md` print `cited` or `declared`, with no `(no Approach verdict)`?** Run it — don't eyeball it. Either ≥1 cited URL (version/date checked) for every library/API/version/security/best-practice/error-string fact, or `No external surface — <reason>` naming what you checked and found absent. No third option, and every URL one you actually opened. A cited block with **no verdict** means you looked things up but never checked whether the *decided approach* still holds — which is where step 4's measured value came from. *Most-skipped step in the skill — measured 2026-08-01, **12 of 318** plans carried a citation and **0** carried the opt-out. It stayed at 3.8% because nothing checked; now `research` and `ship` do, warn-only.*
- **Does `## Design constraints` decide rather than defer?** Exact token variable names (not "the accent colour"), the file defining them, one exemplar `file:line`, the non-negotiables at risk — plus **≥1 Done criterion binding it** (no-new-hex grep, icon-set check, per-theme `proof:ui` shot, reduced-motion guard). Otherwise `No visual surface — <reason>`. No third option. *A plan that touches a stylesheet and names no token is how invented values enter the codebase.*
- **Decided approach validated, not silently swapped?** Any conflict surfaced to the user, not quietly replaced.
- **From an issue?** Exactly one of `closes_issue:` / `issue:` in the front matter, same repo, and the key chosen by answering "does anything in the report remain after this ships?" rather than by how complete the fix feels. `plan-number issue <file>` names the issue it resolved to; `none` on a plan you wrote from an issue means the reference is missing.
- **STOP conditions** specific to this plan's real risks, not boilerplate?
- **No secret values anywhere** — credential *type* + `file:line` only.
- **Every Done criterion runnable by a headless Linux executor?** No physical device, iOS simulator, GUI, or toolchain absent from CI — or the plan is marked operator-only in Status. (Plan 283 stalled on an `xcodebuild` gate nothing in the fleet can run.)
- **Planned at** SHA filled, drift-check paths match Scope.
- **Did the destination checks run?** Use `plan-number next`; report ghosts; search plans and PRs. Judge candidate matches by outcome and acceptance criteria. A shared path alone must not prevent the requested plan.
- **Every operator-gated exclusion in Scope backed by a recorded grep or test**, or turned into an explicit operator-gated step? `depends_on:` agrees with the State line?
- Exactly **one** plan; README not hand-edited; landed via `plan-number ship` and the **number it printed** reported. With `--local`: left uncommitted in the checkout, nothing pushed, reported as inert with its provisional number.

## Hard rules

- **Only ever create/modify files under `plans/`.** Never edit source — this skill plans, it does not implement. *Sole carve-out:* step 3's reproduction may need a throwaway repro test; write it, use it, **delete it before finishing** — it is never part of the deliverable and never gets committed.
- **Never reproduce a secret value** — type + `file:line` only; recommend rotation if found.
- **Never implement the plan, never open a PR.** No `gh pr create`, no source commits. The one thing you *do* commit is the plan file itself, on `main`, per step 8's grant. With `--local` you commit nothing.
- **One plan per invocation.** Batches are `improve`'s job.

## Red flags — STOP

Catch yourself thinking any of these → re-read the rule:

| Thought | Reality |
|---|---|
| "I'm committing the plan anyway — I'll fold in that one-line source fix too" | The grant is *exactly* `plans/NNN-slug.md` + its README row. Anything else in that commit breaks it. |
| "Next number = highest `plans/NNN-*.md` in my checkout + 1" | Run `plan-number next`. Worktree-local numbering collided on 14% of plans and silently dropped 4. |
| "I'll `git fetch` and read `origin/main` myself — same result, one less tool" | Not the same: stale the moment another session pushes, blind to uncommitted plans in your own checkout, and it trips over reserved bands (900/901/902 → hands out 903). |
| "I picked the number correctly from `origin/main`, so it's mine" | Nothing reserved it. A number is only *claimed* when `ship` pushes it — which is why ship re-checks and renumbers. |
| "The checkout is dirty / I'm on a branch — I'll leave the plan and let Eden commit it" (no `--local`) | `ship` pushes from a throwaway worktree and never touches your tree. An uncommitted plan is inert and invisible; that is how 4 plans were lost. When Eden wants it left local, he passes `--local`. |
| "`--local` was passed, but the grant says commit by default and an uncommitted plan is inert — I'll ship it anyway" | The flag is the operator's instruction for this invocation and overrides the grant. Leave the files uncommitted and report them as inert. A push the operator opted out of is a false report, not a favour. |
| "`--local` means it isn't shipping, so I can skip `plan-number research`, the State line, or the number check" | Only step 8 changes. Steps 2 to 7 run in full: the operator lands the file later with `plan-number ship`, which expects a finished plan. |
| "A local `plans/` file already has this slug — it's a duplicate, stop" | Check `plan-number ghosts` first. 11 of Derive's untracked plans were stale copies of work that already landed at N+1 — a ghost, not a duplicate. |
| "Edge Functions are out of scope, and this change surely doesn't reach them" | Grep the key or symbol across the excluded tree and paste the result. Plans 923 and 927 skipped that and both blocked on a one-word Edge Function edit. |
| "Another plan touches this file, so I must stop" | Compare outcomes and acceptance criteria. Toolbar shortcuts and a toolbar inset change can touch the same file without duplicating work. |
| "`ship` renumbered my plan — I'll rename it back to the number I wrote" | It renumbered because your number was taken upstream. Report what it printed; renaming back re-creates the collision. |
| "It's a 2-line change / too trivial for a plan — I'll just fix it" | This skill never edits source. Write the plan, or offer to fix it directly — don't silently implement. |
| "It's from an issue and the fix looks complete — `closes_issue:` it is" | `closes_issue:` closes the report on the person who filed it the moment the PR merges, with nobody looking. Plan 245 fixed half of #1391; a blanket close would have shut a half-built request. Walk the report's symptoms; any one not covered means `issue:`. |
| "It's a bugfix — I'll describe the symptom from the report and write the plan" | Reproduce it *first* for real information (exact error, stack trace, wrong value); a guessed symptom misdiagnoses the fix. If you truly can't repro, say so in the plan. |
| "I know this library / API well enough — I'll write it from memory" · "I'm confident about this one — citing it is ceremony" | Confidence is the symptom, not the exemption. A source you opened beats recall ~9 times out of 10, and you cannot feel the 1 in 10 from the inside. Cite it or declare it. |
| "This one is genuinely internal — I'll just leave `## Research` out" · "It's an internal refactor" (as the whole reason) | An omitted section and a skipped step are indistinguishable — that is why **305 of 318** plans look identical to a skip. And "internal refactor" restates the change; it isn't a reason. Write `No external surface — <the angles you checked and found absent>`. |
| "I read `package.json` and the local code — that's my research" | Recon tells you *which version you're on*; it can't tell you whether that version's idiom changed, was superseded, or carries an advisory. **Measured:** a baseline agent on a `React.memo` plan checked React 19.2.7 / Next 16.1.6 locally, declared `No external surface`, ran **zero** searches — and missed the one question that decided the approach ("is manual memo still recommended now that React Compiler exists?"). Recon sets up the search; it never replaces it. |
| "The task is obviously routine — the security-flavoured ones are what need research" | Backwards. Overtly risky tasks *pull* research out of you anyway; routine-feeling ones are where skipping is invisible and unchallenged. That asymmetry is the whole failure mode. |
| "Eden said 'don't overthink it / file it quickly' — research is the part I trim" | Time pressure is exactly when recollection is most likely wrong and least likely checked. The dispatch is one subagent call — the cheapest thing in the plan. Trim scope, never sources. |
| "I did some searching and found a couple of links — the Research section is done" | Citations prove you *looked*; they don't prove the decision survives. The block needs all five: version read first, ≥2 independent sources, URL+version+date each, an explicit `Approach verdict`, and a reference implementation. `plan-number research` prints `(no Approach verdict)` when the last one is missing. |
| "The skill says dispatch a subagent, but I'll just search directly — close enough" | Fine, and expected — the requirement is the finished block, not the method. But researching inline puts "how much is enough?" back in your hands, which is the exact decision that gets skipped. If you go direct, walk the five fields deliberately. |
| "I'll drop in a URL I'm fairly sure is right so the section reads as done" | Never cite a page you didn't open. `plan-number research` can't tell the difference; the executor following a dead link can. A fabricated citation is worse than none — it reads as verified. |
| "`ship` printed RESEARCH MISSING but the push succeeded, so it's fine" | Warn-only means the banner **is** the check — there is nothing else. Repeat it verbatim and say the plan shipped unresearched. "Shipped ✓" while it fired is a false report. |
| "It's a UI change — I'll say 'follow the design system' and let the executor read the docs" | The executor is zero-context and possibly a cheaper model; it won't read 2,700 lines of design docs to style one panel. Name the exact tokens, the exemplar `file:line`, and the rules that apply. A pointer is a gap. |
| "There's no token for this exact shade — I'll pick a close hex so the executor isn't stuck" | Then the design system has a hole, and that's the user's decision, not a value you invent in a plan. Say the token is missing and make it a STOP condition. |
| "Research turned up a better approach than we decided — I'll just put that in the plan" | `write-plan` crystallizes the decision; it doesn't make a new one. Surface the conflict and let the user choose. |
| "To be self-contained, paste the exact secret so the executor can grep it" | Never. Type + `file:line` only; the executor greps by variable name; recommend rotation. |
| "The test/lint won't run here, so I'll write my own verify harness" | You don't run them and don't need a toolchain. Record the repo's real commands; the executor runs them. |
| "I'll reference what we decided earlier" | The executor has zero context. Inline it or it doesn't exist. |
| "I'll re-audit the codebase first to be safe" | The decision is made — crystallize it. Use `improve` when you actually need to discover. |
| "Close enough — I'll guess the command / say *the relevant module*" | Real `file:line` from reading the file; exact commands from `package.json`. |
| "I'll write plans for all of it" | One plan per invocation. Use `improve` for batches. |
