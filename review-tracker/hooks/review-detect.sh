#!/bin/bash
# Auto-mark that a tracked review ran. Inspects the hook payload for either a /command
# prompt or a tool invocation naming a review. Never blocks (always exit 0).
INPUT=$(cat)
RT="$HOME/.claude/bin/review-track"

# Parse "session_id<TAB>lowercased-blob-of-relevant-fields".
PARSED=$(printf '%s' "$INPUT" | node -e '
  let d="";process.stdin.on("data",c=>d+=c);process.stdin.on("end",()=>{
    let j={};try{j=JSON.parse(d)}catch{}
    const sid=j.session_id||"";
    const blob=[j.prompt,j.tool_name,JSON.stringify(j.tool_input||"")]
      .join(" ").toLowerCase().replace(/\s+/g," ");
    process.stdout.write(sid+"\t"+blob);
  });' 2>/dev/null)
SID="${PARSED%%$'\t'*}"
BLOB="${PARSED#*$'\t'}"

emit() {
  [ -x "$RT" ] || return 0
  if [ -n "$SID" ]; then "$RT" "$@" --session "$SID" >/dev/null 2>&1 || true
  else "$RT" "$@" >/dev/null 2>&1 || true; fi
}

case "$BLOB" in
  *"/code-review"*|*'"code-review"'*|*"code_review"*) emit ran cr ;;
esac
case "$BLOB" in
  *"thermo-nuclear"*|*"thermo_nuclear"*|*"thermonuclear"*) emit ran tn ;;
esac
exit 0
