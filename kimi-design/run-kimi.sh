#!/usr/bin/env bash
# Headless Kimi K3 design generation into ~/design-lab/.
# Usage: run-kimi.sh <outfile> <brief-file> [model]
# Prints the kimi transcript to stdout; the HTML lands at $DIR/<outfile>.
set -uo pipefail

KIMI="${KIMI_BIN:-$HOME/.kimi-code/bin/kimi}"
DIR="${DESIGN_DIR:-$HOME/design-lab}"
OUT="${1:?usage: run-kimi.sh <outfile> <brief-file> [model]}"
BRIEF="${2:?missing brief file}"
MODEL="${3:-k3}"

# --- preflight -------------------------------------------------------------
[ -x "$KIMI" ] || { echo "FATAL: kimi not found at $KIMI" >&2; exit 3; }
[ -f "$BRIEF" ] || { echo "FATAL: brief file not found: $BRIEF" >&2; exit 3; }

if [ ! -f "$HOME/.kimi-code/config.toml" ] && [ ! -f "$HOME/.kimi-code/auth.json" ]; then
  echo "FATAL: kimi-code is not authenticated." >&2
  echo "  Eden must run:  kimi login    (device-code flow, needs a browser)" >&2
  echo "  Then re-run this skill." >&2
  exit 4
fi

# Never let an --auto agent loose inside a git repo.
if git -C "$DIR" rev-parse --git-dir >/dev/null 2>&1; then
  echo "FATAL: $DIR is inside a git repo; refusing to run --auto there." >&2
  exit 5
fi

mkdir -p "$DIR"

# --- run -------------------------------------------------------------------
# --auto: fully autonomous, never blocks on a question (required for headless).
# --add-dir: workspace scope. cwd is $DIR so relative writes land there.
PROMPT="$(cat "$BRIEF")

Write the finished page to exactly one self-contained file: $DIR/$OUT
Inline all CSS and JS. No build step. Overwrite the file if it exists.
Do not create any other files. Do not touch anything outside $DIR."

cd "$DIR" || exit 3
echo "--- kimi $MODEL -> $DIR/$OUT ($(date -Is)) ---"
"$KIMI" -p "$PROMPT" --auto -m "$MODEL" --add-dir "$DIR"
rc=$?
echo "--- kimi exited rc=$rc ---"

if [ -f "$DIR/$OUT" ]; then
  echo "OK: $DIR/$OUT ($(wc -c <"$DIR/$OUT") bytes, $(wc -l <"$DIR/$OUT") lines)"
else
  echo "MISS: $DIR/$OUT was not created" >&2
  exit 6
fi
exit $rc
