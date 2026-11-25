---
name: followups
description: Use at the end of a work session or when handing off to the next one. Triggers - "/followups", "wrap up", "wrap it up", "what's left", "where did we land", "recap", "what should we do next", "where does this go from here", or just before /clear or ending a session. Produces a forward-facing handoff (Done / Open / Next / Directions / Worth knowing), printed in chat only and written in plain /bro language. Do not use mid-task with active in-progress todos, or when the user wants a persisted plan file (use plans/ or the improve skill instead).
user_invocable: true
---

# /followups

A forward-facing handoff, not a recap. Produces a short **Done / Open / Next / Directions / Worth knowing** briefing, **printed in chat only**. Write no files.

The recap half is the cheap half. The value is in the last three sections: what to do next, where the work should go, and what a future session would otherwise rediscover the hard way.

**Write it like `/bro`.** Plain human language, no jargon, the way one person tells another where things stand. The reader should understand every line without opening the code. See "Write each line so it lands" in Step 4.

**Core principle: two halves, two standards of proof.**

- **Backward half** (Done, Open) is evidence only. Ground every line in git, todos, or output you saw this session.
- **Forward half** (Next, Directions, Worth knowing) is where you think ahead. Every item still names the thing in this session that prompted it. A direction with no trigger is slop.

## When to use

- Closing out a session: "wrap up", "what's left", "where did we land"
- Handing off to the next session or before `/clear`
- The user asks where the work goes from here
- The user types `/followups`

**Do NOT use when:** you are mid-task with active in-progress todos (keep working), or the user wants a durable plan another agent will execute (use `plans/` or the `improve` skill; this skill writes nothing to disk).

## Step 1 - Gather evidence (batch these in parallel)

Backward:

- `git log --oneline` for commits made this session, `git status` for uncommitted and untracked changes
- TodoWrite state: which todos are `completed` vs `pending`/`in_progress`
- Scan the conversation for explicit deferrals: "later", "out of scope", "punt", "skip for now", "follow-up", "TODO", "next session", "we should also"
- Whether verification (lint / test / build) actually **ran and passed this session**, rather than being attempted or assumed

Forward, so the directions rest on something real:

- TODO / FIXME comments in the code this session touched
- Open plan files in `plans/` or `docs/` that this work advances, blocks, or invalidates
- The next obvious consumer of what you built: who calls it, what is still stubbed, what is half-migrated
- Adjacent problems the session bumped into and walked past
- Anything measured this session that changes a prior assumption

## Step 2 - Classify

| Bucket | Goes here | Standard |
|---|---|---|
| **Done** | Work committed, or changed and verified passing this turn | a commit SHA, or a green check you ran this session |
| **Open** | Uncommitted WIP, pending todos, failing or un-run checks, deferrals | the artifact exists but is not finished or verified |
| **Next** | Concrete immediate actions, the size of one sitting | drawn from Open and explicit deferrals |
| **Directions** | Upgrade and feature moves the work now points at, bigger than one sitting | each names its trigger from this session |
| **Worth knowing** | Durable facts a future session would pay to rediscover | a number, a constraint, a dead end, a decision and its reason |

If something was done but **not verified**, it goes under Done with `(unverified)`. Never silently promote it. This matches the repo rule: do not call anything done or passing without confirming it this turn.

### Directions: the bar

A direction is a product or architecture move, not a chore. "Add tests", "improve performance", "clean up the module" are not directions.

Each direction carries three things:

1. **The move.** One sentence, concrete enough to argue with.
2. **The trigger.** What in this session makes it worth raising now. A measurement, a constraint you hit, a duplicated shape, a user-visible gap the work exposed.
3. **The size**, labelled as an estimate. Rough is fine, "one edge function" or "needs a new corpus" beats silence.

Rules:

- **Max 3.** Rank by leverage and cut the rest. A fourth idea dilutes the first three.
- **Check before proposing.** If the codebase already does it, or a plan file already covers it, name the plan and drop the idea.
- **Zero directions is a valid answer.** Some sessions point nowhere. Say nothing rather than manufacture a roadmap.
- Do not repackage the user's own stated goals back at them.

### Worth knowing: the bar

This is the section that survives `/clear`. Prefer facts that are expensive to re-derive and invisible in the diff:

- A measured number, with its units and its n
- A refuted approach and why it failed. Dead ends are the most valuable and the most often lost
- A constraint discovered the hard way: an API limit, an ordering requirement, a footgun in a tool
- A decision and the reason behind it, where the code shows the what but not the why
- A stale claim in a doc or comment that you found to be wrong

If an item would be lost across sessions and belongs in long-term memory, say so in one clause. Do not write the memory file from this skill.

## Step 3 - Cut everything that is not useful

A line earns its place only if the next session acts differently for having read it. Apply this to every bucket. When in doubt, cut.

| Cut | Why |
|---|---|
| Anything `git log`, `git status`, or the diff already shows plainly | The next session reads git anyway |
| Routine green checks (lint passed, build passed) | Expected state, not information |
| Which files you touched | Report behaviour, not mechanism |
| Restated user instructions or the task premise | The next session gets the same prompt |
| Vague Next items ("improve tests", "clean up") | Not actionable alone |
| Work already captured in a `plans/` file or an issue | Name the plan, drop the detail |
| A direction with no trigger from this session | That is a guess wearing a suit |
| Generic best practice with no local hook | The next session already knows |

Keep only:

- A result the next session would otherwise get wrong or redo
- A surprise: a failure, a wrong assumption, a number that contradicts the plan
- A blocker, with what unblocks it
- A deliberate deferral, with the reason
- A move the evidence now argues for
- A fact that cost real time to learn

Empty output is a valid result. Print `Nothing worth carrying forward.` and stop.

## Step 4 - Print the briefing (in chat, no files)

Terse and scannable. Skip empty sections. Done and Open stay one line per item. Directions get two lines each, since a bare title is not arguable. Write the whole briefing the way you would say it to the next person, not the way a status report reads.

### Write each line so it lands

Terse and clear are different goals. Where the two fight, clear wins. Cut a whole line rather than compress two lines into one.

- **Each line stands alone.** The reader may read one bullet and skip the rest. No line may borrow its subject from the line above it.
- **Name the thing again.** Never open a line with a bare "it", "this", "that", "these". After a section break the reader has no antecedent to attach a pronoun to.
- **Same thing, same word, every time.** If it is the decode budget, call it the decode budget in every line. A synonym makes the reader stop and ask whether you mean something new.
- **Known first, new second.** Open with the thing the reader already holds, then attach the new fact to it. "The fixture holds 54 images" comes before "the 54 images decode to 316MB".
- **One idea per line.** Two clauses carrying new information are two lines.
- **Numbers carry units, direction, baseline and n.** Write "840MB to 390MB (n=3, simulator)", never "much lower". Label every number measured, cited or estimated.
- **Expand an unfamiliar name on first use**, inline, in four words or fewer. Skip this for vocabulary the reader uses daily.
- **Say what happened, not what it resembles.** Drop the metaphor and name the plain verb.
- **Paths go on their own trailing line.** Never thread a path through a sentence.
- **Say it the way you would say it out loud.** Read the line back to yourself. If you would not say it to a colleague standing next to you, rewrite it. "The cap runs before paint now" beats "the budget is enforced upstream of the paint boundary".
- **No jargon. Say what the term means instead.** Write "the test set has no correct answers in it", not "no `ok` slice in the corpus". Write "the model thinks longer", not "higher reasoning effort". Internal names, variable names, provider plumbing and acronyms the reader would have to look up all get translated.
- **Keep an identifier only when the reader has to type, search or click it.** A commit SHA, a command, a path, a flag or a product name the reader will look for stays exactly as written. Put it at the end of the line, after the plain sentence that explains it.
- **Cut the filler words too.** The words no person says out loud: leverage, surface, seam, regime, holistic, robust, comprehensive, nuanced, foster, harness.

| Unclear | Clear |
|---|---|
| "It is much better now" | "steady state 840MB to 390MB (measured, n=3, simulator)" |
| "That approach did not work" | "culling frees no memory; WKWebView holds the decoded bitmap regardless" |
| "Fixed the perf issue and refactored the loader too" | two lines, one idea each |
| "the checker is green", after calling it the linter | call it the linter in both lines |
| "the cap kicks in downstream of paint" | "the cap applies after first paint, so hydration still allocates all 54 images" |
| "the budget is enforced upstream of the paint boundary" | "the cap runs before paint now" |
| "this unlocks a more holistic approach to memory" | "one budget now covers images and strokes together" |
| "errorPerCase == statusPerCase hides false positives" | "the test set has only wrong answers in it, so it can't catch the reader flagging correct work" |
| "pinned recognition to glm-5.3-flash via Relace" | "the handwriting reader now always uses one model through one provider (c38541df7)" |

```
Done
- The handwriting reader now always uses one model, glm-5.3-flash, through one provider, Relace (c38541df7)
- The consent screen now lists Relace as a provider we send data to (3646446b2)

Open
- Our public page of data processors still names the old provider. That page lives outside the repo, so nobody updated it.
- One todo left: find out how often the reader marks correct work as wrong.

Next
- Update the public data processors page to name Relace.
- Add correct answers to the test set. Today the test set holds only wrong answers, so it can't catch the reader flagging good work.

Directions
- Pick the provider per job instead of one for everything. Relace reuses cached prompts 85% of the time and costs 5.25x less. DeepInfra reuses none but answers just as fast. Live requests and overnight batches want different providers. Estimate: medium, one server function.
- Make the test set able to catch false alarms at all. No model test so far could see them, so every accuracy score we have reads too high. Estimate: large, needs newly labelled examples.

Worth knowing
- How long the model thinks depends on the provider, not the model. Modal's default thinks 12x longer than Z.AI's and cut off 37% of answers, which threw off an early score.
- How often the cache gets reused also depends on the provider. The 0% figure came from the provider we tested, not the model. Worth saving to memory.
```

## Rules

- **Write no files.** The deliverable is the chat message. Do not save it to `FOLLOWUPS.md`, a plan, or memory. The user chose in-chat output deliberately. If they later want it persisted, that is a separate ask.
- **No padding.** A two-line wrap-up is fine. Never manufacture Next or Directions items to look thorough.
- **Each Next item stands alone**, actionable by a fresh session without re-reading this one.
- **Label estimates as estimates.** A confident guess is not a finding.

## Common mistakes

| Mistake | Fix |
|---|---|
| "Done: fixed the bug" with no commit or test | Check git and whether the test ran. Unverified goes to Done with `(unverified)`, or to Open. |
| Directions that are chores ("add tests", "refactor") | Raise the altitude, or cut the item. A direction changes what the product or the architecture does. |
| Directions invented from vibes | Every direction names the trigger from this session. No trigger, no line. |
| Five directions instead of three | Rank by leverage, keep the top three, delete the rest. |
| Proposing what the codebase already has | Check first. If a plan covers it, name the plan instead. |
| Worth knowing full of things the diff shows | That section is for what the code cannot tell you: numbers, dead ends, reasons. |
| Writing a file anyway | This skill prints to chat. Persisting is a different task. |
| Restating the whole session narratively | It is a scannable briefing, not a story. |
| A bullet that only parses after reading the one above it | Every line stands alone. Name its subject again. |
| A line opening with a bare "it", "this" or "that" | The reader lost the antecedent at the section break. Name the noun. |
| "faster", "better", "much lower" | Give the number, the baseline and the n. |
| Two words for one thing across the briefing | Pick one term and repeat it. Variety costs the reader a re-read. |
| Writing like a status report instead of talking | Read the line aloud. If you would not say it to a colleague, rewrite it. |
| Jargon the reader has to decode | Say what it means in plain words. Keep an identifier only if the reader must type or search it. |
