# Testing the roles of passive isolation and active social motivation in lexical variation using experimental microsocieties

This repository holds the experiment, the data pipeline and the analyses for a preregistered study of how linguistic conventions diverge between groups. Nine participants play a tangram reference game in three groups of three. In Phase 1 each group describes and identifies the same tangrams among themselves. In Phase 2 the groups are either kept apart (`refer_separated`), mixed so that listeners hear speakers from other groups (`refer_mixed`), mixed and rewarded for identifying whether a speaker came from their own group (`social_mixed`), or told about that reward before the game begins (`social_first`). The preregistration is a Stage 1 manuscript and is frozen.

The full sample, 120 started games collected in 31 Prolific sessions between 2026-09-22 and 2026-10-08, is not in the repository: the processed data exist only in the author's checkout, so the analyses can be read here but not run from a clone. The results themselves are in the repository: every estimates table, macro file and figure under `results/` is committed, so the numbers the article quotes can be read and traced to the commit that produced them. The pilot the preregistration reports on, four games from March 2026, and the LLM benchmark behind its check for AI-assisted play are at the git tag `pilot-archive`, from which the preregistration's supplementary analyses reproduce.

## How the pieces fit together

The work runs in one direction, from the game to the article, and each step has its own directory and its own `make` verb:

```
experiment/   the Empirica game, which writes an export zip per session
     │   make data        preprocessing/ (Python) turns the exports into one dataset
     ▼
data/full/    the dataset: hand-written inputs at the top, generated files one level down
     │   make test        the integrity suite checks the dataset against the design and the raw tables
     │   make models      models/ (R) fits one script per analysis and writes its estimates
     ▼
results/      the estimates tables, and from them
     │   make report      report/ (Python) writes the macros and draws the figures
     │   make sync        copies the macros and figures into the Overleaf project
     ▼
writing/manuscript/   the article reads the macros and the figures
```

```
experiment/        the Empirica game: React client, Node server, Playwright tests (see experiment/README.md)
preprocessing/     the data pipeline: extraction, combination, preprocessing, the message filter, the measures and the model inputs, with their tests
data/              one directory per dataset: the hand-written inputs at the top and the generated files one level down, in a directory per stage (raw, tables, classifier, measures, model_inputs, cache); data/README.md is the codebook
models/            the R models: config.R, the helpers in models/R/ with their tests, and one script per analysis in checks/, primary/ and secondary/
results/           the estimates tables the model scripts write, the macro files and the figures, with the hand-made figures (the Illustrator source, the schematic and condition diagrams, the avatar designs) in figures/manual/
report/            the Python side of the article: the two macro writers, the figure modules, the figure style and the bootstrap
writing/           Overleaf projects, one per manuscript (not committed; synced through Overleaf)
simulations/       the design-matched simulation behind the speaker random effect, and the power analysis
operations/        the Prolific tooling (payments, blocklist, tally) and procedures.md, the record of how a session was run
```

`make help` lists every target. The verbs are groups of finer steps: `make data` is `extract`, `combine` and `process`; `make models` builds whichever estimates tables are out of date; `make report` is `stats` (both macro writers) and `figures`. `make all` runs data, test, models and report in order.

## Setup

Node 20 and [Empirica](https://empirica.ly/) run the experiment. Python 3.11 or later with [uv](https://docs.astral.sh/uv/) and R 4.5 with renv run the analyses.

```bash
curl -fsS https://install.empirica.dev | sh   # Empirica
cd experiment && npm install && cd ..          # the game and its Playwright tests
uv sync                                        # Python
Rscript -e 'renv::restore()'                   # R
```

The analyses need no credentials. Running or deploying the experiment and the Prolific tooling read a `.env` file at the repository root, created with `cp .env.example .env` and filled in (the variables are documented in the example), and running the game locally needs `experiment/.empirica/empirica.toml`, created from `empirica.toml.example` with fresh random values. Both files are gitignored because they hold a hostname, an organization name and tokens. Contributors should also run `git config core.hooksPath .githooks`: the pre-commit hook refuses a commit that stages a participant identifier and runs the tests for whatever the commit touches. GitHub Actions runs the server unit tests and the Python unit tests on every push.

## Reproducing the results

```bash
make test
```

This runs the data integrity suite on the dataset (`full` unless `DATASET` names another), the Python unit tests for the preprocessing, the measures and the report layer, and the R tests for the model helpers. The integrity suite checks the tables against the experiment's design and server logic, rebuilds the utterances from the chat log, recomputes the similarity tables from the saved embeddings, and reconciles the processed tables with the raw ones. It needs the dataset, so on a clone without `data/full/` it stops with a message that says so, while the unit tests run anywhere.

The results reproduce from the processed tables alone. With a dataset's `tables/`, `classifier/` and `measures/` directories under `data/full/`,

```bash
make model-inputs models report
```

rebuilds the model inputs, fits every model and writes the macros and figures into `results/`, to be compared with the committed ones. Only the model fitting needs R: `make report` on its own, which draws the figures and writes the macros from the model inputs and the committed estimates, needs just the Python environment. `make measures` recomputes the similarity tables and description properties from the utterances first; it needs the sentence-transformer model and takes a few minutes. The steps before that, from the raw exports to the tables, need the exports themselves and Vertex AI credit for the message filter.

## The data

Every dataset has the same layout, defined once in `preprocessing/dataset_paths.py` and mirrored in `models/config.R`. The files at the top of the dataset directory are the ones somebody wrote by hand; everything the pipeline generates sits one level down, in a directory named for the step that writes it, and everything the models and the report layer generate goes to `results/`:

| Path | Written by | Contents |
|---|---|---|
| `data/<name>/` | by hand | `runs.txt`, the Empirica export timestamps the dataset is built from, and the exclusion and exception files described in the codebook |
| `data/<name>/raw/` | `make data` | The raw Empirica tables, stacked across those exports, with identifying columns removed, and the `manifest.json` that records what went into them |
| `data/<name>/tables/` | `make data` | The analysis-ready tables: `games`, `players`, `trials`, `messages`, `speaker_utterances`, `speaker_utterances_filtered`, `social_guesses` and `dropouts` |
| `data/<name>/classifier/` | `make data` | The message filter's label cache, the record of the model that wrote it, and the author's annotation check |
| `data/<name>/measures/` | `make data` | The measures computed from the descriptions: the SBERT embeddings, the pairwise and block-by-block similarity tables in sentence-embedding and content-word (Jaccard) versions, each speaker's Phase 1 to Phase 2 similarity, and the per-description properties |
| `data/<name>/model_inputs/` | `make data` | The aggregated tables the models are fit to |
| `data/<name>/cache/` | `make models` | Fitted objects kept between runs: the permutation results, the brms fits and the H4 models that later scripts reuse; never committed |
| `results/estimates/` | `make models` | One tidy estimates table per model script, with a `manifest.json` naming the script, the columns and the git commit that wrote each |
| `results/stats/` | `make report` | The six macro files the manuscript reads |
| `results/figures/` | `make report` | The figures, each with the table it plots beside it, and the hand-made figures in `manual/` |

The scripts take `--dataset <name>` and `make` takes `DATASET=<name>`; both default to `full`. A dataset other than `full` keeps its results inside its own directory, `data/<name>/results/`, so a trial run never touches the committed ones. The columns, and the optional input files that record exclusions and documented anomalies, are described in [`data/README.md`](data/README.md). Timestamps taken in a participant's browser are comparable only within that participant, because browser clocks are not synchronized; the codebook says which columns are on the server's clock.

In code, the layout supplies the paths, so none is typed:

```python
import pandas as pd
from preprocessing.dataset_paths import dataset_dirs

dirs = dataset_dirs("full")
trials = pd.read_csv(dirs.tables / "trials.csv", low_memory=False)
```

```r
source("models/config.R")   # the paths and constants of the active dataset
tables <- load_tables()     # the processed tables and the measures, as a named list
```

`make data` runs three steps:

1. `extract_run.py <zip>` unzips an export into `data/runs/<timestamp>/raw/`, removes the identifying columns, redacts Prolific-id-shaped tokens from every text field, and registers the export in `runs.txt`.
2. `combine_runs.py` stacks the registered exports, keeping the newest version of each record, drops the games listed in `exclude_games.txt`, and writes `raw/` with its `manifest.json` and `tables/dropouts.csv`.
3. `process_data.py` runs `preprocessing.py`, which writes the analysis-ready tables; `filter_nonreferential.py`, which labels each speaker message as referential or not with Gemini on Vertex AI and rebuilds the utterances from the referential messages (labels are cached, so only unlabeled messages are sent, and `--skip-filter` uses the unfiltered utterances); `compute_measures.py`, which writes the embeddings, the similarity tables and the description properties; and `build_model_inputs.py`, which aggregates them into the tables the models are fit to.

The raw exports under `experiment/data/` are not committed because they identify participants. `make smoke ZIP=<export>` runs the whole pipeline on one export in a throwaway dataset, so a bad export is caught before it is added to a real one.

## The analyses

The preregistered analyses are R scripts in `models/`, one per analysis, grouped as the preregistration groups them: `checks/` holds the convention-formation, dropout and survey checks, `primary/` the hypotheses H1 through H4 with their robustness reruns and Bayes factors, and `secondary/` the secondary analyses. Each script fits its models, prints their summaries, and writes what it estimated as a tidy table to `results/estimates/<family>/<name>.csv`, named after the script. A script that builds on another's estimates reads them from there rather than refitting: the game-level regressions of H1, H2 and H3a all read the per-game group-specificity estimates that `primary/group_specificity.R` writes. `make models` treats every estimates table as a Make target that depends on the data it reads, the shared R code in `models/R/` and the estimates it builds on, so it reruns only what changed. The Bayes factors are the slow step: `primary/bayes_factors.R` refits the models in brms and caches the fits, and `BAYES_FACTORS=never make models` skips it while leaving its previous estimates in place.

`make report` then formats the results. `report/inferential.py` turns the estimates tables into the macro files `checks.tex`, `primary.tex` and `secondary.tex`, and `report/descriptives.py` writes `overview.tex`, `exploratory.tex` and `survey.tex` from the processed tables and the per-game estimates. Every macro file carries the writer and the git commit in its header. `report/figures/` holds one module per figure, each writing its PDF and the table it plots side by side, and `uv run python -m report.figures <name>` draws one of them; `report/plot_style.py` is the one description of how the figures look, with a slide size and a type scale for talks, and `report/bootstrap.py` the one bootstrap, which resamples games. `make sync` copies the macro files and the figures, the hand-made ones included, into the article's Overleaf project. A run on any dataset other than `full` is marked in every output as not being results.

## Running the experiment

```bash
cd experiment
rm .empirica/local/tajriba.json   # a fresh database
empirica                          # admin at http://localhost:3000/admin, players at http://localhost:3000/
```

Create a batch in the admin panel, choose a treatment (two per condition, one per tangram set) and open nine player tabs. [`experiment/README.md`](experiment/README.md) covers the game's layout, deployment, error monitoring and the test suite. The sessions themselves, from a scheduling survey to approvals and payment, were run by hand on Prolific following [`operations/procedures.md`](operations/procedures.md); `make payments`, `make tally` and `make sync-blocklist` are the tooling around that work and need a Prolific token in `.env`.

## Power analysis

`simulations/power_analysis/` justifies the sample size with data simulated from Boyce et al. (2023), rendered with [Quarto](https://quarto.org/):

```bash
quarto render simulations/power_analysis/power_analysis_setup.Qmd   # simulate the data
quarto render simulations/power_analysis/power_analysis_plots.Qmd   # plot the power curves
```

The rendered documents go to `simulations/power_analysis/_output/`, which is not committed.
