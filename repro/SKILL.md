---
name: repro
description: Use when a bug claim needs proving before anyone fixes it, such as a GitHub issue, a QA finding, a support ticket, an audit line, or a symptom described in prose, and no failing test exists yet. Also use when an existing test's result is the thing in doubt.
---

# repro

Turn a claim into a red test plus a named mechanism, or into a refutation that
survives review. Stop there. The fix is a separate turn.

## Procedure

1. **Search before you probe.** Grep the worklog by code identifier, never by the
   words that describe the symptom. A nonzero count is a list to open, every hit.
   Commands in `derive.md`.
2. **Quote the claim verbatim** in the spec's describe block. The reporter's
   words, not your paraphrase. You will reread them when the result surprises you.
3. **Pick the cheapest layer that shows the symptom.** Pure function, then store
   or reducer, then Playwright. Add a second layer only when the first cannot
   express the symptom.
4. **Read `derive.md` before the first Playwright line.** Ports, accounts, video,
   load, and the probe traps that have already cost a run.
5. **Run it, then run the control for the outcome you got.** See below.
6. **Name the mechanism with `file:line`.** A root-cause guess is not a finding.
   Label an untested mechanism a hypothesis, in those words.
7. **Write the artefact.** Red gets a spec plus a finding doc. Green gets a
   refutation doc. A refutation is a document, never a line in chat.
8. **Stop.** Hand the fix to `superpowers:systematic-debugging`. `pnpm verify` is
   the fixer's gate, not yours.

## The two controls

| Result | Run this control | Expect |
|---|---|---|
| red | remove the cause you named | green |
| green | inject the defect | red |

Green is the dangerous outcome. A red test gets read again by whoever fixes it.
A refutation closes a ticket and nobody looks twice.

Change one thing. A control that changes two things tells you nothing. Worked
examples with measured numbers: `controls.md`.

## A refutation refutes your probe first

The product is refuted only as far as the probe models it. When a test goes green
on a real user report, the report stays unexplained. Write that down, and name the
one observation that would decide it.

## Video

Every e2e repro spec opens with `test.use({ video: 'on' })`. The config is
`retain-on-failure`, so a green run loses its recording, and a refutation is
exactly the run you want to watch. Then chain `/playwright-video`, red or green.

Starting point: `spec-template.ts`.

## Where artefacts go

| Kind | Path |
|---|---|
| e2e | `derive-web/tests/e2e/repro/<slug>.spec.ts` |
| unit | `derive-web/tests/<mirrored path>/<name>.repro.test.ts` |
| finding or refutation | `docs/superpowers/findings/YYYY-MM-DD-<slug>.md` |
| branch | `repro/<issue>-<slug>`, worktree under `~/code/.worktrees/` |

Model doc: `docs/superpowers/findings/2026-08-18-c10-blank-ink-on-pan.md`. The
title states the conclusion. The reporter's words come first, verbatim. One bold
sentence names the mechanism. Then `file:line` with the hunk.

## Red flags

- "The test is red, so the bug is confirmed." Which bug?
- "It passed, so I cannot reproduce it." Can the probe see anything at all?
- A zero in a pass line, as in `PASS 0 conflict(s) inspected`. Zero assertions ran.
- The test calls a helper the product path never calls.
- Your control changed two things.
- You are about to fix it. That is the next turn, and someone else's.
