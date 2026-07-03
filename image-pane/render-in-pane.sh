#!/usr/bin/env bash
# Runs INSIDE the tmux pane (launched by image-pane.sh). Renders one or more
# images with chafa, then holds the pane open until the user deliberately
# presses q or Enter.
#
# Why a separate script (not a `bash -lc "..."` string in image-pane.sh):
# packing all this into a quoted string was fragile and, combined with the
# stdin hazard below, closed the pane instantly. A real file is robust.
#
# The stdin hazard: `chafa -w 9` auto-detects the terminal's graphics support by
# sending capability queries; the replies come back ON STDIN. Over SSH they can
# arrive late (network latency). A naive "press any key" read treats a stray
# reply byte as the keypress and closes the pane immediately. So we (1) drain
# stdin until it's quiet, then (2) loop reading single bytes and only close on a
# real q/Enter — stray escape-sequence bytes (ESC, '[', digits, ';', letters)
# never match, so the pane survives them.

usage() { echo "usage: render-in-pane.sh <image> [<image> ...]" >&2; exit 64; }
[ $# -ge 1 ] || usage

# High quality: -w 9 (max work) and NO forced symbols, so chafa picks the best
# output the terminal supports — sixel/kitty graphics if available, else its
# rich Unicode symbol set. tmux passthrough carries graphics to the outer term.
chafa -w 9 "$@"

# (1) Drain stray capability-query replies until stdin is quiet for 0.2s.
while read -rs -t 0.2 -n 64 _ 2>/dev/null; do :; done

if [ "$#" -gt 1 ]; then
  title="$(basename "$1") (+$(($# - 1)) more)"
else
  title="$(basename "$1")"
fi
printf '\n[ %s — press q or Enter to close ]' "$title"

# (2) Only a deliberate q/Enter closes; everything else (incl. late stray
# bytes) is ignored. Ctrl-C also closes (kills this script -> pane exits).
while true; do
  IFS= read -rsn1 k 2>/dev/null || break
  case "$k" in q|Q|'') break ;; esac
done
