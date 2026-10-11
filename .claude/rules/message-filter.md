---
paths:
  - "analysis/filter_nonreferential.py"
---

# Non-referential message filter

`analysis/filter_nonreferential.py` uses Gemini through Vertex AI and needs `gcloud auth application-default login` and a project with Vertex AI enabled (the project can be set in `.env`; the script falls back to the gcloud default). Every run spends credit: count the calls and say so before running anything.

Speaker messages that carry no information about the target ("thanks", "ready") are removed before speaker utterances are concatenated and embedded. The classifier sees batches of numbered message texts and nothing else, at temperature 0, and labels each R or NR under the criterion "when in doubt, R" (`CLASSIFICATION_PROMPT`). Labels are cached in `messages_classified.csv`, keyed on `gameId, roundId, senderId, timestamp, text`, so only messages without a label are ever sent. `classify` prints the count and the estimated calls (batches of 30) and proceeds only with `--yes` or an interactive yes; it writes back the labels obtained before a failed batch; and at temperature 0 a batch occasionally comes back malformed (`BatchParseError`), which a different `--batch-size` (29, 31, 27, 23) moves past. `MODEL_ID` is `gemini-2.5-flash`, the model behind the full sample's labels. Each dataset's `messages_classified.model.json` records the model, dates and counts of its labels; add a line after classifying new messages.

The preregistration promises a manual check of the labels before the primary contrasts are examined, with no agreement target. `sample` draws `annotation_sample.csv` (200 speaker messages, stratified by length and block, fixed seed, no condition or model label shown); the author fills `human_label` with R or NR, saves it as `human_labels.csv`, and `validate` reports agreement, the confusion matrix, Cohen's kappa and every disagreement. `apply` writes `speaker_utterances_filtered.csv` with the sidecar that `.claude/rules/data-pipeline.md` describes; every downstream step prefers the filtered file when it exists and is current.

```bash
uv run python analysis/filter_nonreferential.py sample   --data-dir data/<name> --n 200
uv run python analysis/filter_nonreferential.py classify --data-dir data/<name> --dry-run
uv run python analysis/filter_nonreferential.py classify --data-dir data/<name>            # asks before the first call
uv run python analysis/filter_nonreferential.py validate --data-dir data/<name>
uv run python analysis/filter_nonreferential.py apply    --data-dir data/<name>
```
