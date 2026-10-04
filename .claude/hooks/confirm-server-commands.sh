#!/bin/bash
# PreToolUse hook for the Bash tool.
#
# Makes Claude Code ask the user before any command that reaches the
# production server (ssh, scp, rsync) and could stop or restart a running
# game: restarting or stopping the empirica service, deleting, moving or
# truncating tajriba.json, uploading a bundle (the server restarts whenever
# empirica.tar.zst changes), rebooting, or killing processes. During data
# collection a game may be running at any time, and the agent cannot tell
# from the outside, so the user confirms each time. Local commands (the test
# harness deletes the local tajriba.json) are not affected. Matching is
# deliberately loose: a needless prompt costs a click, a missed one can end
# nine people's game.

set -o pipefail

input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

printf '%s' "$command" | grep -qE '(^|[^[:alnum:]_-])(ssh|scp|rsync)([[:space:]]|$)' || exit 0

reason=""
if printf '%s' "$command" | grep -qE 'systemctl[^|;&]*(restart|stop|kill|reload)'; then
  reason="it restarts or stops the empirica service"
elif printf '%s' "$command" | grep -qE 'tajriba\.json' \
  && printf '%s' "$command" | grep -qE '(^|[^[:alnum:]_])(rm|mv|truncate|shred)[[:space:]]|>[[:space:]]*[^&]*tajriba\.json'; then
  reason="it deletes, moves or overwrites tajriba.json"
elif printf '%s' "$command" | grep -qE 'empirica\.tar\.zst'; then
  reason="it touches the deployed bundle, and the server restarts whenever the bundle changes"
elif printf '%s' "$command" | grep -qE '(^|[^[:alnum:]_])(reboot|shutdown|poweroff|kill|pkill|killall)([[:space:]]|$)'; then
  reason="it reboots the server or kills processes"
fi

if [ -n "$reason" ]; then
  jq -n --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason: ("This command reaches the production server and " + $reason + ", which ends any game in progress. Confirm that no game is running right now before allowing it.")
    }
  }'
fi

exit 0
