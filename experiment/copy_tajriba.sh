#!/bin/bash
#
# copy_tajriba.sh — Back up experiment data from the production server
#
# Runs `empirica export` on the server to produce a CSV zip, then
# copies it into a timestamped local directory under data/.
#
# Usage:
#   bash copy_tajriba.sh            # loop every 5 minutes (default)
#   bash copy_tajriba.sh --once     # single backup and exit
#   bash copy_tajriba.sh --help     # show this help
#
# Requires SSH access to the production server.
# Set EMPIRICA_SERVER in .env or environment (see .env.example).

set -euo pipefail

# Load .env if present
if [[ -f "$(dirname "$0")/../.env" ]]; then
    set -a; source "$(dirname "$0")/../.env"; set +a
fi

if [[ -z "${EMPIRICA_SERVER:-}" ]]; then
    echo "Error: EMPIRICA_SERVER not set. Copy .env.example to .env and fill in values." >&2
    exit 1
fi

REMOTE="root@${EMPIRICA_SERVER}"
REMOTE_DIR="~/empirica"
INTERVAL=300  # seconds between backups
MAX_FAILURES=3

# --- help ---
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    sed -n '2,/^$/{ s/^# \{0,1\}//; p; }' "$0"
    exit 0
fi

# --- setup ---
current_datetime=$(date +"%Y%m%d_%H%M%S")
dest="data/$current_datetime"
mkdir -p "$dest"

consecutive_failures=0

do_backup() {
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    local remote_zip="/tmp/empirica-export-$(date +%Y%m%d_%H%M%S).zip"

    echo "[$timestamp] Running empirica export on server..."
    if ! ssh "$REMOTE" "cd $REMOTE_DIR && empirica export --out $remote_zip" 2>&1; then
        consecutive_failures=$((consecutive_failures + 1))
        echo "[$timestamp] WARNING: empirica export failed (attempt $consecutive_failures/$MAX_FAILURES)." >&2
        if [[ $consecutive_failures -ge $MAX_FAILURES ]]; then
            echo "[$timestamp] ERROR: $MAX_FAILURES consecutive failures — exiting." >&2
            exit 1
        fi
        return 1
    fi

    echo "[$timestamp] Copying zip to $dest/..."
    if ! scp "$REMOTE:$remote_zip" "$dest/"; then
        consecutive_failures=$((consecutive_failures + 1))
        echo "[$timestamp] WARNING: scp failed (attempt $consecutive_failures/$MAX_FAILURES)." >&2
        ssh "$REMOTE" "rm -f $remote_zip" 2>/dev/null || true
        if [[ $consecutive_failures -ge $MAX_FAILURES ]]; then
            echo "[$timestamp] ERROR: $MAX_FAILURES consecutive failures — exiting." >&2
            exit 1
        fi
        return 1
    fi

    # Clean up remote zip
    ssh "$REMOTE" "rm -f $remote_zip" 2>/dev/null || true

    consecutive_failures=0
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] Backup succeeded → $dest/$(basename "$remote_zip")"
}

# --- clean exit on Ctrl-C ---
trap 'echo ""; echo "[$(date +"%Y-%m-%d %H:%M:%S")] Interrupted. Backups saved in $dest/"; exit 0' INT

# --- one-shot mode ---
if [[ "${1:-}" == "--once" ]]; then
    do_backup
    exit $?
fi

# --- loop mode (default) ---
echo "Backing up every $((INTERVAL / 60)) minutes. Press Ctrl-C to stop."
while true; do
    do_backup
    sleep "$INTERVAL"
done
