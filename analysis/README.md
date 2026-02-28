# Analysis Pipeline

## Overview

`run_pipeline.py` is the single entry point for processing raw Empirica export zips into analysis-ready data, figures, and rendered Quarto notebooks. It also provides subcommands for browsing past runs.

```
experiment/data/<timestamp>/empirica-export-*.zip
        |
        v
  run_pipeline.py              (unzip → bonuses → anonymize → preprocess → embeddings → visualize → render)
        |
        v
  analysis/<datetime>/         (timestamped output directory)
  ├── bonuses.csv              (Prolific IDs + bonus amounts)
  ├── raw/                     (anonymized raw Empirica CSVs)
  ├── data/                    (preprocessed analysis-ready CSVs)
  └── outputs/                 (plots and animations)
```

## Fetching data from production

```bash
cd experiment
bash copy_tajriba.sh            # loop every 5 minutes
bash copy_tajriba.sh --once     # single backup
```

This SSHs into the production server, runs `empirica export`, and copies the zip locally to `experiment/data/<timestamp>/`.

## Running the pipeline

```bash
# Process the most recent zip
uv run python analysis/run_pipeline.py

# Process a specific zip
uv run python analysis/run_pipeline.py experiment/data/20260222_125327/empirica-export-20260222_132407.zip

# Skip slow steps
uv run python analysis/run_pipeline.py --skip-embeddings   # skip SBERT (~minutes)
uv run python analysis/run_pipeline.py --skip-visualize    # skip plots/animations
uv run python analysis/run_pipeline.py --skip-render       # skip Quarto notebooks
```

The pipeline creates/updates a symlink `analysis/processed_data -> analysis/<datetime>/data/` so that Quarto notebooks always read from the latest run.

## Browsing runs

```bash
# List all runs with metadata
uv run python analysis/run_pipeline.py list

# Show what processed_data points to
uv run python analysis/run_pipeline.py status

# Print bonus CSV (latest or specific run)
uv run python analysis/run_pipeline.py bonuses
uv run python analysis/run_pipeline.py bonuses --run 20260225_210047
```

## Output structure

Each pipeline run produces a timestamped directory:

```
analysis/20260227_123619/
├── bonuses.csv              # Prolific IDs + bonus amounts (sensitive)
├── raw/                     # Anonymized raw Empirica export CSVs
│   ├── game.csv
│   ├── player.csv           # participantIdentifier REMOVED
│   ├── playerRound.csv
│   └── ...
├── data/                    # Preprocessed analysis-ready CSVs
│   ├── games.csv
│   ├── trials.csv
│   ├── messages.csv
│   ├── speaker_utterances.csv
│   ├── embeddings.npy
│   ├── umap_projections.csv
│   └── ...
└── outputs/                 # Plots and animations
    ├── pilot_social_mixed_listener_accuracy.png
    └── ...
```

## Standalone exploratory scripts

These scripts run standalone analyses on preprocessed data. Both default to reading from `analysis/processed_data` but accept `--data-dir`:

```bash
# Contact network analysis (refer_mixed condition)
uv run python analysis/contact_network_analysis.py
uv run python analysis/contact_network_analysis.py --data-dir analysis/20260225_210047/data

# Label dynamics analysis (refer_mixed condition)
uv run python analysis/label_dynamics_analysis.py
uv run python analysis/label_dynamics_analysis.py --data-dir analysis/20260225_210047/data
```

## Prerequisites

- **Python** (managed by [uv](https://docs.astral.sh/uv/)): pandas, sentence-transformers, umap-learn
- **R** (managed by renv): tidyverse, lme4, lmerTest, emmeans, tidyboot, patchwork, here
- **Quarto** for rendering `.qmd` files

## Analysis documents

| File | Contents |
|------|----------|
| `00_preprocess.qmd` | Load/validate data, summaries, exclusion criteria checks |
| `01_outcome_neutral.qmd` | Outcome-neutral criteria: description length reduction, accuracy increase, convention stability, group-specificity permutation test |
| `02_primary_analysis.qmd` | H1/H2 hypothesis tests: weighted least squares on group-specificity, planned contrasts |
| `03_secondary_analysis.qmd` | Semantic change, referential accuracy, in-group vs out-group, social accuracy correlation |
| `04_exploratory.qmd` | Full temporal dynamics, UMAP visualization, utterance properties |

## Notes

- The SBERT model used is `paraphrase-MiniLM-L12-v2` (384-dimensional embeddings).
- `blockNum` in the data is 0-indexed within each phase (resets to 0 at start of Phase 2).
- Timestamped output directories are git-ignored. Only scripts and notebooks are tracked.
