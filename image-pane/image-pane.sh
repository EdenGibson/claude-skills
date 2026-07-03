#!/usr/bin/env bash
# image-pane: render an image with `chafa` in a new tmux split pane below
# Claude Code, so the user can SEE it without leaving the session. On a headless
# devbox there's no GUI viewer and the TUI only shows the attachment path, so we
# paint the image as colored terminal blocks instead.
#
# Usage:
#   image-pane <image> [<image> ...]          serve over HTTP for full-res browser viewing (default)
#   image-pane <image> [<image> ...] --cli    render inline in a tmux pane with chafa
#
# Multiple images are combined into ONE global display: a single web page (web,
# the default) or a single tmux pane (--cli) showing every image together.
#
# Exit codes:
#   0   ok (web server started, or pane opened)
#   64  usage error
#   66  file not found
#   69  no tmux session available (--cli only)
#   70  chafa not installed (--cli only)
#   71  python3 not installed (web mode — the default)

set -euo pipefail

# Parse args: collect image paths, note the optional --cli flag.
# Default is web (serve over HTTP, full resolution); --cli opts into the inline
# tmux/chafa render.
web=1
files=()
for arg in "$@"; do
  case "$arg" in
    --cli) web=0 ;;            # opt out of web: render inline in a tmux pane with chafa
    --web) web=1 ;;            # explicit web (also the default)
    -*) echo "image-pane: unknown option: $arg" >&2; exit 64 ;;
    *)
      if [ ! -f "$arg" ]; then
        echo "image-pane: file not found: $arg" >&2
        exit 66
      fi
      files+=("$(realpath "$arg")")
      ;;
  esac
done

if [ "${#files[@]}" -eq 0 ]; then
  echo "usage: image-pane <image> [<image> ...] [--cli]" >&2
  exit 64
fi

# web (default): serve the image(s) over HTTP for full-resolution browser viewing.
# Goal: ONE-SHOT access from the user's other devices (e.g. home laptop) — no
# port-forward. The devbox is on Tailscale and so is the laptop, so we bind to
# the *tailnet* interface and hand back the MagicDNS URL: the laptop reaches it
# directly. Binding to the tailnet IP (not 0.0.0.0) keeps it off the public
# interface. No tailnet? Fall back to localhost + an `ssh -L` hint.
# The server runs detached (nohup + disown) so this command returns immediately.
if [ "$web" -eq 1 ]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "image-pane: python3 not installed (needed to serve images; pass --cli to render inline instead)." >&2
    exit 71
  fi

  bind_ip="127.0.0.1"; url_hosts=("localhost"); tailnet=0
  if command -v tailscale >/dev/null 2>&1; then
    ts_ip="$(tailscale ip -4 2>/dev/null | head -1 || true)"
    if [ -n "${ts_ip:-}" ]; then
      ts_name="$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // empty' 2>/dev/null || true)"
      ts_name="${ts_name%.}"                 # strip trailing dot from MagicDNS name
      bind_ip="$ts_ip"; tailnet=1
      url_hosts=()
      [ -n "$ts_name" ] && url_hosts+=("$ts_name")   # nice MagicDNS URL first
      url_hosts+=("$ts_ip")                          # raw IP always works
    fi
  fi

  serve_dir="$(mktemp -d)"
  for f in "${files[@]}"; do
    ln -sf "$f" "$serve_dir/$(basename "$f")"
  done

  # Combine every image into ONE global display: a single index.html that stacks
  # all of them on one page. The user opens one URL and sees the whole set in
  # order (a before/after/diff comparison reads top-to-bottom). We build it even
  # for a single image so the entry URL ("/") is consistent either way.
  {
    cat <<'HTML_HEAD'
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>image-pane</title>
<style>
  body { margin:0; background:#0b0b0b; color:#bbb;
         font:14px/1.5 system-ui, -apple-system, sans-serif; }
  .wrap { display:flex; flex-direction:column; align-items:center;
          gap:28px; padding:28px 16px; }
  figure { margin:0; max-width:100%; }
  img { max-width:100%; height:auto; display:block;
        border:1px solid #2a2a2a; background:#000; }
  figcaption { margin-top:8px; text-align:center; color:#777;
               font-family:ui-monospace, monospace; }
</style>
</head>
<body>
  <div class="wrap">
HTML_HEAD
    for f in "${files[@]}"; do
      base="$(basename "$f")"
      printf '    <figure><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>\n' \
             "$base" "$base" "$base"
    done
    cat <<'HTML_TAIL'
  </div>
</body>
</html>
HTML_TAIL
  } > "$serve_dir/index.html"

  port=$(( (RANDOM % 20000) + 20000 ))
  nohup python3 -m http.server "$port" --bind "$bind_ip" --directory "$serve_dir" \
        >/dev/null 2>&1 &
  pid=$!
  disown
  sleep 0.3
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "image-pane: web server failed to start on port $port (port in use?)" >&2
    exit 1
  fi

  if [ "$tailnet" -eq 1 ]; then
    echo "serving ${#files[@]} image(s) as one page on your tailnet (pid $pid) — open on any Tailscale device, no forwarding:"
  else
    echo "serving ${#files[@]} image(s) as one page on localhost (pid $pid):"
  fi
  # One combined URL (the global display) per reachable host.
  for h in "${url_hosts[@]}"; do
    echo "  http://$h:$port/"
  done
  [ "$tailnet" -eq 0 ] && \
    echo "from your laptop:  ssh -L $port:localhost:$port <you>@<this-host>   then open the URL"
  echo "stop: kill $pid"
  exit 0
fi

# --- inline tmux render path (default) ---
if ! command -v chafa >/dev/null 2>&1; then
  echo "image-pane: chafa not installed (needed to render images in the terminal)." >&2
  exit 70
fi

# Pick a tmux session, mirroring glow-pane:
#   - If we're already inside tmux ($TMUX set), let tmux use the current one.
#   - Otherwise target the first existing session. We deliberately DON'T pin a
#     window/pane index — they shift as the user navigates, which is exactly the
#     fragility this script exists to avoid.
if [ -n "${TMUX:-}" ]; then
  target_args=()
else
  session="$(tmux list-sessions -F '#{session_name}' 2>/dev/null | head -1 || true)"
  if [ -z "$session" ]; then
    echo "image-pane: no tmux session running. Start one with 'tmux new' first." >&2
    exit 69
  fi
  target_args=(-t "$session")
fi

# Human-friendly title for the pane border: one file -> its basename;
# many -> "first.png (+N more)".
first_base="$(basename "${files[0]}")"
if [ "${#files[@]}" -gt 1 ]; then
  pane_title="${first_base} (+$((${#files[@]} - 1)) more)"
else
  pane_title="$first_base"
fi

# Command run INSIDE the new pane: the companion renderer + the image paths.
# Using a real script file (not a packed `bash -lc "..."` string) avoids quoting
# fragility and the instant-close bug — see render-in-pane.sh for the stdin
# hazard it handles. printf '%q' quotes the script path and each image safely.
render_script="$(dirname "$(realpath "$0")")/render-in-pane.sh"
cmd="bash $(printf '%q' "$render_script")"
for f in "${files[@]}"; do
  cmd+=" $(printf '%q' "$f")"
done

# `-v` = vertical split (new pane BELOW, full width) — right for wide artifacts
#        like 3-way comparison images. glow-pane uses -h for tall markdown.
# `-c`  = working dir for the new pane (first file's dir).
# `-P -F '#{pane_id}'` = print the new pane id so we can title it.
first_dir="$(dirname "${files[0]}")"
new_pane="$(tmux split-window "${target_args[@]}" -v -c "$first_dir" \
              -P -F '#{pane_id}' "$cmd")"

# Title the pane (visible in its border) and enable borders for THIS window only
# (window scope, so other tmux windows are untouched).
tmux select-pane -t "$new_pane" -T "$pane_title"
window_id="$(tmux display-message -p -t "$new_pane" '#{window_id}')"
tmux set-option -w -t "$window_id" pane-border-status top

echo "opened in tmux pane $new_pane (title: \"$pane_title\")"
echo "files: ${files[*]}"
echo "(press q or Enter in the pane to close it)"
