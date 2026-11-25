/**
 * Template for derive-web/tests/e2e/repro/<slug>.spec.ts
 *
 * Two rules the template exists to enforce:
 *   1. video: 'on', so a REFUTATION keeps its recording. The config's
 *      'retain-on-failure' deletes the video of a test that passes.
 *   2. Every operand of every comparison is asserted to exist before the
 *      comparison runs. Two nulls compare equal and read as a pass.
 */
import { test, expect } from '@playwright/test'
import { signIn } from '../helpers/supabaseMocks'

test.use({ video: 'on' })

test.describe('<issue>: <one-line symptom in the reporter\'s words>', () => {
  test('<what the user does> leaves <what the user sees>', async ({ page }) => {
    // signIn(page, options?) mocks Supabase auth, then opens the seeded page
    // onto the canvas. Measured 2026-09-11: 23 call sites in this directory,
    // every one of them bare. The qa accounts belong to the node probe
    // harness, never to a spec. See derive.md.
    await signIn(page)

    // --- POSITIVE CONTROL -------------------------------------------------
    // Prove the instrument can see this class of defect BEFORE trusting a
    // green result. Drive a state you know is broken, or assert the probe
    // reads a non-null baseline. Delete this block only when the test is red.
    const baseline = await page.evaluate(() => document.querySelectorAll('canvas').length)
    expect(baseline, 'probe found no canvas at all, so it cannot see the symptom').toBeGreaterThan(0)

    // --- DRIVE ------------------------------------------------------------
    // Read derive.md first. One arm per context. No storageState for a
    // cold-device arm. No abort() to simulate a hang.

    // --- MEASURE ----------------------------------------------------------
    const before = await page.evaluate(() => /* the number the symptom moves */ 0)
    const after = await page.evaluate(() => /* same number, after the action */ 0)

    expect(before, 'before was never produced').not.toBeNull()
    expect(after, 'after was never produced').not.toBeNull()
    expect(after, 'the reported symptom').toBe(before)
  })
})
