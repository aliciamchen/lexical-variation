#!/bin/bash
# PreToolUse hook for the Bash tool: gate `git commit`.
#
# 1. Participant-privacy guard. Blocks the commit if any staged data file
#    (anything under data/, or any .csv/.json under experiment/) contains a
#    Prolific-ID-shaped token (exactly 24 hex characters) or a header column
#    that the anonymization step is supposed to strip (see SENSITIVE_COLUMNS
#    in analysis/extract_run.py). Non-anonymized participant data was once
#    committed by accident; this makes that a hard stop.
# 2. Server unit tests. If staged files touch experiment/server/src/, runs
#    `npm run test:unit` (vitest on scoring.js and reshuffling.js; seconds).
# 3. Data integrity suite. If staged files touch analysis/*.py or
#    data/pilots/, runs `uv run pytest analysis/test_data_integrity.py`
#    (about three seconds on the pilot data).
#
# Other Bash commands pass through untouched. Playwright end-to-end tests are
# deliberately not run here; they take many minutes.

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

# ── 1. Privacy guard ────────────────────────────────────────
sensitive_cols='participantIdentifier|prolificPid|studyId|sessionId|urlParams'
hex24='(^|[^0-9a-fA-F])[0-9a-f]{24}([^0-9a-fA-F]|$)'
violations=""
while IFS= read -r f; do
  case "$f" in
    data/*|experiment/*.csv|experiment/*.json|experiment/*/*.csv|experiment/*/*.json) ;;
    *) continue ;;
  esac
  # Prefer the staged blob; fall back to the working tree for -a/pathspec cases.
  content=$(git show ":$f" 2>/dev/null || cat "$f" 2>/dev/null) || continue
  header=$(printf '%s\n' "$content" | head -n 1)
  if printf '%s' "$header" | grep -qE "(^|,|\")($sensitive_cols)(LastChangedAt)?(\"|,|$)"; then
    violations+="  $f: header contains a sensitive participant column"$'\n'
  elif printf '%s' "$content" | grep -qE "$hex24"; then
    violations+="  $f: contains a 24-hex token shaped like a Prolific ID"$'\n'
  fi
done <<< "$staged"

if [ -n "$violations" ]; then
  deny "Commit blocked: staged data files may contain participant identifiers.

$violations
Only anonymized data may be committed. Re-run analysis/extract_run.py (which strips SENSITIVE_COLUMNS) or remove the file from the commit. If this is a false positive, ask the user to commit it themselves."
fi

# ── 2. Server unit tests ────────────────────────────────────
if printf '%s\n' "$staged" | grep -qE '^experiment/server/src/'; then
  if command -v npm >/dev/null 2>&1 && [ -d experiment/server/node_modules ]; then
    log=$(mktemp)
    if ! npm run --silent test:unit --prefix experiment >"$log" 2>&1; then
      out=$(tail -n 60 "$log"); rm -f "$log"
      deny "Commit blocked: server unit tests failed (npm run test:unit in experiment/).

$out

Fix the failures and retry. --no-verify bypasses Git hooks, not this agent hook."
    fi
    rm -f "$log"
  fi
fi

# ── 3. Data integrity suite ─────────────────────────────────
if printf '%s\n' "$staged" | grep -qE '^(analysis/[^/]+\.py|data/pilots/)'; then
  if command -v uv >/dev/null 2>&1; then
    log=$(mktemp)
    if ! uv run pytest analysis/test_data_integrity.py -q >"$log" 2>&1; then
      out=$(tail -n 60 "$log"); rm -f "$log"
      deny "Commit blocked: data integrity suite failed (uv run pytest analysis/test_data_integrity.py).

$out

Fix the failures and retry. --no-verify bypasses Git hooks, not this agent hook."
    fi
    rm -f "$log"
  fi
fi

exit 0
