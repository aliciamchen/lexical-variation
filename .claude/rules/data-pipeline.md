---
paths:
  - "analysis/**"
  - "data/**"
  - "experiment/data/**"
  - "experiment/copy_tajriba.sh"
---

# Data and analysis pipeline

## Datasets

The pipeline is keyed by a dataset name. The pilot sessions are the dataset `pilots`; the full sample will be a second dataset beside it (suggested name `full`), never an edit of the pilot paths. The layout is defined once in `analysis/dataset_paths.py` (Python scripts) and mirrored in `analysis/config.R` (`use_dataset()`, for the notebooks); keep the two in sync. The active dataset is `--dataset` on a script, else the `DATASET` environment variable, else `pilots`. `make` exports `DATASET` to every step, so `make all DATASET=full` runs the whole pipeline on the full sample.

| Directory | Contents | Committed? |
|-----------|----------|------------|
| `experiment/data/<timestamp>/` | Raw Empirica export zips from `copy_tajriba.sh` | No |
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
  cd experiment
  bash copy_tajriba.sh            # loop every 5 minutes (default)
  bash copy_tajriba.sh --once     # single backup and exit
  bash copy_tajriba.sh --help     # show usage
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
| `config.R` | Shared paths (`use_dataset()`), palettes, ggplot theme (sourced by all .qmd notebooks) |
| `group_specificity.R` | Group-specificity estimation with permutation testing (called by notebooks; caches RDS keyed by an input hash in `analysis/derived/<name>/`) |
| `plot_style.py` | Shared Python plotting constants (imported, not run directly) |
| `test_data_integrity.py` | Pytest validation of `data/<name>/` CSV structure for the active dataset |
| `test_compute_derived.py` | Pytest unit tests for the derived-metric definitions (latest-utterance selection, trajectory start rule, lexical uniqueness) |
| `test_preprocessing.py` | Pytest unit tests for `preprocessing.flag_length_increase` (the AI-use trigger in `players.csv`) and `filter_nonreferential.build_filtered_utterances` (rounds with no referential message are dropped, not emptied) |
| `mixed_models.R` | `fit_progressively()`: the preregistered random-effects simplification (maximal model, then drop correlations, then slopes by smallest variance); sourced by `config.R`; `simplification_log()` and `random_effects_structure()` report what was fit |
| `test_mixed_models.R` | Plain `stopifnot` tests of the simplification procedure on simulated data (`Rscript analysis/test_mixed_models.R`, also run by `make test`) |
| `bayes_factors.R` | brms/bridgesampling Bayes factors for non-significant planned contrasts (called from `02_primary_analysis.qmd`; `BAYES_FACTORS=auto\|always\|never`) |

## Processing new data

Raw Empirica exports land in `experiment/data/` via `empirica export` or the backup script. Each export is a cumulative snapshot of one server, so keep only the latest export per server in `runs.txt`.

```bash
# 1. Extract each zip
uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip

# 2. Register the timestamp in data/<name>/runs.txt, then combine
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

All notebooks source `config.R`, which sets `data_dir`, `derived_dir`, and `figures_dir` for the active dataset (`DATASET`, default `pilots`). A notebook tied to one dataset calls `use_dataset("<name>")` after sourcing it; `SI_pilot.qmd` does this so it always documents the pilot.

**For the pilot data** (these feed the preregistration manuscript) -- run after the pipeline:

| Notebook | Generates |
|----------|-----------|
| `SI_pilot.qmd` | Pilot data analyses → `figures/pilots/` + `paper/stats/pilot.tex` |
| `llm_simulation/SI_llm_simulation.qmd` | LLM benchmark → `figures/llm_plots/` + `paper/stats/llm.tex` |

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

Analysis notebooks write statistics as `\newcommand` definitions to `paper/stats/*.tex`, which are `\input`'d by `paper/main.tex`. This keeps numbers in sync between the analysis and the manuscript.

After re-rendering a notebook, commit the updated `paper/stats/*.tex` file so the paper picks up the new numbers. The generated files have a `% AUTO-GENERATED` header to discourage manual edits.

**Note:** The `paper/` directory is in `.gitignore` (it's synced via Overleaf, not this repo). The stats files live inside `paper/stats/` and are managed on the Overleaf side.

## Figures → manuscript

Figures are generated in `figures/<name>/` (`figures/pilots/` for the SI) and `figures/llm_plots/`. The manuscript references them from `figures/` (relative to `paper/`). Run the sync script to copy them:

```bash
bash figures/sync_figures.sh
```

This copies all `SI_*.pdf` files into `paper/figures/`. Overleaf doesn't support paths outside the project root, so figures must live inside `paper/`. `SI_group_specificity.pdf` in the manuscript was hand-adjusted in Illustrator; `SI_pilot.qmd` writes the generated version as `SI_group_specificity_generated.pdf` so the two can be compared without overwriting the edited one.
