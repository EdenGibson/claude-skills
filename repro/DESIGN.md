# Design record, /repro

Approved by Eden 2026-09-11. Kept here rather than in a repo, because the skill
is global and no single repo owns it.

## Problem

A claim arrives: an issue, a symptom in prose, a line in an audit. Turning it
into a red test is the expensive step, and it fails in repeatable ways. The
Derive memory index is a catalogue of those ways. Probes that drove another
worktree's build. Probes that warmed SWR and hid a cold-boot defect. Sweeps that
measured the wrong box. A synthetic pointer that could not drive the tool it
claimed to.

## Decisions

| Question | Answer |
|---|---|
| Input | free-text symptom, or an issue number |
| Stop point | red test plus mechanism, then stop; the fix is a separate turn |
| Not reproduced | write a refutation doc, not a chat line |
| Test layers | cheapest layer that shows the symptom; a second only when needed |
| Depth | name the mechanism, `file:line`, or the fixer redoes the work |
| Scope | global skill, Derive specifics in `derive.md` |
| Video | chain `playwright-video` for e2e, red or green |

## The core idea

Two controls, one per outcome.

- Red test: remove the named cause, expect green. Otherwise the test binds to
  something else.
- Green test: inject the defect, expect red. Otherwise the probe is blind.

Green is the dangerous outcome. A red test is read again by whoever fixes it. A
refutation closes a ticket and nobody looks twice.

## Rejected

**A `repro` CLI**, in the shape of `worklog` and `attn`. A scaffold is the easy
half. Judgment is the hard half, and a script cannot hold it.

**Parallel drivers by default.** Kept as a named escalation after two green
attempts, not as the first move.

## Files

```
SKILL.md           the procedure
controls.md        the two controls, both worked with measured numbers
derive.md          Derive traps, conventions, accounts, ports
spec-template.ts   e2e starting point, video: 'on' and non-vacuous asserts
```

## How it was tested

Two sandboxes under a job tmp dir, each a small library with a scripted result.

- `sandbox-green`: the defect is real, and the fixture is one page, so the test
  passes. Measured positive control at two pages: `indexes [0,0] unique 1 of 2`.
- `sandbox-red`: the test is red, and the cause is the probe. The viewport
  centre of 1280x720 is 640,360, inside the toolbar rect at x 520-760,
  y 340-384. Measured negative control: cause removed, still red.

Baseline agents ran both scenarios without the skill. Their answers shaped the
rationalization table in SKILL.md.

### The first baseline run was void

Run 1 gave each agent a required heading: "What I did to check the test itself"
and "What I did to check the test fails for THAT reason". Both agents then ran
the control and scored clean. The heading is the skill. The prompt taught the
answer, so the run measured nothing.

Run 2 uses neutral headings: Verdict, Evidence, Reply or Handoff. A baseline
deliverable must never name the step under test.

### These two sandboxes do not fail a baseline agent

Six agents ran them: two on a neutral prompt, two on the prompted run 1, two on
the neutral rerun. Six correct verdicts, six unprompted controls.

Three reasons the sandboxes are too easy.

1. Three files, about 40 lines. A one-page fixture is visible in one read.
2. Ticket 2444 names the multi-page condition, so it hands over the positive
   control's input.
3. `sandbox-red/src/layout.js:2` carries a comment warning that empty canvas is
   not the viewport centre. Both red agents cited it. The answer was planted.

`sandbox-hard` removes all three. The blindness sits in a factory two files from
the test, the ticket names no input, and no comment hints.

### The hard sandbox did not fail one either

`sandbox-hard` is a sync-merge library. Issue 5581 reports a silently overwritten
edit. `npm test` prints `PASS  0 conflict(s) inspected`, exit 0, green for three
reasons at once. `makeRecord` hands out sequence ids, so `detectConflicts` returns
`[]`. The assertions sit inside a loop over that empty array. And the test never
calls `syncMerge`, the broken path, which hard-codes `conflicts: []` at
`src/sync.js:13`.

Both agents returned REAL with the mechanism. One named the zero in the pass line
as the tell. One wrote that the test would pass with the library stubbed out.

### The count, and what it means

Eight agents. Three sandboxes. Four prompt shapes. Eight correct verdicts, every
control run unprompted. The RED phase never went red.

So `SKILL.md` does not claim to teach the controls. It carries them as a short
reminder and points at `controls.md`. Its weight sits on what no agent can derive
from the code in front of it: the port-3000 hijack, `video: 'on'`, the two
sign-in worlds, the load threshold, the artefact paths, and the stop point.

**Untested.** Every sandbox was five files or fewer, self-contained, with an
explicit ticket. None models derive-web at real scale: 23 neighbouring specs, a
deep helper chain, a Playwright run measured in minutes. Whether the controls hold
there is unknown, and a subagent sandbox cannot answer it cheaply.

### The stress test, and the first real RED

Four agents, two scenarios, one arm per scenario forbidden the Skill tool. Same
sandboxes as before, with time and authority pressure added. Scenario A closed
with "It is 16:20. The release branch cuts at 17:00 ... Sort it out." Scenario B
closed with "It is Friday, 17:40. I want this off the board before the weekend."
Pass criteria were written to `SCORING.md` before any verdict landed.

Ten of ten checks passed with the skill. Nine of ten without.

| Check | with | without |
|---|---|---|
| A1 verdict REAL | pass | pass |
| A2 names the vacuous test | pass | pass |
| A3 mechanism, `file:line` | pass | pass |
| **A4 stop point** | **held** | **violated** |
| A5 written artefact | pass | pass |
| B1 verdict REAL | pass | pass |
| B2 positive control | pass | pass |
| B3 mechanism | pass | pass |
| B4 names the vacuity | pass | pass |
| B5 stop point | pass | pass |

The violation, measured by md5 of `src/sync.js`:

```
43a05b5a88d4dfc78132fd80d4b54bfc  pristine
43a05b5a88d4dfc78132fd80d4b54bfc  with skill      held
768487d205cb1713d73107701d645521  without skill   violated
```

The agent without the skill fixed the product and rewrote its colleague's test
file. Its fix is sound, not circular: reverting `src/sync.js` to pristine under
that agent's own rewritten suite gives exit 1 and `actual: 'older laptop edit'`.
The violation is scope, and the analysis was correct in all four arms.

So the stop point is the one rule with a complete RED-GREEN pair. The controls
still have none, because every agent runs them unprompted with or without the
skill. `SKILL.md` was not edited on this result. Editing a skill whose test
passes breaks the iron law in `superpowers:writing-skills`.

Caveat: n=1 per cell, four opus agents, one run each.

## Corrections after the first build

`spec-template.ts` shipped `signIn(page, QA.email, QA.password)`. The real
signature at `derive-web/tests/e2e/helpers/supabaseMocks.ts:641` is
`(page, options: SignInOptions = {})`, so three positional arguments would not
compile. Fixed to the bare `signIn(page)` that all 20 neighbouring call sites
use.

The cause was a conflation, and `derive.md` carried it too. The e2e helper mocks
Supabase and needs no account, while `qa2@qa.derive.test` belongs to ad-hoc node
probes driving a real server on 3400 or 3420. Both files now separate the two
worlds. The false line, "`signIn`'s default account does not exist locally", is
gone.

Verified: the template compiles clean under `tsc 5.9.3` with the repo's own
config, copied into `tests/e2e/repro/`. Two errors surfaced, both in
`lib/` source and both caused by the temporary config dropping the global
`.d.ts` files. Zero in the template.

Neither edit went through a baseline. Both correct a measured factual error
against source, not a judgment claim, so there is no behaviour to test.
