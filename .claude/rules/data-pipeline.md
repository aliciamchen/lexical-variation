---
paths:
  - "analysis/**"
  - "data/**"
  - "experiment/data/**"
  - "experiment/copy_tajriba.sh"
---

# Data and Analysis Pipeline

## Data

- Live data: `experiment/.empirica/local/tajriba.json`
  - This changes to csvs by running `empirica export`
- Backup from production server:
  ```bash
  cd experiment
  bash copy_tajriba.sh            # loop every 5 minutes (default)
  bash copy_tajriba.sh --once     # single backup and exit
  bash copy_tajriba.sh --help     # show usage
  ```
  The script SSHs into `root@tangramcommunication.empirica.app`, runs `empirica export` in `~/empirica` to produce a CSV zip, then copies it locally into `experiment/data/<timestamp>/`. Safe to run while the experiment is live. Exits automatically after 3 consecutive failures.

## Analysis Pipeline

`analysis/run_pipeline.py` is the single entry point for all data processing. It has subcommands for different workflows.

**Scripts:**

| Script | Purpose |
|--------|---------|
| `run_pipeline.py` | Entry point — process zips, combine runs, browse metadata |
| `preprocessing.py` | Raw Empirica CSVs → analysis-ready CSVs (called by run_pipeline) |
| `compute_embeddings.py` | Speaker utterances → SBERT embeddings, similarity metrics, H3c description properties (concreteness, lexical uniqueness, word frequency), UMAP |
| `animate_umap.py` | UMAP projections → animated videos of embedding trajectories |
| `plot_style.py` | Shared plotting constants and helpers (imported, not run directly) |
| `test_data_integrity.py` | Pytest validation of preprocessed CSV structure and content |
| `exploratory/` | Ad-hoc analysis scripts (contact networks, label dynamics) — not part of the pipeline |
| `filter_nonreferential.py` | LLM classifier to filter non-referential messages |
| `llm_simulation/` | LLM Phase 1 simulation subfolder (see below) |

**Quarto notebooks** (`00_preprocess.qmd` through `05_exit_survey.qmd`) read from `analysis/processed_data/` (a symlink updated by `run_pipeline.py`).

### Processing a single run

```bash
# Process the most recent zip under experiment/data/
uv run python analysis/run_pipeline.py

# Process a specific zip
uv run python analysis/run_pipeline.py experiment/data/20260222_125327/empirica-export-20260222_132407.zip

# Skip slow steps
uv run python analysis/run_pipeline.py --skip-embeddings --skip-visualize --skip-render
```

Steps: unzip → extract bonuses → anonymize → preprocess → [filter messages] → embeddings → visualize → render notebooks.

Output goes to `analysis/{datetime}/` with `raw/`, `data/`, and `figures/` subdirectories.

### Combining multiple runs

When data spans multiple Empirica server runs, use the `combine` subcommand:

```bash
# Combine and preprocess only
uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147

# Full pipeline (embeddings + plots)
uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147

# Skip slow steps
uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147 --skip-embeddings --skip-visualize
```

Stacks raw CSVs, filters failed games (lobby timeouts), runs preprocessing, writes `manifest.json`. Raw and preprocessed data go to `data/pilots/` (`raw/` subdirectory + CSVs); figures and manifest stay in `analysis/pilots/`. Each run must already be processed (i.e. `analysis/{timestamp}/raw/` must exist).

### Browsing runs and metadata

```bash
uv run python analysis/run_pipeline.py list                               # list all runs
uv run python analysis/run_pipeline.py status                             # show processed_data symlink
uv run python analysis/run_pipeline.py bonuses                            # print latest bonuses
uv run python analysis/run_pipeline.py bonuses --run 20260225_210047      # specific run
```

### Running individual scripts standalone

```bash
uv run python analysis/animate_umap.py --data-dir data/pilots/ --output-dir analysis/pilots/figures/
uv run python analysis/compute_embeddings.py data/pilots/
uv run pytest analysis/test_data_integrity.py -v
```

### Stats → LaTeX pipeline

Analysis notebooks write statistics as `\newcommand` definitions to `paper/stats/*.tex`, which are `\input`'d by `paper/main.tex`. This keeps numbers in sync between the analysis and the manuscript, and works with Overleaf (the generated `.tex` files are committed to git).

| Notebook | Generates | Commands |
|----------|-----------|----------|
| `analysis/SI_pilot.qmd` | `paper/stats/pilot.tex` | `\pilotBetaLen`, `\pilotNSig`, `\pilotDuration`, etc. |
| `analysis/llm_simulation/SI_llm_simulation.qmd` | `paper/stats/llm.tex` | `\llmNPass`, `\llmMeanAcc`, `\llmSim`, etc. |

After re-rendering a notebook, commit the updated `paper/stats/*.tex` file so the paper picks up the new numbers. The generated files have a `% AUTO-GENERATED` header to discourage manual edits.

**Note:** The `paper/` directory is in `.gitignore` (it's synced via Overleaf, not this repo). The stats files live inside `paper/stats/` and are managed on the Overleaf side.

### Figures → manuscript

Analysis plots are generated in `analysis/pilot_outputs/` and `analysis/llm_baseline_outputs/`. The manuscript (`paper/main.tex`) references them from `figures/` (relative to `paper/`). Run the sync script to copy them before pushing to Overleaf:

```bash
bash paper/sync_figures.sh
```

This copies all `SI_*.pdf` files into `paper/figures/`. Overleaf doesn't support paths outside the project root, so figures must live inside `paper/`.
