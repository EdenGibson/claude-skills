---
name: verifying-thoroughly
description: Use when finishing non-trivial work where passing tests do not prove the system actually behaves correctly — UI features, integrations, cross-system changes, bug fixes whose original symptom needs reproduction, deployments, or anything user-facing. Requires triangulated, behavioral, adversarial evidence beyond unit tests before claiming done.
---

# Verifying Thoroughly

## Overview

Tests passing means *the assertions you wrote* hold. It does not mean the system works. Real verification proves *behavior*, not assertions.

**Core principle:** Evidence of actual behavior, from multiple independent angles, beats any single signal.

**Violating the letter of this rule is violating the spirit of this rule.**

## Sister Skill

`verification-before-completion` covers the baseline: run the command, read the output, never claim without evidence. **This skill kicks in when "I ran the tests" is not sufficient evidence** — non-trivial, cross-system, user-facing, or hard-to-test work.

## The Iron Law

```
TESTS PASSING ≠ SYSTEM WORKING

For non-trivial work, claim "done" only with behavioral evidence
from at least TWO independent angles, including the original symptom
for bug fixes.
```

## When This Applies

- UI / frontend features (must exercise in browser)
- Cross-system changes (DB + API + client must all show consistency)
- Integrations and external services (real request, real response, no mocks)
- Bug fixes (the *original symptom* must be the verification)
- Performance work, migrations, deployments (production-shaped check)
- Agent-delegated work (verify the diff and the behavior, don't trust the report)
- Anything where mocks could pass while production breaks

When NOT to use:
- Pure-function unit work fully covered by tests
- One-line obvious changes with no behavioral surface
- Cases already covered by `verification-before-completion` alone

## The Verification Hierarchy

Escalating strength of evidence. Reach for the highest level the situation supports.

| Level | Evidence | Sufficient for |
|-------|----------|----------------|
| 1. Static | Type-check, lint, build exit 0 | Sanity, not correctness |
| 2. Unit tests | Assertions hold in isolation | Pure functions, contracts |
| 3. Integration | Real dependencies (DB, network) | Component boundaries |
| 4. Behavioral | Exercise the actual feature path | User-facing work |
| 5. Triangulated | ≥2 independent sources agree | Cross-system claims |
| 6. Adversarial | Tried to break it; original symptom reproduced and fixed | Bug fixes, high-stakes |

If you stopped at level 2 for level-4-or-higher work, you have not verified.

## The Triangulation Rule

One source of truth proves nothing — the source itself might be wrong. For any claim, find a **second independent angle** that must also agree.

| Claim | Angle 1 | Angle 2 |
|-------|---------|---------|
| "API saved the record" | API 200 response | DB row exists with expected values |
| "Email sent" | Service returned success | Inbox actually received it |
| "Button works" | Click handler runs | UI state visible in DOM |
| "Migration ran" | Migration log says ok | Schema actually changed |
| "Deploy succeeded" | CI green | Live endpoint returns new build |
| "Agent did the work" | Agent's report | git diff shows actual changes |
| "Auth flow fixed" | Login succeeds | Token works on a protected route |
| "Cache invalidated" | Invalidation called | Fresh value returned next read |

Independent means: different tool, different layer, different process — not the same thing measured twice.

## The Adversarial Probe

Before claiming done, spend two minutes trying to break it.

- What's the obvious edge case I didn't test?
- What if input is empty / null / huge / malformed / wrong type?
- What if this runs twice / concurrently / offline / after a restart?
- What does failure mode look like — is it actually handled?
- Could this regress a feature elsewhere?
- What did I assume that I never verified?

If you can't think of an attack, you haven't tried.

## Red-Green for Bug Fixes

A fix is unverified until you've proven the fix is what fixed it.

```
1. Reproduce original symptom    → confirms you understand the bug
2. Apply fix                     → run verification → passes
3. Revert fix                    → run verification → MUST fail
4. Restore fix                   → run verification → passes again
```

If step 3 still passes, your "fix" wasn't the cause — the bug is still there, masked.

## Quick Reference: Methods Beyond Tests

When unit tests aren't enough, reach for these:

- **Manual exercise**: actually use the feature as a user would
- **Browser DevTools**: Network tab for real requests, Console for real errors, Elements for real DOM state
- **Database read**: `SELECT` the row you just wrote, with the values you expect
- **Log inspection**: tail logs while exercising the feature
- **curl / direct request**: bypass your client, hit the endpoint raw
- **Fresh process**: kill server, restart, verify state survives (or doesn't, as expected)
- **Different machine / browser / account / network**: rules out user-specific cache or local-only state
- **Diff inspection**: `git diff` — did the change you intended actually land, and only that
- **Revert-and-retest**: prove the change is what's responsible
- **Production-shaped run**: build + run in prod mode, not dev
- **Telemetry / monitoring / dashboards**: real-world signal, not synthetic
- **Different tool reading the same truth**: psql vs ORM, curl vs SDK, raw HTTP vs framework client
- **Boundary probes**: empty, max size, unicode, concurrent, repeated, offline
- **Visual/screenshot diff**: UI looks right, not just renders

## Red Flags — STOP

- "Tests pass, shipping it" (for UI / cross-system work)
- "It worked when I tried it once"
- "The agent reported success"
- "Should be fine, I changed only one thing"
- "I don't need to actually open the browser"
- "The mock returns the right value"
- "I already manually tested earlier"
- About to mark done without reproducing the original symptom (for fixes)
- About to claim deploy success without hitting the live endpoint
- About to trust a delegated agent's report without checking the diff
- Tired and wanting work over
- "Different work so this rule doesn't apply"

**All of these mean: do one more independent verification before claiming done.**

## Rationalization Table

| Excuse | Reality |
|--------|---------|
| "Unit tests pass" | Unit tests pass on the code you wrote, not the system |
| "Integration tests pass" | Did they hit a real DB? real network? or mocks? |
| "It worked locally" | Local ≠ deployed. Verify deployed. |
| "The mock returns success" | Mocks lie. That's their job. |
| "I'm confident" | Confidence isn't evidence |
| "Original bug is rare" | Then reproducing it *is* the verification |
| "Manual check is overkill" | Then prove tests cover behavior, not assertions |
| "Agent's diff looks right" | Read the diff line by line, then run it |
| "TypeScript compiled" | Compilation ≠ runtime correctness |
| "CI is green" | CI tests what you wrote. Did you write the right tests? |
| "Just this once" | No exceptions |
| "Spirit not letter" | Violating letter = violating spirit |
| "I can see in the code it should work" | Reading ≠ running |

## Workflow Checklist

For non-trivial work, copy this and check off before claiming done:

```
Verification Progress:
- [ ] Identified the actual user-visible behavior being claimed
- [ ] Picked verification level appropriate to the claim (≥4 for user-facing)
- [ ] Exercised the real path, not mocks
- [ ] At least 2 independent angles agree (Triangulation Rule)
- [ ] If a bug fix: red-green cycle done (revert → fail → restore → pass)
- [ ] Adversarial probe: spent 2 min trying to break it
- [ ] Read full output / diff / logs, not just exit code
- [ ] State the claim WITH the evidence, not before
```

## Pattern Examples

**UI feature done:**
```
✅ Ran feature in browser → saw expected DOM → checked Network for correct request → DB row exists → "Feature works: [evidence]"
❌ "Tests pass, should work in browser"
```

**Bug fix done:**
```
✅ Reproduced symptom → applied fix → symptom gone → reverted fix → symptom returns → restored fix → symptom gone → "Fixed: [red-green evidence]"
❌ "Added a test, it passes, fixed"
```

**Agent delegation done:**
```
✅ Agent reports success → read full git diff → ran the changed code → verified behavior → "Agent's work verified: [evidence]"
❌ "Agent said it succeeded, marking complete"
```

**Deploy done:**
```
✅ CI green → curl live endpoint → response includes new build hash → smoke-tested feature on prod → "Deployed: [evidence]"
❌ "CI green, deploy successful"
```

## The Bottom Line

Tests are a floor, not a ceiling.

For anything non-trivial: verify behavior from a second independent angle, reproduce the original symptom for bug fixes, and spend two minutes trying to break it.

If you don't have evidence from two independent angles, you don't have verification — you have hope.
