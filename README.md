# Testing the roles of passive isolation and active social motivation in lexical variation using experimental microsocieties

## Table of contents

- [Repository structure](#repository-structure)
- [Setup](#setup)
- [Running the experiment](#running-the-experiment)
- [Data files](#data-files)
- [Analysis pipeline](#analysis-pipeline)
- [LLM simulation](#llm-simulation)
- [Power analysis](#power-analysis)

## Repository structure

```
├── experiment/               # Empirica app (React client + Node server)
│   ├── client/src/           # React components & game UI
│   ├── server/src/           # Game logic (callbacks, constants)
│   ├── shared/               # Shared constants (timing, scoring)
│   ├── tests/                # Playwright end-to-end tests
│   └── .empirica/            # Treatments, lobbies, config
├── data/
│   ├── pilots/               # Pilot dataset (committed)
│   └── pilot_runs/           # Per-run outputs from extract_run.py (gitignored)
├── analysis/                 # Analysis code & outputs
│   ├── llm_simulation/       # LLM Phase 1 benchmark simulation
│   └── power_analysis/       # Power analysis for sample size justification
├── figures/                  # Generated & design assets
├── paper/                    # Manuscript (gitignored; synced via Overleaf)
```

## Setup

The game is built with [Empirica](https://empirica.ly/). Install it:

```bash
curl -fsS https://install.empirica.dev | sh
```

Analysis notebooks are rendered with [Quarto](https://quarto.org/docs/get-started/), which needs to be installed before running any `quarto render` commands.

Install dependencies:

```bash
# JavaScript (experiment)
cd experiment && npm install

# Python (analysis)
uv sync

# R (analysis)
# In R: renv::restore()
```

Note: `rpy2` requires R to be installed. Cairo-based packages may require additional system libraries: `brew install cairo pango`

Configure environment variables (needed for running the experiment and for gemini, but not for reproducing analyses):

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

## Data files

The preprocessed pilot data is in `data/pilots/`. See [`data/pilots/README.md`](data/pilots/README.md) for descriptions of the data columns. 

| File | Description |
|------|-------------|
| `raw_anonymized/` | Anonymized raw Empirica CSVs (9 files), with Prolific IDs and PII stripped |
| `games.csv` | One row per game session — condition, tangram set, block counts |
| `players.csv` | One row per player — group assignment, score, exit survey responses |
| `trials.csv` | One row per player per round — role, target, click, accuracy |
| `messages.csv` | Individual chat messages, deduplicated across players in a group |
| `messages_classified.csv` | Messages augmented with LLM referential/non-referential classification |
| `speaker_utterances.csv` | Speaker messages concatenated per round (all messages) |
| `speaker_utterances_filtered.csv` | Same as above, but with non-referential messages removed first |
| `social_guesses.csv` | Listener guesses about speaker group membership (social conditions only) |

## Analysis pipeline

### Reproducing pilot results

The preprocessed pilot data (including filtered utterances) is committed in `data/pilots/`. After installing dependencies (see [Setup](#setup)):

```bash
make pilot    # derive metrics + render notebooks
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
| `combine_runs.py <runs>` | `data/pilot_runs/*/raw/` | `data/pilots/raw_anonymized/` + `manifest.json` |
| `process_data.py` | `data/pilots/raw_anonymized/` | `data/pilots/*.csv` + `analysis/pilot_derived/` |
| ↳ `preprocessing.py` | `data/pilots/raw_anonymized/` | `data/pilots/*.csv` |
| ↳ `filter_nonreferential.py` | `data/pilots/messages.csv` | `data/pilots/speaker_utterances_filtered.csv` (requires Vertex AI; `--skip-filter`) |
| ↳ `compute_derived.py` | `data/pilots/*.csv` | `analysis/pilot_derived/` (`--skip-derived`) |

### Processing new data

Raw Empirica exports (`.zip` files) are in `experiment/data/` via `empirica export` or the backup script. (Note: these are not committed because they contain identifiable participant data). To process: 

```bash
make all    # extract zips → combine → process → render notebooks
```

Or step by step:

```bash
# 1. Extract each zip (unzip, anonymize, extract bonuses)
uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip
uv run python analysis/extract_run.py experiment/data/20260301_214147/empirica-export-20260301_214147.zip

# 2. Combine runs (stack raw CSVs into data/pilots/raw_anonymized/)
uv run python analysis/combine_runs.py 20260301_132907 20260301_214147

# 3. Run the pipeline (preprocess → filter → derived metrics)
uv run python analysis/process_data.py
```

### Notebooks for the registered report

These produce the figures and stats for the manuscript. Run after data are processed: 

```bash
quarto render analysis/SI_pilot.qmd                              # pilot analyses
quarto render analysis/llm_simulation/SI_llm_simulation.qmd      # LLM benchmark
```

| Notebook | Generates | Output |
|----------|-----------|--------|
| `SI_pilot.qmd` | Pilot data analyses | `figures/pilot_plots/` + `paper/stats/pilot.tex` |
| `llm_simulation/SI_llm_simulation.qmd` | LLM benchmark | `figures/llm_plots/` + `paper/stats/llm.tex` |

The stats are written as `\newcommand` definitions to `paper/stats/*.tex`, which the manuscript `\input`s. Sync figures to the paper before pushing to Overleaf:

```bash
bash figures/sync_figures.sh   # copies SI_*.pdf into paper/figures/
```

### Notebooks for the full sample (not yet active)

These will run the pre-registered analyses on the full dataset. Currently they read from `data/pilots/` + `analysis/pilot_derived/` — the paths in `config.R` will need to be updated to point at the full sample data when it's collected.

| Notebook | Purpose |
|----------|---------|
| `00_data_overview.qmd` | Data overview |
| `01_outcome_neutral.qmd` | Outcome-neutral criteria (convention formation) |
| `02_primary_analysis.qmd` | Primary analyses (H1 & H2) |
| `03_secondary_analysis.qmd` | Secondary analyses |
| `04_exploratory.qmd` | Exploratory analyses |
| `05_exit_survey.qmd` | Exit survey responses |

## LLM simulation

All simulation code is in `analysis/llm_simulation/`. The code simulates groups of 3 LLM agents playing the reference game to benchmark whether AI can form stable conventions (paper, AI detection section). This uses Gemini via Vertex AI (needs a Google Cloud project with the Vertex AI API enabled): 

```bash
# Install gcloud CLI if needed: https://cloud.google.com/sdk/docs/install

# Login and set up application default credentials
gcloud auth application-default login

# Set your default project
gcloud config set project YOUR_PROJECT_ID
```

Your credentials will be stored at `~/.config/gcloud/application_default_credentials.json`.

The script auto-detects the project from your gcloud config. You can override with:
- `--project` flag
- `GOOGLE_CLOUD_PROJECT` environment variable
- `.env` file with `GOOGLE_CLOUD_PROJECT=your-project-id`

### Running the simulations

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

The power analysis provides sample size justification using simulated data from Boyce et al. (2023). The code is in `analysis/power_analysis/`.

```bash
quarto render analysis/power_analysis/power_analysis_setup.Qmd    # generate simulated data
quarto render analysis/power_analysis/power_analysis_plots.Qmd    # plot power curves
```
