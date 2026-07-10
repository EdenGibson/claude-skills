---
name: hifi-design
description: Use when taking a Derive UI to high fidelity in the real React app instead of throwaway HTML — promoting an html-design mockup (e.g. current.html) to the real shipping component, or iterating on a real Derive component's look live on the laptop with all four themes. WYSIWYG, nothing to translate. Derive-only.
---

# hifi-design — high-fidelity React design loop

## Overview

The high-fidelity other half of `html-design`. Instead of mocking in throwaway HTML and
then re-building in React, you design **in the real Derive app** inside a disposable
`app/scratch` route, live-reloading on your laptop over the tailnet. Real tokens, real four
themes, real fonts, real Phosphor — so **what you see is what ships and there is nothing to
translate**.

Use `html-design` for cheap low-fidelity exploration; use this once a design is close to
final. Translating a token-native mockup into the scratch route is transcription, not
reinterpretation.

## The loop

1. **Ensure the harness** (idempotent — reuse if the files already exist):
   copy the two templates in `templates/` to **untracked** files, then locally ignore them so
   they never ship. Run from the Derive repo (or worktree) root — the repo root is `Derive/`,
   the Next app is `derive-web/`, so the ignore pattern is repo-root-relative:
   ```bash
   S=derive-web/.claude/skills/hifi-design/templates
   mkdir -p derive-web/app/scratch
   cp "$S/page.tsx"    derive-web/app/scratch/page.tsx
   cp "$S/Scratch.tsx" derive-web/app/scratch/Scratch.tsx
   GITDIR=$(git rev-parse --git-common-dir); case "$GITDIR" in /*) ;; *) GITDIR="$PWD/$GITDIR";; esac
   grep -qxF 'derive-web/app/scratch/' "$GITDIR/info/exclude" 2>/dev/null || \
     echo 'derive-web/app/scratch/' >> "$GITDIR/info/exclude"
   ```
   `derive-web/app/scratch/page.tsx` is stable chrome (a 4-theme switcher that renders
   `<Scratch/>`). `derive-web/app/scratch/Scratch.tsx` is the surface you edit every iteration.
   Using `--git-common-dir` makes the ignore apply from a worktree too.

2. **Ensure `next dev` on the tailnet** — use the `dev` skill (handles node/env/tailnet/port).
   **Reuse a warm server** if one is already up; don't cold-start twice. Print the URL only on
   first run/restart: `http://devbox:<port>/scratch`.

3. **Iterate in `Scratch.tsx`:**
   - *Given a mockup* (e.g. `~/design-lab/current.html`) → transcribe it into real tokens /
     components / Phosphor. Start from the token-native `derive-base.html` vocabulary.
   - *Fresh* → build directly in React.
   - Each save → Fast Refresh → the laptop updates.

4. **Graduate** (out of this loop): when the design is done it moves into the real component
   tree via the normal worktree → PR flow. The scratch route stays throwaway — never commit it.

## Why it stays lightweight

- No new build tooling — reuses `next dev` + the `dev` skill + the tailnet.
- One warm server per session; keep `Scratch.tsx` imports shallow so Fast Refresh stays snappy.
- Touches **zero tracked files**: the route is untracked and ignored via `.git/info/exclude`,
  so it is absent from CI builds and cannot ship.
- Renders under the real root layout, so `globals.css` tokens, the 4 themes, fonts, and the
  `PhosphorIconProvider` come for free (no toolchain re-creation).

## Auth

`AuthGuard` is global and redirects unauthenticated users, but a normal signed-in dev session
renders `/scratch` fine. To preview **without** a session (e.g. a headless check), add `/scratch`
to `AuthGuard`'s never-redirect carve-out (the same mechanism `/auth/desktop-bridge` uses) — a
one-line, dev-only change; revert it, never commit it.

## Verify it works

The route is a client tree, so a bare `curl` returns the app-shell skeleton (AuthGuard resolves
client-side). To confirm the design actually renders: open `http://devbox:<port>/scratch` in a
browser holding your dev session, or temporarily apply the auth carve-out above and curl for
token-driven markup, then revert.

## Common mistakes

- **Committing the scratch route.** It must stay untracked — verify `git status` is clean of it.
- **Hard-coded hex / emoji in `Scratch.tsx`.** Same design-system rules as the app: tokens via
  `var(--…)`, icons via `@phosphor-icons/react`. That is also what keeps graduation a copy-paste.
- **Cold-starting a second `next dev`.** Reuse the warm server; only (re)print the URL on restart.
- **Fighting the app's theme store.** The switcher sets `data-theme` directly for QA; if the app's
  `ThemeProvider` overrides it, use the app's own theme control instead.
