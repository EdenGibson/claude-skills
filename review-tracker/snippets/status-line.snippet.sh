# ============================================================================
# review-tracker: statusline snippets to insert into ~/.claude/hooks/status-line.sh
# Requires SESSION_ID to already be parsed from the statusline stdin JSON, e.g.:
#   SESSION_ID=$(parse session_id)
# ============================================================================

# --- SNIPPET 1 --------------------------------------------------------------
# Insert AFTER the context-meter block and BEFORE the "# Build the output line"
# section. Reads ~/.claude/skill-state/$SESSION_ID.json and renders the segment.
# Rendering: cr/tn with total>0 -> "LABEL applied/total" (yellow in-progress,
# green when complete); ran with total==0 -> green "LABEL ✓"; not-run -> omitted.

# --- Review tracker segment ---
REV_SEGMENT=""
if [ -n "$SESSION_ID" ]; then
  REV_SEGMENT=$(SESSION_ID="$SESSION_ID" node -e '
    (() => {
      const fs = require("fs"), os = require("os"), path = require("path");
      const sid = process.env.SESSION_ID;
      let st = {};
      try {
        st = JSON.parse(fs.readFileSync(
          path.join(os.homedir(), ".claude", "skill-state", sid + ".json"), "utf8"));
      } catch { return; }
      const parts = [];
      for (const [key, label] of [["cr", "CR"], ["tn", "TN"]]) {
        const e = st[key];
        if (!e || !e.ran) continue;
        if (e.total > 0) {
          const done = e.applied >= e.total;
          const color = done ? "\x1b[32m" : "\x1b[33m";
          parts.push(`${color}${label} ${e.applied}/${e.total}\x1b[0m`);
        } else {
          parts.push(`\x1b[32m${label} ✓\x1b[0m`);
        }
      }
      if (parts.length) process.stdout.write("rev: " + parts.join(" "));
    })();
  ' 2>/dev/null)
fi

# --- SNIPPET 2 --------------------------------------------------------------
# In the output-line build, append the segment BEFORE the task title so a long
# task can never truncate it off the right edge:

[ -n "$REV_SEGMENT" ]  && PARTS="$PARTS | $REV_SEGMENT"
# (existing line, keep AFTER the one above:)
# [ -n "$TASK" ]         && PARTS="$PARTS | $TASK"
