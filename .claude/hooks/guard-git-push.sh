#!/bin/bash
# PreToolUse hook for the Bash tool.
#
# The repository is public and the author publishes `main`. An agent may push
# a branch (and open a draft pull request for the author to review), but it
# must never move `main` itself. This hook denies: a push whose target is
# `main` (named, as `HEAD:main`, or implied because the current branch is
# `main`), a push of every branch (`--all`, `--mirror`), a force push in any
# spelling (`--force*`, `-f`, a `+refspec`), deleting `main` on the remote, and
# `gh pr merge`. Every other push falls through to the normal permission
# prompt, so a branch push is confirmed by the author in an interactive
# session. Matching is deliberately loose: a false block costs a rerun, a
# false allow publishes to the default branch.

set -o pipefail

input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')
cwd=$(printf '%s' "$input" | jq -r '.cwd // ""')

deny() {
  jq -n --arg reason "$1" --arg cmd "$command" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("Blocked by the git-push guard: " + $reason + ".\n\nCommand: " + $cmd + "\n\nPush to a branch named agent/<topic> and open a draft pull request instead; the author merges and publishes main.")
    }
  }'
  exit 0
}

if printf '%s' "$command" | grep -qE '(^|[^[:alnum:]_-])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)'; then
  deny "merging a pull request moves main, which the author does"
fi

printf '%s' "$command" | grep -qE '(^|[^[:alnum:]_-])git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?([[:space:]]+-[^[:space:]]+)*[[:space:]]+push([[:space:]]|$)' || exit 0

# The push segment: from `push` to the end of that shell command.
segment=$(printf '%s' "$command" | sed -E 's/.*[[:space:]]push([[:space:]]|$)/push /; s/[|;&].*$//')

if printf '%s' "$segment" | grep -qE '(^|[[:space:]])--(force|force-with-lease|force-if-includes)([=[:space:]]|$)' \
  || printf '%s' "$segment" | grep -qE '(^|[[:space:]])-[a-zA-Z]*f[a-zA-Z]*([[:space:]]|$)' \
  || printf '%s' "$segment" | grep -qE '(^|[[:space:]])\+[^[:space:]]'; then
  deny "a force push rewrites published history"
fi

if printf '%s' "$segment" | grep -qE '(^|[[:space:]])--(all|mirror)([[:space:]]|$)'; then
  deny "pushing every branch includes main"
fi

# Refspecs: the non-option words after `push <remote>`. A refspec pushes to the
# branch after the colon, or to the branch itself when there is no colon.
words=$(printf '%s' "$segment" | tr -s '[:space:]' '\n' | sed '1d' | grep -vE '^-' )
remote=""
targets=""
while IFS= read -r w; do
  [ -z "$w" ] && continue
  if [ -z "$remote" ]; then remote="$w"; continue; fi
  targets="$targets ${w##*:}"
done <<< "$words"

current_branch() {
  git -C "${cwd:-.}" rev-parse --abbrev-ref HEAD 2>/dev/null
}

if [ -z "$targets" ] || printf '%s' "$targets" | grep -qE '(^|[[:space:]])HEAD([[:space:]]|$)'; then
  branch=$(current_branch)
  [ -z "$branch" ] && deny "the current branch could not be determined, so the push may target main"
  targets="$targets $branch"
fi

if printf '%s' "$targets" | grep -qE '(^|[[:space:]])(main|master|refs/heads/main|refs/heads/master)([[:space:]]|$)'; then
  if printf '%s' "$segment" | grep -qE '(^|[[:space:]])(--delete|-d)([[:space:]]|$)'; then
    deny "deleting main on the remote"
  fi
  deny "pushing to main publishes it, which the author does"
fi

exit 0
