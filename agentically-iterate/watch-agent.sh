#!/usr/bin/env bash
# Watch one background agent until its file appears.
# Usage: watch-agent.sh OUTPUT_FILE DONE_FILE [STALL_SECONDS]
#   OUTPUT_FILE  the agent's transcript, from its dispatch result
#   DONE_FILE    the file the agent must write, such as cold/review-a.md
# Prints one line and exits:
#   done            DONE_FILE exists
#   stalled: ...    the transcript stopped growing first (default 3600 s)
set -u
out=$1 done=$2 limit=${3:-3600}
while :; do
  if [ -e "$done" ]; then echo done; exit 0; fi
  if [ -e "$out" ]; then
    age=$(( $(date +%s) - $(stat -L -c %Y "$out") ))
    if [ "$age" -gt "$limit" ]; then echo "stalled: no output for ${age}s"; exit 1; fi
  fi
  sleep 30
done
