---
name: run-analysis
description: Use when running the preregistered model scripts in models/ against the full sample, writing or checking the statistics macros and figures in results/, syncing them into the manuscript, or planning the long Bayes-factor run -- "run the models", "run the confirmatory analyses", "rerun the primary analyses", "regenerate the stats macros", "rebuild the results".
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Run the models and write the results

The preregistered analyses are the R scripts in `models/checks/`, `models/primary/` and `models/secondary/`, one per analysis (`.claude/rules/data-pipeline.md` has the layout, the estimates shape and the macro flow). Each reads the dataset that `DATASET` names through `models/config.R`, which refuses a filtered-utterance file whose sidecar does not match `messages.csv`, and writes its estimates to `results/estimates/<family>/<name>.csv`. `report/inferential.py` and `report/descriptives.py` then write the six macro files in `results/stats/`, and `report/figures/` the figures. `results/` is committed, so the regression check for any change is `git diff results/`. `DATASET` defaults to `full`; a run on any other dataset, such as `smoke`, says so in every output and its numbers are not results.

1. **Check the data first.** `make test DATASET=full` must pass, and the dataset must be the one the run should report (`data/full/runs.txt`, the exclusion files, the classifier check). A run on data that are about to change is wasted time.

2. **A fast run** catches script errors before the long one: `BAYES_FACTORS=never make models` runs every script whose estimates are out of date and skips the Bayes factors, leaving their previous estimates in place. Make decides what is out of date from the data files, the shared R code and the estimates each script builds on; `make -n models` shows the plan. Read each script's output for warnings and the `fit_progressively()` steps it prints; a script that errors stops Make, so fix it and run it alone with `Rscript models/<family>/<name>.R`. The whole frequentist set takes a few minutes on the full sample; `make models -j4` runs independent scripts in parallel.

3. **The Bayes factors.** `make bayes-factors` (or `make models` with the default `BAYES_FACTORS=auto`) runs `models/primary/bayes_factors.R`, which refits the primary models in brms and bridge-samples them. The fits are cached by a hash of their data and formula in `data/full/cache/bayes_factors/` and refit only when the data change; on the 120 games the three refits took about twenty minutes, so run it detached and read the log:

   ```bash
   nohup make bayes-factors > /tmp/bayes-factors.log 2>&1 &
   ```

   `auto` computes a Bayes factor for the non-significant planned contrasts, `always` for every one. The script records any bridgesampling warning (`logml could not be estimated within maxiter`) beside the result in `primary/bayes_factors.csv`, and the formatter writes no macro for a Bayes factor that carries one, whatever its size.

4. **Write the results.** `make report` runs the two macro writers and the figures; `make stats` or `make figures` runs one side. Every macro file has a `% AUTO-GENERATED` header naming its writer and a second line naming the git commit, and must not be hand-edited. Then `git diff --stat results/` says which tables, macro files and figures changed; a macro that moved by more than rounding is worth a sentence in the report, and a macro that disappeared means its analysis wrote no row (read the script's output for why). `make sync` copies the macros and the PDFs into `writing/manuscript/`; it never touches `writing/preregistration/`, whose statistics and figures are frozen.

5. **Report**: the dataset and its game count, the Bayes-factor setting, the warnings and simplification steps worth knowing, and what changed under `results/`. The `build-report` skill takes it from there. Commit `results/` together with the code change that produced it, when asked.
