---
name: html-design
description: Iterate on standalone HTML/CSS design mockups with a live-reloading preview served over Tailscale to Eden's laptop. Use when Eden wants to design, mock up, prototype, or iterate on a web page/UI/component and see it render on his laptop — "design a landing page", "mock up a pricing page", "make me a hero section", "iterate on this layout", "show me a design", "/html-design ...". The devbox is headless, so the preview is served (bound to 0.0.0.0) at http://devbox:4321 and auto-refreshes as the HTML is edited.
user_invocable: true
---

# html-design — live-reload HTML design loop

Iterate on standalone HTML design mockups on the headless devbox and watch them
update live on Eden's laptop over Tailscale. A tiny pure-stdlib Python server
(`server.py`, ~20 MB, no Node/npm) serves a design folder and pushes an
auto-refresh to the browser whenever a file changes.

## The loop

```
Eden: "/html-design a pricing page, dark, playful"
  1. ensure the live server is running (start once; reuse if already up)
  2. author the HTML with the frontend-design skill → write design/current.html
  3. print the clickable URL once:  http://devbox:4321

Eden (watching on laptop): "make the CTA bigger, less purple"
  → edit design/current.html → server pushes reload → laptop refreshes itself
```

The server is **persistent**: start it once, then every later edit auto-appears.
Only print the URL the first time (or if the server had to be (re)started).

## Workspace & files

- **Design folder (default `~/design-lab/`)** — persistent, cross-project, *never*
  inside a git repo so mockups don't get committed. Override with `--dir <path>`.
- **Working file: `current.html`** — the file you edit in place each iteration.
- **Variants** — when Eden wants alternatives, write `v2.html`, `pricing-alt.html`,
  etc. (or use `--new <name>`). With >1 file, `/` becomes an auto-built gallery
  with iframe previews; each variant page still live-reloads.
- Make designs **self-contained single files**: inline CSS/JS, CDN for Tailwind/
  fonts/icons is fine. No build step.

## Steps

### 1. Parse args
Free-text after the command is the design request. Recognized flags:
- `--dir <path>` — serve a different folder (default `~/design-lab`)
- `--port <n>` — default `4321`
- `--new <name>` — start a fresh variant file `<name>.html` instead of editing `current.html`
- `stop` — stop the server (`python3 ~/.claude/skills/html-design/server.py stop [port]`) and finish

### 2. Resolve the laptop-reachable host
Same pattern as the `dev` skill — the server binds `0.0.0.0`, but the URL you
print must use the tailnet name so it opens on the laptop:
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
- **New design or a polished ask:** invoke the `frontend-design` skill to author
  the HTML so it looks distinctive, not generic-AI. Write its output to
  `$DIR/current.html` (or the `--new` variant file).
- **Iteration on existing design:** edit the relevant file in place with Edit.
  Don't regenerate from scratch — make the targeted change Eden asked for.
- Keep it one self-contained `.html` file.

### 5. Tell Eden the URL (first time / after a (re)start only)
```
Design live at → http://<HOST>:<PORT>   (auto-refreshes as I edit)
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
