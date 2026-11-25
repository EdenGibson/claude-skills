import { test } from 'node:test';
import assert from 'node:assert';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, existsSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = fileURLToPath(new URL('./plan-number', import.meta.url));

const git = (cwd, ...args) =>
  execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();

const run = (cwd, ...args) =>
  execFileSync('node', [SCRIPT, ...args], { cwd, encoding: 'utf8' }).trim();

const README_HEAD = `# Plans

| Plan | Title | Status |
|---|---|---|
`;

const row = (n, slug) => `| [${n}](${n}-${slug}.md) | ${slug} | TODO |`;

/**
 * A plan file as the repo actually writes them: YAML front matter FIRST, then the heading.
 *
 * The front matter is not decoration — `pnpm plans:index` reads the `plan:` field and nothing
 * else to number a row. This fixture carried only the heading until 2026-08-03, which is
 * precisely why the renumber path could leave `plan:` stale for 420 plans undetected.
 */
function planBody(n, slug) {
  return (
    `---\nplan: "${n}"\ntitle: "${slug}"\npriority: "P2"\neffort: "M"\ndepends_on: "none"\n---\n\n` +
    `# Plan ${n}: ${slug}\n\n## Status\n\n- **Priority**: P2\n\n## Why this matters\n\nBecause.\n`
  );
}

/** Build a bare "origin" plus a clone, with the given plans already on main. */
function makeRepo(plans = []) {
  const root = mkdtempSync(join(tmpdir(), 'plannum-'));
  const origin = join(root, 'origin.git');
  const work = join(root, 'work');
  execFileSync('git', ['init', '--bare', '-b', 'main', origin]);
  execFileSync('git', ['clone', origin, work], { stdio: 'ignore' });
  git(work, 'config', 'user.email', 't@t.t');
  git(work, 'config', 'user.name', 'T');
  mkdirSync(join(work, 'plans'), { recursive: true });
  writeFileSync(
    join(work, 'plans', 'README.md'),
    README_HEAD + plans.map(([n, s]) => row(n, s)).join('\n') + '\n',
  );
  for (const [n, s] of plans) {
    writeFileSync(join(work, 'plans', `${n}-${s}.md`), planBody(n, s));
  }
  git(work, 'add', '-A');
  git(work, 'commit', '-m', 'seed');
  git(work, 'push', 'origin', 'main');
  return { root, origin, work };
}

/** Push a plan straight to origin from a second clone, simulating a rival session. */
function rivalPush(origin, root, n, slug) {
  const other = join(root, `rival-${n}`);
  execFileSync('git', ['clone', origin, other], { stdio: 'ignore' });
  git(other, 'config', 'user.email', 'r@r.r');
  git(other, 'config', 'user.name', 'R');
  writeFileSync(join(other, 'plans', `${n}-${slug}.md`), planBody(n, slug));
  const readme = join(other, 'plans', 'README.md');
  writeFileSync(readme, readFileSync(readme, 'utf8').trimEnd() + '\n' + row(n, slug) + '\n');
  git(other, 'add', '-A');
  git(other, 'commit', '-m', `plan(${n})`);
  git(other, 'push', 'origin', 'main');
}

/** Write an untracked local plan in the working checkout, plus its README row. */
function writeLocalPlan(work, n, slug) {
  const file = join(work, 'plans', `${n}-${slug}.md`);
  writeFileSync(file, planBody(n, slug));
  const readme = join(work, 'plans', 'README.md');
  writeFileSync(readme, readFileSync(readme, 'utf8').trimEnd() + '\n' + row(n, slug) + '\n');
  return file;
}

test('next: takes max+1 from origin/main', () => {
  const { work } = makeRepo([[347, 'alpha'], [348, 'beta']]);
  assert.equal(run(work, 'next'), '349');
});

test('next: never hands out a number an untracked local plan already holds', () => {
  // The ghost case: 349 exists only in the dirty checkout. Numbering blind to it
  // hands out 349 again and collides with work this box already wrote.
  const { work } = makeRepo([[348, 'beta']]);
  writeLocalPlan(work, 349, 'local-one');
  assert.equal(run(work, 'next'), '350');
});

test('next: never hands out a number held on another fetched branch', () => {
  const { work, origin, root } = makeRepo([[348, 'beta']]);
  const other = join(root, 'branchclone');
  execFileSync('git', ['clone', origin, other], { stdio: 'ignore' });
  git(other, 'config', 'user.email', 'r@r.r');
  git(other, 'config', 'user.name', 'R');
  git(other, 'checkout', '-b', 'feature');
  writeFileSync(join(other, 'plans', '349-on-a-branch.md'), planBody(349, 'on-a-branch'));
  git(other, 'add', '-A');
  git(other, 'commit', '-m', 'branch plan');
  git(other, 'push', 'origin', 'feature');
  assert.equal(run(work, 'next'), '350');
});

test('next: a far-off reserved band does not inflate the number', () => {
  // Derive carries plans/900-rehearsal.md, 901-added.md, 902-x.md from a loop rehearsal.
  // max+1 over everything hands out 903 and abandons the real 3xx sequence forever.
  const { work } = makeRepo([[348, 'beta'], [900, 'rehearsal'], [902, 'x']]);
  assert.equal(run(work, 'next'), '349');
});

test('next: skips a number retired by a rename, never recycles it', () => {
  const { work } = makeRepo([[348, 'beta'], [349, 'was-here']]);
  git(work, 'rm', '-q', 'plans/349-was-here.md');
  git(work, 'commit', '-q', '-m', 'retire 349');
  git(work, 'push', '-q', 'origin', 'main');
  assert.equal(run(work, 'next'), '350');
});

test('ghosts: reports untracked local plans whose slug already landed under another number', () => {
  const { work } = makeRepo([[329, 'tutor-answer-arialive'], [330, 'other-thing']]);
  writeLocalPlan(work, 328, 'tutor-answer-arialive'); // stale pre-renumber copy
  writeLocalPlan(work, 351, 'genuinely-new');
  const out = run(work, 'ghosts');
  assert.match(out, /328-tutor-answer-arialive/);
  assert.match(out, /329-tutor-answer-arialive/);
  assert.doesNotMatch(out, /genuinely-new/);
});

test('ship: pushes the plan to origin/main without touching the dirty checkout', () => {
  const { work, origin } = makeRepo([[348, 'beta']]);
  const file = writeLocalPlan(work, 349, 'my-plan');
  writeFileSync(join(work, 'src.ts'), 'dirty unrelated edit\n'); // checkout must stay dirty & untouched
  const out = run(work, 'ship', file);

  const landed = git(work, 'ls-tree', '-r', '--name-only', 'origin/main', '--', 'plans/');
  assert.match(landed, /plans\/349-my-plan\.md/);
  assert.match(out, /349/);
  // The rival-free case must not renumber.
  assert.doesNotMatch(out, /renumber/i);
  // Dirty unrelated file survives untouched, and we never committed it.
  assert.equal(readFileSync(join(work, 'src.ts'), 'utf8'), 'dirty unrelated edit\n');
  const committed = git(work, 'show', '--name-only', '--pretty=format:', 'origin/main');
  assert.doesNotMatch(committed, /src\.ts/);
});

test('ship: commit contains only the plan file and plans/README.md', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writeLocalPlan(work, 349, 'my-plan');
  writeFileSync(join(work, 'plans', 'stray-note.txt'), 'not part of the grant\n');
  run(work, 'ship', file);
  const files = git(work, 'show', '--name-only', '--pretty=format:', 'origin/main')
    .split('\n')
    .filter(Boolean)
    .sort();
  assert.deepEqual(files, ['plans/349-my-plan.md', 'plans/README.md']);
});

test('ship: renumbers when the number was claimed upstream after the plan was written', () => {
  // The exact reported failure: we wrote 349 correctly from origin/main,
  // then another session pushed its own 349 before we shipped.
  const { work, origin, root } = makeRepo([[348, 'beta']]);
  const file = writeLocalPlan(work, 349, 'my-plan');
  rivalPush(origin, root, 349, 'rival-plan');

  const out = run(work, 'ship', file);

  const landed = git(work, 'ls-tree', '-r', '--name-only', 'origin/main', '--', 'plans/');
  assert.match(landed, /plans\/350-my-plan\.md/, 'should land at the next free number');
  assert.match(landed, /plans\/349-rival-plan\.md/, "must not clobber the rival's plan");
  assert.match(out, /renumber/i, 'should report the renumber');

  // Heading inside the file follows the new number.
  const body = git(work, 'show', 'origin/main:plans/350-my-plan.md');
  assert.match(body, /^# Plan 350:/m);
  assert.doesNotMatch(body, /# Plan 349:/);

  // README carries a row for the new number and none for the old one.
  const readme = git(work, 'show', 'origin/main:plans/README.md');
  assert.match(readme, /350-my-plan\.md/);
  assert.doesNotMatch(readme, /349-my-plan\.md/);
  assert.match(readme, /349-rival-plan\.md/, "rival's README row must survive");
});

test('ship: renumber rewrites the YAML plan: field, not just the filename and heading', () => {
  // The real failure (423 -> 428, shipped 2026-08-02 as 03e01bd2e): ship renamed the file and
  // rewrote `# Plan NNN`, but left `plan: "423"` in the front matter. `pnpm plans:index` reads
  // ONLY that field, so the generated index emitted two rows numbered 423 and none for 428 —
  // the plan was invisible to the executor while looking perfectly correct in `ls`.
  const { work, origin, root } = makeRepo([[348, 'beta']]);
  const file = writeLocalPlan(work, 349, 'my-plan');
  rivalPush(origin, root, 349, 'rival-plan');

  run(work, 'ship', file);

  const body = git(work, 'show', 'origin/main:plans/350-my-plan.md');
  assert.match(body, /^plan: "350"$/m, 'front-matter plan: must follow the renumber');
  assert.doesNotMatch(body, /^plan: "349"$/m, 'the stale number must not survive in front matter');
});

test('ship: reconciles a front-matter number that already disagreed with the filename', () => {
  // Self-heal, not just renumber-heal: the filename is the plan's identity, so a `plan:` field
  // that drifted for any other reason is corrected on the way out rather than shipped stale.
  const { work } = makeRepo([[348, 'beta']]);
  const file = writeLocalPlan(work, 349, 'my-plan');
  writeFileSync(file, readFileSync(file, 'utf8').replace('plan: "349"', 'plan: "347"'));

  const out = run(work, 'ship', file);

  const body = git(work, 'show', 'origin/main:plans/349-my-plan.md');
  assert.match(body, /^plan: "349"$/m, 'filename is the identity; front matter must match it');
  assert.doesNotMatch(body, /^plan: "347"$/m);
  assert.match(out, /front matter/i, 'a silent correction is how the last bug hid — say so');
});

test('ship: leaves a plan with no front matter alone', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = join(work, 'plans', '349-my-plan.md');
  writeFileSync(file, `# Plan 349: my-plan\n\n## Why this matters\n\nBecause.\n`);

  run(work, 'ship', file);

  const body = git(work, 'show', 'origin/main:plans/349-my-plan.md');
  assert.doesNotMatch(body, /^---$/m, 'must not invent a front-matter block');
  assert.match(body, /^# Plan 349: my-plan$/m);
});

// Mirrors Derive's real plans/README.md: prose, a plan table whose first cell is a BARE
// number (no .md link), and further unrelated tables below it.
const REAL_README = `# Implementation Plans

Generated by the \`improve\` skill across successive passes.

- **Pass 1 — 2026-06-11** (audit at \`2c743251\`).

| Plan | Title | Priority | Effort | Depends on | Status |
|------|-------|----------|--------|------------|--------|
| 001 | Confirm and close out the rotation | P0 | M | — | TODO |
| 348 | Multi-cell range selection | P2 | M | — | TODO |

## Findings considered and rejected

| Finding | Severity | Outcome |
|---|---|---|
| L-5 no HSTS header | Low | **Plan 032** |
| I-1 worker-secret compare | Info | **Rejected** |
`;

test('ship: inserts into the plan table of a real-world README, not a later table', () => {
  const { work } = makeRepo([[348, 'beta']]);
  writeFileSync(join(work, 'plans', 'README.md'), REAL_README);
  git(work, 'add', '-A');
  git(work, 'commit', '-m', 'real readme');
  git(work, 'push', 'origin', 'main');

  const file = join(work, 'plans', '349-my-plan.md');
  writeFileSync(file, planBody(349, 'my-plan'));
  writeFileSync(
    join(work, 'plans', 'README.md'),
    REAL_README.replace(
      '| 348 | Multi-cell range selection | P2 | M | — | TODO |',
      '| 348 | Multi-cell range selection | P2 | M | — | TODO |\n| 349 | My plan | P2 | S | — | TODO |',
    ),
  );
  run(work, 'ship', file);

  const readme = git(work, 'show', 'origin/main:plans/README.md');
  const lines = readme.split('\n');
  const idx = lines.findIndex((l) => l.startsWith('| 349 |'));
  assert.notEqual(idx, -1, 'row must be present');
  assert.match(lines[idx], /My plan/, 'must reuse the authored row, not a synthesized one');
  assert.equal(lines[idx - 1], '| 348 | Multi-cell range selection | P2 | M | — | TODO |');
  // Must not have been dumped into the rejected-findings table at the bottom.
  assert.ok(idx < lines.findIndex((l) => l.startsWith('## Findings')), 'row landed in wrong table');
});

test('ship: renumbering rewrites a bare-number README cell', () => {
  const { work, origin, root } = makeRepo([[348, 'beta']]);
  writeFileSync(join(work, 'plans', 'README.md'), REAL_README);
  git(work, 'add', '-A');
  git(work, 'commit', '-m', 'real readme');
  git(work, 'push', 'origin', 'main');

  const file = join(work, 'plans', '349-my-plan.md');
  writeFileSync(file, planBody(349, 'my-plan'));
  writeFileSync(
    join(work, 'plans', 'README.md'),
    REAL_README.trimEnd() + '\n| 349 | My plan | P2 | S | — | TODO |\n',
  );
  rivalPush(origin, root, 349, 'rival-plan');
  run(work, 'ship', file);

  const readme = git(work, 'show', 'origin/main:plans/README.md');
  assert.match(readme, /^\| 350 \| My plan \|/m, 'bare-number cell must be renumbered');
  assert.doesNotMatch(readme, /^\| 349 \| My plan \|/m);
});

test('ship: local copy is cleared once it is on origin/main, so no ghost is left behind', () => {
  const { work, origin, root } = makeRepo([[348, 'beta']]);
  const file = writeLocalPlan(work, 349, 'my-plan');
  rivalPush(origin, root, 349, 'rival-plan');
  run(work, 'ship', file);
  assert.equal(existsSync(file), false, 'stale 349 copy must not linger as an untracked ghost');
  assert.equal(existsSync(join(work, 'plans', '350-my-plan.md')), false);
});

// --------------------------------------------------------------- research gate
//
// Warn-only by design (Eden, 2026-08-01): a missing ## Research section must be
// LOUD but must never block a push — the plan-executor loops ship plans
// unattended and a hard gate would strand them.

/** spawn plan-number capturing stdout, stderr and status separately. */
function runFull(cwd, ...args) {
  const r = spawnSync('node', [SCRIPT, ...args], { cwd, encoding: 'utf8' });
  return { out: r.stdout || '', err: r.stderr || '', status: r.status };
}

const RESEARCH_CITED = `# Plan 349: my plan

## Research

- Zod coerces on \`.coerce.number()\` since v3.20 — https://zod.dev/?id=coercion (checked 2026-08-01, zod 3.23.8)

## Why this matters

Because.
`;

const RESEARCH_DECLARED = `# Plan 349: my plan

## Research

No external surface — pure internal refactor of a private helper, no library, API, version or error-string angle.

## Why this matters

Because.
`;

const RESEARCH_EMPTY = `# Plan 349: my plan

## Research

TODO — will fill this in later.

## Why this matters

Because.
`;

const RESEARCH_MISSING = `# Plan 349: my plan

## Why this matters

Because.
`;

/** A plan whose only "## Research" heading is inside a fenced code block. */
const RESEARCH_FENCED_ONLY = `# Plan 349: my plan

## Why this matters

Here is the template we follow:

\`\`\`markdown
## Research

- Something https://example.com
\`\`\`

## Steps
`;

function writePlanWithBody(work, n, slug, body) {
  const file = join(work, 'plans', `${n}-${slug}.md`);
  writeFileSync(file, body);
  const readme = join(work, 'plans', 'README.md');
  writeFileSync(readme, readFileSync(readme, 'utf8').trimEnd() + '\n' + row(n, slug) + '\n');
  return file;
}

test('research: a section with a URL classifies as cited', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', RESEARCH_CITED);
  const r = runFull(work, 'research', file);
  assert.equal(r.status, 0);
  assert.match(r.out, /^cited\b/m);
  assert.match(r.out, /1 citation/);
});

test('research: the literal no-external-surface line classifies as declared', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', RESEARCH_DECLARED);
  const r = runFull(work, 'research', file);
  assert.equal(r.status, 0);
  assert.match(r.out, /^declared\b/m);
});

test('research: a section with neither a URL nor the declared line is empty', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', RESEARCH_EMPTY);
  const r = runFull(work, 'research', file);
  assert.match(r.out, /^empty\b/m);
  assert.match(r.err, /RESEARCH/i, 'must warn loudly on stderr');
});

test('research: no section at all classifies as missing', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', RESEARCH_MISSING);
  const r = runFull(work, 'research', file);
  assert.match(r.out, /^missing\b/m);
  assert.match(r.err, /RESEARCH/i);
});

test('research: warn-only — empty and missing still exit 0, never block', () => {
  const { work } = makeRepo([[348, 'beta']]);
  for (const body of [RESEARCH_EMPTY, RESEARCH_MISSING]) {
    const file = writePlanWithBody(work, 349, 'my-plan', body);
    assert.equal(runFull(work, 'research', file).status, 0, 'gate must never be hard');
  }
});

test('research: a ## Research heading inside a code fence does not count as the section', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', RESEARCH_FENCED_ONLY);
  const r = runFull(work, 'research', file);
  assert.match(r.out, /^missing\b/m, 'a fenced template block is not a real Research section');
});

test('ship: warns on stderr when Research is missing but still lands the plan', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', RESEARCH_MISSING);
  const r = runFull(work, 'ship', file);
  assert.equal(r.status, 0, 'warn-only: a missing Research section must not block the push');
  assert.match(r.err, /RESEARCH/i, 'the warning is the whole point — it must be visible');
  const landed = git(work, 'show', 'origin/main:plans/349-my-plan.md');
  assert.match(landed, /# Plan 349/, 'the plan must still be on origin/main');
});

test('ship: a properly cited plan ships with no research warning', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', RESEARCH_CITED);
  const r = runFull(work, 'ship', file);
  assert.equal(r.status, 0);
  assert.doesNotMatch(r.err, /RESEARCH MISSING/i, 'no false alarm on a cited plan');
});

// ------------------------------------------------- research: output requirements
//
// Bind the REQUIREMENTS, not the mechanism (Eden, 2026-08-01). Nothing can verify a
// research subagent actually ran — two test agents researched inline and said so — but
// the fields the dispatch guarantees ARE checkable. Warn-only, same as the rest.

const CITED_WITH_VERDICT = `# Plan 349: my plan

## Research

- Next 16 does not enable React Compiler by default — https://nextjs.org/docs/x (checked 2026-08-01, next@16.1.6)
- Manual memo remains correct when the compiler is off — https://react.dev/reference/react/memo (checked 2026-08-01, react@19.2.7)

**Approach verdict**: CURRENT — no compiler configured in next.config.ts.

**Reference implementation**: components/sidebar/PageTile.tsx:44

## Why this matters

Because.
`;

const CITED_NO_VERDICT = `# Plan 349: my plan

## Research

- Next 16 does not enable React Compiler by default — https://nextjs.org/docs/x (checked 2026-08-01, next@16.1.6)

## Why this matters

Because.
`;

test('research: a cited section with an Approach verdict passes clean', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', CITED_WITH_VERDICT);
  const r = runFull(work, 'research', file);
  assert.equal(r.status, 0);
  assert.match(r.out, /^cited\b/m);
  assert.doesNotMatch(r.err, /verdict/i, 'no complaint when the verdict is present');
});

test('research: a cited section with no Approach verdict still counts as cited but warns', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', CITED_NO_VERDICT);
  const r = runFull(work, 'research', file);
  assert.equal(r.status, 0, 'warn-only — an incomplete block never blocks');
  assert.match(r.out, /^cited\b/m, 'it is still cited; the verdict is a separate axis');
  assert.match(r.err, /verdict/i, 'must say the approach was never actually validated');
});

test('research: a declared opt-out needs no Approach verdict', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', RESEARCH_DECLARED);
  const r = runFull(work, 'research', file);
  assert.doesNotMatch(r.err, /verdict/i, 'no external surface means nothing to validate');
});

test('ship: warns about a missing Approach verdict but still lands the plan', () => {
  const { work } = makeRepo([[348, 'beta']]);
  const file = writePlanWithBody(work, 349, 'my-plan', CITED_NO_VERDICT);
  const r = runFull(work, 'ship', file);
  assert.equal(r.status, 0);
  assert.match(r.err, /verdict/i);
  assert.match(git(work, 'show', 'origin/main:plans/349-my-plan.md'), /# Plan 349/);
});

// ------------------------------------------------------ ship: issue label flip
//
// A plan that cites a GitHub issue marks that issue as spoken for at push time: add
// `planned`, remove `needs-triage`, and leave a comment carrying `<!-- plan: NNN -->`.
// Why here and not in a loop: no loop holds label authority, and the one skill that did
// (issue-work) was removed on 2026-08-03. Ship runs in Eden's own session, so it is the one
// place every plan passes through under his authority. Warn-only, like the research check:
// the plan is already on origin/main by the time this runs.

/** Install a fake `gh` on PATH that logs every call and answers from env. */
function fakeGh(root, env = {}) {
  const bin = join(root, 'fakebin');
  mkdirSync(bin, { recursive: true });
  const log = join(root, 'gh.log');
  const script = `#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$GH_LOG"
if [ -n "$GH_FAIL" ]; then echo "fake gh: forced failure" >&2; exit 1; fi
case "$1 $2" in
  "repo view") printf '%s\\n' "$GH_REPO_SLUG" ;;
  api*)
    case "$2" in
      */comments*) printf '%s\\n' "\${GH_COMMENTS_JSON:-[]}" ;;
      *) printf '%s\\n' "$GH_ISSUE_JSON" ;;
    esac ;;
esac
exit 0
`;
  writeFileSync(join(bin, 'gh'), script, { mode: 0o755 });
  return {
    log,
    env: {
      ...process.env,
      PATH: `${bin}:${process.env.PATH}`,
      GH_LOG: log,
      GH_REPO_SLUG: 'Acme/Repo',
      GH_ISSUE_JSON: JSON.stringify({
        number: 42,
        state: 'open',
        title: 'Eraser deletes the whole text box',
        body: 'I tried to rub out one word and the entire paragraph vanished.',
        labels: [{ name: 'needs-triage' }, { name: 'bug' }],
      }),
      GH_COMMENTS_JSON: '[]',
      ...env,
    },
  };
}

function runEnv(cwd, env, ...args) {
  const r = spawnSync('node', [SCRIPT, ...args], { cwd, encoding: 'utf8', env });
  return { out: r.stdout || '', err: r.stderr || '', status: r.status };
}

const ghLog = (log) => (existsSync(log) ? readFileSync(log, 'utf8') : '');

/** A plan as the template writes it, with an optional front-matter key and Status Issue bullet. */
function issuePlan(n, slug, { key = null, value = null, bullet = null, state = 'TODO — authored 2026-09-06' } = {}) {
  const fm = [`plan: "${n}"`, `title: "${slug}"`, `priority: "P2"`, `effort: "M"`, `depends_on: "none"`];
  if (key) fm.push(`${key}: "${value}"`);
  const status = ['- **Priority**: P2', '- **Planned at**: commit `abc1234`, 2026-09-06'];
  if (bullet) status.push(`- **Issue**: ${bullet}`);
  status.push(`- **State**: ${state}`);
  return (
    `---\n${fm.join('\n')}\n---\n\n# Plan ${n}: ${slug}\n\n## Status\n\n${status.join('\n')}\n\n` +
    `## Research\n\nNo external surface — internal.\n\n## Why this matters\n\nBecause.\n`
  );
}

test('ship: --related on an Issue bullet flips labels, comments with the marker, and writes issue:', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: 'https://github.com/Acme/Repo/issues/42' }));
  const r = runEnv(work, env, 'ship', file, '--related');
  assert.equal(r.status, 0);
  const calls = ghLog(log);
  assert.match(calls, /^issue edit 42 --repo Acme\/Repo --add-label planned --remove-label needs-triage$/m);
  assert.match(calls, /^issue comment 42 --repo Acme\/Repo /m);
  assert.match(calls, /<!-- plan: 349 -->/);
  assert.match(calls, /plans\/349-my-plan\.md/);
  assert.match(calls, /stays open/i, 'a related-only link must say the issue stays open');
  assert.match(r.out, /issue #42/);
  // The explicit related choice writes no closing keyword, and ship reports it.
  const landed = git(work, 'show', 'origin/main:plans/349-my-plan.md');
  assert.match(landed, /^issue: "42"$/m);
  assert.doesNotMatch(landed, /^closes_issue:/m);
  assert.match(r.out, /added issue: "42"/);
});

test('ship: closes_issue front matter says the PR will close the issue and adds no default', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'closes_issue', value: '42', bullet: 'https://github.com/Acme/Repo/issues/42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0);
  const calls = ghLog(log);
  assert.match(calls, /^issue edit 42 /m);
  assert.match(calls, /close this issue/i);
  assert.doesNotMatch(calls, /stays open/i);
  const landed = git(work, 'show', 'origin/main:plans/349-my-plan.md');
  assert.match(landed, /^closes_issue: "42"$/m);
  assert.doesNotMatch(landed, /^issue:/m);
  assert.doesNotMatch(r.out, /added issue:/);
});

test('ship: the marker and link carry the number the plan actually shipped at', () => {
  const { work, origin, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'issue', value: '42' }));
  rivalPush(origin, root, 349, 'rival-plan');
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0);
  assert.match(r.out, /renumbered 349 -> 350/);
  const calls = ghLog(log);
  assert.match(calls, /<!-- plan: 350 -->/);
  assert.match(calls, /plans\/350-my-plan\.md/);
  assert.doesNotMatch(calls, /<!-- plan: 349 -->/);
});

test('ship: the "`owner/repo` #N" bullet form resolves too', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: '`Acme/Repo` #42 (OPEN, filed 2026-08-26 by a tester)' }));
  const r = runEnv(work, env, 'ship', file, '--related');
  assert.equal(r.status, 0);
  assert.match(ghLog(log), /^issue edit 42 /m);
});

test('ship: a number that resolves to a pull request is skipped with a warning', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root, {
    GH_ISSUE_JSON: JSON.stringify({ number: 42, state: 'open', labels: [], pull_request: { url: 'x' } }),
  });
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'closes_issue', value: '42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0);
  assert.match(r.err, /pull request/i);
  const calls = ghLog(log);
  assert.doesNotMatch(calls, /^issue edit/m);
  assert.doesNotMatch(calls, /^issue comment/m);
});

test('ship: an issue URL in another repo is ignored, never flipped', () => {
  // Plan 246 cites mozilla/pdf.js#20899. A bare number lifted from that URL would label
  // whatever Derive issue happens to carry the same number.
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'closes_issue', value: 'https://github.com/mozilla/pdf.js/issues/20899' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0);
  assert.match(r.err, /outside Acme\/Repo/i);
  const calls = ghLog(log);
  assert.doesNotMatch(calls, /^api /m);
  assert.doesNotMatch(calls, /^issue /m);
});

test('ship: already labelled and already commented means no edit and no second comment', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root, {
    GH_ISSUE_JSON: JSON.stringify({ number: 42, state: 'open', labels: [{ name: 'planned' }] }),
    GH_COMMENTS_JSON: JSON.stringify([{ body: 'Planned earlier.\n\n<!-- plan: 349 -->' }]),
  });
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'issue', value: '42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0);
  const calls = ghLog(log);
  assert.doesNotMatch(calls, /^issue edit/m, 'idempotent: nothing to change');
  assert.doesNotMatch(calls, /^issue comment/m, 'idempotent: marker already there');
  assert.match(r.out, /issue #42/);
});

test('ship: a closed issue is left alone with a warning', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root, {
    GH_ISSUE_JSON: JSON.stringify({ number: 42, state: 'closed', labels: [{ name: 'needs-triage' }] }),
  });
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'issue', value: '42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0);
  assert.match(r.err, /closed/i);
  assert.doesNotMatch(ghLog(log), /^issue (edit|comment)/m);
});

test('ship: a gh failure is warn-only — the plan still lands and exit is 0', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { env } = fakeGh(root, { GH_FAIL: '1' });
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'issue', value: '42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0, 'the push already happened; a label failure must not turn it into an error');
  assert.match(r.err, /label flip|issue #42|gh/i);
  assert.match(git(work, 'show', 'origin/main:plans/349-my-plan.md'), /# Plan 349/);
});

test('ship: a plan with no issue reference never calls gh', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan', issuePlan(349, 'my-plan', { bullet: '—' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0);
  assert.equal(ghLog(log), '', 'no reference, no network');
  assert.doesNotMatch(git(work, 'show', 'origin/main:plans/349-my-plan.md'), /^issue:/m);
});

test('issue: dry run names the issue and reports a missing key without writing anything', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const bulletOnly = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: 'https://github.com/Acme/Repo/issues/42 (Sentry ABC-1)' }));
  let r = runEnv(work, env, 'issue', bulletOnly);
  assert.equal(r.status, 0);
  assert.match(r.out, /^no key: #42 in Acme\/Repo/);
  assert.doesNotMatch(ghLog(log), /^(api|issue) /m, 'read-only: no api reads, no writes');

  const closes = writePlanWithBody(work, 350, 'other-plan',
    issuePlan(350, 'other-plan', { key: 'closes_issue', value: '42' }));
  r = runEnv(work, env, 'issue', closes);
  assert.match(r.out, /^closes_issue: #42 in Acme\/Repo/);
  assert.match(r.out, /Closes #42/);

  const none = writePlanWithBody(work, 351, 'plain-plan', issuePlan(351, 'plain-plan', { bullet: '—' }));
  r = runEnv(work, env, 'issue', none);
  assert.match(r.out, /^none\b/);

  const outside = writePlanWithBody(work, 352, 'upstream-plan',
    issuePlan(352, 'upstream-plan', { bullet: 'https://github.com/mozilla/pdf.js/issues/20899' }));
  r = runEnv(work, env, 'issue', outside);
  assert.match(r.out, /^outside\b/);
});

test('ship: "from GitHub issue #N" in the State bullet counts when nothing else names the issue', () => {
  // Plans 551 and 577 shipped with the issue only in their State provenance line.
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { state: 'TODO — authored 2026-09-06 against `abc1234`, from GitHub issue #42 (feedback id x)' }));
  const r = runEnv(work, env, 'ship', file, '--related');
  assert.equal(r.status, 0);
  assert.match(ghLog(log), /^issue edit 42 /m);
  assert.match(git(work, 'show', 'origin/main:plans/349-my-plan.md'), /^issue: "42"$/m);
});

test('ship: a bare "#N" in State prose that is not called an issue is left alone', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { state: 'DONE — merged via PR #42 on 2026-09-05' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0);
  assert.equal(ghLog(log), '', 'a PR number must never be read as an issue');
});

// ------------------------------------------------- ship: the closing key is a choice
//
// `closes_issue:` is what makes the executor write `Closes #N`, which is the only thing that
// closes the issue on merge. Measured 2026-09-12: 0 of 672 plans carried it and 5 carried
// `issue:`, because ship wrote the safe `issue:` default by itself and nobody ever overrode it.
// 153 needs-triage issues were open, 7 of them with a merged PR against them. So the default is
// the defect. Ship now refuses to guess: the author names the key or the plan does not land.

test('ship: a bullet-only issue with no key and no flag stops before the commit', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: 'https://github.com/Acme/Repo/issues/42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.notEqual(r.status, 0, 'an unnamed key must block, never default');
  assert.match(r.err, /--closes/);
  assert.match(r.err, /--related/);
  // Nothing landed and nothing was destroyed: the author fixes the plan and ships again.
  assert.equal(existsSync(file), true, 'the local plan must survive a refusal');
  assert.match(git(work, 'ls-tree', '--name-only', 'origin/main', 'plans/'), /348-beta\.md/);
  assert.doesNotMatch(git(work, 'ls-tree', '--name-only', 'origin/main', 'plans/'), /349-my-plan\.md/);
  assert.doesNotMatch(ghLog(log), /^issue (edit|comment)/m, 'no issue is touched by a refusal');
});

test('ship: the refusal quotes the issue so the author decides without leaving the terminal', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: '#42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.notEqual(r.status, 0);
  assert.match(r.err, /Eraser deletes the whole text box/, 'the title, so the author sees the ask');
  assert.match(r.err, /entire paragraph vanished/, 'the reported symptom, not just the number');
});

test('ship: a gh failure still blocks — an unreadable issue is not a licence to guess', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { env } = fakeGh(root, { GH_FAIL: '1' });
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: '#42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.notEqual(r.status, 0);
  assert.match(r.err, /--closes/);
  assert.equal(existsSync(file), true);
});

test('ship: --closes writes closes_issue: and tells the issue the PR will close it', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: 'https://github.com/Acme/Repo/issues/42' }));
  const r = runEnv(work, env, 'ship', file, '--closes');
  assert.equal(r.status, 0);
  const landed = git(work, 'show', 'origin/main:plans/349-my-plan.md');
  assert.match(landed, /^closes_issue: "42"$/m);
  assert.doesNotMatch(landed, /^issue: "42"$/m, 'one key, never both');
  assert.match(ghLog(log), /close this issue/i);
  assert.doesNotMatch(ghLog(log), /stays open/i);
  assert.match(r.out, /added closes_issue: "42"/);
});

test('ship: --closes blocks when no front matter can carry closes_issue:', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { env } = fakeGh(root);
  const file = writePlanWithBody(
    work,
    349,
    'my-plan',
    '# Plan 349: my-plan\n\n## Status\n\n- **Issue**: #42\n\n## Research\n\nNo external surface — internal.\n',
  );
  const r = runEnv(work, env, 'ship', file, '--closes');
  assert.notEqual(r.status, 0, 'never land a plan when the chosen key was not written');
  assert.match(r.err, /front matter/i);
  assert.equal(existsSync(file), true);
});

test('ship: an explicit front-matter key needs no flag', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { log, env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'issue', value: '42', bullet: '#42' }));
  const r = runEnv(work, env, 'ship', file);
  assert.equal(r.status, 0, 'the author already chose; do not ask twice');
  assert.match(ghLog(log), /^issue edit 42 /m);
});

test('ship: a flag that contradicts the front matter is refused', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { key: 'issue', value: '42' }));
  const r = runEnv(work, env, 'ship', file, '--closes');
  assert.notEqual(r.status, 0);
  assert.match(r.err, /issue: "42"/, 'name the key already in the file');
  assert.equal(existsSync(file), true);
});

test('ship: --closes and --related together is refused', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: '#42' }));
  const r = runEnv(work, env, 'ship', file, '--closes', '--related');
  assert.notEqual(r.status, 0);
  assert.equal(existsSync(file), true);
});

test('ship: --closes on a plan that names no issue is refused, never silently ignored', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan', issuePlan(349, 'my-plan', { bullet: '—' }));
  const r = runEnv(work, env, 'ship', file, '--closes');
  assert.notEqual(r.status, 0);
  assert.match(r.err, /no issue/i);
  assert.equal(existsSync(file), true);
});

test('issue: the dry run names both flags instead of promising a default', () => {
  const { work, root } = makeRepo([[348, 'beta']]);
  const { env } = fakeGh(root);
  const file = writePlanWithBody(work, 349, 'my-plan',
    issuePlan(349, 'my-plan', { bullet: 'https://github.com/Acme/Repo/issues/42' }));
  const r = runEnv(work, env, 'issue', file);
  assert.equal(r.status, 0, 'the dry run reports, it never blocks');
  assert.match(r.out, /--closes/);
  assert.match(r.out, /--related/);
});
