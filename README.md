# lexical-variation

In the game (built with [Empirica](https://empirica.ly/)), 9 players in 3 groups describe tangram images to each other across two phases, with 4 between-subjects conditions that orthogonally manipulate interaction patterns and social-signaling goals in Phase 2:

- **refer + separated**: same groups throughout Phase 2 (baseline)
- **refer + mixed**: groups reshuffled every trial in Phase 2, masked identities
- **social + mixed**: reshuffled + social guessing task (listeners guess if speaker is from their original group)
- **social-first + mixed**: told about social identification reward before Phase 1, then same as social + mixed

## Repository structure

```
├── experiment/               # Empirica app (React client + Node server)
│   ├── client/src/           # React components & game UI
│   ├── server/src/           # Game logic (callbacks, constants)
│   ├── shared/               # Shared constants (timing, scoring)
│   ├── tests/                # Playwright end-to-end tests
│   └── .empirica/            # Treatments, lobbies, config
├── analysis/                 # Data processing & analysis
│   ├── run_pipeline.py       # Main entry point for data processing
│   ├── 00_preprocess.qmd     # Load & validate preprocessed data
│   ├── 01_outcome_neutral.qmd # Outcome-neutral criteria (convention formation)
│   ├── 02_primary_analysis.qmd # Primary analyses (H1 & H2)
│   ├── 03_secondary_analysis.qmd # Secondary analyses
│   ├── 04_exploratory.qmd    # Exploratory analyses
│   ├── 05_exit_survey.qmd    # Exit survey responses
│   ├── SI_pilot.qmd          # SI: pilot data analyses
│   ├── compute_embeddings.py # SBERT embeddings & similarity metrics
│   ├── filter_nonreferential.py # LLM-based message classifier
│   └── llm_simulation/       # LLM Phase 1 benchmark simulation
├── data/                     # Preprocessed datasets (committed)
│   └── pilots/               # Pilot data (4 games, 1 per condition)
├── paper/                    # LaTeX manuscript (gitignored; synced via Overleaf)
│   └── stats/                # Auto-generated stats from notebooks
└── figures/                  # Design assets (tangrams, avatars)
```

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

## Testing

```bash
cd experiment
npx playwright test              # test mode (shorter games)
npx playwright test --headed     # visible browser
npx playwright show-report       # view report
```

See [`experiment/README.md`](experiment/README.md) for details on test architecture and writing new tests.

## Analysis pipeline

To reproduce the analyses from the pilot data:

```bash
uv sync                                    # install Python deps
# In R: renv::restore()                    # install R deps
uv run python analysis/compute_embeddings.py data/pilots/   # SBERT embeddings
quarto render analysis/SI_pilot.qmd        # pilot analyses
quarto render analysis/llm_simulation/SI_llm_simulation.qmd # LLM benchmark
```

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

### Rendering notebooks

Quarto notebooks (`00_preprocess.qmd` through `05_exit_survey.qmd`) read from `analysis/processed_data/`, a symlink updated by `run_pipeline.py`.

```bash
quarto render analysis/SI_pilot.qmd
quarto render analysis/02_primary_analysis.qmd
```

### Stats → manuscript

Analysis notebooks write statistics as `\newcommand` definitions to `paper/stats/*.tex`, which are `\input`'d by the manuscript (`paper/main.tex`). This keeps numbers in the paper in sync with the analysis code.

| Notebook | Generates |
|----------|-----------|
| `analysis/SI_pilot.qmd` | `paper/stats/pilot.tex` |
| `analysis/llm_simulation/SI_llm_simulation.qmd` | `paper/stats/llm.tex` |

Re-render the relevant notebook to update the stats files after any data or analysis changes.

### Figures → manuscript

Analysis notebooks save plots to `analysis/pilot_outputs/` and `analysis/llm_baseline_outputs/`. The manuscript references these from `paper/figures/`. To sync before pushing to Overleaf:

```bash
bash paper/sync_figures.sh
```

This copies all `SI_*.pdf` files into `paper/figures/` so Overleaf can find them (Overleaf doesn't support paths outside the project root).

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
