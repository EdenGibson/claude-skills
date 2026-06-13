#!/bin/bash
# Delete per-session review-track state files older than 7 days. Never blocks.
DIR="$HOME/.claude/skill-state"
[ -d "$DIR" ] && find "$DIR" -maxdepth 1 -type f -name '*.json' -mtime +7 -delete 2>/dev/null
exit 0
