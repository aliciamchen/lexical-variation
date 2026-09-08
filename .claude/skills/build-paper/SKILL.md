---
name: build-paper
description: Use when compiling, checking, or updating the manuscript in paper/ (main.tex or the cover letter), syncing figures or statistics into it, or diagnosing a LaTeX build with undefined citations, an empty .bbl, or a truncated PDF.
allowed-tools: Bash, Read, Grep, Glob
---

# Build the manuscript

`paper/` is gitignored and synced with Overleaf through Dropbox, so edits there are never committed to this repository. The manuscript was written as a Stage 1 registered report and now serves as the preregistration; do not convert tense or remove registered-report sections unless asked (the conversion checklist is in `full-sample-todos.md`).

1. **Sync inputs.** If figures changed, run `bash figures/sync_figures.sh` (copies `SI_*.pdf` into `paper/figures/`). If notebooks were re-rendered, confirm `paper/stats/pilot.tex` and `paper/stats/llm.tex` carry the new values; they have a `% AUTO-GENERATED` header and must not be hand-edited. Check that every macro used in `main.tex` is defined:

   ```bash
   cd paper && grep -oh '\\[a-zA-Z]*' main.tex | sort -u > /tmp/used.txt \
     && grep -oh 'newcommand{\\[a-zA-Z]*' stats/*.tex | sed 's/newcommand{//' | sort -u > /tmp/defined.txt
   ```

2. **Build**: `cd paper && latexmk -pdf main.tex`. The cover letter builds the same way from `paper/cover_letter/`.

3. **Recognize a Dropbox race.** If every citation is undefined, `main.bbl` is empty, `.aux` files contain NUL bytes, or the PDF is suddenly short, Dropbox has raced the build. Do not debug the bibliography. Copy `paper/` to a directory outside Dropbox (the scratchpad works), run `latexmk -C` there, remove the stale biber PAR cache (`find /var/folders -maxdepth 4 -type d -name 'par-*' -user "$(whoami)" 2>/dev/null`, then `rm -r` that directory), rebuild, and copy back only the PDF.

4. **Check the result**: page count against the previous build, `grep -c 'Warning--' main.blg` for bibliography warnings, and `grep -n 'undefined' main.log` for references. Report warnings; never resolve them by deleting content.
