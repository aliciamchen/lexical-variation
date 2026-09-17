#!/bin/bash
# PreToolUse hook for the Bash tool: gate an agent's `git commit` on the same
# checks as the repository's git pre-commit hook (.githooks/pre-commit), so the
# rules live in one place. A human commit from the terminal runs the git hook
# directly once `git config core.hooksPath .githooks` is set (see README).
#
# Other Bash commands pass through untouched.

set -o pipefail

input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

case "$command" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

project_dir="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
cd "$project_dir" 2>/dev/null || exit 0

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# Staged files, widened for `git commit -a`/`--all` (commits unstaged tracked
# changes too) and for pathspec commits (`git commit path -m ...`).
staged=$(git diff --cached --name-only --diff-filter=ACMR)
if [[ "$command" =~ (^|[[:space:]])-[a-zA-Z]*a || "$command" == *"--all"* ]]; then
  staged=$(printf '%s\n%s\n' "$staged" "$(git diff --name-only --diff-filter=ACMR)")
fi
staged=$(printf '%s\n' "$staged" | sed '/^$/d' | sort -u)
[ -z "$staged" ] && exit 0

out=$(STAGED_FILES="$staged" bash .githooks/pre-commit 2>&1) && exit 0
deny "$out

--no-verify bypasses Git hooks, not this agent hook."
