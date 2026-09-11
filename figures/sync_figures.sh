#!/bin/bash
# Copy generated figures into a writing project's figures/ for Overleaf compatibility.
# Run from the repo root: bash figures/sync_figures.sh [writing/<project>]
# (default: writing/preregistration)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT="${1:-writing/preregistration}"
DEST="$REPO_ROOT/$PROJECT/figures"
mkdir -p "$DEST"

cp "$SCRIPT_DIR"/pilots/SI_*.pdf "$DEST"/
cp "$SCRIPT_DIR"/llm_plots/SI_*.pdf "$DEST"/

echo "Synced figures to $DEST"
