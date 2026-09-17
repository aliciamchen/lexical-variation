---
name: process-new-run
description: Use when a new Empirica export has arrived in experiment/data/<timestamp>/ and needs to flow into the committed dataset and manuscript statistics -- "process the new run", "add yesterday's session", "regenerate the pilot stats" -- or when re-running the pipeline after changing preprocessing.
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Process a new experiment run

Directory layout and the script table are in `.claude/rules/data-pipeline.md`; `make help` lists the targets. This is the procedure.

1. **Find what is new.** Compare `ls experiment/data/` with `uv run python analysis/extract_run.py list`. Exports arrive from `copy_tajriba.sh`, one timestamped zip per backup.

2. **Smoke-test the export first**: `make smoke ZIP=experiment/data/<run>/empirica-export-<run>.zip` runs extract → combine → process (no Vertex AI) → the integrity suite in a throwaway dataset `smoke` without touching any real dataset's `runs.txt`. The block-count checks fail for TEST_MODE games and that is expected; anything else that fails is a problem with the export to raise before going on. Remove `data/smoke/` and `analysis/derived/smoke/` afterwards.

3. **Extract each new zip**: `uv run python analysis/extract_run.py <zip> --dataset <name>`. This unzips into `data/runs/<timestamp>/raw/`, strips the sensitive participant columns, writes `bonuses.csv`, and registers the timestamp in `data/<name>/runs.txt` (`--no-register` skips that). The pilot is frozen: the script refuses to run without `--dataset` and refuses new runs for `pilots`; the full sample is its own dataset, created with `mkdir data/<name>`. Print bonuses for Prolific payment with `extract_run.py bonuses --run <timestamp>`.

4. **Combine.** `make combine DATASET=<name>`. It refuses duplicate run arguments and hard-fails on duplicated record ids across runs. Do not work around that: it means two exports are cumulative snapshots of the same server, so keep only the latest one per server. Rehearsal or deploy-check games that ran on the production server go in `data/<name>/exclude_games.txt` (one game id per line, `#` comments) before combining; the step drops them and prints how many rows went. It also writes `data/<name>/dropouts.csv` (quiz failures, lobby timeouts, late arrivals) for the attrition report.

5. **Process and validate.** `make process DATASET=<name>` runs preprocessing, the non-referential filter, and derived metrics. Participants excluded after the fact go in `data/<name>/participant_exclusions.csv` (`playerId,reason`) before this step. The filter's `classify` is cached in `messages_classified.csv` and sends only messages without a label; run `uv run python analysis/filter_nonreferential.py classify --data-dir data/<name> --dry-run` first, report the number of messages and estimated Gemini calls, and get the go-ahead before running it (it also asks unless `--yes`). Without Vertex AI use `make process-no-filter` and report that filtering was skipped: the derived step then warns loudly and uses the unfiltered utterances. Preprocessing deletes a `speaker_utterances_filtered.csv` whose sidecar no longer matches `messages.csv`; rerun `classify` and `apply` to rebuild it. Then `make test DATASET=<name>`. If the integrity suite fails on a legitimate design feature, fix the test with a justification; never edit the data to pass.

6. **Regenerate outputs.** `make notebooks DATASET=<name>` (the SI notebooks for the pilot, the numbered analysis notebooks otherwise), then `bash figures/sync_figures.sh`. Review `git diff --stat` for `data/`, `analysis/derived/` (including the `*_jaccard.csv` tables), and `figures/`, and list which macros in `writing/preregistration/stats/*.tex` changed value (the files are untracked, so diff against the Overleaf copy or print before-and-after values).

7. **Before any commit**, eyeball `head -1 data/<dataset>/raw_anonymized/player.csv` for identifier columns; the pre-commit hook also blocks Prolific-shaped ids. Commit only when asked. Remind the user that `writing/preregistration/stats/*.tex` and `writing/preregistration/figures/` must be synced to Overleaf by hand.
