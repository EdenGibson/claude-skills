---
name: dev
description: "Start the dev server (worktree-aware: assigns port based on worktree index)"
user_invocable: true
model: haiku
effort: low
---

# /dev — Start Dev Server

Start the project's dev server with worktree support. When running inside a git worktree, assigns a unique port so multiple worktrees can run simultaneously. The server binds to the devbox's tailnet IP only, and the printed URL uses the Tailscale hostname so it's clickable from Eden's laptop.

**Never bind `0.0.0.0`.** This box has a public interface, so a wide bind exposes the dev server to the internet. `HOSTNAME=0.0.0.0`, `-H 0.0.0.0`, `--host` with no value, and a bare `next dev` with no `-H` all bind every interface.

## Steps

### 1. Detect project and dev command

Look at `package.json` (or equivalent) to find the dev script. Common patterns:
- `npm run dev` / `pnpm dev` (JS/TS projects)
- `python -m uvicorn app.main:app --reload` (FastAPI)
- Check project CLAUDE.md or README for specific instructions

If the project has a subdirectory structure (e.g., a `frontend/` or app directory with its own `package.json`), identify the correct directory to run from.

### 2. Assign port based on worktree index

Run:

```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```

Parse `git worktree list --porcelain`. The first listed worktree is the main one. Find the 0-based index of the current worktree in the list and compute:

```
PORT = default_port + index
```

Where `default_port` is the project's standard port (3000 for Next.js, 5173 for Vite, 8000 for Python, etc.). The main worktree gets the default port, additional worktrees get default+1, default+2, etc.

If not in a git repo or no worktrees exist, just use the default port.

### 3. Resolve the bind address and the URL host

This devbox is on Eden's tailnet as `devbox` (MagicDNS), which resolves to the tailnet IP. Bind the server to that IP, and print the URL with `devbox` so clicking it opens the page on the laptop.

```bash
if BIND=$(tailscale ip -4 2>/dev/null) && [ -n "$BIND" ]; then
  HOST=devbox          # MagicDNS short name, resolves to $BIND from the laptop
else
  BIND=127.0.0.1       # tailnet down: loopback only, never 0.0.0.0
  HOST=localhost
fi
```

### 4. Start the dev server on the tailnet IP

Pass the bind address explicitly. Most dev servers either default to loopback, which the laptop can't reach, or to every interface, which is unsafe here.

| Stack | Command |
|---|---|
| Next.js (pnpm) | `sleep infinity \| pnpm dev -H "$BIND" -p <port>`, see the stdin note below |
| Next.js (npm) | `sleep infinity \| npm run dev -- -H "$BIND" -p <port>` |
| Vite | `npm run dev -- --host "$BIND" --port <port>` |
| FastAPI / uvicorn | `uvicorn app.main:app --reload --host "$BIND" --port <port>` |
| Other | find the framework's bind flag and pass `$BIND`; prefer flags over editing scripts |

**Hold stdin open for Next.js (v16+/Turbopack):** its dev TUI treats stdin EOF as "quit", and background tasks run with stdin from `/dev/null` — the server goes Ready, serves a request or two, then exits cleanly (code 0, trailing `[?25h`) within seconds. Piping `sleep infinity` into it keeps stdin open so it stays up. Harmless for versions that don't need it. If another framework's dev server also exits ~immediately with code 0 despite a successful start, suspect the same stdin-EOF quit and apply the same pipe.

Start it as a background task with `run_in_background: true`, and do not append `&`. A trailing `&` orphans the server and the task reports done at once. Send the log to `$CLAUDE_JOB_DIR/tmp/` when that variable is set, never to shared `/tmp`. Example for Next.js:

```bash
cd <app dir> && sleep infinity | pnpm dev -H "$BIND" -p <port> > "$CLAUDE_JOB_DIR/tmp/dev-<port>.log" 2>&1
```

### 5. Confirm the bind, then tell the user the URL

Wait for the server's ready line in the log, then check the listening address:

```bash
ss -ltn | grep ":<port>\b"
```

The line must read `LISTEN ... <BIND>:<port>`. If it shows `0.0.0.0:<port>`, `*:<port>` or `[::]:<port>`, stop the server at once and tell the user.

Only then print the clickable URL (Claude Code terminal renders it as click-to-open):

```
Dev server running → http://<HOST>:<port>
```

If `HOST=devbox`, the user clicks once and it opens in their laptop browser. If `HOST=localhost`, mention that the tailnet appears to be down and they'll need SSH forwarding instead.
