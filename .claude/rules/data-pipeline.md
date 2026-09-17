---
paths:
  - "analysis/**"
  - "data/**"
  - "experiment/data/**"
  - "operations/copy_tajriba.sh"
---

# Data and analysis pipeline

## Datasets

The pipeline is keyed by a dataset name. The pilot sessions are the dataset `pilots`; the full sample will be a second dataset beside it (suggested name `full`), never an edit of the pilot paths. The layout is defined once in `analysis/dataset_paths.py` (Python scripts) and mirrored in `analysis/config.R` (`use_dataset()`, for the notebooks); keep the two in sync. The active dataset is `--dataset` on a script, else the `DATASET` environment variable, else `pilots`. `make` exports `DATASET` to every step, so `make all DATASET=full` runs the whole pipeline on the full sample.

| Directory | Contents | Committed? |
|-----------|----------|------------|
| `experiment/data/<timestamp>/` | Raw Empirica export zips from `operations/copy_tajriba.sh` | No |
| `data/runs/<timestamp>/` | Per-run extracts (raw/, bonuses.csv), shared across datasets | No (gitignored) |
| `data/<name>/runs.txt` | The export timestamps combined into the dataset, one per line | Yes |
| `data/<name>/exclude_games.txt` | Optional input: Empirica game ids of test and rehearsal games to drop at the combine step (one per line, `#` comments) | Yes |
| `data/<name>/raw_anonymized/` | Anonymized raw Empirica CSVs stacked across those runs | Yes |
| `data/<name>/*.csv` | Preprocessed analysis-ready CSVs (games, players, trials, messages, speaker_utterances, social_guesses) | Yes |
| `data/<name>/manifest.json` | Provenance: which runs were combined, which games were filtered or excluded, how many dropout records | Yes |
| `data/<name>/dropouts.csv` | Written by `combine_runs.py`: one row per player record with no real game (`playerId,batchId,ended,exitReason,quizAttempts`), for the attrition report | Yes |
| `data/<name>/participant_exclusions.csv` | Optional input: `playerId,reason` for participants excluded after the fact; preprocessing drops their messages and flags `excluded`/`exclusionReason` on trials.csv and social_guesses.csv | Yes |
| `data/<name>/speaker_utterances_filtered.source.json` | Sidecar written by `filter_nonreferential.py apply`: the sha256 and row count of the `messages.csv` the filtered utterances were built from | Yes |
| `data/smoke/`, `analysis/derived/smoke/` | Throwaway dataset written by `make smoke ZIP=<zip>` | No (delete after use) |
| `analysis/derived/<name>/` | Computed outputs from `compute_derived.py`: embeddings, SBERT similarities, the same pairs scored by content-word Jaccard (`pairwise_similarities_jaccard.csv`, `block_pairwise_similarities_jaccard.csv`), UMAP, and cached model fits | Yes |
| `figures/<name>/` | Notebook figures (`figures/pilots/` holds the SI figures from `SI_pilot.qmd`) | Yes |
| `figures/llm_plots/` | SI PDF figures from `SI_llm_simulation.qmd` | Yes |

Cached fits are keyed to their inputs: `group_specificity.R` stores a hash of the pairwise data next to `gs_results_<speaker structure>.rds` and recomputes when it differs, and `bayes_factors.R` names each fit by a hash of data and formula. The speaker structure is in both the hash and the filename, so the full-sample notebooks and `SI_pilot.qmd` keep separate caches instead of overwriting each other's permutation run on every render. A stale cache can therefore not be reused silently, but recomputing the permutation test takes several minutes. The brms fits under `analysis/derived/<name>/bayes_factors/` are gitignored (tens of megabytes, reproducible); the group-specificity RDS files are committed.

## Data

- Live data: `experiment/.empirica/local/tajriba.json`
  - Export to CSVs by running `empirica export`
- Backup from production server:
  ```bash
  bash operations/copy_tajriba.sh            # loop every 5 minutes (default)
  bash operations/copy_tajriba.sh --once     # single backup and exit
  bash operations/copy_tajriba.sh --help     # show usage
  ```
  The script SSHs into the production server (set via `EMPIRICA_SERVER` in `.env`), runs `empirica export` in `~/empirica` to produce a CSV zip, then copies it locally into `experiment/data/<timestamp>/`. Safe to run while the experiment is live. Exits automatically after 3 consecutive failures.

## Pipeline scripts

Three scripts, run in order (`make extract combine process` does the same for the active dataset):

```bash
# 1. Extract each Empirica export zip (unzip, anonymize, extract bonuses)
uv run python analysis/extract_run.py <zip>                    → data/runs/{timestamp}/raw/

# 2. Combine the runs listed in data/<name>/runs.txt (stack raw CSVs, filter failed games)
uv run python analysis/combine_runs.py --dataset <name>        → data/<name>/raw_anonymized/

# 3. Run the analysis pipeline (preprocess → filter → derived metrics)
uv run python analysis/process_data.py --dataset <name>        → data/<name>/, analysis/derived/<name>/
```

`combine_runs.py` writes `data/<name>/dropouts.csv` from the player records that never played a real game (quiz failures, lobby timeouts, arrivals after the games were full), and removes from `raw_anonymized/player.csv` any record of a real game that never started; `preprocessing.py` honors `data/<name>/participant_exclusions.csv` (`playerId,reason`, reason required, unknown ids refused): excluded players' messages leave `messages.csv` and `speaker_utterances.csv`, so every derived measure is computed without them, and `excluded`/`exclusionReason` are set on their own rows and on the rows of listeners they spoke to, while `responseOpportunity` is left as computed. `combine_runs.py` also honors `data/<name>/exclude_games.txt` (game ids of rehearsal or deploy-check games that ran on the production server; `#` comments allowed): the listed games and every dependent row are dropped, the count is printed, and the ids go into `manifest.json` under `excluded_games`. `extract_run.py --no-register` extracts a zip without adding it to `runs.txt`; its options (`--dataset`, `--batch`, `--all-batches`, `--no-register`) may come in any order around the zip path, and `list`, `bonuses`, and `early-ended` are subcommands. Positional runs given to `combine_runs.py` for the frozen `pilots` dataset must be exactly the runs in `data/pilots/runs.txt` unless `--allow-pilot` is passed (`dataset_paths.FROZEN_DATASET` names the frozen dataset for both scripts). `preprocessing.py` reports, once per column, how many JSON values of the export it could not parse and treated as missing; silence means every value parsed.

Step 3 runs these sub-steps in order:

| Step | Script | Inputs → Outputs |
|------|--------|------------------|
| Preprocess | `preprocessing.py` | `data/<name>/raw_anonymized/` → `data/<name>/*.csv` |
| Filter | `filter_nonreferential.py` | `data/<name>/messages.csv` → `messages_classified.csv` (the label cache) → `speaker_utterances_filtered.csv` + `.source.json` (requires Vertex AI for new messages; `--skip-filter`) |
| Derived | `compute_derived.py` | `data/<name>/*.csv` → `analysis/derived/<name>/`: the SBERT tables plus `pairwise_similarities_jaccard.csv` and `block_pairwise_similarities_jaccard.csv`, which have the rows of `pairwise_similarities.csv` and `block_pairwise_similarities.csv` in the same order with `similarity` replaced by the Jaccard overlap of the two descriptions' content-word sets (NaN where either side has none; the analysis omits those pairs and reports coverage) (`--skip-derived`) |

Quarto notebooks and animations are run separately (see below).

**The classifier's labels are cached.** `filter_nonreferential.py classify` treats `messages_classified.csv` as a cache keyed on (`gameId`, `roundId`, `senderId`, `timestamp`, `text`): only speaker messages of the current `messages.csv` without a cached label are sent, so reprocessing that leaves messages unchanged costs nothing. It prints the number of messages and the estimated API calls (messages / batch size of 30) before any call and proceeds only with `--yes` or an interactive yes; `--dry-run` stops at the estimate (`uv run python analysis/filter_nonreferential.py classify --data-dir data/<name> --dry-run`). Labels obtained before a failed batch are written back, so a rerun resumes. `MODEL_ID` in the script (`gemini-2.0-flash`, which produced the pilot labels) is the default of `--model`. `validate` reads `data/<name>/human_labels.csv` by default, the author's annotation of `annotation_sample.csv` (from `sample`), and refuses a file with empty labels. The utterances themselves are assembled by `preprocessing.assemble_speaker_utterances()` for both the filtered and the unfiltered file.

**Filtered utterances are tied to `messages.csv` by a sidecar.** `apply` writes `speaker_utterances_filtered.source.json` (sha256 and row count of the `messages.csv` it read; the labels in `messages_classified.csv` are joined onto the current `messages.csv` by message key, and an unlabeled speaker message is an error that says to rerun `classify`). `compute_derived.py` refuses `speaker_utterances_filtered.csv` when the sidecar is missing or stale ("filtered utterances are stale; rerun the filter or pass --utterances-file speaker_utterances.csv"); `process_data.py --skip-filter` falls back to `speaker_utterances.csv` with a loud warning instead; and `preprocessing.py` deletes a filtered file whose sidecar no longer matches when it rewrites `messages.csv`, printing what it deleted. `dataset_paths.filtered_utterances_status()` is the one check all three use. Never hand-copy a filtered file between datasets.

**Smoke-testing an export.** `make smoke ZIP=experiment/data/<run>/empirica-export-<run>.zip` runs extract → combine → `process_data.py --skip-filter` → the integrity suite in a throwaway dataset `smoke` (`data/smoke/`, `analysis/derived/smoke/`; delete both afterwards, they are not for committing). The block-count checks are expected to fail for TEST_MODE games. `make extract` resolves each run's zip as `experiment/data/<run>/empirica-export-<run>.zip` or, failing that, `experiment/data/*/empirica-export-<run>.zip`, and aborts naming the run when neither exists.

**Other scripts** (not pipeline steps):

| Script | Purpose |
|--------|---------|
| `dataset_paths.py` | Dataset layout and the `--dataset` / `DATASET` resolution shared by the Python scripts and tests |
| `config.R` | The one file a notebook sources: dataset paths (`use_dataset()`), writing-project paths, design constants, palettes, ggplot theme, and it sources every helper in `analysis/R/` |
| `R/prepare.R` | `load_tables()` and the shared data preparation (`phase1_utterances()`, `listener_trials()`, `attach_speaker()`, `social_guess_trials()`, `final_phase1_properties()`, ...): the recodes every notebook used to repeat. Also the response-opportunity denominator: `code_accuracy()`, `technical_exclusions()`, `response_opportunity_summary()`, `late_arrival_summary()`, and the `denominator` argument that pins the pilot SI to the earlier coding |
| `R/group_specificity.R` | Per-game group-specificity fits (`game_specificity_table()`, `gs_wide()`, optional covariates) and the seeded permutation test with a hash-keyed RDS cache in `analysis/derived/<name>/`. `speaker_structure` picks the random-effects structure: `"multimembership_pair"` (the preregistered default: a shared speaker effect plus an intercept for the unordered pair), `"multimembership"` (speaker only), or `"separate"` (the earlier per-pair-position structure, which only `SI_pilot.qmd` asks for). The structure is part of both the cache key and the cache filename. |
| `R/multimembership.R` | The shared multiple-membership speaker intercept: `speaker_pair_weights()` builds the 1/2-weighted membership matrix and `lmer_multimember()` fits it by REML through lme4's modular interface, replacing one block of `Zt`. `fit_group_specificity_mm()` is the per-game wrapper. |
| `R/mixed_models.R` | `fit_progressively()`: the preregistered random-effects simplification (maximal model, then drop correlations, then slopes by smallest variance); `simplification_log()` and `random_effects_structure()` report what was fit |
| `R/contrasts.R` | `fit_h12_wls()` (the H1/H2 weighted regression and planned contrasts), `pairwise_weights()`, `contrast_table()`, and `robustness_rerun()` for the subset-of-games checks |
| `R/convergence.R` | `fit_h3b()` fits the categorical-block model to group--tangram--block means and tests social-first minus social-mixed at Phase 1 block 3; the linear slope contrast is secondary. Game and nested group random effects remain in the simplification procedure. |
| `R/reshuffle.R` | `reshuffle_health()`: per-game summary of what the Phase 2 reshuffle produced (roster at the first and last round, trios versus pairs, share of trios with exactly one in-group listener, speaker reassignments), reported in `00_data_overview.qmd` |
| `R/bayes_factors.R` | brms/bridgesampling Bayes factors for non-significant planned contrasts; `maybe_bayes_factor()` applies the `BAYES_FACTORS=auto\|always\|never` decision; packages load on first use |
| `R/effects.R` | `report_effect_sizes()`, `cohens_d_games()`, `fmt_pval()` |
| `R/attrition.R` | `player_attrition()`, `game_status()`, `complete_games()`, and the differential-dropout tests reported in `00_data_overview.qmd` |
| `R/survey.R` | `exit_survey_responses()`, `has_field()`, `felt_human_flags()`, `likert_by_condition()` for `05_exit_survey.qmd` (handles the pilot's pre-revamp fields) |
| `R/stats_tex.R` | `write_stats_tex()` / `write_stats_lines()`: statistics as `\newcommand` macros with letters-only name checks |
| `R/plots.R` | Condition and group scales, Phase 2 layers, `save_fig()` into the dataset's figures directory |
| `tests/` | Plain `stopifnot` tests of the R helpers on simulated data, one file per helper (`Rscript analysis/tests/run_all.R`, also run by `make test` and the pre-commit hook) |
| `plot_style.py` | Shared Python plotting constants (imported, not run directly) |
| `test_data_integrity.py` | Pytest validation of `data/<name>/` CSV structure for the active dataset |
| `test_compute_derived.py` | Pytest unit tests for the derived-metric definitions (latest-utterance selection, trajectory start rule, lexical uniqueness, the Jaccard tables lining up with the SBERT ones, refusal of a stale filtered file) |
| `test_preprocessing.py` | Pytest unit tests for the preprocessing rules and the pipeline's guards: `flag_length_increase` (the AI-use trigger in `players.csv`), utterance assembly (one definition for both utterance files, NaN keys refused), `build_filtered_utterances` (rounds with no referential message are dropped, not emptied), the response-opportunity columns, `activeGroups`/`activeGroupsMin`, the server network columns, participant and game exclusions, dropouts, the filtered-utterance sidecar, the classifier's label cache and human-label checks, the frozen-pilot guard, and `extract_run.py`'s command line |
| `simulate_mm_speaker.R` | Design-matched simulations for the multiple-membership speaker intercept: convergence, pair-ordering invariance, interval calibration, and the inverse-variance weights in the game-level regression, under incomplete endpoint coverage and omitted pair-level dependence. Writes `analysis/derived/simulations/mm_speaker.rds` |

## Processing new data

Raw Empirica exports land in `experiment/data/` via `empirica export` or the backup script. Each export is a cumulative snapshot of one server; `combine_runs.py` unions the registered exports on record id and keeps the newest version of each record, so overlapping exports are safe to list.

```bash
# 1. Extract each zip
uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip

# 2. Combine (extract_run.py registered the timestamp in data/<name>/runs.txt already)
uv run python analysis/combine_runs.py --dataset pilots

# 3. Run the pipeline (preprocess → filter → derived metrics)
uv run python analysis/process_data.py --dataset pilots                  # full pipeline
uv run python analysis/process_data.py --dataset pilots --skip-filter    # if no Vertex AI

# 4. Validate and render (separate steps)
make test DATASET=pilots
make notebooks DATASET=pilots
```

Starting the full sample: `mkdir data/full`, write its `runs.txt`, then the same commands with `--dataset full` (or `make all DATASET=full`). The integrity suite applies the production bonus rate to every dataset other than `pilots`.

## Browsing runs

```bash
uv run python analysis/extract_run.py list                               # list extracted runs
uv run python analysis/extract_run.py bonuses                            # print latest bonuses
uv run python analysis/extract_run.py bonuses --run 20260225_210047      # specific run
```

## Running individual scripts standalone

```bash
uv run python analysis/compute_derived.py data/pilots/ --output analysis/derived/pilots/
uv run python analysis/animate_umap.py --data-dir data/pilots/ --umap-dir analysis/derived/pilots/ --output-dir figures/pilots/
uv run pytest analysis/test_data_integrity.py analysis/test_compute_derived.py analysis/test_preprocessing.py -v
DATASET=full uv run pytest analysis/test_data_integrity.py -v
```

## Quarto notebooks

All notebooks source `config.R`, which sets `data_dir`, `derived_dir`, and `figures_dir` for the active dataset (`DATASET`, default `pilots`) and sources the helpers in `analysis/R/`; `list2env(load_tables(), envir = globalenv())` then loads every data and derived table as a variable. A notebook tied to one dataset calls `use_dataset("<name>")` before loading; `SI_pilot.qmd` does this so it always documents the pilot. Data preparation goes through the functions in `R/prepare.R` rather than inline recodes, and the per-game group-specificity estimates come from `game_specificity_table()` so every notebook reports the same numbers.

**For the pilot data** (these feed the preregistration manuscript) -- run after the pipeline:

| Notebook | Generates |
|----------|-----------|
| `SI_pilot.qmd` | Pilot data analyses → `figures/pilots/` + `writing/preregistration/stats/pilot.tex` |
| `llm_simulation/SI_llm_simulation.qmd` | LLM benchmark → `figures/llm_plots/` + `writing/preregistration/stats/llm.tex` |

**For the full sample** (the preregistered analyses; `make notebooks DATASET=<name>` renders all of them, and they default to the pilot data until the full sample exists):

| Notebook | Purpose |
|----------|---------|
| `00_data_overview.qmd` | Data overview |
| `01_outcome_neutral.qmd` | Convention-formation checks: shared-Phase-1 trend models, all-condition descriptive reporting, no pass/fail gate |
| `02_primary_analysis.qmd` | Primary analyses (H1 through H4) |
| `03_secondary_analysis.qmd` | Secondary analyses |
| `04_exploratory.qmd` | Exploratory analyses |
| `05_exit_survey.qmd` | Exit survey responses |

## Accuracy denominators

Both accuracy outcomes are proportions of *eligible listener response
opportunities*, not of submitted answers. `preprocessing.py` writes
`hasSpeakerMessage` and `responseOpportunity` on `trials.csv`, and
`social_guesses.csv` is an opportunity frame with one row per eligible
Phase 2 listener rather than one row per submitted guess, so a nonresponse
is visible instead of vanishing. `R/prepare.R` codes a correct on-time
answer as 1 and an incorrect answer, an ordinary timeout, and a late arrival
all as 0.

Lateness is established separately for each outcome: `lateClick` for a
tangram selection and `lateSocialGuess` for a social guess, both set by the
server at the end of the Feedback stage from a snapshot taken at the
Selection deadline. Documented technical failures go in
`data/<dataset>/technical_exclusions.csv` (gameId, playerId, roundId,
outcome, reason) and become missing rather than unsuccessful; the file is
optional and every row needs a reason.

`SI_pilot.qmd` passes `denominator = "submitted"` so the pilot keeps the
coding its published numbers were computed with, as the manuscript states.
Do not switch it to the default.

## Session instrumentation and the two clocks

Timing, device, and engagement records added in September 2026 (client code in
`experiment/client/src/instrumentation.js`, `Chat.jsx`, `Refgame.jsx`, and
`Tangram.jsx`). None of it exists in the pilot, so every field is optional in
`preprocessing.py` and the pilot must keep processing byte-identically.

Two clocks meet in `trials.csv`, and confusing them is the easy mistake:

- **Participant clock** (`selectionRenderedAt`, `tangramSelectedAt`,
  `clickedAt`, `socialGuessSelectedAt`, and `composeStartedAt` in
  `messages.csv`). Valid *within* one participant, never across, because
  browser clocks are not synchronized. The derived `selectionRt`,
  `socialGuessRt`, and `composeMs` are all within-participant differences and
  are therefore safe.
- **Server clock** (`selectionStartedAt`, `selectionEndedAt`,
  `selectionDurationMs`, read from `stage.csv` by `selection_stage_times()`).
  Comparable across everyone.

Two column pairs look redundant and are not. `clickedAt` is when a selection
was committed to the server and is what the late-arrival audit uses;
`tangramSelectedAt` is when the participant chose. They coincide in the
referential conditions but not in the social ones, where both answers are held
in local state until submit -- so `tangramSelectedAt` is the only response-time
column comparable across conditions, and `clickedAt` is not a response time.

An `offline` event carries the moment the connection dropped, but it is
written only once the connection is back, together with the `online` that
ended it (`shared/engagement.js`). So the two always arrive as a pair, and a
participant who went offline and never returned leaves no `offline` record at
all -- their absence shows up as missing data instead.

`players.csv` carries the device context as flattened `client*` columns and the
engagement log as counts (`tabHiddenCount`, `tabHiddenMs`, `offlineCount`,
`resizeCount`, `engagementLogTruncated`); the per-event list stays in
`raw_anonymized/player.csv`. The raw user agent is recorded during a session
for debugging but is in `SENSITIVE_COLUMNS` in `extract_run.py`, so it is
stripped at anonymization and never committed.

## Stats → LaTeX pipeline

`convention_check_data()` in `R/prepare.R` keeps all four conditions for
descriptive reporting but restricts the full-sample convention-formation trend
models to `H12_CONDITIONS`. These checks inform H1/H2 interpretation and do not
gate any primary analysis. `SI_pilot.qmd` deliberately retains its historical
four-condition models and original pilot summaries; do not silently refit
those models when updating the full-sample checks.

Analysis notebooks write statistics as `\newcommand` definitions to `writing/preregistration/stats/*.tex`, which are `\input`'d by `writing/preregistration/main.tex`. This keeps numbers in sync between the analysis and the manuscript.

After re-rendering a notebook, commit the updated `writing/preregistration/stats/*.tex` file so the paper picks up the new numbers. The generated files have a `% AUTO-GENERATED` header to discourage manual edits.

**Note:** `writing/` is in `.gitignore`: each project directory is a clone of its Overleaf project's git remote, so it is versioned on the Overleaf side, not in this repo. The stats files live inside `writing/preregistration/stats/` and are managed on the Overleaf side.

## Figures → manuscript

Figures are generated in `figures/<name>/` (`figures/pilots/` for the SI) and `figures/llm_plots/`. The manuscript references them from `figures/` (relative to `writing/preregistration/`). Run the sync script to copy them:

```bash
bash figures/sync_figures.sh
```

This copies all `SI_*.pdf` files into `writing/preregistration/figures/`. Overleaf doesn't support paths outside the project root, so figures must live inside `writing/preregistration/`. `SI_group_specificity.pdf` in the manuscript was hand-adjusted in Illustrator; `SI_pilot.qmd` writes the generated version as `SI_group_specificity_generated.pdf` so the two can be compared without overwriting the edited one.
