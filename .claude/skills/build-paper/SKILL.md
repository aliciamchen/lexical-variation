---
name: build-paper
description: Use when compiling, checking, or updating the manuscript in paper/ (main.tex or the cover letter), syncing figures or statistics into it, or diagnosing a LaTeX build with undefined citations, an empty .bbl, or a truncated PDF.
allowed-tools: Bash, Read, Grep, Glob
---

# Build the manuscript

Manuscripts live under `writing/`, one directory per Overleaf project, gitignored and mirrored to Overleaf through Dropbox, so edits there are never committed to this repository. `writing/preregistration/` is the preregistration; `writing/manuscript/` will be the full-sample article. The manuscript was written as a Stage 1 registered report and now serves as the preregistration; do not convert tense or remove registered-report sections unless asked (the conversion checklist is in `full-sample-todos.md`).

1. **Sync inputs.** If figures changed, run `bash figures/sync_figures.sh` (copies `SI_*.pdf` into `writing/preregistration/figures/`). If notebooks were re-rendered, confirm the generated statistics carry the new values; every such file has a `% AUTO-GENERATED` header and must not be hand-edited. The preregistration reads `writing/preregistration/stats/pilot.tex` and `llm.tex`, written by `SI_pilot.qmd` and the LLM notebook. The full-sample article reads `writing/manuscript/stats/`, one file per notebook (`overview`, `checks`, `primary`, `secondary`, `exploratory`, `survey`) written by `00`–`05` with macro names prefixed by notebook; those only hold real values once the notebooks have been rendered against `DATASET=full`, since the pilot cannot estimate most of them. Check that every macro used in the manuscript is defined (swap the directory for whichever project you are building):

   ```bash
   cd writing/preregistration && grep -oh '\\[a-zA-Z]*' main.tex | sort -u > /tmp/used.txt \
     && grep -oh 'newcommand{\\[a-zA-Z]*' stats/*.tex | sed 's/newcommand{//' | sort -u > /tmp/defined.txt
   ```

2. **Build**: `cd writing/preregistration && latexmk -pdf main.tex`. The cover letter builds the same way from `writing/preregistration/cover_letter/`.

3. **Recognize a Dropbox race.** If every citation is undefined, `main.bbl` is empty, `.aux` files contain NUL bytes, or the PDF is suddenly short, Dropbox has raced the build. Do not debug the bibliography. Copy the project directory to a directory outside Dropbox (the scratchpad works), run `latexmk -C` there, remove the stale biber PAR cache (`find /var/folders -maxdepth 4 -type d -name 'par-*' -user "$(whoami)" 2>/dev/null`, then `rm -r` that directory), rebuild, and copy back only the PDF.

4. **Check the result**: page count against the previous build, `grep -c 'Warning--' main.blg` for bibliography warnings, and `grep -n 'undefined' main.log` for references. Report warnings; never resolve them by deleting content.
