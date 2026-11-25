---
name: design-system
description: Use when checking a UI change against a project's design system, auditing an existing surface, reviewing someone else's UI diff, or before calling any visual change done. Also use before writing a new design gate, to decide whether the rule deserves one. Finds the project's own system first and defers to it; carries no project's tokens. Works in any repo.
---

# design-system — prove a UI change is right

## What this is

The method, not any project's tokens. It finds whatever design system the
current repo actually has, applies the checks that hold in any token-based
system, and tells you when a rule is worth a test rather than a reminder.

**If the project has its own design skill, that skill is the payload and it wins
on every specific.** This is what you do with it: this one for method, that one
for paths, tokens and per-domain acceptance tests.

**Name no project's skill here.** An earlier version asserted that a particular
repo's design skill existed. Section 1's own discovery command could not find
it, because the skill was untracked on the branch under test. A skill that
contradicts its own commands teaches you to trust the prose over the evidence,
which is backwards. Find it or report that you could not.

Read-only on source. Auditing is not editing.

**Every rule here came from a specific measured failure.** The rules are in this
file. The measurements live in `evidence.md` beside it, cited as §E1 to §E9.
Read a section there when a rule looks arbitrary, when you want to argue with
one, or before you write a rule of your own.

## 1. Find the system before you judge anything

**Skill version: 2026-08-19e.** Quote this in your report. A reviewer comparing
your findings to the skill needs to know which text you were served, and the
file on disk may have changed since.

**Run these from the repo root**, meaning the directory `git rev-parse
--show-toplevel` prints. Not the app directory, and not your cwd. In a monorepo
the two differ, and the choice changes the answer. Every command below takes its
file list from `git ls-files`, which is repo-root-relative whatever your cwd, so
this is the one decision you have to get right by hand.

**Use `git ls-files`, never a bare `find` or `grep -r`.** It lists only tracked
files on the branch you are on, excluding build output, ignored directories and
nested checkouts in one move. A `find`-based version ranked the one correct
token file **twelfth**, below the `head` cutoff, behind webpack chunks and stale
worktrees (`evidence.md` §E1). Keep the `-c` and the sort; ranking by hit count
is what makes the answer readable.

```bash
git rev-parse --is-inside-work-tree || echo "not a git repo: see the find fallback below"

# A project design skill: its own paths, tokens, acceptance tests. It wins.
git ls-files '*.claude/skills/*' | grep -i design

# Auto-loaded cards: the default to reach for while writing.
git ls-files '*CLAUDE.md' '*AGENTS.md'

# The entries. List the FILES, not the directory.
git ls-files '*docs/design/*'

# The tokens. Highest count is the definitions file; the rest are local overrides.
git ls-files -z '*.css' | xargs -0 -r grep -c -e '--[a-z][a-z0-9-]*[[:space:]]*:' \
  | grep -v ':0$' | sort -t: -k2 -rn | head
```

**Not a git repo? Bound the depth, and prune nested checkouts by name.**

```bash
timeout 60 find . -maxdepth 5 \
  \( -name node_modules -o -name .git -o -name dist -o -name build -o -name .next \
     -o -name worktrees -o -name .worktrees -o -name refwt -o -name vendor \) -prune \
  -o -name CLAUDE.md -print
```

`-not -path` filters output *after* walking a directory. `-prune` stops the walk.
Neither depth nor pruning is sufficient alone: at depth 3 the same search hit
**45% recall** while keeping two stale nested copies, and dropped six real cards
that all sat at depth 4. Prune nested checkouts **by name**, because depth does
not exclude them.

**A find-based count that matches your expectation is the easiest wrong answer
to accept.** Reconcile against `git ls-files` whenever git is available. If a
bounded find still times out, report that you could not establish the answer.
Never raise the timeout and never present a partial walk as a survey.

Full timings and the failure I shipped here: `evidence.md` §E2.

**These commands exit non-zero when they find nothing.** `xargs` returns 123 if
the command it ran failed on any batch, and `grep` "fails" on no match. A clean
"this repo has no design gates" therefore looks like a broken command to
anything checking `$?`. Judge these by their output, never by exit status, and
never wrap them in `set -e`.

Three traps in reading the output:

- **`docs/design/` is not proof of a design system.** In one repo tested it held
  `multi-provider-design.md` and `phase1-codex-provider-plan.md`, which are
  architecture plans. "Design" means two different things. Listing the files
  rather than the directory is what exposes this, so read the names.
- **Do not filter cards by directory name.** A repo whose only card sits at the
  repo root is real, and a `components|app|src` filter throws it away.
- **Silence is ambiguous.** An empty result means "absent" or "my command is
  broken", and you cannot tell which from the output. Before reporting absence,
  re-run the command with its filters removed and confirm the unfiltered version
  returns something.

### What the result means

| Docs | Tokens | What you may claim |
|---|---|---|
| present | present | Full audit. Sections 2 to 6 all apply. |
| absent | **present** | Audit against the tokens only. The token file IS the system. You may say a value is off-token; you may **not** say it is off-*intent*, because nobody wrote the intent down. |
| present | absent | Read the docs, then check whether the code implements them at all. |
| absent | absent | **Say so and stop.** |

The middle row is the normal state of a small repo, and it was missing from the
first version of this skill. An auditor hit it and had to improvise past the
gap. Auditing against a system nobody wrote down produces opinions, and an
opinion delivered as a finding is the exact failure this skill exists to
prevent. Offer to help write the first entry instead.

## 2. Look things up in this order

Stop at the first layer that answers you. Going deeper costs context for nothing.

1. **The card** (`components/CLAUDE.md` or equivalent). Loads automatically when
   you edit files in that tree. Covers the routine call: which duration, which
   radius, which surface token, which easing.
2. **The entry** (`docs/design/*.md`). The reasoning, the per-theme numbers, the
   rejected alternatives.
3. **The correction ledger**, if the project keeps one. What the owner has
   actually overridden before, with the quote and the date. **Nothing in a
   ledger binds until it is promoted into an entry.** Treat an unpromoted line
   as evidence of a preference, not as a rule.
4. **The gate** (the tests). Source is truth. A doc can be stale.

If the card and an entry disagree, **the entry wins and the card is a bug**. Fix
the card in the same change.

## 3. Find out what is already enforced, before you hand-audit anything

**Never carry a gate count in your head, and never write one into a document.**
Derive's skill wrote down "around 65 gate files" and was wrong by 36 within
weeks. Find the test roots, then read their listings with your own eyes:

```bash
git ls-files | grep -oE '(^|.*/)(tests?|__tests__|spec)/' | sort -u   # test roots
git ls-files '*test*' | grep -E '\.(ts|tsx|js|jsx|mjs|py|rb|go|rs|sql)$' \
  | grep -iE 'design|style|theme|token|contrast|a11y'
```

**The extension filter is load-bearing.** Without it, `*test*` matches any path
containing the word, and archived `*-design.md` specs sort to the top. A design
*spec* read as a design *gate* inverts what this section establishes.

**Do not hardcode directory names.** A locator tuned to one repo's layout
reports "no gates" rather than "I do not know where they are". The first version
found 105 gates in its home repo and **0** in the next one tested.

**Never count gates by grepping contents** for `design|token|theme`. That
returned **510** against a true **105**, sweeping up every auth-token test in
the repo. Section 5's first failure mode, committed by the tool meant to teach
it (`evidence.md` §E3).

**If the repo has no tests at all, say so and move on.** Sections 5 and 6 assume
a gate exists to reason about. With zero tests every rule is unenforced by
definition, and that is the most useful finding you can report.

### Is this one rule already gated?

**A grep can only produce candidates here. It can never answer the question.**
Treat a hit as a file to open, never as a yes.

```bash
# STEP 1, locate candidates. Search the PROPERTY NAME, nothing more.
git ls-files '*test*' | grep -E '\.(ts|tsx|js|jsx|mjs|py|rb|go|rs|sql)$' \
  | xargs -r grep -ln 'min-height'              # <- the property, not the value

# STEP 2, open each hit and answer ONE question: what corpus does it walk?
#   Hardcoded selector, or one imported stylesheet -> SURFACE-SCOPED.
#   Globs the tree, or derives its list from a manifest -> RULE-SCOPED.

# STEP 3, the only real proof. Break the rule in a file the gate should catch,
# run it, confirm it goes red naming that file. Then restore.
```

**Search a test for the property, never for the formatted value.** Source files
contain the literal `min-height: 100dvh`. Tests almost never do, because a real
gate is a helper plus a regex that no literal search can match:

```js
declarations(body, 'min-height').some((v) => /\d+(dvh|vh)\b/.test(v))
```

**The asymmetry is the point.** Search the violating form in *source*. Search
the property in *tests*. Source states values; tests describe them. Applying the
source rule to tests made an earlier version of this skill answer "not gated"
about a working gate, having previously answered "gated" about a file nothing
covered. Same command, inverted error, both wrong (`evidence.md` §E5).

**Do not carry a candidate count between branches.** One search returned 18 on
one branch and 21 on another, both correct. A count describes a checkout, never
the repo. Quote one only with the ref you measured it on, or leave it out.

**The asymmetry is the point.** "Search the violating form" is right for source
and wrong for tests, because source states values and tests describe them. An
earlier version of this skill applied the source rule to tests and inverted its
own answer: the old text said "gated" when nothing covered the file, the
corrected-but-still-literal text said "not gated" about a gate that exists.

**Surface-scoped versus rule-scoped is the distinction that matters, and it is
the one a grep cannot see.** A surface-scoped gate proves the rule holds on the
file it was written for. It says nothing about the file you are auditing.

**This exact shortcut deleted a real finding.** An auditor grepped, got one
genuine passing test back, read it as "gated, skip", and dropped its
highest-severity finding. The test asserts the rule and quotes the card, but its
corpus is one hardcoded selector in one stylesheet. Two files violated the rule.
The gate covered one.

A false "already gated" is the most expensive wrong answer this skill can give
you, because it ends the investigation and leaves no trace that it did.

When you report, say which kind you found. "Gated" and "gated on one surface,
not this one" are different findings, and only the second tells the owner a gate
needs promoting.

Then run them, and run whatever static scan the project has:

**Read every package.json, not the one in your cwd.** In a monorepo the root
manifest is usually a thin wrapper that forwards to a child, so scanning it
alone finds nothing.

```bash
git ls-files '*package.json' | grep -v node_modules | while read -r p; do
  node -e "
    const s=require('$PWD/'+'$p').scripts||{};
    for (const k in s) if (/design|compliance|contrast|token|stylelint|a11y|axe|(^|[:_-])ui([:_-]|\$)/i.test(k))
      console.log('$p'.padEnd(26), k, '->', s[k]);
  " 2>/dev/null
done
```

Scanning only `./package.json` at a monorepo root returned **0** matching
scripts. The same pattern across every tracked manifest returned **6**,
including `ui:compliance` and `colour:contrast`.

**`lint` is deliberately not in that pattern.** Bare ESLint proves nothing about
tokens, themes or motion, and matching it produced a confident false positive.
Dropping it is only safe *because* the scan is workspace-wide. Narrowing the
pattern and the search together is what produced the zero (`evidence.md` §E4).

### Enforcement is not only tests and scripts

**Look for write-time hooks.** A repo can enforce a rule at the moment code is
written rather than at CI. A hook is invisible to both scans above, so a
tests-and-scripts sweep reports "unenforced" for a rule that fires on every edit.

```bash
git ls-files '*hooks/*.sh' '*hooks/*.mjs' '*hooks/*.js' '.husky/*' \
  '*.claude/settings*.json' | grep -v node_modules
```

**Match executables, not the word "hooks".** A bare `*hooks/*` returned **275**
paths in the repo tested, because React component hooks live in `lib/hooks/`.
The extension filter cuts that to **10** and still finds the design hook.

Read what a hook actually does before you count it. A hook that *blocks* is a
gate. A hook that only *prints* is a reminder, so the rule is still unenforced
and belongs in your findings. Say which kind you found.

Hand-checking a rule that a test already proves **for the file in front of you**
is wasted work. Read that qualifier literally. It is the whole content of the
sentence.

**Only skip a rule when a gate covers the file you are auditing.** Not when a
gate exists. Not when a gate mentions the rule. The check is: does this gate's
corpus include this file, and have I seen it go red?

An earlier version of this line read "only hand-check what no gate covers", and
that phrasing is what produced the worst failure recorded in this skill. It
sounds identical and it is not. "A gate covers the rule" and "a gate covers this
file" differ by exactly one surface-scoped test, and the reader who cannot tell
them apart stops investigating and loses the finding.

Then ask whether the gap deserves a gate, using section 6.

## 4. The checks that hold in any token-based system

These transfer. The project's own skill adds the specifics on top.

**Every check below has a precondition. Establish it first, or the check
produces a confident wrong answer in a repo that never opted into the rule.**

- **Tokens before values.** A hard-coded colour, radius or duration in component
  CSS is a review failure, not a preference. *Precondition:* the repo has a
  token file. With no tokens there is nothing to prefer, so report the absence
  instead of flagging every literal. Detect the value, not the string: a naive
  hex grep flags `/* ...#ff0000 */` in a comment.

  **Before calling a literal a violation, check the token exists.** Look up the
  value in the scale. Three different findings hide here, and they need
  different fixes:

  | Situation | Finding |
  |---|---|
  | A token holds this exact value | Violation. Swap it. |
  | A token is one step away | Violation. Name the nearest token and the delta. |
  | **No token, the scale stops short** | **The scale is the bug, not the file.** |

  The third row is not pedantry. A repo's spacing scale topped out at 32px while
  a real surface needed 48px, so every author reaching past the end wrote a
  literal. Reporting six files as violators hides the single decision that
  causes all six. Report the gap in the scale, and say which values are
  currently stranded outside it.
- **Themed by default.** Every theme the project ships, not the one on your
  screen. *Precondition:* count the themes first.

  ```bash
  git ls-files '*.css' | xargs -r grep -ho "\[data-theme=[^]]*\]\|prefers-color-scheme: *[a-z]*" \
    | tr -d "\"'" | sed 's/\[data-theme=//; s/\]//' | grep -E '^[a-z-]+$|^prefers' | sort -u
  ```

  The `tr`, `sed` and `^[a-z-]+$` make the number **well-formed**. Raw, it
  reported 8 for a 4-theme app, counting quote variants and a `[data-theme=...]`
  doc comment separately.

  **Well-formed is not true. The count is an upper bound.** Normalised, the same
  app returned **5**. The extra entry appeared in 4 stylesheets with **0** token
  blocks defined, so that selector can never match. No CSS grep can strip a dead
  theme. Cross-check against the app's own list:

  ```bash
  git ls-files '*.ts' | xargs -r grep -n "ThemeId *=\|type Theme *=" | head   # the enum
  git ls-files '*.css' | xargs -r grep -c "data-theme='<name>'" | grep -v ':0$'  # blocks per theme
  ```

  A theme in CSS with no token block is a dead selector, worth one finding by
  itself. An auditor who trusts the raw count instead hand-checks every file
  against a theme that cannot render, and reports each one as a gap.

  **If the count is 1, this check is void.** Read literally without the count, it
  condemns every rule in a single-theme repo, which is how an auditor was nearly
  led to report 8 tokens as violations on a site that ships one theme.

  **A count of 0 is not "no themes", it is "no theme mechanism".** Nothing here
  is themed, so every colour is unconditional. Say that once and move on.
- **Reduced motion respected.** *Precondition:* find out whether a global reset
  exists.

  ```bash
  git ls-files '*.css' '*.tsx' '*.ts' | xargs -r grep -ln 'prefers-reduced-motion\|reducedMotion'
  ```

  If a global reset exists, a file with no reduced-motion block of its own is
  usually correct, not a gap. Confirm the change rides it. **If no global reset
  exists anywhere, that is exactly one finding, not one per animated
  declaration.** A repo with 12 animations and no reset has a single missing
  layer. Reporting 12 buries the fix under the symptoms.
- **Pointer parity.** A control that exists on hover must exist on touch. A
  hover gate with no `(pointer: coarse)` or `(hover: none)` fallback makes the
  control unreachable by finger.
- **No `transition: all`.** List the properties.
- **No raw easing curve where a token exists.**
- **Focus lands somewhere visible**, on every interactive element, in every
  theme.

### Accessibility, which is part of the design system and not a separate audit

An earlier version of this skill omitted these entirely, in a repo that ships a
`colour:contrast` script. **Run the project's own accessibility check before
hand-checking any of this**, and say you ran it.

- **Contrast is a property of a pair.** Report foreground *on* a named
  background, in the theme you measured, with the ratio. A colour alone cannot
  pass or fail. Reading computed colour is its own trap: `getComputedStyle` can
  return `lab()` or an unresolved `oklch(from ...)`, and a naive parser turns
  that into a plausible wrong number.
- **Touch targets.** Check the *rendered* box, including padding, not the icon
  glyph inside it. A 16px icon in a 44px button is correct.
- **`prefers-contrast` and forced colours**, if the project ships a
  high-contrast theme. A theme that exists but is never tested is a gap worth
  one finding.
- **Motion and focus already appear above.** Do not report them twice.

## 5. The two failure modes that produce false findings

Both are about evidence, and both have burned this method repeatedly. Check for
them by reflex.

### Measuring the string, not the property

The recurring error is asking whether a file *contains* some text instead of
whether the rule *holds*. Grepping for `Escape` cannot see a shared hook that
provides it. Counting `<Modal>` textually sweeps up comments.

**Worked example, measured in Derive.** For "controls hidden behind hover",
asking whether a hover block *mentions* `opacity` gave 36 flags for 1 real
defect: 2.8% precision. The common pattern is `.x:hover { opacity: 1 }` over a
class already resting at 0.5, which is the rule being *followed*. Asking the
effect question instead, *is it hidden at rest, and does nothing outside a
hover-gated block bring it back*, gave 2 flags, both registered exceptions, 0
false negatives. Same rule, same codebase, 18x fewer things to read.

**The recipe is always the same three steps.** Name the effect, not the token.
Find the *resting* value. Then find everything that overrides it.

```bash
# WRONG: "does a hover block mention opacity" -> flags the rule being followed
git ls-files '*.module.css' | xargs -r grep -l ':hover'

# RIGHT: "what is invisible at rest" -> flags only what the rule forbids
git ls-files '*.module.css' | xargs -r awk '/^\.[A-Za-z-]+ *\{/{c=$1}
  /opacity: *0;|visibility: *hidden|display: *none/{print FILENAME": "c}'
```

Verified on a fixture with four cases: a class resting at 0.5 that hovers to 1
(rule followed), a class resting at 0 that only hover reveals (rule broken), a
hex inside a comment, and a real hard-coded hex. The string check flagged 2 of 2
hover cases and 2 of 2 hex cases, half of each wrong. The effect check flagged
exactly the one broken class.

Four separate Derive findings were falsified this way: hover files 9 to 1, focus
rings 37 to 0, menu Escape 4 to 0, and a "12x12 tap target" on a branch that
never renders. **Establish the effective value**: follow overrides, media
queries, shared hooks, and computed defaults.

### A guard that cannot fail

A gate whose corpus walk returns `[]` passes every assertion and reports success
forever. Derive's inline-`<svg>` detector was structurally dead for months while
printing `0 violation(s)`. Fixing one character exposed 9 real sites.

The nastier variant is **partial, not empty**: the guard runs, passes, and checks
less than it claims. A focus-visible guard matched 1 of the 3 rules it was
written to cover, for months, because an ambiguous regex backtracked. The same
fix took it from 9410ms to 79ms. It was green the whole time.

So **assert the corpus size, not just the findings**. And if a gate is
mysteriously slow, suspect it is searching wrong before you raise its timeout.

> **Never trust a gate you have not seen fail.** Break the thing it guards,
> watch it go red with a diagnostic that names the offender, then restore. A
> green tick on an unproven gate is not evidence.

## 6. Adding a rule: gate, ratchet, reminder, or nothing

Decide with a count, never with an impression. Count the current violations
first, then pick the row.

**"Few" means you can read and judge every one of them, in practice under about
10. "Many" means you cannot, so you are sampling.** The boundary is your
capacity to inspect each case, not a fixed number. If you are guessing at the
population rather than reading it, treat it as many.

| Violations found | Mechanism |
|---|---|
| 0 | Absolute gate. |
| Few, **all wrong** | **Fix them in this change, then absolute gate**, with no exception list. The most common real case, and the one an earlier version of this table had no row for. Landing a ratchet here permanently grandfathers defects you could have deleted in minutes. |
| Few, all permanently correct | Absolute gate, each exception registered inline **with its reason**. |
| Few, mixed | Fix the wrong ones, register the correct ones, then absolute gate. |
| Many, mostly wrong | Diff-scoped ratchet: judge only the lines a change *adds*. Existing ones are grandfathered structurally and the count can only fall. |
| Many, mostly legitimate | **Build no gate.** A rule that must be suppressed constantly trains people to suppress it. Make it a write-time reminder, or leave it in the doc. |

Two more constraints worth holding:

- **Promote a gate from one surface to the whole rule only when recurrence is
  proven**: two existing gates encode the same rule, or the ledger shows the
  same correction twice. No speculative generalisation.
- **Is the violation decidable from the text alone?** If a regex can say the
  rule *applies* but never that it is *broken*, a gate produces false failures.
  That rule wants a reminder, not a test.

## Report shape

Every finding carries the rule, the file and selector, and the **effective**
value you established. No impressions. If you could not establish the effective
value, say that instead of guessing.

State plainly which checks a test already covers and which you did by hand. The
hand-done ones are the ones that can be wrong.
