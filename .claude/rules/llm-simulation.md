---
paths:
  - "analysis/llm_simulation/**"
  - "analysis/filter_nonreferential.py"
---

# LLM Simulation & Message Filter

## LLM Simulation (Phase 1 benchmark)

All LLM simulation code lives in `analysis/llm_simulation/`. Simulates groups of 3 LLM agents playing the Phase 1 reference game using Gemini via Vertex AI. Used as an AI detection benchmark (paper, AI detection section). Requires `gcloud auth application-default login` and a GCP project with Vertex AI enabled.

| File | Purpose |
|------|---------|
| `llm_simulation.py` | Run one group simulation (3 players, 16 tangrams) |
| `llm_prompts.yaml` | Speaker/listener prompt templates |
| `run_llm_simulation.sh` | Orchestrate N groups with configurable model/temperature |
| `process_llm_results.py` | Convert group JSONs → analysis CSVs + SBERT similarity |
| `SI_llm_simulation.qmd` | R Quarto notebook: plots, exclusion criterion, draft SI paragraph |
| `tangram_images.py` | SVG-to-PNG conversion utility |

```bash
# 1. Run simulation
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 2 --blocks 2  # quick test
bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 20 --temperature 0  # full run

# 2. Process JSONs → CSVs
uv run python analysis/llm_simulation/process_llm_results.py

# 3. Render analysis notebook
cd analysis/llm_simulation && quarto render SI_llm_simulation.qmd
```

Each group simulation runs 6 blocks x 6 tangrams = 36 rounds with 3 API calls per round (1 speaker + 2 listeners) = 108 Gemini calls per group. Output is JSON per group in `analysis/llm_simulation/llm_results_{timestamp}/`.

**Fault tolerance:** Results are saved after every round, so interrupted runs preserve all completed work. If a group fails (API error, laptop sleep, etc.), re-run the shell script with `--output-dir` pointing at the same results directory:

```bash
# Resume a failed/interrupted run — completed groups are skipped, partial groups resume
bash analysis/llm_simulation/run_llm_simulation.sh --output-dir analysis/llm_simulation/llm_results_nucleus_20260321_182301
```

Note: closing a laptop suspends processes even inside tmux (tmux only survives terminal disconnects, not system sleep). Use `--output-dir` to resume after reopening.

The processing script (`process_llm_results.py`) automatically skips incomplete group files (those still marked `in_progress`).

## Non-Referential Message Filter

LLM-based classifier to filter non-referential messages (e.g., "thanks", "good job") from speaker utterances before SBERT embedding analysis. Uses Gemini via Vertex AI.

```bash
# Sample messages for human annotation (stratified by length and block)
uv run python analysis/filter_nonreferential.py sample --data-dir data/pilots/ --n 200

# Classify all speaker messages with LLM
uv run python analysis/filter_nonreferential.py classify --data-dir data/pilots/

# Validate against human labels (target: 95% agreement)
uv run python analysis/filter_nonreferential.py validate --data-dir data/pilots/ --labels data/pilots/human_labels.csv

# Apply filter -> produce speaker_utterances_filtered.csv
uv run python analysis/filter_nonreferential.py apply --data-dir data/pilots/

# Full pipeline with filtering (combines classify + apply + embeddings on filtered data)
uv run python analysis/run_pipeline.py --filter-messages
```

Output: `messages_classified.csv` (with `is_referential` column) and `speaker_utterances_filtered.csv` (non-referential messages removed before concatenation).

**Filtered data is used by default.** When `speaker_utterances_filtered.csv` exists in the data directory, all downstream analysis automatically uses it:
- `compute_embeddings.py` prefers filtered file (override with `--utterances-file speaker_utterances.csv`)
- `pilot_analysis.py` prefers filtered file
- All Quarto notebooks (`00`–`04`, `SI_pilot`) use the `utterances_file` variable from `config.R`, which resolves to filtered when present
- The `config.R` variable `utterances_file` controls which file the R notebooks load
