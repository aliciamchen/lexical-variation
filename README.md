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

## LLM tools

Both tools use Gemini via Vertex AI. Requires `gcloud auth application-default login` and a GCP project with Vertex AI enabled.

### LLM simulation (Phase 1 benchmark)

All simulation code lives in `analysis/llm_simulation/`. Simulates groups of 3 LLM agents playing the reference game to benchmark whether AI can form stable conventions (paper, AI detection section).

```bash
# Run simulation (quick test)
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 2 --blocks 2

# Full run for paper
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 20 --temperature 0

# Process results → CSVs, then render analysis notebook
uv run python analysis/llm_simulation/process_llm_results.py
cd analysis/llm_simulation && quarto render SI_llm_simulation.qmd
```

### Non-referential message filter

Classifies speaker messages as referential vs non-referential (e.g., "thanks", "good job") for filtering before SBERT analysis. Target: 95% agreement with human labels.

```bash
# Classify + filter
uv run python analysis/filter_nonreferential.py classify --data-dir data/pilots/
uv run python analysis/filter_nonreferential.py apply --data-dir data/pilots/

# Or as part of the full pipeline
uv run python analysis/run_pipeline.py --filter-messages

# Validation workflow
uv run python analysis/filter_nonreferential.py sample --data-dir data/pilots/ --n 200
# ... manually label annotation_sample.csv -> human_labels.csv ...
uv run python analysis/filter_nonreferential.py validate --data-dir data/pilots/ --labels data/pilots/human_labels.csv
```

Once `speaker_utterances_filtered.csv` exists in the data directory, all downstream analysis (embeddings, Quarto notebooks, plots) automatically uses it instead of the unfiltered version.
