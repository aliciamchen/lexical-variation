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
│   ├── pilots/               # Pilot dataset (committed); the full sample sits beside it, uncommitted until collection ends
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

The single `.env` file at the repository root is read only on your own machine: `empirica bundle` compiles the Sentry DSN into the client bundle and refuses to build a production bundle without it, and `operations/copy_tajriba.sh` uses the server hostname to pull backups. The Google Cloud project for the Gemini-based filter can also be set there, but the scripts fall back to your `gcloud` default project. Keep real hostnames and organization names in `.env`, never in committed files.

The Empirica admin password and the service token that the game server uses to talk to its database are in `experiment/.empirica/empirica.toml`, which is also gitignored because `empirica bundle` ships it to the production server. Create it from the template with fresh random values before running the experiment locally or building a bundle:

```bash
cp experiment/.empirica/empirica.toml.example experiment/.empirica/empirica.toml   # then replace both values
```

Finally, point git at the repository's pre-commit hook. It refuses any commit that stages a data file with a participant identifier in it, and it runs the unit tests that cover whatever the commit touches:

```bash
git config core.hooksPath .githooks
```

## Running the experiment

See [`experiment/README.md`](experiment/README.md) for full documentation on local development, production deployment, running sessions, copying data, error monitoring, and testing. The Prolific side of a session (the screening survey, the allowlist, reminders, publishing, approvals and payments) is done by hand on the Prolific website, and the step-by-step runbook is [`operations/procedures.md`](operations/procedures.md).

Two commands support that work. `make tally DATASET=full` counts the intact games in `data/<dataset>/games.csv` in each of the eight condition-by-tangram-set cells and marks the emptiest cell, which is the treatment the next session should run. It also reports progress against both halves of the preregistered stopping rule, which ends recruitment at whichever limit comes first: 20 intact nine-player games in every condition, or 120 games started in total. The cap counts every game that began, including those that lost a player or did not finish, and `tally` says so when either limit is reached. `make payments DATASET=full` lists what each Prolific study still owes (see [Payments](#payments)). Backups taken with `operations/copy_tajriba.sh` each land in their own `experiment/data/<timestamp>/empirica-export-<timestamp>.zip`, named by the export's timestamp, so every backup during a session is an export the pipeline can find; the loop carries on through a failed connection and stops only after three consecutive failures.

Participants reach the game from Prolific with their ID in the study link, and the identifier field is filled from it and locked so that ids cannot be mistyped. The last page of the exit survey keeps the completion code on screen (there is no Finish button to click past it), and reloading during the survey resumes at the first unanswered page. If a batch has to be stopped mid-game, the participants see an explanation, answer the exit survey, and receive the partial completion code with base pay prorated to their time plus the bonus earned so far. Sentry, which monitors client errors, receives no query strings (so no Prolific ids) and records session replays only for sessions that hit an error.

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
| `dropouts.csv` | One row per participant who reached the experiment but played no real game (quiz failure, lobby timeout, arrival after the games were full), with the batch, how Empirica ended the record, the exit reason, and the number of quiz attempts. This is what the attrition report counts |
| `speaker_utterances_filtered.source.json` | The sha256 and row count of the `messages.csv` that `speaker_utterances_filtered.csv` was built from. `compute_derived.py` refuses a filtered file whose record is missing or does not match, so a stale filtered file can never be analyzed in place of the current data |
| `participant_exclusions.csv`, `exclude_games.txt` | Optional inputs, absent for the pilot. `exclude_games.txt` lists the Empirica game ids of rehearsal or deploy-check games that ran on the production server (one per line, `#` comments), and `combine_runs.py` drops them and every row that belongs to them. `participant_exclusions.csv` lists `playerId,reason` for participants excluded after the fact; preprocessing drops their messages and sets `excluded` and `exclusionReason` on their own rows and on the rows of the listeners they described to, in `trials.csv` and `social_guesses.csv`, so every derived measure is recomputed without them |

Sessions from September 2026 onward also record response times, how long each
chat message took to compose, the device and viewport the participant played
on, and when they switched away from the tab or lost their connection. These
columns are empty in the pilot data, which predates the instrumentation, and
are described alongside the others in `data/pilots/README.md`. Timestamps taken
in the participant's browser are meaningful only relative to one another within
that participant, since browser clocks are not synchronized; the columns read
from the server are comparable across everyone, and the column descriptions say
which is which.

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

The filter step requires Vertex AI (see [LLM simulation](#llm-simulation)). Its labels are cached in `messages_classified.csv`, so only speaker messages that have not been labeled before are sent to the model; `uv run python analysis/filter_nonreferential.py classify --data-dir data/<name> --dry-run` prints how many messages would be sent and the estimated number of API calls without calling anything, and a real run asks for confirmation (or `--yes`) first. The pilot labels are committed, so the step can be skipped for the pilot with `make process-no-filter`. Run `make help` to see all available targets.

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
| `extract_run.py <zip>` | Empirica export zip in `experiment/data/` | `data/runs/{timestamp}/raw/`. Strips Prolific IDs and other PII from player.csv, redacts Prolific-id-shaped tokens that participants typed into any text field (a survey answer or a chat message), and registers the run in the dataset's `runs.txt`. |
| `combine_runs.py [--dataset NAME] [runs]` | `data/runs/*/raw/` for the runs in `data/<name>/runs.txt` | `data/<name>/raw_anonymized/` + `manifest.json` |
| `process_data.py [--dataset NAME]` | `data/<name>/raw_anonymized/` | `data/<name>/*.csv` + `analysis/derived/<name>/` |
| ↳ `preprocessing.py` | `data/<name>/raw_anonymized/` | `data/<name>/*.csv` |
| ↳ `filter_nonreferential.py` | `data/<name>/messages.csv` | `data/<name>/speaker_utterances_filtered.csv` (requires Vertex AI; `--skip-filter`) |
| ↳ `compute_derived.py` | `data/<name>/*.csv` | `analysis/derived/<name>/` (`--skip-derived`) |

The block-by-block similarity tables carry one row per pair of speakers who have both described a tangram by that block, and an `allGroupsPaired` flag marking the rows where every original group has two such speakers. Group specificity, the difference between within-group and between-group similarity, is only defined on the flagged rows, which is why the analyses that compute it keep those alone; the descriptive figure that plots the two similarities separately uses every row, so it can show the first block of each phase, where each group has described the tangram once and only between-group pairs exist.

Among the derived outputs, `pairwise_similarities_jaccard.csv` and `block_pairwise_similarities_jaccard.csv` repeat the sentence-embedding similarity tables pair for pair with the Jaccard overlap of the two descriptions' content words, which is the preregistered robustness check on the similarity measure; pairs where either description has no content words carry an empty similarity.

### Payments

`operations/payments.py` (run as `make payments DATASET=full`) works out what each Prolific study still owes. A session can span several Prolific studies and several Empirica batches, and each export is a cumulative snapshot of the server, so neither one export nor one batch lines up with the people a given study has to pay. The step therefore reads every export listed in the dataset's `runs.txt`, takes each player placed in a game, identified by the Prolific ID they entered on the identifier screen (filled in from the study link when it carries one), and asks Prolific, with read-only requests only, for the submissions of every study recorded on any player. Each player is paid in the study where their Prolific ID has a submission, matched by completion code and then by time. That covers participants who reached the game through a link sent by message, because Prolific had not yet shown them the study, and entered the code on the study afterwards. A player who never submitted the game study at all is paid the base pay and bonus as a bonus on their other recent submission, normally the session's scheduling survey. The submissions carry each one's status and the bonuses already paid on it, and they also identify the lobby-timeout participants by the completion code their exit screen gave them, since no game of theirs ever started. A lobby timeout who returned the study without entering that code is found from the export instead, where their record shows they waited in the lobby for a game that never started.

The output is written to `data/payments/<dataset>/`, which is gitignored because it contains Prolific IDs. There is one folder per study, named by the study's creation date and internal name, holding two paste-ready files for Prolific's bulk bonus form (`participant_id,amount`, no header, one line per person): `1_main.csv` with the bonuses, partial pay and lobby pay, and `2_overtime.csv`, which are pasted in that order. Beside them, `status.csv` lists everyone with the amount owed, the amount already paid, and the reason a row is not ready to pay, and `repeats.csv` lists anyone who took part in more than one session; the step prints a warning if anyone was placed in two games, which the eligibility filters should prevent. The step also writes `blocklist_ids.txt`, a plain list of Prolific IDs to paste into the next scheduling survey's custom blocklist. It holds everyone who started a game but is not already excluded through an earlier game study, which means removed players, whose submissions are returned, and players who never submitted the game study, plus the participants who failed the quiz, since they have read the instructions; lobby timeouts never started the task and stay eligible. The directory is rewritten on every run, so running it again after paying on the website shows those people as settled. Finishers are owed their bonus, plus the base reward when they returned their submission instead of submitting the completion code (a returned submission cannot be approved), removed players their partial pay, and lobby timeouts the lobby payment. A removal for inactivity forfeits the bonus; when the researcher decides a removal was not the player's doing (a screen that stopped updating, for example), a line in `data/<dataset>/payment_adjustments.csv` (`playerId,adjustment,reason`, with the Empirica player id and `restore_bonus`) adds the earned bonus back on every later run; partial and lobby pay are paid as a bonus on a returned or awaiting-review submission, and an approved submission, which has already received the full base reward, is owed only whatever part of its amount exceeds that base. Finishers whose time on the study was longer than 60 minutes (the longer of Prolific's recorded time and the game's own record, from the identifier screen to the exit survey), the top of the "45 to 60 minutes" the instructions promise, are also owed overtime for the minutes beyond it, paid at the study's advertised rate and written to the separate `2_overtime.csv`. Games ran 42 to 49 minutes with up to three running at once and 52 to 74 minutes with four or five, so participants in the busy sessions spent well over the time Prolific told them to expect. The step never pays anyone itself. It needs `PROLIFIC_TOKEN` in `.env`, and `--offline` lists the payees by study without contacting Prolific.

### Processing new data

Raw Empirica exports (`.zip` files) are in `experiment/data/<timestamp>/` via `empirica export` or the backup script. They are not committed because they contain identifiable participant data, and they are never edited: each folder is the record of what the server held at that moment, and everything downstream is regenerated from it. The full sample's processed data is not committed yet either; it will be released after collection ends, converted to the RefBank format for reference-game corpora. Before adding an export to a dataset, run it through a throwaway dataset first:

```bash
make smoke ZIP=experiment/data/<run>/empirica-export-<run>.zip
```

This runs the whole pipeline on that one export in a dataset named `smoke` (without the LLM filter) and then the integrity suite, so a bad export is caught before it touches a real dataset. The block-count checks fail for games played in `TEST_MODE`, and the bonus checks fail for exports from before the production pay rate; anything else that fails is a problem with the export. The `smoke` directories are gitignored and are cleared at the start of the next smoke run.

`extract_run.py` registers each export's timestamp in the dataset's `runs.txt` (pass `--no-register` to look at an export without adding it), then the rest of the pipeline follows:

```bash
make all                 # pilot: extract zips → combine → process → test → render notebooks
make all DATASET=full    # the same for a dataset named full (data/full/runs.txt)
```

Or step by step:

```bash
# 1. Extract each zip (unzip, anonymize, register the run)
uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip
uv run python analysis/extract_run.py experiment/data/20260301_214147/empirica-export-20260301_214147.zip

# 2. Combine the runs listed in data/pilots/runs.txt into data/pilots/raw_anonymized/
uv run python analysis/combine_runs.py --dataset pilots

# 3. Run the pipeline (preprocess → filter → derived metrics)
uv run python analysis/process_data.py --dataset pilots
```

For the full sample, `make payments DATASET=full` then shows what each Prolific study still owes (see [Payments](#payments)).

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
| `01_outcome_neutral.qmd` | Convention-formation checks for interpreting H1/H2 |
| `02_primary_analysis.qmd` | Primary analyses (H1 through H4) |
| `03_secondary_analysis.qmd` | Secondary analyses |
| `04_exploratory.qmd` | Exploratory analyses |
| `05_exit_survey.qmd` | Exit survey responses |

Rendering all six on the full sample takes many hours, because the Bayes factors refit three models in brms. `BAYES_FACTORS=never make notebooks DATASET=<name>` skips them for an interim look, and the brms fits are cached so that a render on unchanged data reuses them.

The primary analyses evaluate each prespecified prediction separately with a
two-tailed, unadjusted test at α = 0.05 and require the predicted direction for
support. All results are reported, and this policy does not provide family-wise
error control. H3a, H3b, and the three H3c description-property predictions have
separate interpretations, without an omnibus H3 support decision.

The convention-formation trend checks pool the three conditions with the
shared Phase 1 procedure, excluding `social_first`, while descriptive plots
show each condition and variation across games. These checks inform whether
H1/H2 can be interpreted as convergence or preservation of established
conventions; they do not block reporting the primary contrasts or testing
H3/H4. There is no study-level pass/fail threshold. The historical pilot
notebook retains its original four-condition analyses and does not define
the full-sample policy.

Both accuracy outcomes are proportions of eligible listener response
opportunities rather than of submitted answers. An opportunity is an active
listener assigned to the task on a played trial whose group's speaker sent a
message; a correct answer received by the server's scoring cutoff counts as a
success, and an incorrect answer, an ordinary timeout, and a late arrival all
count as failures. Trials the listener could not have answered leave the
denominator instead of counting against them, so `social_guesses.csv` holds
one row per opportunity, with an empty guess where nobody answered. Lateness
is recorded separately for each outcome, because a tangram selection and a
social guess can arrive at different times. Failures that were documented as
technical are listed in `data/<dataset>/technical_exclusions.csv` with a
reason and treated as missing. The pilot supplement uses the same rule.

The per-game group-specificity model has random intercepts for the tangram
and for the unordered pair of speakers whose descriptions are compared, as the
preregistration states, with no separate speaker term. The pair intercept is
what keeps the standard errors honest: the design-matched simulations in
`analysis/simulate_mm_speaker.R` show that without it the 95% intervals cover
the true value only about 86% of the time when two speakers' descriptions
resemble each other beyond their individual tendencies. Those simulations
also compare structures that add a speaker effect shared across both pair
positions, which `analysis/R/multimembership.R` fits through lme4's modular
interface; they remain available for comparison but are not the preregistered
model.

H3b tests two separately reported contrasts: the difference in average linear
change over Phase 1 blocks 2–6 and the difference in alignment at block 3,
the end of the first scheduled speaker cycle. The analysis averages overlapping
description pairs within each group, tangram, and block. The longitudinal
model includes block slopes for group and tangram; a separate block-3-only
model includes their random intercepts. Neither includes a game term. The
implementation is in `analysis/R/convergence.R`; its tests verify that later
blocks cannot affect the early-alignment estimate. Each model requires at
least two games per condition in its analysis subset, so the current pilot
provides descriptive trajectories only. H3b does not use Bayes factors.

For H1, H2, and H3a, `analysis/R/bayes_factors.R` parameterizes each tested
condition difference directly, placing the preregistered Cauchy prior on
that difference in outcome SD units. The full and null models retain the
same nuisance parameters and priors, including when the tested conditions
have unequal sample sizes.

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
