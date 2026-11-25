# evidence.md — the measured cases behind design-system

Every rule in `SKILL.md` came from a specific failure. The rules are in the
skill. The measurements are here, so the skill stays short enough to read.

Read this when a rule looks arbitrary, when you want to argue with one, or when
you are about to write a rule of your own.

---

## E1. Discovery: `git ls-files` versus `find`

**Rule it produced:** use `git ls-files`, never a bare `find` or `grep -r`.

A `find`-based discovery returned 12 token files for a small site. Four were
compiled webpack chunks. Six belonged to stale detached worktrees. The one file
on the checked-out branch ranked **twelfth**, below the `| head` cutoff, so the
only correct answer was invisible.

Repos invent their own names for nested copies: `refwt/`, `.worktrees/`,
`.claude/worktrees/`. An exclusion list can never be complete. `git ls-files`
excludes build output, ignored directories and nested checkouts in one move,
because it lists what git tracks on the branch you are on.

## E2. The non-git fallback, and a wrong number I shipped

**Rule it produced:** depth 5, prune nested checkouts by name, reconcile against
`git ls-files` when git is available.

Hunting `CLAUDE.md` in a monorepo with 11 real cards:

| Form | Time | Found | Recall |
|---|---|---|---|
| `-not -path '*/node_modules/*'` | killed at 120s | 340 paths | unusable |
| `-prune` on node_modules, .git, dist, build | killed at 120s | never finished | 0 |
| `-maxdepth 3` + that prune list | 0.04s | 7 paths, 2 stale copies | **45%** |
| `-maxdepth 5` + prune checkouts by name | 2.1s | 11 paths | **100%** |

`-not -path` filters output *after* walking a directory. `-prune` stops the walk.

**The depth-3 row shipped in an earlier version of the skill.** It returns 7,
which matched the count already written in the table, so a spot check confirmed
it. Six real cards were missing, all at depth 4, all hot subsystems: `lib/tutor`,
`lib/math`, `lib/storage`, `lib/recognition`, `components/canvas`,
`supabase/functions`. The stated justification, that design system files live
near the top of a tree, was false in exactly the repos big enough to need this
skill. Two `refwt/` copies survived at the same time, because depth does not
exclude a nested checkout. Prune those by name.

## E3. Counting gates by content

**Rule it produced:** find test roots, filter by extension, never grep contents
for the topic.

Counting gate files by grepping contents for `design|token|theme` returned
**510** against a true **105**, because it sweeps up every auth-token test and
every incidental theme mention in the repo.

Without an extension filter, `git ls-files '*test*'` matches any path containing
the word, and three archived `*-design.md` specs sorted to the top of the list.
A design *spec* read as a design *gate* inverts the thing the section
establishes.

An earlier locator searched only directories named `design`, `styles` or `ui`.
That found 105 gates in the repo it was written in and **0** in the next repo
tested, whose tests sit in a plain `tests/`. A locator tuned to one layout
reports "no gates" rather than "I do not know where they are".

## E4. The script scan, and a regression I introduced

**Rule it produced:** read every tracked `package.json`, not the one in cwd.

Dropping `lint` from the match pattern was correct on its own: nearly every JS
repo has a `lint` script and bare ESLint proves nothing about tokens or motion.
Matching it produced a confident false positive in the first repo tested outside
the original.

Combined with scanning only `./package.json`, it returned **0** matching scripts
at a monorepo root, down from 1. The root manifest was a thin wrapper. Scanning
every tracked manifest returned **6**, including `ui:compliance` and
`colour:contrast`, which are precisely what the section exists to find.

Narrowing the pattern and narrowing the search at the same time produced the
zero.

## E5. The `100dvh` gate: the worst failure recorded here

**Rules it produced:** grep the property in tests, never the value; classify a
gate as surface-scoped or rule-scoped; skip a rule only when a gate covers *the
file you are auditing*.

An auditor checked "no `min-height: 100dvh` on full-height surfaces". It grepped,
got one test back, read that as "gated", skipped the rule, and dropped its
highest-severity finding.

The test is genuine:

```js
it('sizes .root with a definite height, not min-height', () => {
    const body = rulesFor(css, '.root').join(';');       // <- ONE stylesheet
    expect(declarations(body, 'min-height').some((v) => /\d+(dvh|vh)\b/.test(v)),
      '.root must not pin a min-height to the viewport').toBe(false);
```

It asserts the rule, quotes the card, and passes. `css` is one component's
stylesheet and the selector is hardcoded. **Two files violate the rule. The gate
covers one.**

### The first correction was also wrong, in the opposite direction

The fix was "search the violating form, `min-height: 100dvh`, not the topic".
Tests almost never contain a formatted value. The real assertion is a helper plus
a regex, which no literal-string search can match.

Measured: `min-height: *100dvh` across the test tree returned exactly one file,
and the match was a **comment** quoting the rule. Strip the comments and the same
search returns **0**, while the gate sits three lines below, working.

So the original text said "gated" when nothing covered the file, and the
correction said "not gated" about a gate that exists. Same command, inverted
error. Searching the bare property name returns a couple of dozen candidates and
never misses.

**The asymmetry is the lesson.** Search the violating form in *source*. Search
the property in *tests*. Source states values; tests describe them.

### The contradiction that kept winning

Two lines below the new warning, older text still read "only hand-check what no
gate covers". That sentence is what produced the skip. "A gate covers the rule"
and "a gate covers this file" differ by exactly one surface-scoped test.

## E6. Theme counting

**Rule it produced:** normalise, then treat the result as an upper bound and
cross-check against the app's own theme list.

A raw grep reported **8** themes in a 4-theme app, because `[data-theme="dark"]`
and `[data-theme='dark']` are different strings and two hits were
`[data-theme=...]` inside a doc comment.

Normalising quotes and filtering to `^[a-z-]+$` returned **5**. Still wrong. The
extra entry, `oled`, appears in 4 stylesheets and has **0** token blocks defined,
so the selector can never match. The app's own enum lists 4.

Normalisation makes a count well-formed. It cannot make it true. A theme present
in CSS with no token block is a dead selector, and worth one finding by itself.

## E7. Counts are properties of a checkout

The candidate-file count for one search returned **18** on one branch and **21**
on another. Both correct. An earlier version of the skill quoted 21 as a fact
about the repo.

A separate case: a worked example claimed 7 matching files where the true figure
on the branch under test was 6, and its category breakdown was non-disjoint,
because one file carried both explanatory prose and the real assertion.

Quote a count only with the ref you measured it on, or leave it out. The argument
almost never needs the number.

## E8. Guards that cannot fail

**Rule it produced:** assert corpus size, and never trust a gate you have not
seen fail.

An inline-`<svg>` detector walked an empty corpus and printed `0 violation(s)`
for months. Fixing one character exposed 9 real sites.

The nastier variant is partial rather than empty. A focus-visible guard matched 1
of the 3 rules it was written to cover, for months, because an ambiguous regex
backtracked. The same fix took it from 9410ms to 79ms. It was green throughout.

A gate that is mysteriously slow is usually searching wrong. Suspect that before
raising its timeout.

## E9. Effect over string, quantified

**Rule it produced:** ask what the rule forbids, not what the file contains.

For "controls hidden behind hover", asking whether a hover block *mentions*
`opacity` gave 36 flags for 1 real defect, 2.8% precision. The common pattern
`.x:hover { opacity: 1 }` over a class already resting at 0.5 is the rule being
*followed*.

Asking the effect question, is it hidden at rest and does nothing outside a
hover-gated block bring it back, gave 2 flags, both registered exceptions, 0
false negatives. Same rule, same codebase, 18x fewer things to read.

Four further findings were falsified the same way: hover files 9 to 1, focus
rings 37 to 0, menu Escape 4 to 0, and a "12x12 tap target" on a branch that
never renders.
