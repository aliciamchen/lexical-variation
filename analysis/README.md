# Analysis Pipeline

## Overview

The analysis pipeline processes raw Empirica export data through two Python preprocessing steps, then runs statistical analyses in R via Quarto documents.

```
experiment/export-data/  (raw Empirica CSVs)
        |
        v
  preprocessing.py       (Python: parse → clean CSVs)
        |
        v
  compute_embeddings.py  (Python: SBERT embeddings + similarity metrics)
        |
        v
  00–04_*.qmd            (R: statistical models + plots)
```

## Prerequisites

- **Python** (managed by [uv](https://docs.astral.sh/uv/)): pandas, sentence-transformers, umap-learn
- **R** (managed by renv): tidyverse, lme4, lmerTest, emmeans, tidyboot, patchwork, here
- **Quarto** for rendering `.qmd` files

Install R packages if needed:

```bash
Rscript -e 'renv::restore()'
```

## Step 1: Export data from Empirica

```bash
cd experiment
empirica export
```

This produces a `.zip` file. Unzip it and move the contents to `experiment/export-data/`:

```bash
unzip <exported-file>.zip -d export-data/
```

## Step 2: Preprocess raw data

```bash
uv run python analysis/preprocessing.py experiment/export-data/ --output analysis/data/
```

**Input:** `experiment/export-data/{game,player,playerRound,round}.csv`

**Output** (in `analysis/data/`):

| File | Description |
|------|-------------|
| `games.csv` | 1 row per game (condition, block counts) |
| `players.csv` | 1 row per player (demographics, scores, exit survey) |
| `trials.csv` | 1 row per player per round (role, clicks, accuracy) |
| `messages.csv` | 1 row per chat message (sender, role, text, timestamp) |
| `speaker_utterances.csv` | 1 row per speaker per trial (concatenated messages, word count) |
| `social_guesses.csv` | 1 row per social guess (social_mixed condition only) |

## Step 3: Compute embeddings and similarity metrics

```bash
uv run python analysis/compute_embeddings.py analysis/data/ --output analysis/data/
```

**Output** (in `analysis/data/`):

| File | Description |
|------|-------------|
| `embeddings.npy` | SBERT embeddings, shape (N, 384) |
| `adjacent_similarities.csv` | Cosine similarity between successive descriptions of the same tangram |
| `pairwise_similarities.csv` | All speaker-pair similarities for Phase 1 and Phase 2 final windows |
| `phase_change_similarities.csv` | Similarity between final Phase 1 and Phase 2 descriptions per participant × tangram |
| `umap_projections.csv` | 2D UMAP coordinates for each utterance |

## Step 4: Render analysis documents

Render from the **project root** (so renv activates correctly):

```bash
quarto render analysis/00_preprocess.qmd
quarto render analysis/01_outcome_neutral.qmd
quarto render analysis/02_primary_analysis.qmd
quarto render analysis/03_secondary_analysis.qmd
quarto render analysis/04_exploratory.qmd
```

Or render all at once:

```bash
for f in analysis/0*.qmd; do quarto render "$f"; done
```

HTML output goes to `_output/analysis/`.

## Analysis documents

| File | Contents |
|------|----------|
| `00_preprocess.qmd` | Load/validate data, summaries, exclusion criteria checks |
| `01_outcome_neutral.qmd` | Outcome-neutral criteria: description length reduction, accuracy increase, convention stability, group-specificity permutation test |
| `02_primary_analysis.qmd` | H1/H2 hypothesis tests: weighted least squares on group-specificity, planned contrasts |
| `03_secondary_analysis.qmd` | Semantic change, referential accuracy, in-group vs out-group, social accuracy correlation |
| `04_exploratory.qmd` | Full temporal dynamics, UMAP visualization, utterance properties |

## Notes

- The SBERT model used is `paraphrase-MiniLM-L12-v2` (384-dimensional embeddings), same as the power analysis.
- Pairwise similarity windows: "phase1_final" and "phase2_final" each use the last 3 blocks of the respective phase.
- `blockNum` in the data is 0-indexed within each phase (resets to 0 at start of Phase 2).
- Models in the Qmd files gracefully handle single-condition or single-game test data by falling back to simpler models.
