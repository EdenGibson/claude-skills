#!/usr/bin/env bash
# glow-pane: render a markdown file with `glow` in a new tmux split pane
# next to Claude Code, so the user can read it without leaving the session.
#
# Usage: glow-pane <file> [<file> ...]
#
# Exit codes:
#   0   pane opened
#   64  usage error
#   66  file not found
#   69  no tmux session available

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: glow-pane <file> [<file> ...]" >&2
  exit 64
fi

# Resolve all files to absolute paths up front; bail early if any are missing.
files=()
for arg in "$@"; do
  if [ ! -f "$arg" ]; then
    echo "glow-pane: file not found: $arg" >&2
    exit 66
  fi
  files+=("$(realpath "$arg")")
done

# Pick a tmux session:
#   - If we're already inside tmux ($TMUX set), let tmux use the current one.
#   - Otherwise, target the first existing session (Claude Code is typically
#     launched from outside tmux on this devbox, but the user has a session
#     attached separately).
if [ -n "${TMUX:-}" ]; then
  target_args=()
else
  session="$(tmux list-sessions -F '#{session_name}' 2>/dev/null | head -1 || true)"
  if [ -z "$session" ]; then
    echo "glow-pane: no tmux session running. Start one with 'tmux new' first." >&2
    exit 69
  fi
  target_args=(-t "$session")
fi

# Build the command glow will run inside the new pane. printf '%q' handles
# spaces, quotes, and other shell metacharacters in filenames.
quoted=""
for f in "${files[@]}"; do
  quoted+=" $(printf '%q' "$f")"
done
cmd="glow -p${quoted}"

# Compute a human-friendly title for the new pane:
#   - one file  → its basename
#   - many files → "first.md (+N more)"
first_base="$(basename "${files[0]}")"
if [ "${#files[@]}" -gt 1 ]; then
  pane_title="${first_base} (+$((${#files[@]} - 1)) more)"
else
  pane_title="$first_base"
fi

# `-h` = horizontal split (new pane to the right).
# `-c` = working directory for the new pane (the first file's dir, so any
#        shell that drops out after glow exits lands somewhere useful).
# `-P -F '#{pane_id}'` = print the new pane's id so we can target it for naming.
first_dir="$(dirname "${files[0]}")"
new_pane="$(tmux split-window "${target_args[@]}" -h -c "$first_dir" \
              -P -F '#{pane_id}' "$cmd")"

# Set the pane title (visible in the pane border) and make sure borders are
# actually shown in this window. pane-border-status is set at -w (window)
# scope so we don't mutate the user's other tmux windows.
tmux select-pane -t "$new_pane" -T "$pane_title"
window_id="$(tmux display-message -p -t "$new_pane" '#{window_id}')"
tmux set-option -w -t "$window_id" pane-border-status top

echo "opened in tmux pane $new_pane (title: \"$pane_title\")"
echo "files: ${files[*]}"
echo "(press q to close the pane)"
