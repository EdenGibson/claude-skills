#!/usr/bin/env bash
# Installer for the review-tracker statusline feature.
# Idempotent: safe to re-run. Auto-deploys the standalone files (helper + hooks)
# and the CLAUDE.md convention; for the SHARED files (status-line.sh, settings.json)
# it detects whether the change is already applied and otherwise points you at the
# snippet rather than risk a bad auto-patch.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

echo "Installing review-tracker into $CLAUDE_DIR ..."
mkdir -p "$CLAUDE_DIR/bin" "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/skill-state"

install -m 0755 "$HERE/bin/review-track"           "$CLAUDE_DIR/bin/review-track"
install -m 0644 "$HERE/bin/review-track.test.mjs"  "$CLAUDE_DIR/bin/review-track.test.mjs"
install -m 0755 "$HERE/hooks/review-detect.sh"     "$CLAUDE_DIR/hooks/review-detect.sh"
install -m 0755 "$HERE/hooks/prune-skill-state.sh" "$CLAUDE_DIR/hooks/prune-skill-state.sh"
echo "  ✓ helper + hooks deployed"

# --- CLAUDE.md convention (auto-append if absent) ---
CMD="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$CMD" ] && grep -q "Review tracking (statusline)" "$CMD"; then
  echo "  ✓ CLAUDE.md convention already present"
else
  [ -f "$CMD" ] && printf '\n' >> "$CMD"
  cat "$HERE/snippets/CLAUDE.md.snippet" >> "$CMD"
  echo "  ✓ appended convention to $CMD"
fi

# --- status-line.sh (guide, don't auto-patch) ---
SL="$CLAUDE_DIR/hooks/status-line.sh"
if [ -f "$SL" ] && grep -q "REV_SEGMENT" "$SL"; then
  echo "  ✓ status-line.sh already renders the rev: segment"
else
  echo "  ! ACTION NEEDED: add the rev: segment to $SL"
  echo "      snippet:    $HERE/snippets/status-line.snippet.sh"
  echo "      (fresh setup? use $HERE/snippets/status-line.sh.reference as a base, then set"
  echo "       statusLine.command in settings.json to bash $SL)"
fi

# --- settings.json hooks (guide, don't auto-patch) ---
SJ="$CLAUDE_DIR/settings.json"
if [ -f "$SJ" ] && grep -q "review-detect.sh" "$SJ"; then
  echo "  ✓ settings.json hooks already wired"
else
  echo "  ! ACTION NEEDED: merge hook + statusLine entries into $SJ"
  echo "      snippet:    $HERE/snippets/settings.hooks.json"
fi

echo ""
echo "Done. Verify the helper:"
echo "  node --test $CLAUDE_DIR/bin/review-track.test.mjs"
