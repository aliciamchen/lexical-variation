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
│   ├── pilots/               # Pilot dataset (committed); the full sample will sit beside it
│   └── runs/                 # Per-run outputs from extract_run.py (gitignored)
├── analysis/                 # Analysis code & outputs
│   ├── derived/              # Derived metrics per dataset (derived/pilots/ committed)
│   ├── llm_simulation/       # LLM Phase 1 benchmark simulation
│   └── power_analysis/       # Power analysis for sample size justification
├── figures/                  # Generated & design assets
├── writing/                  # Overleaf projects, one per manuscript (gitignored; synced via Overleaf)
│   └── preregistration/      # The Stage 1 manuscript that serves as the preregistration
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

Configure environment variables (needed for building and running the experiment, but not for reproducing the analyses):

```bash
cp .env.example .env   # then fill in values
```

The single `.env` file at the repository root is read only on your own machine: `empirica bundle` compiles the Sentry DSN into the client bundle and refuses to build a production bundle without it, and `experiment/copy_tajriba.sh` uses the server hostname to pull backups. The Google Cloud project for the Gemini-based filter can also be set there, but the scripts fall back to your `gcloud` default project. Keep real hostnames and organization names in `.env`, never in committed files.

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
npm test                  # full Playwright suite (test mode: shorter games)
npm run test:group1       # one test group only (test:group1 ... test:group4)
npm run test:unit         # server unit tests (scoring, reshuffling; no browser)
npm run test:report       # view the HTML report
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

The `make test` target runs the data integrity suite on the processed CSVs together with unit tests for the derived-metric definitions (`analysis/test_compute_derived.py`) and for the preprocessing rules that the preregistration states precisely, such as the description-length flag and the treatment of trials with no referential message (`analysis/test_preprocessing.py`). It also runs the R helper tests in `analysis/tests/`, which check the shared data preparation, the group-specificity estimates and permutation test, the planned-contrast helpers, the stats-to-LaTeX writer, and the random-effects simplification procedure that every mixed model goes through (`fit_progressively()` in `analysis/R/mixed_models.R`: the maximal structure, then correlations removed, then slopes dropped from the smallest variance component, as preregistered). The primary-analysis notebook computes Bayes factors for non-significant planned contrasts with `brms`, which takes several minutes per contrast; set the environment variable `BAYES_FACTORS=never` before rendering to skip them, or `BAYES_FACTORS=always` to compute them for every contrast.

### Datasets

The pipeline is keyed by a dataset name. The pilot sessions are the dataset `pilots`, and the full sample will be a second dataset beside it rather than an edit of the pilot paths. Every dataset follows the same layout, which is defined once in `analysis/dataset_paths.py` for the Python scripts and mirrored in `analysis/config.R` for the notebooks:

| Path | Contents |
|------|----------|
| `data/<name>/runs.txt` | The Empirica export timestamps that make up the dataset, one per line |
| `data/<name>/raw_anonymized/` | The anonymized raw Empirica CSVs, stacked across those runs |
| `data/<name>/*.csv` | The preprocessed analysis-ready CSVs |
| `analysis/derived/<name>/` | Derived metrics (embeddings, similarities, UMAP) and cached model fits |
| `figures/<name>/` | Figures written by the notebooks |

The active dataset is chosen with the `DATASET` environment variable, or the `--dataset` flag on the individual scripts, and defaults to `pilots`. For example, `make all DATASET=full` runs the whole pipeline on a dataset named `full`, and `DATASET=full quarto render analysis/02_primary_analysis.qmd` renders a notebook against it. Per-run extracts are shared across datasets in `data/runs/`.

### Data processing scripts

There are three scripts that should be run in order. Each reads the previous script's output:

| Script | Reads from | Writes to |
|--------|-----------|-----------|
| `extract_run.py <zip>` | Empirica export zip in `experiment/data/` | `data/runs/{timestamp}/raw/` + `bonuses.csv`. Strips Prolific IDs and other PII from player.csv. |
| `combine_runs.py [--dataset NAME] [runs]` | `data/runs/*/raw/` for the runs in `data/<name>/runs.txt` | `data/<name>/raw_anonymized/` + `manifest.json` |
| `process_data.py [--dataset NAME]` | `data/<name>/raw_anonymized/` | `data/<name>/*.csv` + `analysis/derived/<name>/` |
| ↳ `preprocessing.py` | `data/<name>/raw_anonymized/` | `data/<name>/*.csv` |
| ↳ `filter_nonreferential.py` | `data/<name>/messages.csv` | `data/<name>/speaker_utterances_filtered.csv` (requires Vertex AI; `--skip-filter`) |
| ↳ `compute_derived.py` | `data/<name>/*.csv` | `analysis/derived/<name>/` (`--skip-derived`) |

### Processing new data

Raw Empirica exports (`.zip` files) are in `experiment/data/` via `empirica export` or the backup script. (Note: these are not committed because they contain identifiable participant data). Register each export's timestamp in the dataset's `runs.txt`, then process:

```bash
make all                 # pilot: extract zips → combine → process → test → render notebooks
make all DATASET=full    # the same for a dataset named full (data/full/runs.txt)
```

Or step by step:

```bash
# 1. Extract each zip (unzip, anonymize, extract bonuses)
uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip
uv run python analysis/extract_run.py experiment/data/20260301_214147/empirica-export-20260301_214147.zip

# 2. Combine the runs listed in data/pilots/runs.txt into data/pilots/raw_anonymized/
uv run python analysis/combine_runs.py --dataset pilots

# 3. Run the pipeline (preprocess → filter → derived metrics)
uv run python analysis/process_data.py --dataset pilots
```

### Notebooks for the pilot data

These produce the figures and statistics for the pilot section of the preregistration manuscript. Run them after data are processed:

```bash
quarto render analysis/SI_pilot.qmd                              # pilot analyses
quarto render analysis/llm_simulation/SI_llm_simulation.qmd      # LLM benchmark
```

| Notebook | Generates | Output |
|----------|-----------|--------|
| `SI_pilot.qmd` | Pilot data analyses | `figures/pilots/` + `writing/preregistration/stats/pilot.tex` |
| `llm_simulation/SI_llm_simulation.qmd` | LLM benchmark | `figures/llm_plots/` + `writing/preregistration/stats/llm.tex` |

The stats are written as `\newcommand` definitions to `writing/preregistration/stats/*.tex`, which the manuscript `\input`s. Sync figures to the paper before pushing to Overleaf:

```bash
bash figures/sync_figures.sh   # copies SI_*.pdf into writing/preregistration/figures/
```

### Notebooks for the full sample

These run the preregistered analyses on whichever dataset `DATASET` names, and default to the pilot data (`data/pilots/` and `analysis/derived/pilots/`) because the full sample has not been collected yet. Once it has, `make notebooks DATASET=<name>` renders all of them against it.

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

# Full run as in the paper: 20 groups with nucleus sampling (temperature 1.0, top-p 0.95, the script's default)
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 20

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
