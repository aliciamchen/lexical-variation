#!/bin/bash
# Open multiple isolated Chrome windows for testing the experiment.
# Each window has its own profile so it acts as a separate player.
#
# Usage:
#   bash experiment/open_players.sh        # open 9 players (default)
#   bash experiment/open_players.sh 3      # open 3 players
#   bash experiment/open_players.sh clean  # remove temp profiles

URL="https://tangramcommunication.empirica.app"
PROFILE_DIR="/tmp/chrome-tangram"

if [ "$1" = "clean" ]; then
  rm -rf "$PROFILE_DIR"-*
  echo "Cleaned up temp Chrome profiles"
  exit 0
fi

NUM_PLAYERS="${1:-9}"

for i in $(seq 1 "$NUM_PLAYERS"); do
  open -na "Google Chrome" --args --user-data-dir="$PROFILE_DIR-$i" "$URL"
  echo "Opened player $i"
done

echo "Opened $NUM_PLAYERS Chrome windows"
echo "Run 'bash experiment/open_players.sh clean' to remove temp profiles"
