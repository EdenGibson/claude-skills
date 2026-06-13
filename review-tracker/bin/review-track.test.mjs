import { test } from 'node:test';
import assert from 'node:assert';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = fileURLToPath(new URL('./review-track', import.meta.url));

function run(args, { home, session = 'sess1' } = {}) {
  return execFileSync('node', [SCRIPT, ...args], {
    env: { ...process.env, HOME: home, CLAUDE_CODE_SESSION_ID: session, CLAUDE_SESSION_ID: '' },
    encoding: 'utf8',
  });
}
const statePath = (home, session = 'sess1') =>
  join(home, '.claude', 'skill-state', `${session}.json`);
const readState = (home, session = 'sess1') =>
  JSON.parse(readFileSync(statePath(home, session), 'utf8'));
const freshHome = () => mkdtempSync(join(tmpdir(), 'rt-'));

test('ran creates key with ran=true', () => {
  const home = freshHome();
  run(['ran', 'cr'], { home });
  assert.deepStrictEqual(readState(home).cr, { ran: true, total: 0, applied: 0 });
});

test('review sets total and resets applied', () => {
  const home = freshHome();
  run(['fixed', 'cr', '2'], { home });
  run(['review', 'cr', '5'], { home });
  assert.deepStrictEqual(readState(home).cr, { ran: true, total: 5, applied: 0 });
});

test('fixed increments by 1 by default and clamps to total', () => {
  const home = freshHome();
  run(['review', 'cr', '2'], { home });
  run(['fixed', 'cr'], { home });
  assert.strictEqual(readState(home).cr.applied, 1);
  run(['fixed', 'cr', '5'], { home });
  assert.strictEqual(readState(home).cr.applied, 2);
});

test('fixed before review increments from zero, ran=true, no clamp when total=0', () => {
  const home = freshHome();
  run(['fixed', 'tn', '3'], { home });
  assert.deepStrictEqual(readState(home).tn, { ran: true, total: 0, applied: 3 });
});

test('reset removes the session file', () => {
  const home = freshHome();
  run(['ran', 'cr'], { home });
  assert.ok(existsSync(statePath(home)));
  run(['reset'], { home });
  assert.ok(!existsSync(statePath(home)));
});

test('no session id is a silent no-op (exit 0, no file written)', () => {
  const home = freshHome();
  execFileSync('node', [SCRIPT, 'ran', 'cr'], {
    env: { ...process.env, HOME: home, CLAUDE_CODE_SESSION_ID: '', CLAUDE_SESSION_ID: '' },
    encoding: 'utf8',
  });
  const dir = join(home, '.claude', 'skill-state');
  assert.ok(!existsSync(dir) || readdirSync(dir).length === 0);
});

test('unknown key exits non-zero', () => {
  const home = freshHome();
  assert.throws(() => run(['ran', 'xx'], { home }));
});

test('cr and tn are independent', () => {
  const home = freshHome();
  run(['review', 'cr', '5'], { home });
  run(['review', 'tn', '3'], { home });
  run(['fixed', 'cr', '2'], { home });
  const st = readState(home);
  assert.strictEqual(st.cr.applied, 2);
  assert.strictEqual(st.tn.applied, 0);
});
