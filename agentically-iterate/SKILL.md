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
  skill call, such as `/agentically-iterate`, and mark the cut `[...]`.
  When the request names only the work, such as "on the suppression
  criteria", also copy, verbatim, the user's earlier messages in the
  session that say what the work should achieve. Name the goal they state.
  When no message states a goal, end with `needs input:` before round 0
  and ask what the work should achieve, with the measure
- `## Criteria`, numbered, 40 at most
- `## Items` when the work has two or more parts judged one by one, such as
  variants, plates or pages: one `- <name>` line each. One artefact shown at several
  sizes, themes or devices is one item, such as one drawing on desktop and
  iPad. Name the sizes inside the item's criteria instead
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

1. Every goal in the request, and every issue the user asks to be dealt
   with, gets its own criterion that quotes the user's words and can block.
   Tag each such criterion `(user)`, even when you chose its number. A
   `(user)` criterion is never `(assumed)`, and only the user may lower its
   bar. The one exception is a default visual bar below, which you wrote
   and may revise as in When a finding cannot be met. List such issues
   under `## Issues the user raised`. When the user asks for a gain, such
   as better, faster or more accurate, the bar is a gain
   over the base, with a number: write "held-out agreement rises by 2 rows
   or more over base", never "at least base". A non-regression bar is a
   guard, never the criterion for a goal. Every such criterion needs a
   command or a judged panel an agent can run. When no agent can measure a
   user goal, such as one only a paid API can score, stop before round 0
   and end with `needs input:`. When the request concerns how work looks
   or moves, make it a judged criterion: the subject a reader should see,
   the images to crop, any controls, and the bar. Controls are versions the user rejected. The criterion is `(user)`.
   Its default bar is the one part tagged `(assumed)`, and the user's words
   set any bar they name. Default bar: each item's median score is 4 or more, and at least 1 above the
   controls' pooled median while that median is below 5. No two readers
   name the same odd detail in one item.
2. Tag every other criterion the user did not state `(assumed)`. Give each
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
grep -niE '\b(pass(es)?|rounds?|loops?|again|earlier|previous(ly)?|fixed|still|remains?|no longer|anymore|now|current(ly)?)\b|iterat|agentic|[a-z]+(st|nd|rd|th) (pass|round|loop)' "$RUN/cold/brief.md" || true
```

Every hit must read the same to someone who knows nothing of earlier work.
Reword any hit that does not. A hit inside the user's verbatim words stays
as the user wrote it. A brief never names a pass count, a round, an
earlier review or the reason behind a Decisions line.

Then test the brief against the base. Run each scripted `(user)` criterion
3 times on the base commit, in a scratch checkout. Write one line per run
to `$RUN/history/base-check.md`, and read only that file.

- A gain bar must clear the base's spread: set it above the best of the 3
  base runs, by at least the gap between the best and the worst run.
- A `(user)` criterion that the base passes usually means a weak check,
  such as a test that misses the bug's trigger. Rewrite the check so it
  exercises what the user described, and run it again on the base. End
  with `needs input:` before round 0 only when no runnable check you can
  write fails on the base, and give the base results.
- A judged criterion, or work with no base version, gets no base check.
  Write `no base check: <reason>` in `base-check.md`. Never run a panel
  yourself.

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
round in git, run this undo command:
```bash
export GIT_INDEX_FILE="$RUN/history/undo.idx"
git -C "$WORK" read-tree "$(cat "$RUN/history/tree-N")" && git -C "$WORK" checkout-index -a -f && git -C "$WORK" clean -fd
```

## The loop

`N` names the current round. The state file holds `phase=` one of round0,
review, exec, outage, needs-input or done. Rewrite it after each step.
During review it also holds `done=` with the letters that have a valid
verdict, such as `done=b`.
During the loop, read only the check script's output, the Blocking sections,
`cold/brief.md`, `history/state`, `history/ledger.md`, `history/items.md`, each exec report,
and the Notes sections of a round where both pass. Never open screenshots
or whole reviews. Your context then lasts the run.

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
3. On each finish, first run `test -e "$RUN/cold/review-<letter>.md"`.
   When the file is missing and the finish reads like a session limit, a
   rate limit, `429`, `overloaded` or `API Error`, follow the outage
   bullet in Stalls and outages, and skip the rest of this step. When the
   file is missing otherwise, leave the watch running, follow the finish
   without a file bullet in Stalls and outages, and skip the rest of this
   step. When the file exists, `TaskStop` that agent's watch. The watch
   cannot see the file once it moves, and would report a false stall an
   hour later. Then run `python3 "$S/check-review.py"
   "$RUN/cold/review-<letter>.md" "$RUN/cold/brief.md"`. The script prints
   PASS or FAIL, then one ITEM line per item, or one LOST line. Only on PASS
   or FAIL, move the file to `$RUN/history/review-N-<letter>.md` and add the
   letter to `done=` in the state file. A LOST line is a lost review. Every
   lost review gets the path `$RUN/history/lost-N-<letter>-<k>.md`, with `k`
   one more than the lost files already there for that round and letter.
   Move the file there, or `touch` that path when no file exists. On a lost
   review, `TaskStop` that agent and its watch, and dispatch a new one for
   the same letter, with `N` unchanged. The other letter's verdict stands.
   Two lost files for one round and letter end the loop with `failed:`. A
   review killed by a process restart is an outage, never a lost review.
4. Both PASS: read the Notes section of both reviews. A goal note says
   that the user's quoted request, or an issue under `## Issues the user
   raised`, still holds or gains nothing. A note that starts with
   `unmeasured:` never counts; list it in the Report. Any other goal note
   counts when both reviews make the same point, or when one review backs
   it with a command's output. When any goal note counts, the round does
   not pass:
   - Tighten that goal's criterion in place, keeping its number, as in
     Brief edits. Set the new bar from the number in the note's evidence.
     A goal with no criterion yet gets a new `(user)` one.
   - Write `$RUN/history/exec-N-input.md`: one numbered finding per goal
     note, quoting the note, the criterion's new text, the review file it
     came from, and `Done when: criterion <K> passes`.
   - Write a ledger line per goal note, naming both review files. Step 7
     skips these findings.
   - Move every item a counted note covers out of `## Frozen items` in
     `$RUN/history/items.md`, and record each move in the ledger.
   - Skip step 5, and go to step 6.
   With no goal note that counts, go to Report.
5. When the brief has items, update them. An item fails a round when
   either review fails it.
   - An item both reviews pass goes under `## Frozen items` in
     `$RUN/history/items.md`. It stays in the brief, and reviewers judge
     it every round.
   - A frozen item that either review fails leaves `## Frozen items`
     before step 6, so the executor may edit it again.
   - An item that fails the same `(assumed)` criterion in three consecutive
     rounds, with an executor run between each, goes under `## Dropped
     items` in `$RUN/history/items.md`, and its `- <name>` line leaves
     `## Items` in the brief. Never drop an item that fails any `(user)`
     criterion in that round, and never drop the last item in `## Items`.
     Those failures go to When a finding cannot be met.
   Record each move in the ledger, and refreeze as in Brief edits. When
   every blocking finding of the round sits on an item you just dropped, and
   no blocking finding rests on a `(user)` criterion, the round counts as a
   pass. Write its ledger lines and run step 4 on it.
6. Render the executor prompt with
   `sed "s|{RUN}|$RUN|g; s|{N}|$N|g" "$S/executor.md"`. Pick its model:
   look in the ledger for an applied finding on the same item and the same
   criterion as any blocking finding now. For work without items, match the
   same criterion and the same file. Any match means inherit, else sonnet.
   Dispatch it as a new `general-purpose` Agent with a watch. On its
   finish, read `$RUN/history/exec-N.md` and snapshot
   `tree-N`.
7. Append one line per finding, other than those step 4 logged, to
   `$RUN/history/ledger.md`: round, review
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
real. History goes to the ledger and `history/items.md`, which reviewers never read.

History also leaks by side routes. Keep `history/` out of `cold/`. Executors
never commit, and never write review wording or the story of a change into
the work, its comments, meta files or READMEs. Nobody writes memory or a
`CLAUDE.md` file while the loop runs, since every later reviewer loads them.

Never SendMessage a reviewer that wrote its review. It keeps its own
conclusions.

## Brief edits

The brief changes in five ways only:

- apply the user's answer to a `needs input:`, as in Resume. The answer
  may add, tighten or lower any criterion, since only the user may lower a
  `(user)` bar
- revise an `(assumed)` criterion, as in When a finding cannot be met
- add a Decisions line, as in Flip-flops
- remove a dropped item from `## Items`, as in loop step 5
- tighten a `(user)` criterion from a goal note, or add a missing one, as
  in loop step 4. Edit it in place and keep its number and its `(user)`
  tag. Its bar must be one the work fails at that moment. Each goal gets
  this edit once per run. A second counted goal note on the same goal ends
  the loop with `needs input:`. Write the criterion as a plain requirement
  that never mentions a review, a round or a change

Any other change ends the loop with `needs input:`. That covers any other
new criterion the user did not give, any lower bar on a `(user)` criterion other than its
default visual bar, a looser number, a criterion turned `(unverified)` mid-run, and a
criterion the environment no longer lets agents check, such as a command
another session reports as unsafe. After an allowed edit, rerun the history
grep, refresh `brief.frozen`, and rerun the `md5sum` line from setup.

Never edit a prompt file after you render it. A different prompt comes
only from a different render command, as in When a finding cannot be met.
Never write a review or an exec report yourself.

## When a finding cannot be met

One executor's word is not enough. The first executor to mark a finding
impossible may be wrong, so dispatch a second executor on the inherit model
for the same round. Render its prompt with
`sed "s|history/exec-{N}\.md|history/exec-{N}-confirm.md|g; s|{RUN}|$RUN|g; s|{N}|$N|g" "$S/executor.md"`,
which names `exec-N-confirm.md` as its output file. Snapshot `tree-N` again
when it finishes. The finding is unmeetable only when the second
executor also marks it impossible. A finding is also unmeetable when the same
criterion fails on the same file or behaviour in 3 rounds after executors
claimed it fixed, unless loop step 5 drops the item it sits on.

- It rests on an `(assumed)` criterion, or on a default visual bar: you
  wrote that number, so revise it.
  Edit the criterion in place and keep its tag. Add a plain Decisions line
  that states the new requirement. Put the old number, the evidence and the
  review file names in the ledger, never in the brief.
- It rests on anything else the user stated, or on any other `(user)`
  criterion or bar: end
  the loop with `needs input:`.
  File the finding with the `attn` skill where it exists. Only the user can
  change the user's own requirement.

## Flip-flops

An executor may report two findings that no single change satisfies, quoting
both. The brief then lacks a decision. Pick the side the user's request
favours and add it under `## Decisions` as a plain requirement. When the
only side that settles it lowers a `(user)` bar other than a default
visual bar, end the loop with `needs
input:` instead. Record the
reason and both review files in the ledger. Every Decisions line leads the
final report, because you made the choice without the user.

## Stalls and outages

- After each dispatch, run `bash "$S/watch-agent.sh" <output_file>
  <done_file>` with Bash in the background. The output file comes from the
  dispatch result. The done file is `cold/review-<letter>.md`,
  `history/exec-N.md` or `history/exec-N-confirm.md`. Whenever you stop or replace an agent, `TaskStop`
  its watch too.
- The watch prints `stalled` when the transcript stops growing for 60
  minutes. `TaskStop` the agent. A stalled reviewer is a lost review.
  Redispatch a stalled executor once, with `N` unchanged. A second stall
  of that executor ends the loop with `failed:`.
- A finish without the agent's file, and not an outage under the next
  bullet, is not a finish. Send that agent one
  message: `Continue. Run every remaining command in the foreground, then
  write <file>.` A second stop without the file counts as stalled. A reviewer stalled
  that way is a lost review, and an executor stalled that way follows the
  stall rule above.
- A finish that reads like a session limit, a rate limit, `429`,
  `overloaded` or `API Error` is an outage, not a lost review. `TaskStop`
  the agent and its watch, and set `phase=outage`. The other letter's
  verdict stands. Wait in the background until the reset time the error
  names.
- Before any redispatch after an outage or a stall, wait until no other
  agent of the round runs. Then kill by PID every process left with a
  working directory under `$WORK`. Kill every process that still holds the
  run's lock: `fuser -k /tmp/<RUN basename>.lock || true`. Snapshot the
  tree into a scratch index and compare it with the last `tree-N`. On a mismatch, run the undo
  command from Round 0. Then redispatch with `N` unchanged.
- A process restart of this session is an outage. Only a restart message
  proves a restart, such as "Continue from where you left off" or an
  "automatically restarted" note. A denied, cancelled or interrupted result
  never proves a restart by itself. The restart kills every running agent
  of the round, and their task IDs no longer work. Treat every agent and
  watch as dead, so skip the wait. A file already at
  `history/review-N-<letter>.md` keeps its verdict; `done=` names its letter.
  None of the killed agents counts as a lost review or a stalled executor.
  A denial from before the restart message is not a permission problem.
  Follow the redispatch steps above, with `N` unchanged. A permission
  problem is real only when a fresh agent, dispatched to run the same
  command after the restart, is denied again. Never run that command
  yourself.
- An expired login needs the user. Set `phase=needs-input`, end with
  `needs input:`, and file it with the `attn` skill where it exists.

## What ends the loop

The loop ends when both reviews in one round pass and no goal note counts, as
in loop step 4, or when the user says stop. These end it with `failed:`: two lost
files for one round and letter, as in loop step 3, and a second stall of one executor.
These end it with `needs input:`: a request with no stated goal, a user
goal no agent can measure, a
`(user)` criterion the base passes with no stricter check possible, an
unmeetable user requirement, a second counted goal note on one goal, a flip-flop that only a lower `(user)` bar
settles, a brief edit outside the five allowed ones, and an expired login.
Every `needs input:` exit writes `phase=needs-input` to the state file
first. Nothing else ends the loop:
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
user answers.

- Before `history/tree-0` exists, use the answer to finish the brief,
  including any new `(user)` criterion it gives. Then run the history grep,
  the base check and the freeze from setup, do Round 0, and only then go to
  step 1.
- Once `history/tree-0` exists, apply the answer as a Decisions line, a
  revised criterion or a new `(user)` criterion, as in Brief edits.
  Refreeze, and go to step 1.

## Report

Write `phase=done` to the state file. Lead with these, in order:

1. every Decisions line, revised `(assumed)` criterion, `(unverified)`
   criterion, dropped item, and model choice outside the table
2. every `unmeasured:` goal note, since no agent could check it
3. the Notes that both passing reviews repeat, each with a one-line fix.
   Offer one new run on them, and never start it yourself

Then give the rounds run, the paths of the two passing reviews, each round's
findings from the ledger, and the final check output. List all other Notes,
deduplicated. End with the snapshot directory, for undo.
