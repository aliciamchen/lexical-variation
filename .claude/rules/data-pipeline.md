---
paths:
  - "analysis/**"
  - "data/**"
  - "experiment/data/**"
  - "operations/copy_tajriba.sh"
---

# Data and analysis pipeline

## Datasets

The pipeline is keyed by a dataset name. The pilot sessions are the dataset `pilots`; the full sample will be a second dataset beside it (suggested name `full`), never an edit of the pilot paths. The layout is defined once in `analysis/dataset_paths.py` (Python scripts) and mirrored in `analysis/config.R` (`use_dataset()`, for the notebooks); keep the two in sync. The active dataset is `--dataset` on a script, else the `DATASET` environment variable, else `pilots`. `make` exports `DATASET` to every step, so `make all DATASET=full` runs the whole pipeline on the full sample.

| Directory | Contents | Committed? |
|-----------|----------|------------|
| `experiment/data/<timestamp>/` | Raw Empirica export zips from `operations/copy_tajriba.sh` | No |
| `data/runs/<timestamp>/` | Per-run extracts (raw/, bonuses.csv), shared across datasets | No (gitignored) |
| `data/<name>/runs.txt` | The export timestamps combined into the dataset, one per line | Yes |
| `data/<name>/raw_anonymized/` | Anonymized raw Empirica CSVs stacked across those runs | Yes |
| `data/<name>/*.csv` | Preprocessed analysis-ready CSVs (games, players, trials, messages, speaker_utterances, social_guesses) | Yes |
| `data/<name>/manifest.json` | Provenance: which runs were combined | Yes |
| `analysis/derived/<name>/` | Computed outputs from `compute_derived.py`: embeddings, similarities, UMAP, and cached model fits | Yes |
| `figures/<name>/` | Notebook figures (`figures/pilots/` holds the SI figures from `SI_pilot.qmd`) | Yes |
| `figures/llm_plots/` | SI PDF figures from `SI_llm_simulation.qmd` | Yes |

Cached fits are keyed to their inputs: `group_specificity.R` stores a hash of the pairwise data next to `gs_results.rds` and recomputes when it differs, and `bayes_factors.R` names each fit by a hash of data and formula. A stale cache can therefore not be reused silently, but recomputing the permutation test takes several minutes. The brms fits under `analysis/derived/<name>/bayes_factors/` are gitignored (tens of megabytes, reproducible); the group-specificity RDS files are committed.

## Data

- Live data: `experiment/.empirica/local/tajriba.json`
  - Export to CSVs by running `empirica export`
- Backup from production server:
  ```bash
  bash operations/copy_tajriba.sh            # loop every 5 minutes (default)
  bash operations/copy_tajriba.sh --once     # single backup and exit
  bash operations/copy_tajriba.sh --help     # show usage
  ```
  The script SSHs into the production server (set via `EMPIRICA_SERVER` in `.env`), runs `empirica export` in `~/empirica` to produce a CSV zip, then copies it locally into `experiment/data/<timestamp>/`. Safe to run while the experiment is live. Exits automatically after 3 consecutive failures.

## Pipeline scripts

Three scripts, run in order (`make extract combine process` does the same for the active dataset):

```bash
# 1. Extract each Empirica export zip (unzip, anonymize, extract bonuses)
uv run python analysis/extract_run.py <zip>                    → data/runs/{timestamp}/raw/

# 2. Combine the runs listed in data/<name>/runs.txt (stack raw CSVs, filter failed games)
uv run python analysis/combine_runs.py --dataset <name>        → data/<name>/raw_anonymized/

# 3. Run the analysis pipeline (preprocess → filter → derived metrics)
uv run python analysis/process_data.py --dataset <name>        → data/<name>/, analysis/derived/<name>/
```

Step 3 runs these sub-steps in order:

| Step | Script | Inputs → Outputs |
|------|--------|------------------|
| Preprocess | `preprocessing.py` | `data/<name>/raw_anonymized/` → `data/<name>/*.csv` |
| Filter | `filter_nonreferential.py` | `data/<name>/messages.csv` → `speaker_utterances_filtered.csv` (requires Vertex AI; `--skip-filter`) |
| Derived | `compute_derived.py` | `data/<name>/*.csv` → `analysis/derived/<name>/` (`--skip-derived`) |

Quarto notebooks and animations are run separately (see below).

**Other scripts** (not pipeline steps):

| Script | Purpose |
|--------|---------|
| `dataset_paths.py` | Dataset layout and the `--dataset` / `DATASET` resolution shared by the Python scripts and tests |
| `config.R` | The one file a notebook sources: dataset paths (`use_dataset()`), writing-project paths, design constants, palettes, ggplot theme, and it sources every helper in `analysis/R/` |
| `R/prepare.R` | `load_tables()` and the shared data preparation (`phase1_utterances()`, `listener_trials()`, `attach_speaker()`, `social_guess_trials()`, `final_phase1_properties()`, ...): the recodes every notebook used to repeat |
| `R/group_specificity.R` | Per-game group-specificity fits (`game_specificity_table()`, `gs_wide()`, optional covariates) and the seeded permutation test with a hash-keyed RDS cache in `analysis/derived/<name>/` |
| `R/mixed_models.R` | `fit_progressively()`: the preregistered random-effects simplification (maximal model, then drop correlations, then slopes by smallest variance); `simplification_log()` and `random_effects_structure()` report what was fit |
| `R/contrasts.R` | `fit_h12_wls()` (the H1/H2 weighted regression and planned contrasts), `pairwise_weights()`, `contrast_table()`, and `robustness_rerun()` for the subset-of-games checks |
| `R/bayes_factors.R` | brms/bridgesampling Bayes factors for non-significant planned contrasts; `maybe_bayes_factor()` applies the `BAYES_FACTORS=auto\|always\|never` decision; packages load on first use |
| `R/effects.R` | `report_effect_sizes()`, `cohens_d_games()`, `fmt_pval()` |
| `R/attrition.R` | `player_attrition()`, `game_status()`, `complete_games()`, and the differential-dropout tests reported in `00_data_overview.qmd` |
| `R/survey.R` | `exit_survey_responses()`, `has_field()`, `felt_human_flags()`, `likert_by_condition()` for `05_exit_survey.qmd` (handles the pilot's pre-revamp fields) |
| `R/stats_tex.R` | `write_stats_tex()` / `write_stats_lines()`: statistics as `\newcommand` macros with letters-only name checks |
| `R/plots.R` | Condition and group scales, Phase 2 layers, `save_fig()` into the dataset's figures directory |
| `tests/` | Plain `stopifnot` tests of the R helpers on simulated data, one file per helper (`Rscript analysis/tests/run_all.R`, also run by `make test` and the pre-commit hook) |
| `plot_style.py` | Shared Python plotting constants (imported, not run directly) |
| `test_data_integrity.py` | Pytest validation of `data/<name>/` CSV structure for the active dataset |
| `test_compute_derived.py` | Pytest unit tests for the derived-metric definitions (latest-utterance selection, trajectory start rule, lexical uniqueness) |
| `test_preprocessing.py` | Pytest unit tests for `preprocessing.flag_length_increase` (the AI-use trigger in `players.csv`) and `filter_nonreferential.build_filtered_utterances` (rounds with no referential message are dropped, not emptied) |

## Processing new data

Raw Empirica exports land in `experiment/data/` via `empirica export` or the backup script. Each export is a cumulative snapshot of one server; `combine_runs.py` unions the registered exports on record id and keeps the newest version of each record, so overlapping exports are safe to list.

```bash
# 1. Extract each zip
uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip

# 2. Combine (extract_run.py registered the timestamp in data/<name>/runs.txt already)
uv run python analysis/combine_runs.py --dataset pilots

# 3. Run the pipeline (preprocess → filter → derived metrics)
uv run python analysis/process_data.py --dataset pilots                  # full pipeline
uv run python analysis/process_data.py --dataset pilots --skip-filter    # if no Vertex AI

# 4. Validate and render (separate steps)
make test DATASET=pilots
make notebooks DATASET=pilots
```

Starting the full sample: `mkdir data/full`, write its `runs.txt`, then the same commands with `--dataset full` (or `make all DATASET=full`). The integrity suite applies the production bonus rate to every dataset other than `pilots`.

## Browsing runs

```bash
uv run python analysis/extract_run.py list                               # list extracted runs
uv run python analysis/extract_run.py bonuses                            # print latest bonuses
uv run python analysis/extract_run.py bonuses --run 20260225_210047      # specific run
```

## Running individual scripts standalone

```bash
uv run python analysis/compute_derived.py data/pilots/ --output analysis/derived/pilots/
uv run python analysis/animate_umap.py --data-dir data/pilots/ --umap-dir analysis/derived/pilots/ --output-dir figures/pilots/
uv run pytest analysis/test_data_integrity.py analysis/test_compute_derived.py analysis/test_preprocessing.py -v
DATASET=full uv run pytest analysis/test_data_integrity.py -v
```

## Quarto notebooks

All notebooks source `config.R`, which sets `data_dir`, `derived_dir`, and `figures_dir` for the active dataset (`DATASET`, default `pilots`) and sources the helpers in `analysis/R/`; `list2env(load_tables(), envir = globalenv())` then loads every data and derived table as a variable. A notebook tied to one dataset calls `use_dataset("<name>")` before loading; `SI_pilot.qmd` does this so it always documents the pilot. Data preparation goes through the functions in `R/prepare.R` rather than inline recodes, and the per-game group-specificity estimates come from `game_specificity_table()` so every notebook reports the same numbers.

**For the pilot data** (these feed the preregistration manuscript) -- run after the pipeline:

| Notebook | Generates |
|----------|-----------|
| `SI_pilot.qmd` | Pilot data analyses → `figures/pilots/` + `writing/preregistration/stats/pilot.tex` |
| `llm_simulation/SI_llm_simulation.qmd` | LLM benchmark → `figures/llm_plots/` + `writing/preregistration/stats/llm.tex` |

**For the full sample** (the preregistered analyses; `make notebooks DATASET=<name>` renders all of them, and they default to the pilot data until the full sample exists):

| Notebook | Purpose |
|----------|---------|
| `00_data_overview.qmd` | Data overview |
| `01_outcome_neutral.qmd` | Outcome-neutral criteria (convention formation) |
| `02_primary_analysis.qmd` | Primary analyses (H1 & H2) |
| `03_secondary_analysis.qmd` | Secondary analyses |
| `04_exploratory.qmd` | Exploratory analyses |
| `05_exit_survey.qmd` | Exit survey responses |

## Stats → LaTeX pipeline

Analysis notebooks write statistics as `\newcommand` definitions to `writing/preregistration/stats/*.tex`, which are `\input`'d by `writing/preregistration/main.tex`. This keeps numbers in sync between the analysis and the manuscript.

After re-rendering a notebook, commit the updated `writing/preregistration/stats/*.tex` file so the paper picks up the new numbers. The generated files have a `% AUTO-GENERATED` header to discourage manual edits.

**Note:** `writing/` is in `.gitignore`: each project directory is a clone of its Overleaf project's git remote, so it is versioned on the Overleaf side, not in this repo. The stats files live inside `writing/preregistration/stats/` and are managed on the Overleaf side.

## Figures → manuscript

Figures are generated in `figures/<name>/` (`figures/pilots/` for the SI) and `figures/llm_plots/`. The manuscript references them from `figures/` (relative to `writing/preregistration/`). Run the sync script to copy them:

```bash
bash figures/sync_figures.sh
```

This copies all `SI_*.pdf` files into `writing/preregistration/figures/`. Overleaf doesn't support paths outside the project root, so figures must live inside `writing/preregistration/`. `SI_group_specificity.pdf` in the manuscript was hand-adjusted in Illustrator; `SI_pilot.qmd` writes the generated version as `SI_group_specificity_generated.pdf` so the two can be compared without overwriting the edited one.
