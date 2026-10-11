---
name: build-report
description: Use when compiling, checking, or updating a manuscript in writing/ (main.tex or the cover letter), syncing figures or statistics into it, or diagnosing a LaTeX build with undefined citations, an empty .bbl, or a truncated PDF.
allowed-tools: Bash, Read, Grep, Glob
---

# Build the manuscript

Manuscripts live under `writing/`, one directory per Overleaf project, gitignored and mirrored to Overleaf through Dropbox, so edits there are never committed to this repository. `writing/preregistration/` is the preregistration, written as a Stage 1 registered report and frozen since 2026-09-21: never change its text, tense or sections. `writing/manuscript/` will be the full-sample article for journal submission, a separate Overleaf project the author clones from the preregistration; so far only its `stats/` directory exists, filled by `make sync` from `results/full/stats/`, and the conversion from registered report to article (the checklist is in `full-sample-todos.md`) happens there, once it exists. The article has no figures yet: they are made by the modules in `report/figures/` under the conventions in `.claude/rules/data-pipeline.md` (style in `report/plot_style.py`), written to `results/full/figures/` and synced as below. Framing and venue are the author's decisions; offer options with a recommendation. When creating it, add a `latexmkrc` with `@default_files = ('main.tex');` so Overleaf builds the right file.

1. **Sync inputs.** `make sync` copies `results/full/stats/*.tex` and `results/full/figures/*.pdf` into the article's `stats/` and `figures/`; it only ever writes to `writing/manuscript/`, never to the frozen preregistration. If the models or the report layer were rerun, confirm the macro files carry the new values (`git diff results/full/stats/`); every such file has a `% AUTO-GENERATED` header naming its writer and the git commit, and must not be hand-edited. The preregistration reads `writing/preregistration/stats/pilot.tex` and `llm.tex`, which are frozen with it; the notebooks that wrote them are at the git tag `pilot-archive`. The full-sample article reads `writing/manuscript/stats/`, one file per family (`checks`, `primary`, `secondary` from `report/inferential.py`; `overview`, `exploratory`, `survey` from `report/descriptives.py`) with macro names prefixed by file; those hold real values only from a run on `DATASET=full`. Check that every macro used in the manuscript is defined (swap the directory for whichever project you are building):

   ```bash
   cd writing/preregistration && grep -oh '\\[a-zA-Z]*' main.tex | sort -u > /tmp/used.txt \
     && grep -oh 'newcommand{\\[a-zA-Z]*' stats/*.tex | sed 's/newcommand{//' | sort -u > /tmp/defined.txt
   ```

2. **Build**: `cd writing/preregistration && latexmk -pdf main.tex`. The cover letter builds the same way from `writing/preregistration/cover_letter/`.

3. **Recognize a Dropbox race.** If every citation is undefined, `main.bbl` is empty, `.aux` files contain NUL bytes, or the PDF is suddenly short, Dropbox has raced the build. Do not debug the bibliography. Copy the project directory to a directory outside Dropbox (the scratchpad works), run `latexmk -C` there, remove the stale biber PAR cache (`find /var/folders -maxdepth 4 -type d -name 'par-*' -user "$(whoami)" 2>/dev/null`, then `rm -r` that directory), rebuild, and copy back only the PDF.

4. **Check the result**: page count against the previous build, `grep -c 'Warning--' main.blg` for bibliography warnings, and `grep -n 'undefined' main.log` for references. Report warnings; never resolve them by deleting content.
