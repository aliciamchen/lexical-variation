# Testing the roles of passive isolation and active social motivation in lexical variation using experimental microsocieties

This repository holds the experiment, the data pipeline and the analyses for a preregistered study of how linguistic conventions diverge between groups. Nine participants play a tangram reference game in three groups of three. In Phase 1 each group describes and identifies the same tangrams among themselves. In Phase 2 the groups are either kept apart (`refer_separated`), mixed so that listeners hear speakers from other groups (`refer_mixed`), mixed and rewarded for identifying whether a speaker came from their own group (`social_mixed`), or told about that reward before the game begins (`social_first`). The preregistration is a Stage 1 manuscript and is frozen.

The full sample, 120 started games collected in 31 Prolific sessions between 2026-09-22 and 2026-10-08, is not public yet: it will be released in the RefBank format for reference-game corpora. Until then the processed data and the derived tables exist only in the author's checkout, so the analyses can be read here but not run from a clone. The pilot the preregistration reports on, four games from March 2026, and the LLM benchmark behind its check for AI-assisted play were retired from the working tree; both remain at the git tag `pilot-archive`, from which the preregistration's supplementary analyses reproduce.

## Repository structure

```
experiment/        the Empirica game: React client, Node server, Playwright tests (see experiment/README.md)
pipeline/          the data pipeline: extraction, combination, preprocessing, the message filter, the derived metrics and the model-input frames, with their tests
analysis/          the R side: config.R, the helpers in analysis/R/ with their tests, and the three Quarto notebooks that fit the preregistered models
paper/             the Python side of the article: the descriptive macros, the figure style and the macro writer
simulations/       the design-matched simulation behind the speaker random effect, and the power analysis
analysis/derived/  derived metrics per dataset: embeddings, similarity tables, frames and cached model fits
analysis/results/  the model estimates the notebooks write for the figures and the descriptive macros
data/              one directory per dataset; data/README.md is the codebook
operations/        the Prolific tooling (payments, blocklist, tally) and procedures.md, the record of how a session was run
figures/           the article's figures per dataset, and figures/manual/ for the hand-made ones (the Illustrator source, the schematic and condition diagrams, the avatar designs)
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

The analyses need no credentials. Running or deploying the experiment and the Prolific tooling read a `.env` file at the repository root, created with `cp .env.example .env` and filled in (the variables are documented in the example), and running the game locally needs `experiment/.empirica/empirica.toml`, created from `empirica.toml.example` with fresh random values. Both files are gitignored because they hold a hostname, an organization name and tokens. Contributors should also run `git config core.hooksPath .githooks`: the pre-commit hook refuses a commit that stages a participant identifier and runs the tests for whatever the commit touches. GitHub Actions runs the server unit tests and the preprocessing unit tests on every push.

## Reproducing the results

```bash
make test
```

This runs the data integrity suite on the processed tables of the active dataset (`full` unless `DATASET` names another), the Python unit tests for the preprocessing and derived-metric definitions, and the R tests for the analysis helpers. The integrity suite checks the tables against the experiment's design and server logic, rebuilds the utterances from the chat log, recomputes the similarity tables from the saved embeddings, and reconciles the processed tables with the raw ones. It needs the processed dataset, so on a clone without `data/full/` it stops with a message that says so, while the unit tests run anywhere.

## The data

Every dataset has the same layout, defined once in `pipeline/dataset_paths.py` and mirrored in `analysis/config.R`:

| Path | Contents |
|---|---|
| `data/<name>/runs.txt` | The Empirica export timestamps the dataset is built from |
| `data/<name>/raw_anonymized/` | The raw Empirica tables, stacked across those exports, with identifying columns removed |
| `data/<name>/*.csv` | The analysis-ready tables: `games`, `players`, `trials`, `messages`, `speaker_utterances`, `speaker_utterances_filtered`, `social_guesses` and `dropouts` |
| `analysis/derived/<name>/` | The SBERT embeddings, the pairwise and block-by-block similarity tables in sentence-embedding and content-word (Jaccard) versions, and cached model fits |
| `figures/<name>/` | The figures |

The scripts take `--dataset <name>` and `make` takes `DATASET=<name>`; both default to `full`. The columns, and the optional input files that record exclusions and documented anomalies, are described in [`data/README.md`](data/README.md). Timestamps taken in a participant's browser are comparable only within that participant, because browser clocks are not synchronized; the codebook says which columns are on the server's clock.

The pipeline from an Empirica export to the processed tables is `make extract combine process test`, or `make all`, which also renders the notebooks:

1. `extract_run.py <zip>` unzips an export into `data/runs/<timestamp>/raw/`, removes the identifying columns, redacts Prolific-id-shaped tokens from every text field, and registers the export in `runs.txt`.
2. `combine_runs.py` stacks the registered exports, keeping the newest version of each record, drops the games listed in `exclude_games.txt`, and writes `raw_anonymized/`, `dropouts.csv` and `manifest.json`.
3. `process_data.py` runs `preprocessing.py`, which writes the analysis-ready tables; `filter_nonreferential.py`, which labels each speaker message as referential or not with Gemini on Vertex AI and rebuilds the utterances from the referential messages (labels are cached, so only unlabeled messages are sent, and `--skip-filter` uses the unfiltered utterances); `compute_derived.py`, which writes the embeddings and similarity tables; and `build_frames.py`, which aggregates them into the tables the models are fit to.
4. `make test` checks the result.

The raw exports under `experiment/data/` are not committed because they identify participants. `make smoke ZIP=<export>` runs the whole pipeline on one export in a throwaway dataset, so a bad export is caught before it is added to a real one.

## The full-sample analyses

The notebooks `analysis/checks.qmd`, `primary.qmd` and `secondary.qmd` are the preregistered analyses: the convention-formation, dropout and survey checks, the primary hypotheses and the secondary analyses. `make notebooks` renders them on the full sample; each writes its statistics to `writing/manuscript/stats/` as `\newcommand` macros for the article and its HTML to `_output/`, and `primary.qmd` writes its per-game estimates to `analysis/results/full/`. `make descriptives` then writes the descriptive macros, the data overview, the exploratory summaries and the exit survey, from the processed tables and those estimates with `paper/descriptives.py`. A render on any other dataset is marked with a warning banner, because its numbers are not results. The Bayes factors in `primary.qmd` refit three models with brms, which took about twenty minutes on the full sample; `BAYES_FACTORS=never make notebooks` skips them, and the fits are cached so that a render on unchanged data reuses them.

## Running the experiment

```bash
cd experiment
rm .empirica/local/tajriba.json   # a fresh database
empirica                          # admin at http://localhost:3000/admin, players at http://localhost:3000/
```

Create a batch in the admin panel, choose a treatment (two per condition, one per tangram set) and open nine player tabs. [`experiment/README.md`](experiment/README.md) covers the game's layout, deployment, error monitoring and the test suite. The sessions themselves, from a scheduling survey to approvals and payment, were run by hand on Prolific following [`operations/procedures.md`](operations/procedures.md); `make payments`, `make tally` and `make sync-blocklist` are the tooling around that work and need a Prolific token in `.env`.

## Power analysis

`simulations/power_analysis/` justifies the sample size with data simulated from Boyce et al. (2023):

```bash
quarto render simulations/power_analysis/power_analysis_setup.Qmd   # simulate the data
quarto render simulations/power_analysis/power_analysis_plots.Qmd   # plot the power curves
```
