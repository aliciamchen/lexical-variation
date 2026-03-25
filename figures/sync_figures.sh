#!/bin/bash
# Copy generated figures into paper/figures/ for Overleaf compatibility.
# Run from the repo root: bash figures/sync_figures.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST="$REPO_ROOT/paper/figures"

cp "$SCRIPT_DIR"/pilot_plots/SI_*.pdf "$DEST"/
cp "$SCRIPT_DIR"/llm_plots/SI_*.pdf "$DEST"/

echo "Synced figures to $DEST"
