---
name: html-design
description: "THE way to show Eden any HTML/CSS you are writing — a live-reloading design server at http://devbox:4321 that auto-refreshes his laptop on every edit, with LaTeX/KaTeX rendering built in. Use whenever you author or iterate on a web page, UI, component, layout, or visual variant — \"design a landing page\", \"mock up a pricing page\", \"make me a hero section\", \"iterate on this layout\", \"show me a design\", \"/html-design ...\". Also use it instead of the `preview` command (devbox:4340) for any HTML you are still editing: `preview` is a static URL Eden must refresh by hand, and is only for finished artifacts like charts, reports, or a built site directory. Never publish `~/design-lab/` through `preview`."
user_invocable: true
---

# html-design — live-reload HTML design loop

Iterate on standalone HTML design mockups on the headless devbox and watch them
update live on Eden's laptop over Tailscale. A tiny pure-stdlib Python server
(`server.py`, ~20 MB, no Node/npm) serves a design folder and pushes an
auto-refresh to the browser whenever a file changes.

**This server (4321), not `preview` (4340).** If you are writing the HTML, it
belongs here — the whole point is that Eden sees each edit land without touching
his browser. `preview` publishes a static URL he has to refresh by hand; it is for
artifacts you're done with (charts, generated reports, a built site dir).
`preview` now refuses paths under `~/design-lab/` for this reason.

## The loop

```
Eden: "/html-design a pricing page, dark, playful"
  1. ensure the live server is running (start once; reuse if already up)
  2. claim a filename from the design itself → ~/design-lab/pricing-dark.html
  3. author the HTML with the frontend-design skill → write that file
  4. print the clickable URL once:  http://devbox:4321/pricing-dark.html

Eden (watching on laptop): "make the CTA bigger, less purple"
  → edit pricing-dark.html → server pushes reload → laptop refreshes itself
```

The server is **persistent**: start it once, then every later edit auto-appears.
Only print the URL the first time (or if the server had to be (re)started).

## Workspace & files

- **Design folder (default `~/design-lab/`)** — persistent, cross-project, *never*
  inside a git repo so mockups don't get committed. Override with `--dir <path>`.
- **Never write `current.html`.** One folder is shared by every agent session
  running in parallel, across every worktree. A shared filename means the last
  writer wins and Eden watches someone else's design replace his.
- **Name the file after the design, and claim it before writing** —
  `pricing-dark.html`, `tooltip-hover.html`. Claim once, at the first write:

  ```bash
  s=pricing-dark; n=$s; i=2   # <- slug from the request, 2-3 words, kebab-case
  until (set -C; : > "$HOME/design-lab/$n.html") 2>/dev/null; do n="$s-$i"; i=$((i+1)); done
  echo "$HOME/design-lab/$n.html"   # the file to author and then edit in place
  ```

  `set -C` makes the create fail if the name is taken, so two sessions choosing
  the same slug get `pricing-dark.html` and `pricing-dark-2.html` rather than
  one clobbered file. Every later iteration edits the file you claimed — don't
  re-run the claim, or you strand Eden's open tab on the old name.
- **Variants** — when Eden wants alternatives, claim a second name the same way
  (or use `--new <name>`). With >1 file, `/` becomes an auto-built gallery
  with iframe previews, ordered **most-recently-edited first** (each card shows
  its age); each variant page still live-reloads.
- **A design page reloads only on its own edits.** The gallery at `/` still
  watches the whole folder, so a design another session just claimed appears
  there without a manual refresh.
- Make designs **self-contained single files**: inline CSS/JS, CDN for Tailwind/
  fonts/icons is fine. No build step.

## Math / LaTeX

**Just write TeX in the mockup — nothing to add to the file.** The server detects
math in a page and wires up KaTeX itself (vendored under `vendor/katex/`, served
from `/__katex/`; the devbox has no outbound internet, so never link a math CDN).

| Write | Renders |
|---|---|
| `\(x_i\)` | inline |
| `$$ \int_0^1 f $$`, `\[…\]` | display |
| `\begin{align}…\end{align}` (also `equation`, `gather`, `alignat`, `CD`) | display |
| `\ce{2H2 + O2 -> 2H2O}` | chemistry (mhchem auto-loads only for `\ce{}`/`\pu{}`) |

Rules that matter when authoring:

- **Single `$…$` is off by default** — a pricing page full of `$29` must not
  become math. Opt in per page with `<body data-latex="dollars">`.
- **Pages with no math get nothing injected** (KaTeX is ~600 KB), so a plain
  mockup is unaffected.
- **Math inside `<code>`/`<pre>`/`<script>` is left as literal text** — that's how
  you show TeX *source* next to its rendered form.
- **Injecting math with JS?** Put `data-latex` on any element to force KaTeX on,
  then call `window.renderMath(el)` after inserting. Options live in
  `window.katexOptions`.
- **Escape hatches:** `data-latex="off"` on `<body>` disables injection for that
  page; `class="no-katex"` disables it for one subtree. A page that loads its own
  KaTeX/MathJax is detected and left completely alone (no double-load).
- Gallery iframe previews render math too.

Working reference: `~/design-lab/latex-demo.html` (every case above, live).

## Steps

### 1. Parse args
Free-text after the command is the design request. Recognized flags:
- `--dir <path>` — serve a different folder (default `~/design-lab`)
- `--port <n>` — default `4321`
- `--new <name>` — use `<name>` as the slug instead of deriving one from the request
- `stop` — stop the server (`python3 ~/.claude/skills/html-design/server.py stop [port]`) and finish

### 2. Resolve the laptop-reachable host
Same pattern as the `dev` skill — the server binds the **tailnet IP** (never
`0.0.0.0`; this box has a public interface), and the URL you print must use the
tailnet name so it opens on the laptop:
```bash
if tailscale status >/dev/null 2>&1; then HOST=devbox; else HOST=localhost; fi
```
If `localhost`, tell Eden the tailnet looks down and he'll need SSH forwarding.

### 3. Ensure the server is running (start once, reuse after)
Start it as a **background** task. It self-detects an already-running instance on
the port and just reuses it (no double-bind), so it's safe to run every time:
```bash
python3 ~/.claude/skills/html-design/server.py "$DIR" "$PORT"
```
Run with `run_in_background: true`. It prints either
`Serving … (live-reload on)` or `… already running … (reusing).`

### 4. Author / edit the HTML
- **New design:** claim a filename with the `set -C` snippet above, then invoke
  the `frontend-design` skill to author the HTML so it looks distinctive, not
  generic-AI. Write its output to the file you claimed.
- **Iteration on existing design:** edit that same file in place with Edit.
  Don't regenerate from scratch — make the targeted change Eden asked for.
- Keep it one self-contained `.html` file.

### 5. Tell Eden the URL (first time / after a (re)start only)
Link the page itself, not the folder — the folder root is a gallery once more
than one design exists, and with parallel sessions it usually does.
```
Design live at → http://<HOST>:<PORT>/<file>.html   (auto-refreshes as I edit)
```
Claude Code renders it clickable. On later iterations just say what changed —
the page refreshes itself, no new URL needed.

## Notes
- **Verify the server is actually up** after step 3 before claiming the URL works
  (e.g. `curl -s -o /dev/null -w '%{http_code}' http://localhost:$PORT/`).
- Stop with `… server.py stop [port]` when Eden is done (optional; it's only ~20 MB).
- The server is stdlib-only and serves `0.0.0.0`, so anyone on the tailnet can
  reach it — fine for Eden's private tailnet; don't put secrets in mockups.
- Tests: `python3 ~/.claude/skills/html-design/test_server.py` (behavioral).
- KaTeX assets are vendored copies of `katex@0.16.45`; refresh them from a
  checkout's `node_modules/katex/dist` (css, `katex.min.js`,
  `contrib/{auto-render,mhchem}.min.js`, `fonts/*.woff2`) and bump
  `KATEX_VERSION` in `server.py`.
