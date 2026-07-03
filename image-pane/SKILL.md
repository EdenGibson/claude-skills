---
name: image-pane
description: Use when the user wants to actually SEE an image on this headless devbox — a screenshot, PNG, diagram, chart, or a comparison/QA artifact Claude generated — where the TUI only shows the file path (`› [image] …`) and there's no GUI viewer to open it. By default it serves the image(s) over the Tailscale tailnet as one full-resolution web page the user opens on their laptop in one shot (no port-forwarding); pass `--cli` to render inline as colored blocks with chafa in a tmux split pane instead. Multiple images are combined into one global display. Triggers include "show me that image/screenshot", "open the png", "let me see it", "view that diagram", "I can't see the image", "render that picture", "pull up the screenshot", or any time you reference a local image file the user would obviously want to look at.
model: haiku
effort: low
---

# image-pane

Make an image the user can actually look at. **By default this serves the image(s) over HTTP** so the user opens a single full-resolution page in their browser; with `--cli` it renders the image with `chafa` in a fresh tmux split pane **below** Claude Code instead. On a headless devbox the TUI only shows the attachment *path* and there's no image app to open the file — this gets it in front of the user's eyes. The image-counterpart of `glow-pane` (which does the same for markdown).

**Web is the default — full resolution, one-shot.** The devbox is on Tailscale and so is the user's laptop, so the server binds to the *tailnet* interface and prints a MagicDNS URL (e.g. `http://devbox.tailf179c3.ts.net:PORT/`) the user opens on any signed-in device **in one shot — no port-forward, no `ssh -L`**. This gives real pixels: zoomable, tiny text legible, shareable in a browser. When the user is right there in the terminal and wants a zero-setup glance without a browser, pass `--cli` to paint the image as colored blocks inline (chafa auto-detects sixel/kitty graphics for a crisp render, or its rich Unicode symbols otherwise; tmux passthrough carries graphics to the outer terminal).

## When to use

- A screenshot, PNG, diagram, chart, or a QA/comparison artifact (e.g. a 3-way before/after render) is the thing the user wants to *look at*
- The user just saw a `› [image] …` line in the TUI and asks "what is that / let me see it"
- They say "show me", "open", "view", "render", "pull it up", "I can't see the image"

**Don't use when:**
- The file isn't an image the browser (default) or chafa (`--cli`) can show (PNG/JPEG/GIF/WebP/SVG/TIFF/AVIF/QOI/XWD)
- Web (default) needs python3 (script exits 71); fall back to `--cli`
- `--cli` needs a running tmux session (script exits 69) and chafa (exits 70); fall back to the default web path, describing the image, or sending it with the file tool

## How to invoke

Run the helper script via Bash. It handles path quoting, tailnet detection, the combined page, and (for `--cli`) pane sizing and titling:

```bash
~/.claude/skills/image-pane/image-pane.sh <path-to-image>
```

The default serves the image over the tailnet and prints a URL the user opens on their laptop — returns immediately (server runs detached) and prints the `kill` line to stop it.

**Multiple images are combined into one global display.** Pass as many as you like:

```bash
~/.claude/skills/image-pane/image-pane.sh a.png b.png c.png
```

All images are stacked **on one page** in order (with `--cli`, in **one pane** in order), so a before/after/diff comparison reads top-to-bottom. The command prints **one** URL for the whole set.

Paths can be relative to cwd or absolute (the script calls `realpath`).

**`--cli` (inline terminal render, zero setup):** paint the image(s) as colored blocks with `chafa` in a tmux split pane below Claude Code. Instant, needs no browser and no forwarding — good for a quick glance when the user is right there in the terminal. chafa auto-picks the best output the terminal supports (sixel/kitty graphics, else its rich Unicode symbol set). Multiple images render in order in the same pane (the global display).

```bash
~/.claude/skills/image-pane/image-pane.sh <path> --cli
```

The default (web) is the high-detail path; reach for `--cli` when the user wants an instant in-terminal look or has no browser at hand.

## Critical: don't Read it back

**After serving the page (or opening the `--cli` pane), do NOT use the `Read` tool on that image.** The point is the *user* sees it with their eyes — Reading the pixels just burns Claude's context for no reason. Confirm the URL/pane and which file(s) it shows, then stop.

## Quick reference

| Situation | What to do |
|-----------|-----------|
| User asks to see an image you just referenced | Open it without asking — default serves a tailnet URL |
| Ambiguous which image | Ask which one (one-liner) before opening |
| Multiple images | Combined into one global display automatically (one page / one pane) |
| User wants an instant in-terminal glance (no browser) | add `--cli` → inline chafa render in a tmux pane |
| File doesn't exist | Script exits 66; tell the user the path was wrong |
| python3 missing (web/default) | Script exits 71; fall back to `--cli` |
| chafa not installed (`--cli`) | Script exits 70; fall back to the default web path / describing |
| No tmux running (`--cli`) | Script exits 69; use the default web path, a short description, or the file tool |

## Exit codes

- `0` — ok (web server started, or `--cli` pane opened)
- `64` — no image argument given / unknown option
- `66` — file not found
- `69` — no tmux session available (`--cli` only)
- `70` — chafa not installed (`--cli` only)
- `71` — python3 not installed (web mode — the default)

## Notes on the web mechanics (default)

- **One global display:** the script writes a single `index.html` into a temp serve dir that stacks every image (each in a `<figure>` with its filename as a caption) and serves it with `python3 -m http.server`. The user opens `http://<host>:<port>/` and sees the whole set; individual images are still fetchable at `/<basename>`.
- **Tailnet one-shot:** if Tailscale is up, it binds to the *tailnet IP* (not `0.0.0.0`, so it's off the public interface and off loopback) and prints the MagicDNS URL first, raw tailnet-IP URL as fallback. No tailnet → localhost + an `ssh -L` hint.
- **Detached:** the server runs via `nohup … & disown`, so the command returns immediately and prints `stop: kill <pid>`.

## Notes on the tmux mechanics (`--cli`)

- Uses `tmux split-window -v` (**vertical** split = new pane *below*, full width) — right for wide artifacts like comparison renders. (glow-pane uses `-h` because markdown is tall/narrow; images are usually wide.)
- **Auto-detects the target session** the same way glow-pane does: `$TMUX` if Claude Code is inside tmux, else the first session from `tmux list-sessions`. It deliberately does **not** pin a window/pane index — those shift as the user navigates, which silently breaks `-t 0:4`-style targeting (the exact bug this script avoids).
- **Quality:** runs `chafa -w 9` with no forced symbol set, so chafa auto-picks the best output — sixel/kitty graphics (crisp) when the terminal supports it, rich Unicode symbols otherwise. Do **not** force `--symbols=block`; that's the coarse, chunky mode.
- The in-pane work lives in a **companion script, `render-in-pane.sh`** (not a packed `bash -lc "…"` string — that was fragile and closed the pane instantly). `image-pane.sh` just launches it with the image paths.
- **Closing:** chafa prints and exits immediately (unlike glow's pager), so the script holds the pane open and closes on a deliberate **`q` or Enter**. It does *not* use "press any key": `chafa -w 9` sends terminal-capability queries whose replies come back on stdin and, over SSH, arrive late — "any key" would treat a stray reply byte as the keypress and slam the pane shut the instant it opened (this bit me in development). So it drains stdin until quiet, then loops reading single bytes, ignoring everything that isn't `q`/Enter. Ctrl-C also closes.
- Pane is **auto-named** with the image basename (or `"first.png (+N more)"`). `pane-border-status top` is set at *window* scope only, so other tmux windows are untouched.
