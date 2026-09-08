#!/bin/bash
# PreToolUse hook for the Bash tool.
#
# Hard-blocks commands that destroy git history or files with no way to
# recover them: git reset --hard, git clean -f*, git branch -D, rm -rf
# (and flag-order variants like -fr, -r -f, --recursive --force). Intended
# as a guardrail for unattended/autonomous sessions where no one is
# watching to decline a permission prompt. Everything else passes through
# untouched. Matching is deliberately loose (biased toward false blocks
# over false allows) since over-blocking just costs a rerun.

set -o pipefail

input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

reason=""

if printf '%s' "$command" | grep -qE 'git[^|;&]*reset[^|;&]*--hard'; then
  reason="git reset --hard discards uncommitted changes irreversibly"
elif printf '%s' "$command" | grep -qE 'git[^|;&]*clean[^|;&]*(-[a-zA-Z]*f|--force)'; then
  reason="git clean -f permanently deletes untracked files"
elif printf '%s' "$command" | grep -qE 'git[^|;&]*branch[^|;&]*(-[a-zA-Z]*D|--delete[^|;&]*--force|--force[^|;&]*--delete)'; then
  reason="git branch -D force-deletes a branch, discarding unmerged commits"
elif printf '%s' "$command" | grep -qE 'rm[^|;&]*(-[a-zA-Z]*[rR][a-zA-Z]*([[:space:]]|$)|--recursive)' \
  && printf '%s' "$command" | grep -qE 'rm[^|;&]*(-[a-zA-Z]*f[a-zA-Z]*([[:space:]]|$)|--force)'; then
  reason="rm -rf permanently deletes files with no recovery"
fi

if [ -n "$reason" ]; then
  jq -n --arg reason "$reason" --arg cmd "$command" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("Blocked by safety hook: " + $reason + ".\n\nCommand: " + $cmd + "\n\nIf you genuinely need to run this, ask the user to run it themselves.")
    }
  }'
  exit 0
fi

exit 0
