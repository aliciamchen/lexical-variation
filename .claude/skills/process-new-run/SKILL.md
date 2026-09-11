---
name: process-new-run
description: Use when a new Empirica export has arrived in experiment/data/<timestamp>/ and needs to flow into the committed dataset and manuscript statistics -- "process the new run", "add yesterday's session", "regenerate the pilot stats" -- or when re-running the pipeline after changing preprocessing.
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Process a new experiment run

Directory layout and the script table are in `.claude/rules/data-pipeline.md`; `make help` lists the targets. This is the procedure.

1. **Find what is new.** Compare `ls experiment/data/` with `uv run python analysis/extract_run.py list`. Exports arrive from `copy_tajriba.sh`, one timestamped zip per backup.

2. **Extract each new zip**: `uv run python analysis/extract_run.py <zip>`. This unzips into `data/runs/<timestamp>/raw/`, strips the sensitive participant columns, and writes `bonuses.csv`. Print bonuses for Prolific payment with `extract_run.py bonuses --run <timestamp>`.

3. **Register the run and combine.** Append the timestamp to `data/<dataset>/runs.txt` (`data/pilots/runs.txt` for the pilot; the full sample is its own dataset, created with `mkdir data/<name>` and a new `runs.txt`) and run `make combine DATASET=<name>`. It refuses duplicate run arguments and hard-fails on duplicated record ids across runs. Do not work around that: it means two exports are cumulative snapshots of the same server, so keep only the latest one per server.

4. **Process and validate.** `make process DATASET=<name>` runs preprocessing, the non-referential filter, and derived metrics; the filter needs Vertex AI credentials and makes one Gemini call per batch of messages, so say so before running it or use `make process-no-filter` and report that filtering was skipped. Then `make test DATASET=<name>`. If the integrity suite fails on a legitimate design feature, fix the test with a justification; never edit the data to pass.

5. **Regenerate outputs.** `make notebooks DATASET=<name>` (the SI notebooks for the pilot, the numbered analysis notebooks otherwise), then `bash figures/sync_figures.sh`. Review `git diff --stat` for `data/`, `analysis/derived/`, and `figures/`, and list which macros in `writing/preregistration/stats/*.tex` changed value (the files are untracked, so diff against the Overleaf copy or print before-and-after values).

6. **Before any commit**, eyeball `head -1 data/<dataset>/raw_anonymized/player.csv` for identifier columns; the pre-commit hook also blocks Prolific-shaped ids. Commit only when asked. Remind the user that `writing/preregistration/stats/*.tex` and `writing/preregistration/figures/` must be synced to Overleaf by hand.
