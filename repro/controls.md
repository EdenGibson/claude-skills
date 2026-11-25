# The two controls

A test result is a claim about your probe. Only a control turns it into a claim
about the product.

| Your test went | Run this control | Expect | Failure means |
|---|---|---|---|
| red | **negative**: remove the cause you named, rerun | green | the test does not bind to your cause |
| green | **positive**: inject the defect, rerun | red | your probe is blind to this defect |

## Why green is the dangerous result

A red test gets read again by whoever fixes it. A refutation closes a ticket and
nobody looks a second time. The positive control is the only thing between a
real defect and a closed ticket, so it is never the step you skip for time.

## The negative control, worked

`sandbox-red`, issue 3102: "I click on blank canvas and the selection bar just
stays there."

The test shows the toolbar, clicks the viewport centre, asserts the toolbar is
gone. Red, with `selection bar survived a click away`. The obvious mechanism is
`toolbars.js:8`, `dismissOnClickAway`.

Name that cause, then remove only that cause:

```js
getToolbar('selection-toolbar').dismissOnClickAway = true   // the named cause, gone
```

Measured: still red. `centre 640 360 -> target selection-toolbar | visible true`.

The test does not bind to the named cause. `layout.js:6` puts the toolbar rect
at x 520-760, y 340-384, and the viewport centre of 1280x720 is 640,360, inside
it. The probe clicked the bar, not the canvas. `documentClick` correctly leaves
a bar visible when you click the bar. **No defect.** The red was the probe.

## The positive control, worked

`sandbox-green`, ticket 2444: "importing a notebook on a shared template PDF
gives me the same page over and over."

The test imports an archive and asserts the `pdfPageIndex` values are unique.
Green, `1 page(s), indexes [0]`.

Before writing "cannot reproduce", inject the defect. The claim is about pages
that **share** a template, so give it two:

```js
pages: [{ id: 'p1', template: 'grid.pdf' }, { id: 'p2', template: 'grid.pdf' }]
```

Measured: `indexes [0,0] unique 1 of 2`. Red.

The probe can see the defect. The first fixture held one page, and one index is
trivially unique, so the green measured the fixture rather than the code.
`importer.js:12` hands every page the template's `firstPageIndex`. **The bug is
real.**

## How to inject, by layer

| Layer | Positive control |
|---|---|
| pure function | feed the input the claim describes, at the size it describes |
| store or reducer | drive the sequence, not one action |
| Playwright | patch the module under test, or drive a surface where the defect is known |
| network arm | register a route handler that never settles; never `abort()` |

## How to remove a cause, by layer

| Layer | Negative control |
|---|---|
| flag or config | flip it in the test's own setup |
| one-line defect | patch the value in place, do not rewrite the function |
| ordering defect | reorder only, change nothing else |
| timing defect | raise the one timeout, not every timeout |

Change one thing. A control that changes two things tells you nothing.

## Red flags

- "The test is red, so the bug is confirmed." Which bug?
- "It passed, so I cannot reproduce it." Can the probe see anything at all?
- "The fixture is representative." Is it large enough to express the defect?
- "The selector returned 0, so the control is gone." An absent selector also
  returns 0.
- "Both hashes matched." Two nulls match.
- "I will run the control if the result is surprising." An unsurprising result
  is exactly the one you will not check.

## The one line to keep

**Name what a null would mean before you run.**
