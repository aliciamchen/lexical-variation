# Testing the roles of passive isolation and active social motivation in lexical variation using experimental microsocieties

This repository holds the experiment, the data pipeline and the analyses for a preregistered study of how linguistic conventions diverge between groups. Nine participants play a tangram reference game in three groups of three. In Phase 1 each group describes and identifies the same tangrams among themselves. In Phase 2 the groups are either kept apart (`refer_separated`), mixed so that listeners hear speakers from other groups (`refer_mixed`), mixed and rewarded for identifying whether a speaker came from their own group (`social_mixed`), or told about that reward before the game begins (`social_first`). The preregistration is a Stage 1 manuscript and is frozen; its pilot analyses reproduce from the data in this repository.

The pilot, four games from March 2026, one per condition, is committed in `data/pilots/`. The full sample, 120 started games collected in 31 Prolific sessions between 2026-09-22 and 2026-10-08, is not public yet: it will be released in the RefBank format for reference-game corpora once the preregistered exclusion review and classifier check are complete. Until then the full-sample notebooks can be read but run only on the pilot.

## Repository structure

```
experiment/        the Empirica game: React client, Node server, Playwright tests (see experiment/README.md)
analysis/          the pipeline scripts, the R helpers the notebooks share (analysis/R/), the Quarto notebooks, and the tests
analysis/derived/  derived metrics per dataset: embeddings, similarity tables, cached model fits (the pilot's are committed)
data/              one directory per dataset; data/pilots/README.md is the codebook
operations/        the Prolific tooling (payments, blocklist, tally) and procedures.md, the record of how a session was run
figures/           the figures the notebooks write, per dataset
writing/           Overleaf projects, one per manuscript (not committed; synced through Overleaf)
```

## Setup

Node 20 and [Empirica](https://empirica.ly/) run the experiment. Python 3.11 or later with [uv](https://docs.astral.sh/uv/), R 4.5 with renv, and [Quarto](https://quarto.org/) run the analyses.

```bash
curl -fsS https://install.empirica.dev | sh   # Empirica
cd experiment && npm install && cd ..          # the game and its Playwright tests
uv sync                                        # Python
Rscript -e 'renv::restore()'                   # R
```

The `rpy2` package needs R installed first, and the Cairo-based packages may need `brew install cairo pango` on macOS.

The analyses need no credentials. Running or deploying the experiment and the Prolific tooling read a `.env` file at the repository root, created with `cp .env.example .env` and filled in (the variables are documented in the example), and running the game locally needs `experiment/.empirica/empirica.toml`, created from `empirica.toml.example` with fresh random values. Both files are gitignored because they hold a hostname, an organization name and tokens. Contributors should also run `git config core.hooksPath .githooks`: the pre-commit hook refuses a commit that stages a participant identifier and runs the tests for whatever the commit touches. GitHub Actions runs the server unit tests and the data checks on the pilot on every push.

## Reproducing the pilot results

```bash
make pilot
```

This recomputes the derived metrics from the committed pilot tables into `analysis/derived/pilots/` and renders the two supplementary notebooks, `analysis/SI_pilot.qmd` and `analysis/llm_simulation/SI_llm_simulation.qmd`. The figures go to `figures/pilots/` and `figures/llm_plots/`, and every statistic is written as a `\newcommand` macro to `writing/preregistration/stats/`, which the preregistration manuscript reads with `\input`, so no number in the manuscript is typed by hand. The step that labels chat messages as referential or not with an LLM is not run, because its labels are committed in `messages_classified.csv`.

```bash
make test
```

This runs the data integrity suite on the processed tables of the active dataset, the Python unit tests for the preprocessing and derived-metric definitions, and the R tests for the analysis helpers. The integrity suite checks the tables against the experiment's design and server logic, rebuilds the utterances from the chat log, recomputes the similarity tables from the saved embeddings, and reconciles the processed tables with the raw ones.

## The data

Every dataset has the same layout, defined once in `analysis/dataset_paths.py` and mirrored in `analysis/config.R`:

| Path | Contents |
|---|---|
| `data/<name>/runs.txt` | The Empirica export timestamps the dataset is built from |
| `data/<name>/raw_anonymized/` | The raw Empirica tables, stacked across those exports, with identifying columns removed |
| `data/<name>/*.csv` | The analysis-ready tables: `games`, `players`, `trials`, `messages`, `speaker_utterances`, `speaker_utterances_filtered`, `social_guesses` and `dropouts` |
| `analysis/derived/<name>/` | The SBERT embeddings, the pairwise and block-by-block similarity tables in sentence-embedding and content-word (Jaccard) versions, and cached model fits |
| `figures/<name>/` | The figures the notebooks write |

The scripts take `--dataset <name>` and `make` takes `DATASET=<name>`; both default to `pilots`. The columns, and the optional input files that record exclusions and documented anomalies, are described in [`data/pilots/README.md`](data/pilots/README.md). Timestamps taken in a participant's browser are comparable only within that participant, because browser clocks are not synchronized; the codebook says which columns are on the server's clock.

The pipeline from an Empirica export to the processed tables is `make extract combine process test`, or `make all`, which also renders the notebooks:

1. `extract_run.py <zip>` unzips an export into `data/runs/<timestamp>/raw/`, removes the identifying columns, redacts Prolific-id-shaped tokens from every text field, and registers the export in `runs.txt`.
2. `combine_runs.py` stacks the registered exports, keeping the newest version of each record, drops the games listed in `exclude_games.txt`, and writes `raw_anonymized/`, `dropouts.csv` and `manifest.json`.
3. `process_data.py` runs `preprocessing.py`, which writes the analysis-ready tables; `filter_nonreferential.py`, which labels each speaker message as referential or not with Gemini on Vertex AI and rebuilds the utterances from the referential messages (labels are cached, so only unlabeled messages are sent, and `--skip-filter` uses the unfiltered utterances); and `compute_derived.py`, which writes the embeddings and similarity tables.
4. `make test` checks the result.

The raw exports under `experiment/data/` are not committed because they identify participants. `make smoke ZIP=<export>` runs the whole pipeline on one export in a throwaway dataset, so a bad export is caught before it is added to a real one.

## The full-sample analyses

The notebooks `analysis/00_data_overview.qmd` to `05_exit_survey.qmd` are the preregistered analyses. `make notebooks DATASET=full` renders them on the full sample; each writes its statistics to `writing/manuscript/stats/<notebook>.tex` for the article and its HTML to `_output/`. On a clone of this repository they run on the pilot, which exercises the code and gives no results, since one game per condition supports none, and a banner says so. The Bayes factors in `02_primary_analysis.qmd` refit three models with brms and take hours on the full sample; `BAYES_FACTORS=never make notebooks DATASET=full` skips them, and the fits are cached so that a render on unchanged data reuses them.

## Running the experiment

```bash
cd experiment
rm .empirica/local/tajriba.json   # a fresh database
empirica                          # admin at http://localhost:3000/admin, players at http://localhost:3000/
```

Create a batch in the admin panel, choose a treatment (two per condition, one per tangram set) and open nine player tabs. [`experiment/README.md`](experiment/README.md) covers the game's layout, deployment, error monitoring and the test suite. The sessions themselves, from a scheduling survey to approvals and payment, were run by hand on Prolific following [`operations/procedures.md`](operations/procedures.md); `make payments`, `make tally` and `make sync-blocklist` are the tooling around that work and need a Prolific token in `.env`.

## LLM simulation

`analysis/llm_simulation/` simulates groups of three Gemini agents playing Phase 1 of the game, the benchmark behind the preregistration's check for AI-assisted play. It needs a Google Cloud project with the Vertex AI API enabled and application-default credentials (`gcloud auth application-default login`); the project is read from `gcloud config`, `GOOGLE_CLOUD_PROJECT` or `--project`.

```bash
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 20    # as in the paper: nucleus sampling, temperature 1.0, top-p 0.95
uv run python analysis/llm_simulation/process_llm_results.py          # the JSON results to CSVs
quarto render analysis/llm_simulation/SI_llm_simulation.qmd
```

The results the preregistration reports are committed in `analysis/llm_simulation/llm_results_nucleus_20260323_012900/`, so the notebook renders without rerunning the simulation.

## Power analysis

`analysis/power_analysis/` justifies the sample size with data simulated from Boyce et al. (2023):

```bash
quarto render analysis/power_analysis/power_analysis_setup.Qmd   # simulate the data
quarto render analysis/power_analysis/power_analysis_plots.Qmd   # plot the power curves
```
