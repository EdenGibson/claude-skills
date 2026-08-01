import { test } from 'node:test';
import assert from 'node:assert';
import { execFileSync } from 'node:child_process';
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

function planBody(n, slug) {
  return `# Plan ${n}: ${slug}\n\n## Status\n\n- **Priority**: P2\n\n## Why this matters\n\nBecause.\n`;
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
