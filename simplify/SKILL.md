---
name: simplify
description: Use when asked to "simplify", "clean up", or review recently changed code for reuse, quality, and efficiency, or when /simplify is invoked. Reviews the diff and fixes issues found.
---

# Simplify: Code Review and Cleanup

Review all changed files for reuse, quality, and efficiency. Fix any issues found.

## Phase 1: Identify Changes

Run `git diff` (or `git diff HEAD` if there are staged changes) to see what changed. If there are no git changes, review the most recently modified files that the user mentioned or that you edited earlier in this conversation.

## Phase 2: Launch Three Review Agents in Parallel

Use the Agent tool to launch all three agents concurrently in a single message. Pass each agent the full diff so it has the complete context.

**Out-of-scope findings:** Each agent's primary job is the changed code — do not go hunting through the wider codebase. But if, while reviewing the diff, an agent *incidentally* notices a clear, unambiguous issue in adjacent code outside the diff (e.g. dead code, real duplication, an obvious bug), it must report it separately under an "Out of scope" heading. Do not fix out-of-scope issues — only report them, so Phase 4 can file them as GitHub issues.

### Agent 1: Code Reuse Review

For each change:

1. **Search for existing utilities and helpers** that could replace newly written code. Look for similar patterns elsewhere in the codebase — common locations are utility directories, shared modules, and files adjacent to the changed ones.
2. **Flag any new function that duplicates existing functionality.** Suggest the existing function to use instead.
3. **Flag any inline logic that could use an existing utility** — hand-rolled string manipulation, manual path handling, custom environment checks, ad-hoc type guards, and similar patterns are common candidates.

### Agent 2: Code Quality Review

Review the same changes for hacky patterns:

1. **Redundant state**: state that duplicates existing state, cached values that could be derived, observers/effects that could be direct calls
2. **Parameter sprawl**: adding new parameters to a function instead of generalizing or restructuring existing ones
3. **Copy-paste with slight variation**: near-duplicate code blocks that should be unified with a shared abstraction
4. **Leaky abstractions**: exposing internal details that should be encapsulated, or breaking existing abstraction boundaries
5. **Stringly-typed code**: using raw strings where constants, enums (string unions), or branded types already exist in the codebase
6. **Unnecessary JSX nesting**: wrapper Boxes/elements that add no layout value — check if inner component props (flexShrink, alignItems, etc.) already provide the needed behavior
7. **Nested conditionals**: ternary chains (`a ? x : b ? y : ...`), nested if/else, or nested switch 3+ levels deep — flatten with early returns, guard clauses, a lookup table, or an if/else-if cascade
8. **Unnecessary comments**: comments explaining WHAT the code does (well-named identifiers already do that), narrating the change, or referencing the task/caller — delete; keep only non-obvious WHY (hidden constraints, subtle invariants, workarounds)

### Agent 3: Efficiency Review

Review the same changes for efficiency:

1. **Unnecessary work**: redundant computations, repeated file reads, duplicate network/API calls, N+1 patterns
2. **Missed concurrency**: independent operations run sequentially when they could run in parallel
3. **Hot-path bloat**: new blocking work added to startup or per-request/per-render hot paths
4. **Recurring no-op updates**: state/store updates inside polling loops, intervals, or event handlers that fire unconditionally — add a change-detection guard so downstream consumers aren't notified when nothing changed. Also: if a wrapper function takes an updater/reducer callback, verify it honors same-reference returns (or whatever the "no change" signal is) — otherwise callers' early-return no-ops are silently defeated
5. **Unnecessary existence checks**: pre-checking file/resource existence before operating (TOCTOU anti-pattern) — operate directly and handle the error
6. **Memory**: unbounded data structures, missing cleanup, event listener leaks
7. **Overly broad operations**: reading entire files when only a portion is needed, loading all items when filtering for one

## Phase 3: Fix Issues

Wait for all three agents to complete. Aggregate their findings and fix each issue directly. If a finding is a false positive or not worth addressing, note it and move on — do not argue with the finding, just skip it.

## Phase 4: Log High-Confidence Skipped & Out-of-Scope Findings as GitHub Issues

Two kinds of findings get filed here:
- **Skipped findings** — issues in the changed code not fixed in Phase 3 (too large, out of scope for this change, or otherwise deferred).
- **Out-of-scope findings** — clear issues the agents reported in code outside the diff. Even though they fall outside what `/simplify` was asked to touch, file them as GitHub issues if they meet the bar below — never silently drop a clear issue just because it is out of scope.

For each such finding, decide whether to file it as a GitHub issue.

**Log a finding as a GitHub issue ONLY when BOTH are true:**

1. You are **above 90% confident the finding is real** — verified by reading the actual code, not speculative.
2. Acting on it would be an **objective improvement** — a clear, uncontested win (e.g. real duplication, dead code, a measurable inefficiency). NOT a subjective preference, and NOT a tradeoff that has real downsides.

**Do NOT log:**
- Anything already fixed in Phase 3.
- Findings below the 90% confidence bar, or where the "fix" is a judgment call / tradeoff (e.g. a cache that delays correctness, a debatable refactor, a style preference).
- Negligible-impact nitpicks.

**How to log:**
- Use `gh issue create --repo <owner>/<repo>`. Get `<owner>/<repo>` from `git remote -v`. A finding that lives in a different repo gets its issue filed in that repo.
- Title: concise and action-oriented. Body: **Summary**, **Suggested fix**, **Why it matters**, **Priority**, and a line noting it was surfaced by `/simplify`.
- If `gh` is unavailable or unauthenticated, list the would-be issues in the summary instead of failing.

## Phase 5: Summarize

Briefly summarize:
- What was fixed (or confirm the code was already clean).
- Which skipped and out-of-scope findings were logged as issues, with links.
- Which findings were skipped without an issue, and why (e.g. below confidence bar, subjective, tradeoff).
