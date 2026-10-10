---
paths:
  - "analysis/**"
  - "data/**"
  - "experiment/data/**"
  - "operations/final_exports.py"
---

# Data and analysis pipeline

## Datasets

The pipeline is keyed by a dataset name: `--dataset` on a script, else the `DATASET` environment variable, else `pilots`. `make` passes `DATASET` to every step (`make all DATASET=full`). The layout is defined in `analysis/dataset_paths.py` and mirrored in `analysis/config.R` (`use_dataset()`); change both together. `pilots` is frozen and committed; `full` is local and stays so until the RefBank release. Everything identifiable (`experiment/data/`, `experiment/pilot_data/`, `data/runs/`, `data/payments/`, `backups/`) is gitignored.

Inputs a dataset directory may hold, each read at the step named:

| File | Read by | Meaning |
|------|---------|---------|
| `runs.txt` | combine | Export timestamps to stack, one per line, `#` comments allowed. Exports are cumulative snapshots of one server, so a later export of the same server replaces an earlier one; `data/full/runs.txt` names the final export of each of its 31 server periods, and `make final-exports` verifies that set |
| `exclude_games.txt` | combine | Game ids dropped with every dependent row: rehearsal games and games with a repeat participant. `make payments` ignores it, so those players are still paid and blocklisted |
| `participant_exclusions.csv` | preprocess | `playerId,reason`, reason required, unknown ids refused. Removes the player's messages from `messages.csv` and both utterance files, so every derived measure excludes them; flags `excluded`/`exclusionReason` on their rows and on the rows of listeners they spoke to in `trials.csv` and `social_guesses.csv`; blanks their `exitSurvey_*` columns in `players.csv` (the answers stay in `raw_anonymized/`). `responseOpportunity` is left as computed |
| `technical_exclusions.csv` | R, `technical_exclusions()` | `gameId,playerId,roundId,outcome,reason`: documented technical failures, which become missing rather than unsuccessful |
| `integrity_exceptions.csv` | integrity suite | `invariant,gameId,playerId,roundId,reason`: the cases where an invariant does not hold. The tests require the cases they find to equal the documented ones, so a new case fails and so does a documented case that disappears. It records data loss and instrumentation races, never analytic choices |
| `payment_adjustments.csv` | `make payments` | See `.claude/rules/operations.md` |

Outputs worth knowing: `manifest.json` (runs combined, games filtered and excluded, dropout count); `dropouts.csv` (player records with no real game: quiz failures, lobby timeouts and overflow arrivals, with `condition` and `tangramSet` from the batch's treatment; the pilot's file has the first five columns only); and the sidecar `speaker_utterances_filtered.source.json` (below).

## Steps

`make extract combine process test notebooks`, or `make smoke ZIP=<zip>` to run everything on a throwaway dataset `smoke` (it clears `data/smoke/` and `analysis/derived/smoke/` itself; leave them afterwards, since the agent hook blocks recursive deletes; the block-count checks fail for TEST_MODE games). The `rebuild-dataset` skill is the procedure for `full`.

- **Extract** (`extract_run.py <zip>`) unzips into `data/runs/<ts>/raw/`, drops `SENSITIVE_COLUMNS` from `player.csv`, redacts 24-hex Prolific-id tokens in every text cell, and registers the timestamp in `runs.txt` unless `--no-register`. It is deterministic.
- **Combine** (`combine_runs.py --dataset <name>`) unions the registered exports on record id, keeping the newest version of each record, drops excluded games, removes player records of games that never started, and writes `dropouts.csv`. Positional runs for the frozen `pilots` dataset must equal its `runs.txt` unless `--allow-pilot`.
- **Process** (`process_data.py`) runs three sub-steps. *Preprocess* (`preprocessing.py`) writes `data/<name>/*.csv`, honors the exclusion files, and prints, per column, how many JSON values it could not parse (silence means all parsed). *Filter* (`filter_nonreferential.py`, see `.claude/rules/llm-simulation.md`) labels speaker messages and writes `speaker_utterances_filtered.csv`; `--skip-filter` falls back to the unfiltered file with a warning. *Derived* (`compute_derived.py`, `--skip-derived` to omit) writes `analysis/derived/<name>/`: the SBERT similarity tables, the same pairs scored by content-word Jaccard in the same row order (`*_jaccard.csv`, NaN where a side has no content words), UMAP, and the final-window pairs.
- **Test** (`make test`) runs the integrity suite on the active dataset, the Python unit tests, and `Rscript analysis/tests/run_all.R`. The suite applies the production bonus rate to every dataset other than `pilots`. Besides the game-as-designed invariants it rebuilds both utterance files from `messages.csv` and the classifier labels, recomputes every row of the pairwise, block and adjacent similarity tables from the utterance file and `embeddings.npy`, and reconciles the processed tables with `raw_anonymized/` and `manifest.json`, so a derived table that no longer follows from the code fails here.

**Filtered utterances are tied to `messages.csv`.** `apply` writes the sidecar with the sha256 and row count of the `messages.csv` it read. `compute_derived.py` and `config.R` refuse a filtered file whose sidecar is missing or stale, and `preprocessing.py` deletes a stale filtered file when it rewrites `messages.csv`. `dataset_paths.filtered_utterances_status()` is the one check. Never copy a filtered file between datasets.

**Caches are keyed to their inputs.** `group_specificity.R` stores a hash of the pairwise data beside `gs_results_<speaker structure>.rds` and recomputes when it differs (several minutes); `bayes_factors.R` names each brms fit by a hash of data and formula (hours; the fits are gitignored, the RDS files committed). A rebuild that changes the pairwise tables refits on the next render.

## Definitions that are easy to get wrong

- **`allGroupsPaired`** on both block tables is 1 where every original group has two speakers who have described that tangram by that block, the preregistered start rule for group specificity; it is 0 in the first block of each phase and where a removed or reassigned speaker leaves a group with one describer. Within-minus-between contrasts filter with `specificity_eligible()` (`R/prepare.R`); the descriptive within-versus-between plots use every row.
- **Accuracy denominators** are eligible listener response opportunities, not submitted answers: `hasSpeakerMessage` and `responseOpportunity` on `trials.csv`, and one row per eligible Phase 2 listener in `social_guesses.csv`. A correct on-time answer is 1; an incorrect answer, a timeout and a late arrival are 0. Lateness is `lateClick` and `lateSocialGuess`, set by the server from its deadline snapshot; `preprocessing.py` reapplies `idle.js`'s rule from `clicked_at_deadline` and `social_guess_at_deadline` for answers that arrived after Feedback ended. `denominator = "submitted"` in `R/prepare.R` is for comparison only, never for reported results.
- **Two clocks.** Participant-clock columns (`selectionRenderedAt`, `tangramSelectedAt`, `clickedAt`, `socialGuessSelectedAt`, `composeStartedAt`) are valid only within one participant, because browser clocks differ by up to minutes; the derived `selectionRt`, `socialGuessRt` and `composeMs` are within-participant differences and safe. Server-clock columns (`selectionStartedAt`, `selectionEndedAt`, `selectionDurationMs` from `stage.csv`, and any raw attribute's `*LastChangedAt`) are comparable across everyone. `tangramSelectedAt` is when the participant chose and is the only response time comparable across conditions; `clickedAt` is when the choice reached the server, which in the social conditions is the submit time.
- **Connection and engagement records** exist only for the September and October 2026 sessions, so every such field is optional in `preprocessing.py` and the pilot must keep processing byte for byte. An `offline` event is written on reconnect, paired with its `online`; a participant who never came back leaves no record. `players.csv` carries the counts (`tabHidden*`, `offline*`, `resizeCount`, `disconnect*`, `pageLoadCount`, `reloadCount`, the `*Truncated` flags); the event lists stay in `raw_anonymized/player.csv`; the raw user agent is stripped at extraction. `disconnect*` count only the part of each drop inside the player's game window, which `summarize_connection()` moves onto the participant's clock with `participant_clock_offsets()` (the median of `selectionRenderedAt` minus `selectionStartedAt` over their trials), the one place the pipeline relates the two clocks.
- **Speaker structures** in `group_specificity.R`: `"pair"` (tangram and unordered speaker-pair intercepts) is the preregistered model and what every notebook reports; `"multimembership_pair"`, `"multimembership"` and `"separate"` are for comparison only. The structure is part of the cache key and filename.
- **Convention-formation checks** (`convention_check_data()`) keep all four conditions for description but fit the trend models on `H12_CONDITIONS`; they inform H1 and H2 and gate nothing. `SI_pilot.qmd` keeps its own four-condition models.
- **Groups.** `originalGroup` persists for the whole game; `currentGroup` changes per trial in mixed Phase 2, where chat names are masked, so `senderName` in `messages.csv` is uninformative there while `senderId` stays valid. The reshuffle guarantees mixing only in rounds where every group is a trio.
- **Repeat participation** is checked by `make payments` (`repeats.csv`), not by the pipeline; a game with a player who had played a full game in an earlier session is excluded whole through `exclude_games.txt`.

## Notebooks and the manuscript

Every notebook sources `config.R`, which sets the dataset's paths, palettes and ggplot theme and sources every helper in `analysis/R/`; `list2env(load_tables(), envir = globalenv())` loads the tables. Data preparation goes through the `R/prepare.R` functions, not inline recodes, and per-game group-specificity estimates come from `game_specificity_table()`, so every notebook reports the same numbers. The R helpers have `stopifnot` tests in `analysis/tests/`, one file per helper.

| Notebooks | Dataset | Writes |
|-----------|---------|--------|
| `00_data_overview` to `05_exit_survey` | `full` (on `pilots` they run as a code check and say so in a banner) | `writing/manuscript/stats/<overview,checks,primary,secondary,exploratory,survey>.tex`; rendered HTML in `_output/` |
| `SI_pilot.qmd` | `pilots`, frozen with the preregistration | `figures/pilots/`, `writing/preregistration/stats/pilot.tex` |
| `llm_simulation/SI_llm_simulation.qmd` | the LLM benchmark | `figures/llm_plots/`, `writing/preregistration/stats/llm.tex` |

Figures: percentile-bootstrap 95% intervals over games with the games as thin lines or points behind the mean, no gridlines, one plot per figure, sentence-case labels, sample sizes written as "16 games" (never "n = 16", which readers take as participants), and never a line for a quantity a condition does not have (`refer_separated` has no out-group speakers). `save_fig()` writes into the dataset's figures directory; slide sets go in the gitignored `figures/meetings/<date>/`.

Statistics reach a manuscript only as `\newcommand` macros written by `write_stats_tex()` (letters-only names, `% AUTO-GENERATED` header, never hand-edited). The `run-analysis` skill is the render procedure, including `BAYES_FACTORS=never|auto|always`. `writing/` is gitignored and versioned on the Overleaf side, so nothing there is committed here. `bash figures/sync_figures.sh writing/manuscript` copies `SI_*.pdf` into the article's project; never run it against `writing/preregistration/`, whose group-specificity figure was edited by hand.
