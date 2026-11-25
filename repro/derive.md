# Reproducing in Derive

Read this before the first Playwright line. Every trap below has already cost a
run.

## Where the artefacts go

| Kind | Path |
|---|---|
| e2e repro | `derive-web/tests/e2e/repro/<slug>.spec.ts` |
| unit repro | `derive-web/tests/<mirrored path>/<name>.repro.test.ts` |
| finding or refutation | `docs/superpowers/findings/YYYY-MM-DD-<slug>.md` |
| branch | `repro/<issue>-<slug>`, in a worktree under `~/code/.worktrees/` |

`derive-web/tests/e2e/repro/` already holds 23 specs. Read the two nearest
neighbours before writing a new one. `docs/superpowers/findings/2026-08-18-c10-blank-ink-on-pan.md`
is the model: red test, `file:line`, measured number.

## Search before you probe

```bash
grep -n -i "<Identifier>" /home/eden/worklog/design-qa-sep/log.html
ls derive-web/tests/e2e/repro/ | grep -i <surface>
```

Grep by code identifier, never by the words that describe the symptom. A heading
makes an argument; it does not index the surface. A nonzero count is a list to
open, every hit, not the first promising one. Grep again when the walk lands
somewhere you did not plan for.

## Running an e2e repro

```bash
cd <worktree>/derive-web
cat /proc/loadavg                      # print it beside the result
PORT=3177 PLAYWRIGHT_BASE_URL=http://localhost:3177 \
  npx playwright test tests/e2e/repro/<slug>.spec.ts --project=chromium
```

**Pass both variables.** `playwright.config.ts` sets
`reuseExistingServer: !process.env.CI` and defaults the URL to port 3000.
Whatever already listens on 3000 gets driven, including another worktree's
static export of a different branch. `PORT` alone moves only `next dev`.
Name the owner with `ss -lptnH | grep ':3000'`, then
`readlink /proc/<pid>/cwd`.

**Load above about 20 fakes failures.** Measured at load 128: a settled
`getByRole().click()` landed on the backdrop and read as a defect. A red run
under load is indistinguishable from a regression. Wait for load under 12, then
rerun.

## Video

`playwright.config.ts:62` sets `video: 'retain-on-failure'`, and Playwright 1.58
has no `--video` flag. A red repro keeps its recording. A **green** one, the
refutation case, has the recording deleted. So every repro spec opens with:

```ts
test.use({ video: 'on' })
```

## Two sign-in worlds, and they do not mix

**A spec under `tests/e2e/` mocks Supabase.** No account exists and none is
needed. Every one of the 23 repro specs calls it bare.

```ts
import { signIn } from '../helpers/supabaseMocks'
await signIn(page)        // mocks auth, lands on /home, opens the seeded page
```

`signIn(page, options)` takes one options object, never positional credentials.
The fields are `user`, `dbRoutes` and `aiConsent`, defined at
`derive-web/tests/e2e/helpers/supabaseMocks.ts:365`. Two siblings stop earlier:
`signInToHome` stays on the dashboard, and `bootstrapCanvasSession` skips the
form for a dev build that already holds a session.

**An ad-hoc probe against a running server uses a real account.** A node script
driving a dev server or a static export on 3400 or 3420 talks to the local
Supabase, so the account is the variable. Password `QaPassw0rd!2026`.

- `qa1@qa.derive.test` never finished onboarding. Every route, `/home`
  included, bounces to `/welcome`. Correct behaviour. Use it only for the
  pre-onboarding surface.
- `qa2@qa.derive.test` and `qa3@qa.derive.test` are onboarded.

A probe that signs in on one port and reads on another runs signed out, and the
helper still returns true. Assert the landing URL, not the boolean.

`/settings` is not a route. Settings opens as a panel from the sidebar.

## Probe traps that produce a false green

- **One arm per browser context.** Derive is local-first, so a second arm in a
  shared context reads the first arm's cached answer and reports clean.
- **Never reuse `storageState` for a cold-device arm.** The saved state carries
  `localStorage`, which warms `betaAccessStore`, `entitlementStore` and
  settings. IndexedDB is empty but the key-value cache is warm, and that is not
  a new device.
- **The tell is a collapsed request count.** A gate that really blocks shows a
  retry ladder. Two requests and an instant render means you measured a
  background revalidation.
- **Never test a hang with `abort()`.** Aborting is the arm the app already
  survives. Register a route handler that never calls fulfil, continue or abort.
- **The vacuous pass.** Two nulls compare equal. An absent selector matches 0.
  Assert each operand was produced, then compare. Name what a null would mean
  before the run.
- **Query the accessibility tree, not the app's own `aria-label`.** A missing
  element and a renamed one look identical to a selector.

## Probe traps that produce a false red

- `cursor: pointer` inherits, so a pointer sweep over-counts. 433 became 129.
- A text box measures its content, not `boxHeight`.
- A target-size sweep must hit-test, not read the box.
- A hit-test of 0 is pointer occlusion, not visual hiding.
- WebKit never focuses a bare scroll container; Chrome does. Re-run every
  keyboard check in WebKit.

## Running unit repros

```bash
pnpm test --maxWorkers=3 tests/lib > lib.log 2>&1; echo "EXIT=$?"
```

Never launch an unfiltered `pnpm test` as a background task. It is killed with
no output. Read pnpm's own exit code; a grep for `Test Files` turns a green
remote run red, because the dispatcher prints its own summary instead.

## Handing over

`/repro` stops at the red test plus the mechanism. `superpowers:systematic-debugging`
owns the fix. `pnpm verify` is the fixer's gate, not yours.
