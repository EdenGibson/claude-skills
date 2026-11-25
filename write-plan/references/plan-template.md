# Handoff Plan Template

> **Before you change this file.** It was forked from `improve`'s template on 2026-07-31 so edits
> here don't silently alter every plan `improve` writes. **The executor-facing contract must stay in
> sync between the two**: the `> Executor instructions` + drift-check block, the `## Status` field set
> (`plan-executor` orders work by Priority/Effort/Depends-on), the `proof:*` tags on Done criteria,
> the `evidence: motion` marker, and the `plans/README.md` row format. Diff against
> `~/.claude/skills/improve/references/plan-template.md` before changing any of those; everything else
> is this skill's to tune. (`## Research` lives only here. `## Design constraints` was mirrored into
> `improve`'s template on 2026-08-01; it is *not* executor contract today — nothing in
> `plan-exec-tick.sh` parses it — so if a design-lint gate ever keys off the heading, both templates
> must then move together.)

Every plan is written for an executor model that has **zero context**: it has not seen the advisor session, the audit, the other plans, or any prior conversation. It may be a smaller/cheaper model. Assume it is competent at following explicit instructions and weak at filling gaps, recovering from ambiguity, or knowing when to stop.

Three properties make a plan executable by a weaker model:

1. **Self-contained context** — everything needed is in the file: paths, code excerpts, conventions, commands.
2. **Verification gates** — every step ends with a command and its expected result. The executor never has to *judge* whether it succeeded.
3. **Hard boundaries and escape hatches** — explicit out-of-scope list, and "STOP and report" conditions instead of letting the model improvise when reality doesn't match the plan.

File naming: `plans/NNN-short-slug.md`, numbered in recommended execution order.

---

## Template

```markdown
---
plan: "NNN"
title: "<same title as the heading below, minus the `Plan NNN:` prefix>"
priority: "P1"
effort: "S"
depends_on: "none"
issue: "<NNNN — only when this plan comes from a GitHub issue in THIS repo; write closes_issue: instead when the plan FULLY resolves it; delete this line otherwise>"
---

# Plan NNN: <Imperative title — what will be true after this plan>

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the `## Status` section at the
> top of THIS file. **Do not edit `plans/README.md`** — it is generated from
> each plan's front matter, and a CI check (`not-edited-on-branch`) fails any
> PR that touches it.
>
> **Drift check (run first)**: `git diff --stat <planned-at SHA>..HEAD -- <in-scope paths>`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1 | P2 | P3
- **Effort**: S | M | L
- **Risk**: LOW | MED | HIGH
- **Depends on**: plans/NNN-*.md (or "none")
- **Category**: bug | security | perf | tests | tech-debt | migration | dx | docs | direction
- **Planned at**: commit `<short SHA>`, <YYYY-MM-DD>
- **Issue**: <GitHub issue URL in this repo — when the plan comes from an issue, or when published via `--issues`; omit otherwise>
- **State**: TODO — <one line: when authored, against which SHA, and why>

**The YAML front matter and the `- **State**:` bullet are both REQUIRED** — they
are what `pnpm plans:index` reads to generate `plans/README.md`. A plan missing
either does not merely lose its row: the generator **throws** and refuses to
regenerate the index at all, so it breaks the ledger for every other plan too.
`- **State**:` is the only bullet that reaches the index's Status column; the
rest of this section is for humans. Keep it to one line (it becomes a table cell).

**Issue keys.** `closes_issue: "N"` means this plan fully resolves issue N: the
executor puts `Closes #N` in the PR body and GitHub closes the issue when the PR
merges. `issue: "N"` means related only: prose citation, no keyword, the issue
stays open after the fix merges. At most one key, same repo only, never a PR
number or an upstream URL, and `issue:` whenever you are unsure — a wrong
`issue:` leaves a report open (recoverable); a wrong `closes_issue:` closes a
live report on the person who filed it (not). `plan-number ship` reads whichever
key is present (falling back to the `- **Issue**:` bullet and writing `issue:`
in), then adds `planned`, removes `needs-triage`, and comments
`<!-- plan: NNN -->` on the issue. The index generator ignores both keys.

## Why this matters

2–5 sentences. The problem, its concrete cost, and what improves when this
lands. Written so the executor (and a human reviewer) understands the intent —
intent is what lets a correct judgment call happen when a detail is off.

## Current state

The facts the executor needs, inlined — never "as discussed" or "see audit":

- The relevant files, each with one line on its role:
  - `src/orders/api.ts` — order-list endpoint; contains the N+1 (lines 130–160)
- Excerpts of the code as it exists today (short, with `file:line` markers),
  enough that the executor can confirm it's looking at the right thing.
- The repo conventions that apply here, with a pointer to one exemplar file:
  "Error handling follows the Result pattern — see `src/lib/result.ts` and its
  use in `src/users/api.ts:40-60`. Match it."

## Research

**Required — never omit this section.** Built from sources you actually opened, not from memory —
by the research dispatch (`~/.claude/skills/write-plan/references/research-dispatch.md`, the fastest
route) or by searching directly. Exactly one of:

- **≥1 citation.** Each external fact this plan rests on (library/API behavior, version
  constraint, security advisory, best-practice choice, verbatim error string) with the URL and
  the date/version checked. Prefer primary sources — official docs *for the version in use*,
  release notes, the actual issue/PR/commit, advisories — over blog summaries, and cross-check
  two where the fact decides the approach. Name the reference implementation you modelled — an external URL, or an in-repo `file:line` when
  this codebase already contains the best exemplar — or "none found".
  Format each as: `- <fact the executor can act on> — <URL> (checked YYYY-MM-DD, <pkg>@<version>)`.
  Close with `**Approach verdict**: CURRENT | SUPERSEDED | DEPRECATED | INSECURE — <one line + URL>`.
- **The literal line** `No external surface — <reason>` where the reason names what you checked and
  found absent ("no library, API, version, security, best-practice or error-string angle"), not
  merely that the code is internal. "It's an internal refactor" restates the change; it is not a
  reason.

An empty or missing section means the research step was skipped, not that none was needed —
a source you actually opened beats recollection roughly 9 times out of 10, and the executor has no
way to catch what you misremembered. Never cite a URL you did not open; a plausible link you
inferred is worse than no citation, because it reads as verified.

Checkable: `plan-number research plans/NNN-slug.md` must print `cited` or `declared`, and must not
add `(no Approach verdict)` — citing sources proves you looked; the verdict is what checks the
decision you are handing to a zero-context executor.

## Design constraints

**Required whenever the change is user-visible** — any new/changed component, stylesheet,
layout, colour, spacing, typography, icon, motion, or copy shown in the product. Exactly one of:

- **The constraints, inlined**, so the executor never has to *choose* a visual value:
  - **Where the design system lives** — the doc path(s) that govern this surface and the one
    rule each imposes, quoted: "`docs/design/surface-elevation.md` — panels use
    `--surface-raised`, never a bespoke shadow."
  - **The exact tokens to use**, by name, with the file they're defined in: "`--color-accent`,
    `--space-3`, `--radius-md` (defined in `app/globals.css` `:root`)." Never "the accent
    colour" — name the variable. If no token exists for something the change needs, say so
    explicitly and state which STOP condition that triggers.
  - **The exemplar to mirror** — one existing component that already does this correctly, with
    `file:line`: "match the panel chrome in `components/canvas/RegionSidePanel.module.css:1-40`."
  - **The non-negotiables that apply here**, from the repo's own list (e.g. tokens before
    values / themed in every theme / `prefers-reduced-motion` respected / icons from the
    project icon set only). List only the ones this change can violate, not the whole charter.
- **The literal line** `No visual surface — <reason>` when nothing a user sees changes
  (pure logic, build config, tests, server-side).

A plan that touches a stylesheet or component and names no tokens is not self-contained: the
executor will invent a value, and an invented value is how hard-coded hex enters the codebase.
If the repo has **no** design system, write `No design system found — <what you checked>` and
name the closest existing component the executor should imitate instead.

## Commands you will need

| Purpose   | Command                  | Expected on success |
|-----------|--------------------------|---------------------|
| Install   | `pnpm install`           | exit 0              |
| Typecheck | `pnpm typecheck`         | exit 0, no errors   |
| Tests     | `pnpm test -- <filter>`  | all pass            |
| Lint      | `pnpm lint`              | exit 0              |

(Exact commands from this repo — verified during recon, not guessed.)

## Suggested executor toolkit

(Optional — include only when relevant skills/tools plausibly exist in the
executor's environment. Skip the section otherwise.)

- Skills the executor should invoke if available, and for what:
  "use `vercel-react-best-practices` when writing the memoization in step 3".
- Reference docs worth reading before starting, by path or URL.

## Scope

**In scope** (the only files you should modify):
- `src/orders/api.ts`
- `src/orders/api.test.ts` (create)

**Out of scope** (do NOT touch, even though they look related):
- `src/orders/legacy-api.ts` — deprecated path, scheduled for deletion;
  changing it wastes effort and risks the v1 clients still pinned to it.
- Any change to the public response shape — clients depend on it.

## Git workflow

(Filled from recon — match the repo's observed conventions.)

- Branch: `advisor/NNN-<slug>` (or the repo's branch-naming convention if one is evident)
- Commit per step or per logical unit; message style: <match repo, e.g. conventional commits — include an example from `git log`>
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: <imperative title>

What to do, precisely. Reference exact files/symbols. Include the target code
shape when it's load-bearing (the pattern to produce, not necessarily every
line).

**Verify**: `<command>` → <expected output>

### Step 2: ...

(Each step small enough to verify independently. Order steps so the codebase
is never broken between steps when possible — e.g. add new path, switch
callers, then remove old path.)

## Test plan

- New tests to write, in which file, covering which cases (list them:
  happy path, the specific bug/regression this plan fixes, named edge cases).
- Which existing test to use as the structural pattern:
  "model after `src/users/api.test.ts`".
- Verification: `<test command>` → all pass, including N new tests.

## Done criteria (machine-checkable — ALL must hold)

Each item is **one testable assertion** ending with a proof-class tag, so the plan-executor can bind
each promise to cited evidence: `proof:cmd` (a command runnable verbatim) | `proof:behavior` (a named
test asserts it) | `proof:ui` (provable by a probe screenshot) | `proof:data` (service-client
readback) | `proof:review` (subjective; grader-attested). Prefer mechanical classes; use
`proof:review` only when nothing runnable can prove it. Include at least one `proof:behavior` (or
`proof:ui`/`proof:data`) for the specific behavior this plan changes — not just type/lint/grep gates.
For changes a still screenshot cannot prove — animations/transitions, canvas or stylus interaction,
drag, multi-step flows — add a line `evidence: motion` anywhere in the plan: the executor then
attaches a 25fps GIF + raw webm of the probe run to its draft PR (PR-report spec §3.6).

**Every criterion must be satisfiable by a headless Linux executor** — no physical device, no iOS
simulator, no GUI, no toolchain absent from CI. A criterion that needs one is a plan the executor
cannot finish: either drop it, restate it as something a probe/test can prove, or mark the whole
plan operator-only and say so in Status. (Measured: this stalled plan 283 at a mandatory
`xcodebuild`-gated step.)

- [ ] `pnpm typecheck` exits 0 · proof:cmd
- [ ] `pnpm test` exits 0; new tests for <X> exist and pass · proof:cmd
- [ ] <the specific user-visible behavior this plan changes, stated as one assertion> · proof:behavior
- [ ] `grep -rn "<old pattern>" src/` returns no matches · proof:cmd
- [ ] No files outside the in-scope list are modified (`git status`) · proof:cmd
- [ ] This plan's own `## Status` section updated; `plans/README.md` NOT modified (it is generated — `git status` shows it clean) · proof:cmd

**When `## Design constraints` is non-empty, at least one criterion must bind it** — a promise
nothing checks is the failure mode this section exists to close. Prefer the mechanical form:

- [ ] No hard-coded colour added: `git diff --merge-base origin/main -- '*.module.css' | grep -E '^\+.*#[0-9a-fA-F]{3}'` returns no matches · proof:cmd
- [ ] Every icon added comes from the project icon set — no inline `<svg>` in the diff · proof:cmd
- [ ] <the surface> renders correctly in each supported theme · proof:ui
- [ ] New `transition`/`animation` declarations sit under a `prefers-reduced-motion` guard · proof:cmd

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts
  (the codebase has drifted since this plan was written).
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file.
- You discover the assumption "<key assumption>" is false.

## Maintenance notes

For the human/agent who owns this code after the change lands:

- What future changes will interact with this (e.g. "if pagination is added
  to this endpoint, the batching in step 2 must be revisited").
- What a reviewer should scrutinize in the PR.
- Any follow-up explicitly deferred out of this plan (and why).
```

---

## Index file: `plans/README.md`

Written once by the advisor after all plans, updated by executors:

```markdown
# Implementation Plans

Generated by the improve skill on <date>. Execute in the order below unless
dependencies say otherwise. Each executor: read the plan fully before starting,
honor its STOP conditions, and update your row when done.

## Execution order & status

| Plan | Title | Priority | Effort | Depends on | Status |
|------|-------|----------|--------|------------|--------|
| 001  | ...   | P1       | S      | —          | TODO   |
| 002  | ...   | P1       | M      | 001        | TODO   |

Status values: TODO | IN PROGRESS | DONE | BLOCKED (with one-line reason) | REJECTED (with one-line rationale — finding fixed independently or approach abandoned)

## Dependency notes

- 002 requires 001 because <reason>.

## Findings considered and rejected

- <finding>: not worth doing because <one line>. (So nobody re-audits it.)
```

## Quality bar — check before finishing each plan

- Could a model that has never seen this repo execute this with only the plan file and the repo? If any step requires knowledge from the advisor session, inline that knowledge.
- Is every verification a command with an expected result, not a judgment ("make sure it works")?
- Does every step name exact files and symbols, not "the relevant module"?
- Are the STOP conditions specific to this plan's actual risks, not boilerplate?
- Would a reviewer reading only "Why this matters" + "Done criteria" understand what they're approving?
- No secret values anywhere in the file — locations and credential types only.
- "Planned at" SHA is filled in and the in-scope paths in the drift check match the Scope section.
- Does the plan touch a component, stylesheet, icon, or motion? Then `## Design constraints` names **exact token variables**, an exemplar `file:line` to mirror, and the applicable non-negotiables — and one Done criterion binds them. "Use the accent colour" is a gap, not a constraint.
