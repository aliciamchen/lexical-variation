#!/bin/bash
#
# copy_tajriba.sh -- Back up experiment data from the production server
#
# Runs `empirica export` on the server to produce a CSV zip, then copies it
# to experiment/data/<timestamp>/empirica-export-<timestamp>.zip: one
# directory per export, named by the zip's own timestamp. That is the layout
# analysis/extract_run.py and the Makefile look for, so every backup taken
# during a session is a usable export, not only the last one.
#
# Usage:
#   bash operations/copy_tajriba.sh            # loop every 5 minutes (default)
#   bash operations/copy_tajriba.sh --once     # one backup; exit status says whether it worked
#   bash operations/copy_tajriba.sh --help     # show this help
#
# The loop carries on through a failed ssh or scp and gives up only after
# 3 consecutive failures.
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
# Anchored to the repository rather than the working directory: the analysis
# pipeline reads exports from experiment/data/<timestamp>/, so the destination
# must not depend on where this script is invoked from.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/experiment/data"

consecutive_failures=0

now() {
    date +"%Y-%m-%d %H:%M:%S"
}

# Count one failure; stop the script once MAX_FAILURES happen in a row.
fail() {
    consecutive_failures=$((consecutive_failures + 1))
    echo "[$(now)] WARNING: $1 failed (attempt $consecutive_failures/$MAX_FAILURES)." >&2
    if [[ $consecutive_failures -ge $MAX_FAILURES ]]; then
        echo "[$(now)] ERROR: $MAX_FAILURES consecutive failures -- exiting." >&2
        exit 1
    fi
    return 1
}

do_backup() {
    local stamp remote_zip dest
    # One timestamp names the remote zip, the local directory and the file in
    # it, so extract_run.py's `experiment/data/<ts>/empirica-export-<ts>.zip`
    # pattern matches every backup.
    stamp=$(date +"%Y%m%d_%H%M%S")
    remote_zip="/tmp/empirica-export-$stamp.zip"
    dest="$DATA_DIR/$stamp"

    echo "[$(now)] Running empirica export on server..."
    if ! ssh "$REMOTE" "cd $REMOTE_DIR && empirica export --out $remote_zip" 2>&1; then
        fail "empirica export" || return 1
    fi

    mkdir -p "$dest"
    echo "[$(now)] Copying zip to $dest/..."
    # Copied under a name extract_run.py never matches, then renamed, so a
    # half-copied zip is never mistaken for an export.
    local partial="$dest/.partial-$stamp.zip"
    if ! scp "$REMOTE:$remote_zip" "$partial"; then
        ssh "$REMOTE" "rm -f $remote_zip" 2>/dev/null || true
        rm -f "$partial"
        rmdir "$dest" 2>/dev/null || true
        fail "scp" || return 1
    fi
    mv "$partial" "$dest/$(basename "$remote_zip")"

    # Clean up remote zip
    ssh "$REMOTE" "rm -f $remote_zip" 2>/dev/null || true

    consecutive_failures=0
    echo "[$(now)] Backup succeeded -> $dest/$(basename "$remote_zip")"
}

# --- clean exit on Ctrl-C ---
trap 'echo ""; echo "[$(now)] Interrupted. Backups are in $DATA_DIR/<timestamp>/"; exit 0' INT

# --- one-shot mode ---
if [[ "${1:-}" == "--once" ]]; then
    if do_backup; then
        exit 0
    fi
    exit 1
fi

# --- loop mode (default) ---
# `|| true` keeps `set -e` from ending the loop on the first failed ssh or scp;
# do_backup itself exits after MAX_FAILURES consecutive failures.
echo "Backing up every $((INTERVAL / 60)) minutes into $DATA_DIR/<timestamp>/. Press Ctrl-C to stop."
while true; do
    do_backup || true
    sleep "$INTERVAL"
done
