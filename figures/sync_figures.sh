#!/bin/bash
# Copy a dataset's figures into a writing project's figures/ directory, where
# Overleaf reads them. Run from the repository root:
#   bash figures/sync_figures.sh writing/manuscript          # figures/full/
#   bash figures/sync_figures.sh writing/manuscript smoke    # figures/smoke/
# writing/preregistration/ is refused: its figures are frozen with the
# preregistration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT="${1:?usage: bash figures/sync_figures.sh writing/<project> [dataset]}"
DATASET="${2:-${DATASET:-full}}"
SRC="$SCRIPT_DIR/$DATASET"
DEST="$REPO_ROOT/$PROJECT/figures"

if [ "${PROJECT%/}" = "writing/preregistration" ]; then
  echo "Refusing to sync into writing/preregistration/: its figures are frozen." >&2
  exit 1
fi
shopt -s nullglob
pdfs=("$SRC"/*.pdf)
if [ ${#pdfs[@]} -eq 0 ]; then
  echo "No PDF figures in $SRC" >&2
  exit 1
fi
mkdir -p "$DEST"
cp "${pdfs[@]}" "$DEST"/
echo "Synced ${#pdfs[@]} figure(s) from $SRC to $DEST"
