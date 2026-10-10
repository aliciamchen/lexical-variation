---
paths:
  - "analysis/llm_simulation/**"
  - "analysis/filter_nonreferential.py"
---

# LLM simulation and the message filter

Both use Gemini through Vertex AI and need `gcloud auth application-default login` and a project with Vertex AI enabled (the project can be set in `.env`; the scripts fall back to the gcloud default). Every run spends credit: count the calls and say so before running anything.

## Phase 1 benchmark (`analysis/llm_simulation/`)

Three LLM agents play Phase 1 (`llm_simulation.py`, prompts in `llm_prompts.yaml`). `run_llm_simulation.sh` orchestrates N groups, `process_llm_results.py` turns the group JSONs into CSVs with SBERT similarities, and `SI_llm_simulation.qmd` writes `figures/llm_plots/` and `writing/preregistration/stats/llm.tex`. The paper's run is `llm_results_nucleus_20260323_012900` (gemini-3.1-pro-preview, temperature 1.0, top-p 0.95, recorded in its `config.json`); `--temperature 0` is greedy decoding and not what the paper reports. A group is 36 rounds of 3 calls, 108 calls. Results are saved after every round, so rerun with `--output-dir <same directory>` to resume (a closed laptop suspends tmux processes too), and the processor skips groups still marked `in_progress`.

```bash
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 2 --blocks 2   # quick test
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 20             # the paper's run
uv run python analysis/llm_simulation/process_llm_results.py
cd analysis/llm_simulation && quarto render SI_llm_simulation.qmd
```

## Non-referential message filter (`analysis/filter_nonreferential.py`)

Speaker messages that carry no information about the target ("thanks", "ready") are removed before speaker utterances are concatenated and embedded. The classifier sees batches of numbered message texts and nothing else, at temperature 0, and labels each R or NR under the criterion "when in doubt, R" (`CLASSIFICATION_PROMPT`). Labels are cached in `messages_classified.csv`, keyed on `gameId, roundId, senderId, timestamp, text`, so only messages without a label are ever sent. `classify` prints the count and the estimated calls (batches of 30) and proceeds only with `--yes` or an interactive yes; it writes back the labels obtained before a failed batch; and at temperature 0 a batch occasionally comes back malformed (`BatchParseError`), which a different `--batch-size` (29, 31, 27, 23) moves past. `MODEL_ID` is `gemini-2.5-flash`, the model behind the full sample's labels; the pilot's came from `gemini-2.0-flash`, which Vertex AI no longer serves. Each dataset's `messages_classified.model.json` records the model, dates and counts of its labels; add a line after classifying new messages.

The preregistration promises a manual check of the labels before the primary contrasts are examined, with no agreement target. `sample` draws `annotation_sample.csv` (200 speaker messages, stratified by length and block, fixed seed, no condition or model label shown); the author fills `human_label` with R or NR, saves it as `human_labels.csv`, and `validate` reports agreement, the confusion matrix, Cohen's kappa and every disagreement. `apply` writes `speaker_utterances_filtered.csv` with the sidecar that `.claude/rules/data-pipeline.md` describes; every downstream step prefers the filtered file when it exists and is current.

```bash
uv run python analysis/filter_nonreferential.py sample   --data-dir data/<name> --n 200
uv run python analysis/filter_nonreferential.py classify --data-dir data/<name> --dry-run
uv run python analysis/filter_nonreferential.py classify --data-dir data/<name>            # asks before the first call
uv run python analysis/filter_nonreferential.py validate --data-dir data/<name>
uv run python analysis/filter_nonreferential.py apply    --data-dir data/<name>
```
