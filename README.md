# lexical-variation

- [Repository structure](#repository-structure)
- [Setup](#setup)
- [Running the experiment](#running-the-experiment)
- [Analysis pipeline](#analysis-pipeline)
- [LLM simulation](#llm-simulation)
- [Power analysis](#power-analysis)

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
├── data/
│   ├── pilots/               # Canonical pilot dataset (committed)
│   │   ├── raw/              #   Anonymized Empirica CSVs
│   │   └── *.csv             #   Preprocessed analysis-ready CSVs
│   └── pilot_runs/           # Per-run outputs from extract_run.py (gitignored)
├── analysis/                 # Analysis code & outputs
│   ├── extract_run.py        # Extract Empirica export zip → data/pilot_runs/
│   ├── combine_runs.py       # Stack raw CSVs from multiple runs → data/pilots/raw/
│   ├── process_data.py       # Run pipeline on data/pilots/ (calls the three scripts below)
│   │   ├── preprocessing.py  #   Raw Empirica CSVs → analysis-ready CSVs
│   │   ├── filter_nonreferential.py  #   LLM-based message classifier 
│   │   └── compute_derived.py        #   SBERT embeddings, similarities, UMAP
│   ├── 00–05_*.qmd           # Pre-registered analysis notebooks (full sample)
│   ├── SI_pilot.qmd          # SI: pilot data analyses
│   ├── pilot_derived/        # Computed outputs (similarities, embeddings, UMAP)
│   ├── llm_simulation/       # LLM Phase 1 benchmark simulation
│   └── power_analysis/       # Power analysis for sample size justification
├── figures/                  # Generated & design assets
│   ├── pilot_plots/          # SI figures from SI_pilot.qmd
│   ├── llm_plots/            # SI figures from SI_llm_simulation.qmd
│   └── ...                   # Tangrams, avatars, etc.
├── paper/                    # Manuscript (gitignored; synced via Overleaf)
│   └── stats/                # Auto-generated stats from notebooks
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

Configure environment variables (needed for running the experiment and LLM tools, not for reproducing analyses):

```bash
cp .env.example .env   # then fill in values
```

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

### Testing

```bash
cd experiment
npx playwright test              # test mode (shorter games)
npx playwright test --headed     # visible browser
npx playwright show-report       # view report
```

See [`experiment/README.md`](experiment/README.md) for details on test architecture and writing new tests.

## Analysis pipeline

### Reproducing pilot results

The preprocessed pilot data (including filtered utterances) is committed in `data/pilots/`. After installing dependencies (see [Setup](#setup)):

```bash
make pilot    # derive metrics + render notebooks (no Vertex AI needed)
```

Or step by step:

```bash
uv run python analysis/process_data.py --skip-filter    # preprocess + derived metrics
quarto render analysis/SI_pilot.qmd                     # pilot analyses → figures + stats
quarto render analysis/llm_simulation/SI_llm_simulation.qmd  # LLM benchmark
```

The filter step requires Vertex AI (see [LLM simulation](#llm-simulation)) and can be skipped since the filtered data is already committed. Run `make help` to see all available targets.

### Data processing scripts

There are three scripts that should be run in order. Each reads the previous script's output:

| Script | Reads from | Writes to |
|--------|-----------|-----------|
| `extract_run.py <zip>` | Empirica export zip in `experiment/data/` | `data/pilot_runs/{timestamp}/raw/` + `bonuses.csv`. Strips Prolific IDs and other PII from player.csv. |
| `combine_runs.py <runs>` | `data/pilot_runs/*/raw/` | `data/pilots/raw/` + `manifest.json` |
| `process_data.py` | `data/pilots/raw/` | `data/pilots/*.csv` + `analysis/pilot_derived/` |
| ↳ `preprocessing.py` | `data/pilots/raw/` | `data/pilots/*.csv` |
| ↳ `filter_nonreferential.py` | `data/pilots/messages.csv` | `data/pilots/speaker_utterances_filtered.csv` (requires Vertex AI; `--skip-filter`) |
| ↳ `compute_derived.py` | `data/pilots/*.csv` | `analysis/pilot_derived/` (`--skip-derived`) |

### Processing new data

Raw Empirica exports land in `experiment/data/` via `empirica export` or the backup script.

```bash
make all    # extract zips → combine → process → render notebooks
```

Or step by step:

```bash
# 1. Extract each zip (unzip, anonymize, extract bonuses)
uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip
uv run python analysis/extract_run.py experiment/data/20260301_214147/empirica-export-20260301_214147.zip

# 2. Combine runs (stack raw CSVs into data/pilots/raw/)
uv run python analysis/combine_runs.py 20260301_132907 20260301_214147

# 3. Run the pipeline (preprocess → filter → derived metrics)
uv run python analysis/process_data.py
```

### Notebooks for the registered report

These produce the figures and stats for the manuscript. Run after the process data pipeline:

```bash
quarto render analysis/SI_pilot.qmd                              # pilot analyses
quarto render analysis/llm_simulation/SI_llm_simulation.qmd      # LLM benchmark
```

| Notebook | Generates | Output |
|----------|-----------|--------|
| `SI_pilot.qmd` | Pilot data analyses | `figures/pilot_plots/` + `paper/stats/pilot.tex` |
| `llm_simulation/SI_llm_simulation.qmd` | LLM benchmark | `figures/llm_plots/` + `paper/stats/llm.tex` |

Stats are written as `\newcommand` definitions to `paper/stats/*.tex`, which the manuscript `\input`s. Sync figures to the paper before pushing to Overleaf:

```bash
bash figures/sync_figures.sh   # copies SI_*.pdf into paper/figures/
```

### Notebooks for the full sample (not yet active)

These will run the pre-registered analyses on the full dataset. Currently they read from `data/pilots/` + `analysis/pilot_derived/` — the paths in `config.R` will need to be updated to point at the full sample data when it's collected.

| Notebook | Purpose |
|----------|---------|
| `00_preprocess.qmd` | Load & validate data |
| `01_outcome_neutral.qmd` | Outcome-neutral criteria (convention formation) |
| `02_primary_analysis.qmd` | Primary analyses (H1 & H2) |
| `03_secondary_analysis.qmd` | Secondary analyses |
| `04_exploratory.qmd` | Exploratory analyses |
| `05_exit_survey.qmd` | Exit survey responses |

## LLM simulation

All simulation code lives in `analysis/llm_simulation/`. Simulates groups of 3 LLM agents playing the reference game to benchmark whether AI can form stable conventions (paper, AI detection section). Uses Gemini via Vertex AI (`gcloud auth application-default login`).

```bash
# Run simulation (quick test)
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 2 --blocks 2

# Full run for paper
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 20 --temperature 0

# Process results → CSVs, then render analysis notebook
uv run python analysis/llm_simulation/process_llm_results.py
cd analysis/llm_simulation && quarto render SI_llm_simulation.qmd
```

## Power analysis

Sample size justification using simulated data from Boyce et al. (2023). This is in `analysis/power_analysis/`.

```bash
quarto render analysis/power_analysis/power_analysis_setup.Qmd    # generate simulated data
quarto render analysis/power_analysis/power_analysis_plots.Qmd    # plot power curves
```
