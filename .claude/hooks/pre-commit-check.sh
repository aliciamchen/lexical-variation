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

# A commit, including one with git's global options before the subcommand
# (`git -c core.hooksPath=... commit`, `git -C <dir> commit`).
git_arg="(\"[^\"]*\"|'[^']*'|[^[:space:]]+)"
git_opt="(-[cC]|--(git-dir|work-tree|namespace|config-env|attr-source))[[:space:]]+$git_arg|-[^[:space:]]+"
commit_re="(^|[[:space:];&|(\`/])git([[:space:]]+($git_opt))*[[:space:]]+commit([[:space:]]|$)"
[[ "$command" =~ $commit_re ]] || exit 0

project_dir="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
cd "$project_dir" 2>/dev/null || exit 0

# Where .githooks is the installed hooks directory, git runs the same checks
# during the commit, so they run here only when the command can skip git's
# hook: --no-verify (or an abbreviation of it, or -n) or a core.hooksPath
# override.
hooks_dir=$(git rev-parse --git-path hooks 2>/dev/null)
lowered=$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')
if [ -x .githooks/pre-commit ] \
  && [ "$(cd "$hooks_dir" 2>/dev/null && pwd -P)" = "$(cd .githooks && pwd -P)" ] \
  && [[ "$lowered" != *"--no-v"* && "$lowered" != *"hookspath"* ]] \
  && ! [[ "$command" =~ (^|[[:space:]])-[a-zA-Z]*n ]]; then
  exit 0
fi

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
