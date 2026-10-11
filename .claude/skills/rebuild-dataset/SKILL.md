---
name: rebuild-dataset
description: Use when the full-sample dataset in data/full/ has to be regenerated -- after a change to extraction, preprocessing or the derived metrics, after an entry in participant_exclusions.csv or exclude_games.txt, after the classifier labels change, or to check that the data reproduce from the raw exports -- "reprocess the data", "rebuild data/full", "rerun the pipeline", "apply the exclusions".
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Rebuild the full-sample dataset

Directory layout and the script table are in `.claude/rules/data-pipeline.md`; `make help` lists the targets. Collection ended on 2026-10-08, so the inputs are fixed: the 31 final exports named in `data/full/runs.txt` (one per server period; `make final-exports` verifies the set against every export), the exclusion files beside it, and the classifier's label cache in `classifier/messages_classified.csv`. The raw export folders under `experiment/data/` are read-only, and nothing under `data/full/` is committed. The procedure:

1. **Snapshot first.** Copy `data/full/tables/`, `data/full/raw/`, `data/full/derived/*.csv` and `data/full/frames/` to the scratchpad, so the effect of the rebuild is measured afterwards rather than assumed.

2. **Extract only if a raw input changed.** The per-run extracts in `data/runs/<timestamp>/raw/` are regenerated from the zips by `make extract DATASET=full` (a few minutes for all 31). Rerun it after a change to `extract_run.py`; otherwise skip it. Extraction is deterministic, so re-extracting reproduces the combined tables byte for byte.

3. **Combine**: `make combine DATASET=full`. It reports collapsed duplicates (none when the runs are the final exports, since no record appears in two of them), the games dropped through `exclude_games.txt`, and the dropout records written to `dropouts.csv`.

4. **Process**: `make process DATASET=full`. The filter step reads the label cache and sends only speaker messages without a label; it prints the count and the estimated Vertex AI calls before anything is sent, and when every message is cached it makes no call. If messages did change, report the estimate and get the go-ahead before `classify --yes`, and add a line to `messages_classified.model.json`. The derived step (embeddings, pairwise tables, description properties) takes about ten minutes; run the whole thing detached with `tee` to a log if the session may not last that long. The frames step that follows (`build_frames.py`) takes seconds, and `make frames` reruns it alone when only it changed.

5. **Test**: `make test DATASET=full`. The suite passes on `full` with no known failures. The documented anomalies are in `data/full/integrity_exceptions.csv`, which the affected tests check exactly, so a documented case that disappears fails as well. A new failure is a finding to report, never something to make pass by editing the data; a legitimate new data loss gets a row in that file with its reason.

6. **Measure the change** against the snapshot: which files differ, and for each, whether values or only row order changed (the combine step stacks runs in export order, so row order follows it). Rows added or removed, columns changed and the games involved go in the report, and anything that touches a preregistered quantity goes in `full-sample-todos.md` for the deviations section.

7. **Downstream.** The group-specificity RDS caches and the Bayes-factor caches in `data/full/cache/` are keyed by the data they were fit on, so a rebuild that changes the pairwise tables invalidates them and the next render refits (see the `run-analysis` skill); `make descriptives` then refreshes the descriptive macros. The exclusion-review packet in `reviews/2026-10-09-exclusion-review/` is rebuilt with its `build_packet.py`. `make payments` is independent of the processed data and reads the exports directly.

8. **Report and stop.** What was rebuilt, the filter's call count, the test result, the measured differences, and what they mean for the notebooks. Do not commit: `data/full/` stays local until its public release, and code changes are committed only when the author asks.
