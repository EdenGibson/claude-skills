---
name: agentically-iterate
description: Use when the user asks to iterate on work until an independent reviewer passes it, wants a fresh-eyes review loop with research-backed judging that repeats until the work passes, or says "agentically iterate" or "loop until the reviewer passes it". Works for any artefact a reviewer can inspect and run, such as code, docs, configs or designs. Not for a single review pass.
---

# agentically-iterate

You implement once. Then a loop runs. Each round, two fresh reviewers judge
the same work in parallel. An executor applies their findings, and two new
reviewers judge again. The loop ends when both reviewers in one round pass
the same work. It has no round cap.

Expect cost. Across 22 loops from 09-25 to 10-11, a loop ran 55 minutes to
21 hours, and a review took a median 11 to 42 minutes, measured. Two
reviewers per round double the review cost of every round. A pass still
missed what the user wanted in 4 of 5 sessions, measured. Most rules below
exist to stop that: the brief must let the user's own words block.

| Role | Instance | Sees | Model |
|---|---|---|---|
| Orchestrator | this session | everything | session |
| Reviewer A and B | two new Agents every round | `$RUN/cold/`, the work, the web | inherit |
| Panel reader | started by a reviewer | shuffled images only | inherit |
| Executor | a new Agent every round | brief, the round's reviews, ledger | sonnet; inherit on a repeat, see loop step 6 |

Never pick the executor model by the kind of finding. Any model outside
this table is a Decisions line in the report.

Bash calls keep no shell variables. The commands below use `$RUN`, `$WORK`
and `$S`. Set all three at the top of every call, with literal paths. `S` is
this skill's base directory. `WORK` is the work tree.

## One run is one loop

A run serves one request, in the user's own words. When its loop ends,
report and stop. Start a new run only when the user asks for one in a new
message that says what to work on, or says yes to a new run you offered.
"keep going", "dont stop" or a general grant continues the current loop and
never starts another. Never start a loop on an earlier loop's Notes unless
the user asks.

## Set up before round 0

The loop edits the work unattended, and every reviewer judges everything in
the work. For code, work in a fresh worktree. Copy in any uncommitted file
the request names, and list it in the brief. In an existing checkout, stop
if `git status --porcelain` prints anything.

```bash
set -eu
RUN=$(mktemp -d -p "${CLAUDE_JOB_DIR:+$CLAUDE_JOB_DIR/tmp}" cr-XXXX 2>/dev/null || mktemp -d -t cr-XXXX)
mkdir -p "$RUN/cold" "$RUN/history"
echo "$RUN"
```

Print `RUN` and `WORK` in your reply, so a context summary keeps them. For
code, confirm `git -C "$WORK" rev-parse --show-toplevel` prints `WORK`.
Every reviewer sees the `RUN` path, so never rename it to something that
hints at rounds, such as `iterate-` or `loop-`.

### The brief

Write `$RUN/cold/brief.md` before you implement anything, so the criteria
come from the request and not from your implementation. The brief holds:

- the user's request, verbatim. Copy it from the user's own messages, never
  from a summary, an older brief or a later "keep going". Cut only the
  skill call, such as `/agentically-iterate`, and mark the cut `[...]`
- `## Criteria`, numbered, 40 at most
- `## Items` when the work has two or more parts judged one by one, such as
  variants, plates or pages: one `- <name>` line each. Add `## Frozen items`
  and `## Dropped items`, each reading `None.`
- where the work lives and how to see it. Name the exact paths that make up
  the work; reviewers judge nothing outside them. For code, give the base
  commit from `git rev-parse HEAD` and say that `git diff <base>` plus
  `git status` show the work
- `## Safe commands`: the exact commands agents may run. Read each script
  before you list it. Nothing in its call chain may deploy, push, send, pay
  or call a paid API. Swap any such command for a local variant. Two
  reviewers run at once, so mark `(exclusive)` every command that writes
  into the work or loads the box for minutes, and write it as `flock -w
  3600 /tmp/<RUN basename>.lock <command>`
- an empty `## Decisions` section

Each criterion is a command and a number, or a judged criterion. Write
"exits within 2 s of SIGTERM for `sh -c "trap '' TERM; sleep 30"`", never
"stops at once". Then apply these rules:

1. At least one criterion quotes the user's words and can block. When the
   request concerns how work looks or moves, make it a judged criterion: the
   subject a reader should see, the images to crop, any controls, and the
   bar. Controls are versions the user rejected. Default bar, `(assumed)`:
   each item's median score is 4 or more, and at least 1 above the
   controls' pooled median while that median is below 5. No two readers
   name the same odd detail in one item.
2. Tag every criterion the user did not state `(assumed)`. Give each
   assumed number a guard: what may not get worse to meet it, and the
   command that checks it. Write "fits 651px tall. Guard: body text stays
   at 14px or more".
3. Give every size or position a tolerance a person can see, at least 2px
   at 1x. Write "540px ±4px", never "540px".
4. Tag `(unverified)` only a check that no agent can observe, such as one
   that needs a paid API. Never tag the criterion that quotes the user. An
   unverified criterion never blocks.
5. A by-eye criterion names its sample: "all items", or a list.
6. When the work turns input into output, such as a renderer, a generator
   or a prompt, add a held-out criterion. The reviewer writes 3 fresh inputs
   from the brief's input spec in every review and judges the outputs.
7. Past 40 criteria, fold the scripted checks into one command in the work,
   such as a test file, and make that one criterion.

Check the brief for history before you freeze it:

```bash
grep -niE '\b(pass(es)?|rounds?|loops?|again|earlier|previous(ly)?|fixed)\b|iterat|agentic|[a-z]+(st|nd|rd|th) (pass|round|loop)' "$RUN/cold/brief.md" || true
```

Every hit must read the same to someone who knows nothing of earlier work.
Reword any hit that does not. A brief never names a pass count, a round, an
earlier review or the reason behind a Decisions line.

Then freeze the brief and the prompts:

```bash
set -eu
for X in a b; do
  sed "s|{COLD}|$RUN/cold|g; s|{OUT}|$RUN/cold/review-$X.md|g" "$S/reviewer.md" > "$RUN/cold/reviewer-$X.md"
  test -s "$RUN/cold/reviewer-$X.md"
done
cp "$S/reader.md" "$RUN/cold/reader.md"
cp "$RUN/cold/brief.md" "$RUN/history/brief.frozen"
md5sum "$RUN/cold/brief.md" "$RUN/cold/reviewer-a.md" "$RUN/cold/reviewer-b.md" "$RUN/cold/reader.md" > "$RUN/history/frozen.md5"
echo "WORK=$WORK N=1 phase=round0" > "$RUN/history/state"
```

## Round 0

Do the best-effort implementation. You may split it across subagents, such
as one per variant. Round 0 attempts every criterion, and never leaves one
for the executor. Run the safe checks. Snapshot the tree without a commit,
so reviewers see no new history:

```bash
set -eu
GIT_INDEX_FILE="$RUN/history/snap.idx" git -C "$WORK" add -A
GIT_INDEX_FILE="$RUN/history/snap.idx" git -C "$WORK" write-tree > "$RUN/history/tree-0"
```

For work outside git, run `cp -a "$WORK" "$RUN/history/tree-0"` instead.
Take the same snapshot as `tree-N` after every executor. To undo a destroyed
round in git, run `git -C "$WORK" restore --source="$(cat
"$RUN/history/tree-N")" --worktree -- . && git -C "$WORK" clean -fd`.

## The loop

`N` names the current round. The state file holds `phase=` one of round0,
review, exec, outage, needs-input or done. Rewrite it after each step.
During the loop, read only the check script's output, the Blocking sections
and each exec summary line. Never open screenshots or whole reviews. Your
context then lasts the run.

1. Run `md5sum -c "$RUN/history/frozen.md5" && test ! -e
   "$RUN/cold/review-a.md" && test ! -e "$RUN/cold/review-b.md"`. On a hash
   mismatch, restore `brief.md` from `brief.frozen`, re-render the prompts,
   and note the tamper in the ledger. Move a stray review file to
   `history/stray-N-<letter>.md` and never read it as a verdict.
2. In one message, dispatch two new `general-purpose` Agents in the
   background. Their whole prompts are `Read <RUN>/cold/reviewer-a.md and
   follow it exactly.` and the same line with `reviewer-b.md`. Leave `name`
   unset and use the description "Cold review" for both. A name like
   `reviewer-4` tells the agent that rounds came before. Start a watch on
   each, as in Stalls and outages.
3. On each finish, `TaskStop` that agent's watch first. The watch cannot
   see the file once it moves, and would report a false stall an hour
   later. Then run `python3 "$S/check-review.py"
   "$RUN/cold/review-<letter>.md" "$RUN/cold/brief.md"`, and move the file
   to `$RUN/history/review-N-<letter>.md`. The script prints PASS or FAIL,
   then one ITEM line per item. A LOST line, or no file, is a lost review.
   `TaskStop` that agent and its watch, and dispatch a new one for the same
   letter, with `N` unchanged. The other letter's verdict stands. Two lost
   reviews in a row for one letter end the loop with `failed:`.
4. Both PASS: go to Report.
5. When the brief has items, update them. An item fails a round when
   either review fails it.
   - An item both reviews pass moves to `## Frozen items`.
   - An item that fails the same criterion in two rounds, with an executor
     run between them, moves to `## Dropped items`. Never drop the last
     item in `## Items` while `## Frozen items` reads `None.`; end with
     `needs input:` instead.
   Record each move in the ledger, and refreeze as in Brief edits. When
   every blocking finding of the round sits on an item you just dropped, the
   round counts as a pass. Write its ledger lines and go to Report.
6. Render the executor prompt with
   `sed "s|{RUN}|$RUN|g; s|{N}|$N|g" "$S/executor.md"`. Pick its model:
   look in the ledger for an applied finding on the same item and the same
   criterion as any blocking finding now. For work without items, match the
   same criterion and the same file. Any match means inherit, else sonnet.
   Dispatch it as a new `general-purpose` Agent with a watch. On its
   finish, read the first line of `$RUN/history/exec-N.md` and snapshot
   `tree-N`.
7. Append one line per finding to `$RUN/history/ledger.md`: round, review
   letter, item, criterion, finding, then applied, declined, impossible or
   dropped, and why. Go to step 1 with `N` one higher.

## Every reviewer gets the same prompt

The two dispatch lines never change, and the md5 covers the files they point
at. Reviewers A and B differ only in their output file. That identity makes
each reviewer a duplicate of the first. Nothing else may reach a reviewer:

- the round number, or any sign that earlier rounds happened
- earlier findings, disputes, executor reports, or "verify these fixes"
- a new pass bar, however sensible
- your view of the work

A reviewer told what the executor fixed checks those items and stops looking.
A reviewer that raises an old point again gives you evidence the point is
real. History goes to the ledger, which only executors read.

History also leaks by side routes. Keep `history/` out of `cold/`. Executors
never commit, and never write review wording or the story of a change into
the work, its comments, meta files or READMEs. Nobody writes memory or a
`CLAUDE.md` file while the loop runs, since every later reviewer loads them.

Never SendMessage a reviewer that wrote its review. It keeps its own
conclusions.

## Brief edits

The brief changes in three ways only:

- revise an `(assumed)` criterion, as in When a finding cannot be met
- add a Decisions line, as in Flip-flops
- move items between `## Items`, `## Frozen items` and `## Dropped items`,
  as in loop step 5

Any other change ends the loop with `needs input:`. That covers a new
criterion, a looser number, a criterion turned `(unverified)` mid-run, and a
criterion the environment no longer lets agents check, such as a command
another session reports as unsafe. After an allowed edit, rerun the history
grep, refresh `brief.frozen`, and rerun the `md5sum` line from setup.

Never edit a rendered prompt. Never write a review or an exec report
yourself.

## When a finding cannot be met

One executor's word is not enough. The first executor to mark a finding
impossible may be wrong, so dispatch a second executor on the inherit model
for the same round. Render its prompt as usual, then change its output file
to `exec-N-confirm.md`. The finding is unmeetable only when the second
executor also marks it impossible. A finding is also unmeetable when the same
criterion fails on the same file or behaviour in 3 rounds after executors
claimed it fixed.

- It rests on an `(assumed)` criterion: you wrote that number, so revise it.
  Edit the criterion in place and keep its tag. Add a plain Decisions line
  that states the new requirement. Put the old number, the evidence and the
  review file names in the ledger, never in the brief.
- It rests on anything the user stated: end the loop with `needs input:`.
  File the finding with the `attn` skill where it exists. Only the user can
  change the user's own requirement.

## Flip-flops

An executor may report two findings that no single change satisfies, quoting
both. The brief then lacks a decision. Pick the side the user's request
favours and add it under `## Decisions` as a plain requirement. Record the
reason and both review files in the ledger. Every Decisions line leads the
final report, because you made the choice without the user.

## Stalls and outages

- After each dispatch, run `bash "$S/watch-agent.sh" <output_file>
  <done_file>` with Bash in the background. The output file comes from the
  dispatch result. The done file is `cold/review-<letter>.md` or
  `history/exec-N.md`. Whenever you stop or replace an agent, `TaskStop`
  its watch too.
- The watch prints `stalled` when the transcript stops growing for 60
  minutes. `TaskStop` the agent. A stalled reviewer is a lost review.
  Redispatch a stalled executor once, with `N` unchanged.
- A finish without the agent's file is not a finish. Send that agent one
  message: `Continue. Run every remaining command in the foreground, then
  write <file>.` A second stop without the file counts as stalled.
- A finish that reads like a session limit, a rate limit, `429`,
  `overloaded` or `API Error` is an outage, not a lost review. `TaskStop`
  the agent and its watch, and set `phase=outage`. The other letter's
  verdict stands. Wait in the background until the reset time the error
  names.
- Before any redispatch after an outage or a stall, wait until no other
  agent of the round runs. Then kill by PID every process left with a
  working directory under `$WORK`. Snapshot the tree into a scratch index
  and compare it with the last `tree-N`. On a mismatch, run the undo
  command from Round 0. Then redispatch with `N` unchanged.
- An expired login needs the user. Set `phase=needs-input`, end with
  `needs input:`, and file it with the `attn` skill where it exists.

## What ends the loop

Both reviews in one round pass. So does the user saying stop, two lost
reviews in a row for one letter, an unmeetable user requirement, a brief edit
outside the three allowed ones, or an expired login. Nothing else ends it:
not the user saying the work looks done, the hour, green tests, the round
count, or your own confidence. Never pause to ask the user a question
mid-loop.

Do not edit the work yourself after round 0, even for a 2-line fix. You hold
the most history and the most stake in round 0. The executor does every edit.

## Resume

After a compaction or a restart, re-read this skill and resume the `RUN` you
printed. Search only when the transcript lost it: look for
`cr-*/history/state` in `$CLAUDE_JOB_DIR/tmp` first, then `/tmp`, and skip
any run whose state reads `phase=done`. Continue from `history/state`. Never redo round 0 once
`history/tree-0` exists. A run at `phase=needs-input` resumes only after the
user answers. Apply the answer as a Decisions line or a revised criterion,
refreeze, and go to step 1.

## Report

Write `phase=done` to the state file. Lead with these, in order:

1. every Decisions line, revised `(assumed)` criterion, `(unverified)`
   criterion, dropped item, and model choice outside the table
2. the Notes that both passing reviews repeat, each with a one-line fix.
   Offer one new run on them, and never start it yourself

Then give the rounds run, the paths of the two passing reviews, each round's
findings from the ledger, and the final check output. List all other Notes,
deduplicated. End with the snapshot directory, for undo.
