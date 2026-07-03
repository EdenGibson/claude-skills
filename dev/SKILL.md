---
name: dev
description: "Start the dev server (worktree-aware: assigns port based on worktree index)"
user_invocable: true
model: haiku
effort: low
---

# /dev — Start Dev Server

Start the project's dev server with worktree support. When running inside a git worktree, assigns a unique port so multiple worktrees can run simultaneously. The server binds to all interfaces and the printed URL uses the Tailscale hostname so it's clickable from Eden's laptop.

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

### 3. Resolve the laptop-reachable host

This devbox is on Eden's tailnet as `devbox` (MagicDNS). The dev server URL printed back to the user must use that hostname, not `localhost`, so clicking it opens the page on the laptop.

Pick the host like this:

```bash
if tailscale status >/dev/null 2>&1; then
  HOST=devbox          # MagicDNS short name — resolves from laptop
else
  HOST=localhost       # fallback if tailnet is down
fi
```

### 4. Start the dev server (bound to all interfaces)

The server **must bind to `0.0.0.0`**, not `127.0.0.1`, or the laptop can't reach it. Most frameworks default to localhost-only, so set the bind explicitly:

| Stack | How to bind to 0.0.0.0 |
|---|---|
| Next.js | `HOSTNAME=0.0.0.0 PORT=<port> npm run dev` (or append `-H 0.0.0.0 -p <port>` to the script) |
| Vite | `HOST=0.0.0.0 PORT=<port> npm run dev` (or append `--host --port <port>`) |
| FastAPI / uvicorn | `uvicorn app.main:app --reload --host 0.0.0.0 --port <port>` |
| Expo | already binds wide; pass `--port <port>` |
| Other | check the framework's bind flag; prefer env vars over editing scripts |

Start as a background task with `run_in_background: true`. Example for Next.js:

```bash
HOSTNAME=0.0.0.0 PORT=<port> npm run dev
```

### 5. Tell the user the URL

Print the clickable tailnet URL (Claude Code terminal renders it as click-to-open):

```
Dev server starting in the background → http://<HOST>:<port>
```

If `HOST=devbox`, the user clicks once and it opens in their laptop browser. If `HOST=localhost`, mention that the tailnet appears to be down and they'll need SSH forwarding instead.
