# lexical-variation

Multiplayer reference game experiment built with [Empirica](https://empirica.ly/) studying lexical variation and social signaling. 9 players in 3 groups describe tangram images to each other across two phases, with experimental conditions affecting group dynamics in Phase 2.

## Setup

Install Empirica:

```bash
curl -fsS https://install.empirica.dev | sh
```

Install dependencies:

```bash
# JavaScript (experiment)
cd experiment && npm install

# Python (analysis)
uv sync

# R (analysis)
# In R: renv::restore()
```

Note: `rpy2` requires R to be installed. Cairo-based packages may require: `brew install cairo pango`

## Running the experiment

See [`experiment/README.md`](experiment/README.md) for full documentation on local development, production deployment, running sessions, copying data, error monitoring, and testing.

Quick start for local development:

```bash
cd experiment
rm .empirica/local/tajriba.json
empirica
```

- Admin: http://localhost:3000/admin
- Players: http://localhost:3000/
- Production: https://tangramcommunication.empirica.app/

## Testing

```bash
cd experiment
npx playwright test              # test mode (shorter games)
npx playwright test --headed     # visible browser
npx playwright show-report       # view report
```

See [`experiment/README.md`](experiment/README.md) for details on test architecture and writing new tests.

## Analysis pipeline

Back up production data, then run the pipeline to go from raw export to figures:

```bash
# 1. Back up data from the production server
cd experiment
bash copy_tajriba.sh --once

# 2. Run the full pipeline (most recent zip)
uv run python analysis/run_pipeline.py

# Or from a specific zip
uv run python analysis/run_pipeline.py experiment/data/20260222_125327/empirica-export-20260222_132407.zip
```

Skip slow steps with flags:

```bash
uv run python analysis/run_pipeline.py --skip-embeddings   # skip SBERT computation
uv run python analysis/run_pipeline.py --skip-visualize    # skip plots and animations
uv run python analysis/run_pipeline.py --skip-render       # skip Quarto notebook rendering
```

The pipeline extracts bonuses (with Prolific IDs), anonymizes raw data, runs preprocessing, computes embeddings and similarity metrics, generates figures, and renders Quarto notebooks. Outputs go to a datetime-stamped directory:

```
analysis/20260222_132407/
├── bonuses.csv       # Prolific IDs + bonus amounts (sensitive, not committed)
├── raw/              # Anonymized raw Empirica CSVs
├── data/             # Preprocessed analysis-ready CSVs + embeddings
└── figures/          # Plots and animations
```

The pipeline maintains a symlink `analysis/processed -> analysis/{datetime}/data/` that always points to the most recently processed dataset. Each pipeline run deletes the old symlink and creates a new one. The Quarto notebooks (`analysis/00_preprocess.qmd` through `05_exit_survey.qmd`) all read from `analysis/processed/` via `here("analysis", "processed")`, so they automatically pick up the latest data without any edits.
