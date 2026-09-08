---
name: process-new-run
description: Use when a new Empirica export has arrived in experiment/data/<timestamp>/ and needs to flow into the committed dataset and manuscript statistics -- "process the new run", "add yesterday's session", "regenerate the pilot stats" -- or when re-running the pipeline after changing preprocessing.
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Process a new experiment run

Directory layout and the script table are in `.claude/rules/data-pipeline.md`; `make help` lists the targets. This is the procedure.

1. **Find what is new.** Compare `ls experiment/data/` with `uv run python analysis/extract_run.py list`. Exports arrive from `copy_tajriba.sh`, one timestamped zip per backup.

2. **Extract each new zip**: `uv run python analysis/extract_run.py <zip>`. This unzips into `data/pilot_runs/<timestamp>/raw/`, strips the sensitive participant columns, and writes `bonuses.csv`. Print bonuses for Prolific payment with `extract_run.py bonuses --run <timestamp>`.

3. **Register the run and combine.** Add the timestamp to `PILOT_RUNS` in the `Makefile` (or the full-sample variable once it exists) and run `make combine`. It refuses duplicate run arguments and hard-fails on duplicated record ids across runs. Do not work around that: it means two exports are cumulative snapshots of the same server, so keep only the latest one per server.

4. **Process and validate.** `make process` runs preprocessing, the non-referential filter, and derived metrics; the filter needs Vertex AI credentials and makes one Gemini call per batch of messages, so say so before running it or use `make process-no-filter` and report that filtering was skipped. Then `make test`. If the integrity suite fails on a legitimate design feature, fix the test with a justification; never edit the data to pass.

5. **Regenerate outputs.** `make notebooks`, then `bash figures/sync_figures.sh`. Review `git diff --stat` for `data/`, `analysis/pilot_derived/`, and `figures/`, and list which macros in `paper/stats/*.tex` changed value (the files are untracked, so diff against the Overleaf copy or print before-and-after values).

6. **Before any commit**, eyeball `head -1 data/pilots/raw_anonymized/player.csv` for identifier columns; the pre-commit hook also blocks Prolific-shaped ids. Commit only when asked. Remind the user that `paper/stats/*.tex` and `paper/figures/` must be synced to Overleaf by hand.
