---
name: run-analysis
description: Use when rendering the preregistered analysis notebooks (analysis/01_*.qmd to 03_*.qmd) against the full sample, writing or checking the statistics macros for the manuscript (the notebooks' and the descriptive ones from analysis/descriptives.py), or planning the long Bayes-factor render -- "render the notebooks", "run the confirmatory analyses", "rerun 02 on full", "regenerate the stats macros".
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Render the analysis notebooks

The notebooks `analysis/01_outcome_neutral.qmd`, `02_primary_analysis.qmd` and `03_secondary_analysis.qmd` are the preregistered analyses (`.claude/rules/data-pipeline.md` has the table and the stats-to-LaTeX flow). They read the dataset that `DATASET` names through `analysis/config.R`, which refuses a filtered-utterance file whose sidecar does not match `messages.csv`. Each writes its statistics as `\newcommand` macros to `writing/manuscript/stats/<notebook>.tex` (`checks`, `primary`, `secondary`), with names prefixed by notebook and no digits in them, and notebook 02 writes its per-game group-specificity estimates to `analysis/results/<dataset>/gs_by_game.csv`. The descriptive macros (`overview`, `exploratory`, `survey`) are written afterwards by `make descriptives` (`analysis/descriptives.py`) from the tables and those estimates. Rendered HTML goes to `_output/`. `DATASET` defaults to `full`; a render on any other dataset, such as `smoke`, gets a warning banner and its macros are not results.

1. **Check the data first.** `make test DATASET=full` must pass, and the dataset must be the one the render should report (`data/full/runs.txt`, the exclusion files, the classifier check). A render on data that are about to change is wasted hours.

2. **A fast render** catches notebook errors before the long one: `BAYES_FACTORS=never make notebooks DATASET=full` renders all three without the brms refits (the group-specificity permutation test is cached by a hash of the pairwise data and recomputed only when it changes). Read each rendered notebook's warnings and the `fit_progressively()` steps it prints; a chunk that errors stops Quarto, so fix the notebook and rerun that one with `DATASET=full quarto render analysis/<notebook>.qmd`.

3. **The confirmatory render.** `02_primary_analysis.qmd` computes Bayes factors for the planned contrasts with brms and bridge sampling. The fits are cached by a hash of their data in `analysis/derived/full/bayes_factors/` and took about 13 hours on 57 games, so run it detached and read the log rather than waiting in the session:

   ```bash
   nohup env DATASET=full BAYES_FACTORS=auto make notebooks > /tmp/render-full.log 2>&1 &
   ```

   `auto` computes a Bayes factor for the non-significant planned contrasts, `always` for every one. The cache survives reruns on unchanged data.

4. **Check the outputs.** Run `make descriptives` after the notebooks so the three descriptive files are current. Every stats file has a `% AUTO-GENERATED` header and must not be hand-edited; `grep -c newcommand writing/manuscript/stats/*.tex` shows how many macros each writer wrote, and a macro that moved by more than rounding since the last render is worth a sentence in the report. The notebooks draw nothing; the article's figures are made in Python (`analysis/plot_style.py` holds their style) and `bash figures/sync_figures.sh writing/manuscript` copies `figures/full/` into the article's project once they exist. The script refuses `writing/preregistration/`, whose figures are frozen with the preregistration.

5. **Report**: the dataset and its game count, the Bayes-factor setting, the warnings and simplification steps worth knowing, and where the macros went. The `build-paper` skill takes it from there. Do not commit rendered HTML or stats files unless asked.
