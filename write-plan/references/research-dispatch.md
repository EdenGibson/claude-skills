# Research dispatch

One copy-paste dispatch that returns a finished `## Research` block.

**Why this file exists.** Step 4 used to ask for judgment — *how many* queries, *which* sources,
*when* it's fine to skip. Judgment under time pressure is exactly what gets skipped: measured on
2026-08-01, **12 of 318** plans in Derive carried any citation at all.

**Dispatching is the fastest path, not a mandate.** Researching directly is fine — measured, both
agents observed under test did exactly that and produced blocks meeting the bar. What is *not*
optional is the finished block: version-read-first, ≥2 independent sources, URL + version + date per
citation, an explicit approach verdict, and a reference implementation. Use this prompt and you get
those for free; go direct and you have to walk them deliberately, because that is where the decision
you were trying not to make sneaks back in.

## When to research

**Every plan.** There is no "this one is obviously internal" branch you get to take on your own
authority — that judgment has to be made *with sources open*. If the answer really is "no external
surface", that conclusion gets written down, which puts the opt-out on the record instead of leaving
a silent hole.

Scale the effort, don't skip it:

| Situation | How |
|---|---|
| Normal plan (one library/API/behavior in play) | one subagent with the prompt below, or the same searches run directly |
| Broad or unfamiliar (new dependency, architecture choice, security surface) | `deep-research` skill instead |
| Verbatim error string, CVE, or "is this still maintained" | lead with the exact string, in quotes |

**A plan matching more than one row takes the broader treatment.** "One library" *plus* a security
surface is a security surface — memory exhaustion, untrusted input, auth, secrets, serialization and
file paths all pull it up a row, however narrow the code change looks.

Model: **sonnet** by default. If the returned block is thin — fewer than 2 sources, no version or
date, or a verdict with no reasoning — **re-dispatch once on opus without asking.** Standing
permission. A thin research block is worse than none, because it looks done.

## The dispatch

Fill the four bracketed slots. Send as a subagent prompt. Change nothing else.

```
Research task for a handoff plan. Return ONLY the markdown block specified at the end.

WHAT THE PLAN WILL DO: [one or two sentences — the decided change]
DECIDED APPROACH: [the specific how that was already chosen this session]
IN-SCOPE FILES: [paths]
EXTERNAL SURFACE TO CHECK: [libraries, APIs, symbols, versions, error strings, security angle —
  everything you can name; write "unsure" and let the researcher find it if you can't]

Repo context you must establish yourself before searching:
- Read the repo's package.json / lockfile / equivalent and record the ACTUAL INSTALLED VERSION of
  every library named above. Research the version in use, never "latest" — this is the single most
  common way plan research goes wrong.

Run SEVERAL targeted searches, not one. At minimum:
1. The exact package/API/symbol name + the installed version.
2. "how to <the task> in <the framework/library>" — find a reference implementation.
3. "is <the decided approach> still recommended" / "<library> deprecated" / "<API> breaking change".
4. Any verbatim error string, exactly as it appears, in quotes.
5. Security/advisory angle if the change touches input handling, auth, secrets, serialization,
   file paths, or anything reachable by untrusted input.

Source rules:
- Follow into PRIMARY sources: official docs FOR THE VERSION IN USE, release notes/changelogs, the
  actual GitHub issue/PR/commit, security advisories. Blog posts are a lead to a primary source,
  not a citation.
- Cross-check at least 2 independent sources for any fact that decides the approach.
- Record the version and the date you checked. This stuff drifts.
- If it's a bug: check whether it is already known or already fixed upstream. That can change the
  entire fix, so search the issue tracker and changelog explicitly.
- Never cite a URL you did not open. A plausible-looking URL you didn't fetch is a fabrication.

RETURN EXACTLY THIS AND NOTHING ELSE:

## Research

<Either a bullet per external fact the plan rests on, each as:>
- <the fact, stated so a zero-context executor can act on it> — <URL> (checked <YYYY-MM-DD>, <pkg>@<version>)

<...or, only if it is genuinely true after searching, the single literal line:>
No external surface — <specific reason>

**Approach verdict**: <CURRENT | SUPERSEDED | DEPRECATED | INSECURE> — <one sentence, with the URL
that establishes it>. If anything other than CURRENT, name what the current recommendation is.

**Reference implementation**: <URL — or an in-repo `file:line` when the best exemplar already
lives in this codebase — of the code worth modelling, or "none found">
```

## What to do with the result

1. **Paste the `## Research` block into the plan.** Verbatim. Don't summarize it away.
2. **Put the reference-implementation URL and the primary docs into `Suggested executor toolkit`**,
   so the zero-context executor inherits the references instead of re-deriving them.
3. **Cite inline where a fact decides something** — in `Why this matters`, in the root-cause line,
   in the step that depends on it. A citation stranded in one section is a citation the executor
   won't connect to the work.
4. **If the verdict is not `CURRENT`: STOP and surface it to the user.** Do not quietly write the
   plan around the better approach. `write-plan` crystallizes a decision; it does not make a new
   one. The user chose the approach and only the user changes it.
5. **Check your own work**: `~/.claude/skills/write-plan/bin/plan-number research plans/NNN-slug.md`
   → must print `cited` or `declared`. `empty` or `missing` means step 4 didn't happen.

## The one honest way to skip

Write the literal line, in the plan, with a real reason:

```
No external surface — pure internal refactor of SyncManager.flush()'s queue ordering; no library,
API, version, security, best-practice or error-string angle.
```

"Internal logic" alone is not a reason — it's a restatement. The reason has to name what you
checked and found absent. And note what the line costs you: it is a claim, on the record, in a file
a reviewer reads. That's the point. Silence was free; this isn't.
