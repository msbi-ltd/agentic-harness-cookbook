#!/usr/bin/env bash
# git-guard.sh: blocks direct pushes to main/master from an agent's Bash tool.
# Claude Code calls this as a PreToolUse hook before every Bash tool call.
# Exit 0 = allow. Exit 2 = block (stderr becomes the reason the agent sees).
#
# This is the real hook referenced by patterns/direct-push-guard.md. It is the
# fast LOCAL net only -- the actual boundary is server-side branch protection.
# See that pattern's "enforcement hierarchy" section.
set -euo pipefail
HERE="$(dirname "$0")"
PARSER="${HERE}/../../scripts/git_push_target.py"

# The tool call arrives as JSON on stdin; pull out the shell command.
cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')

# Only engage if this looks like a git push at all.
if printf '%s' "$cmd" | grep -qE '(^|[;&|]|\s)git\s+push'; then
  # Delegate destination parsing to git_push_target.py, which FAILS CLOSED
  # (exit 1) on a protected target OR anything it can't resolve (bare push,
  # --all, --mirror). If the parser itself is missing, fail closed too rather
  # than waving the push through unexamined.
  if [ ! -f "$PARSER" ]; then
    echo "BLOCKED: push guard parser missing at $PARSER; refusing to allow an unchecked push." >&2
    exit 2
  fi
  # shellcheck disable=SC2086  # intentional word-split so push args reach argv
  if ! python3 "$PARSER" --protected main master -- $cmd; then
    echo "BLOCKED: this push could target a protected branch. Push a feature branch and open a PR." >&2
    exit 2
  fi
fi

exit 0
