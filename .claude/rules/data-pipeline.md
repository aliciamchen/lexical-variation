---
paths:
  - "analysis/**"
  - "data/**"
  - "experiment/data/**"
  - "experiment/copy_tajriba.sh"
---

# Data and analysis pipeline

## Directory layout

| Directory | Contents | Committed? |
|-----------|----------|------------|
| `experiment/data/` | Raw Empirica export zips from `copy_tajriba.sh` | No |
| `data/pilots/raw/` | Anonymized raw Empirica CSVs (10 files) | Yes |
| `data/pilots/*.csv` | Preprocessed analysis-ready CSVs (games, players, trials, messages, speaker_utterances, social_guesses) | Yes |
| `data/pilots/manifest.json` | Provenance: which runs were combined | Yes |
| `data/pilot_runs/{timestamp}/` | Per-run pipeline outputs (raw/, data/, derived/, bonuses.csv) | No (gitignored) |
| `analysis/pilot_derived/` | Computed outputs from `compute_derived.py`: embeddings, similarities, UMAP, RDS caches | Yes |
| `analysis/pilot_plots/` | SI PDF figures from `SI_pilot.qmd` | Yes |
| `analysis/llm_plots/` | SI PDF figures from `SI_llm_simulation.qmd` | Yes |

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
  The script SSHs into `root@tangramcommunication.empirica.app`, runs `empirica export` in `~/empirica` to produce a CSV zip, then copies it locally into `experiment/data/<timestamp>/`. Safe to run while the experiment is live. Exits automatically after 3 consecutive failures.

## Pipeline scripts

Three scripts, run in order:

```bash
# 1. Extract each Empirica export zip (unzip, anonymize, extract bonuses)
uv run python analysis/extract_run.py <zip>           → data/pilot_runs/{timestamp}/raw/

# 2. Combine extracted runs (stack raw CSVs, filter failed games)
uv run python analysis/run_pipeline.py combine <runs> → data/pilots/raw/

# 3. Run the analysis pipeline (preprocess → filter → derived metrics)
uv run python analysis/run_pipeline.py                → data/pilots/, analysis/pilot_derived/
```

Step 3 runs these sub-steps in order:

| Step | Script | Inputs → Outputs |
|------|--------|------------------|
| Preprocess | `preprocessing.py` | `data/pilots/raw/` → `data/pilots/*.csv` |
| Filter | `filter_nonreferential.py` | `data/pilots/messages.csv` → `speaker_utterances_filtered.csv` (requires Vertex AI; `--skip-filter`) |
| Derived | `compute_derived.py` | `data/pilots/*.csv` → `analysis/pilot_derived/` (`--skip-derived`) |

Quarto notebooks and animations are run separately (see below).

**Other scripts** (not pipeline steps):

| Script | Purpose |
|--------|---------|
| `config.R` | Shared paths, palettes, ggplot theme (sourced by all .qmd notebooks) |
| `group_specificity.R` | Group-specificity estimation with permutation testing (called by notebooks, caches RDS in `pilot_derived/`) |
| `plot_style.py` | Shared Python plotting constants (imported, not run directly) |
| `test_data_integrity.py` | Pytest validation of preprocessed CSV structure |

## Processing new data

Raw Empirica exports land in `experiment/data/` via `empirica export` or the backup script.

```bash
# 1. Extract each zip
uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip
uv run python analysis/extract_run.py experiment/data/20260301_214147/empirica-export-20260301_214147.zip

# 2. Combine runs (stack raw CSVs into data/pilots/raw/)
uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147

# 3. Run the pipeline (preprocess → filter → derived metrics)
uv run python analysis/run_pipeline.py                  # full pipeline
uv run python analysis/run_pipeline.py --skip-filter    # if no Vertex AI

# 4. Render notebooks (separate step)
quarto render analysis/SI_pilot.qmd
```

## Browsing runs

```bash
uv run python analysis/run_pipeline.py list                               # list extracted runs
uv run python analysis/run_pipeline.py bonuses                            # print latest bonuses
uv run python analysis/run_pipeline.py bonuses --run 20260225_210047      # specific run
```

## Running individual scripts standalone

```bash
uv run python analysis/compute_derived.py data/pilots/ --output analysis/pilot_derived/
uv run python analysis/animate_umap.py --data-dir data/pilots/ --umap-dir analysis/pilot_derived/ --output-dir analysis/pilot_plots/
uv run pytest analysis/test_data_integrity.py -v
```

## Quarto notebooks

All notebooks read source data from `data/pilots/` and computed outputs from `analysis/pilot_derived/` (paths set in `config.R`).

| Notebook | Purpose |
|----------|---------|
| `00_preprocess.qmd` | Load & validate preprocessed data |
| `01_outcome_neutral.qmd` | Outcome-neutral criteria (convention formation) |
| `02_primary_analysis.qmd` | Primary analyses (H1 & H2) |
| `03_secondary_analysis.qmd` | Secondary analyses |
| `04_exploratory.qmd` | Exploratory analyses |
| `05_exit_survey.qmd` | Exit survey responses |
| `SI_pilot.qmd` | SI pilot data — generates `paper/stats/pilot.tex` and figures in `analysis/pilot_plots/` |
| `llm_simulation/SI_llm_simulation.qmd` | LLM benchmark — generates `paper/stats/llm.tex` and figures in `analysis/llm_plots/` |

## Stats → LaTeX pipeline

Analysis notebooks write statistics as `\newcommand` definitions to `paper/stats/*.tex`, which are `\input`'d by `paper/main.tex`. This keeps numbers in sync between the analysis and the manuscript.

After re-rendering a notebook, commit the updated `paper/stats/*.tex` file so the paper picks up the new numbers. The generated files have a `% AUTO-GENERATED` header to discourage manual edits.

**Note:** The `paper/` directory is in `.gitignore` (it's synced via Overleaf, not this repo). The stats files live inside `paper/stats/` and are managed on the Overleaf side.

## Figures → manuscript

Figures are generated in `analysis/pilot_plots/` and `analysis/llm_plots/`. The manuscript references them from `figures/` (relative to `paper/`). Run the sync script to copy them:

```bash
bash paper/sync_figures.sh
```

This copies all `SI_*.pdf` files into `paper/figures/`. Overleaf doesn't support paths outside the project root, so figures must live inside `paper/`.
