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

`analysis/run_pipeline.py` is the single entry point for all data processing:

```bash
# Back up production data
cd experiment && bash copy_tajriba.sh --once

# Process a single export zip (most recent)
uv run python analysis/run_pipeline.py

# Combine multiple runs into one dataset
uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147

# Skip slow steps
uv run python analysis/run_pipeline.py --skip-embeddings --skip-visualize --skip-render

# Browse past runs
uv run python analysis/run_pipeline.py list
uv run python analysis/run_pipeline.py bonuses
```

Output goes to `analysis/{datetime}/` (single run) or split across `data/pilots/` (raw + preprocessed CSVs) and `analysis/pilots/` (figures, manifest). The `analysis/processed_data` symlink points to the active dataset.

Quarto notebooks (`00_preprocess.qmd` through `05_exit_survey.qmd`) read from `analysis/processed_data/`, a symlink updated by `run_pipeline.py`.
