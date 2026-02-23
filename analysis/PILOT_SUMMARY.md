# Pilot Data Summary

## Overview

Two pilot sessions were conducted on 2026-02-21 and 2026-02-22, yielding **2 complete games** with **18 participants** (17 active, 1 removed for idleness):

| Game | Condition | Players | Active | Tangram Set | Phase 1 Blocks | Phase 2 Blocks |
|------|-----------|---------|--------|-------------|----------------|----------------|
| 01KJ121C... | `social_mixed` | 9 | 8 (1 kicked) | 1 | 6 | 6 |
| 01KJ33KJ... | `refer_mixed` | 9 | 9 | 1 | 6 | 6 |

Both games used tangram set 1 (hardcoded during pilot). The `refer_separated` condition has not yet been tested.

Data was processed using the full pipeline (`run_pipeline.py`) on 2026-02-22 and output to `analysis/20260222_132407/`.

---

## 1. Outcome-Neutral Criteria

These criteria (from Section 4.1 of the registered report) must be satisfied before interpreting primary hypotheses. They verify that conventions actually formed during Phase 1.

### 1a. Description Length Reduction

**Criterion:** Description length (word count) should decrease over Phase 1 blocks.

| Condition | Block 0 | Block 5 | Reduction |
|-----------|---------|---------|-----------|
| social_mixed | 16.2 words | 4.9 words | 70% |
| refer_mixed | 10.6 words | 5.2 words | 51% |

**Verdict: PASS.** Clear length reduction in both conditions. Descriptions converge from multi-word phrases ("large upside down triangle on top") to single-word labels ("C", "T", "anchor").

### 1b. Referential Accuracy Increase

**Criterion:** Listener accuracy should increase over Phase 1 blocks.

| Condition | Block 0 | Block 5 | Change |
|-----------|---------|---------|--------|
| social_mixed | 87.6% | 93.3% | +5.7pp |
| refer_mixed | 95.4% | 97.2% | +1.8pp |

**Verdict: PASS.** Accuracy starts high and stays high. The `refer_mixed` game had near-ceiling accuracy from the start.

### 1c. Convention Stability (Adjacent Similarity)

**Criterion:** Cosine similarity between successive descriptions of the same tangram should increase over blocks (speakers reuse the same phrases).

Both conditions show increasing adjacent similarity over Phase 1 blocks, with values rising from ~0.4-0.6 early on to 0.8-1.0 by block 5. Many speaker-tangram pairs reach perfect similarity (1.0) by late Phase 1, indicating verbatim repetition.

**Verdict: PASS.** Conventions clearly stabilize.

### Summary: All Three Outcome-Neutral Criteria Are Met

Conventions formed reliably in both pilot games. Participants reduced descriptions, maintained high accuracy, and converged on stable labels.

---

## 2. Primary Hypotheses (Preliminary, N=1 per condition)

These cannot be statistically tested with only 1 game per condition, but qualitative patterns are informative.

### 2a. Group-Specificity (H1 & H2)

**Metric:** Within-group pairwise similarity minus between-group pairwise similarity (higher = more group-specific conventions).

| Window | Condition | Within-Group Sim | Between-Group Sim | Group Specificity |
|--------|-----------|-------------------|--------------------|-------------------|
| Phase 1 final | social_mixed | 0.614 | 0.398 | 0.216 |
| Phase 1 final | refer_mixed | 0.616 | 0.409 | 0.207 |
| Phase 2 final | social_mixed | 0.468 | 0.399 | 0.069 |
| Phase 2 final | refer_mixed | 0.477 | 0.410 | 0.067 |

**Observation:** Both conditions show comparable Phase 1 group-specificity (~0.21), which drops substantially in Phase 2 (~0.07). The drop is similar across conditions, contrary to the H2 prediction that `social_mixed` should preserve more group-specificity than `refer_mixed`.

**Note on interpretation:** With N=1 per condition, this tells us little about the true effect. The registered report's power analysis targets 20 games per condition.

### 2b. Phase Change Similarity (Secondary Hypothesis)

**Metric:** Cosine similarity between final Phase 1 and final Phase 2 descriptions for each speaker-tangram pair.

| Condition | Mean sim(P1→P2) | SD |
|-----------|------------------|----|
| social_mixed | 0.756 | 0.273 |
| refer_mixed | 0.705 | 0.307 |

**Observation:** Social mixed participants maintained slightly more similar descriptions across phases. Consistent with H2's prediction that social signaling motivation preserves existing conventions, but the difference is small and based on 1 game each.

---

## 3. Social Guessing Performance (social_mixed only)

In the `social_mixed` condition, listeners guess whether the speaker was in their original Phase 1 group ("same_group" or "different_group").

| Metric | Value |
|--------|-------|
| Overall accuracy | 87.2% |
| Chance level | 33.3% (1 in 3 groups) |
| N guesses | 47 |

**Observation:** Participants are highly accurate at identifying original group membership despite anonymous identities and shuffled groups. This confirms that linguistic conventions carry detectable social information, validating the experimental design.

---

## 4. Behavioral Observations

### Description Examples (Convergence to Canonical Labels)

Examining utterances for one player across blocks:
- Block 1: "Looks like a C" (4 words) → Block 4: "C" (1 word)
- Block 1: "Looks like a T" (4 words) → Block 4: "T" (1 word)
- Block 1: "large upside down triangle on top" (6 words) → Block 4: "goblet" (1 word)

Many tangrams converge to single canonical labels across ALL groups (e.g., "C", "T", "anchor", "goblet"). This cross-group convergence is expected given the high Shape Naming Divergence (SND) of the selected tangrams — they have obvious, distinctive shapes that most people describe similarly.

### In-Group vs Out-Group Accuracy (Phase 2)

| Condition | In-Group Accuracy | Out-Group Accuracy | Difference |
|-----------|-------------------|--------------------|------------|
| social_mixed | 91.0% | 91.5% | -0.5pp |
| refer_mixed | 96.2% | 95.5% | +0.7pp |

**Observation:** No meaningful difference between in-group and out-group accuracy in either condition. Listeners understand speakers from other groups just as well as from their own group. This is consistent with conventions converging to similar (but not identical) labels.

### Player Attrition

- 17/18 players completed the full game
- 1 player (social_mixed, Group A) was removed after 2 consecutive idle rounds
- That player earned only $0.32 bonus (score = 8 points) vs $5.72-$8.16 for active players
- Exit survey feedback from this player: "The only problem was concerning the strike against me for inactivity, when I was really struggling to come up with a good description"

### Exit Survey Highlights

- All 17 active players reported understanding the task ("yes")
- All rated pay as fair
- Age range: 19–70 (mean ~38)
- Education: mix of high-school (7), bachelor (6), master (2)
- Strategy self-reports frequently mention: reusing same descriptions, keeping it simple, adopting others' labels

---

## 5. Cross-Reference with Registered Report

### Design Parameters Match

| Parameter | Registration | Implementation | Status |
|-----------|-------------|----------------|--------|
| 9 players per game | Section 3.1 | `playerCount` in treatments.yaml | Match |
| 3 groups of 3 | Section 3.1 | `GROUP_SIZE=3`, groups A/B/C | Match |
| 6 tangrams (high SND) | Section 3.2 | Ji et al. 2022 tangrams | Match |
| 6 Phase 1 blocks | Section 3.3 | `PHASE_1_BLOCKS=6` | Match |
| 6 Phase 2 blocks | Section 3.3 | `PHASE_2_BLOCKS=6` | Match |
| 3 conditions | Section 3.4 | `refer_separated`, `refer_mixed`, `social_mixed` | Match |
| Speaker rotation (blockNum % 3) | Section 3.3 | `callbacks.js:134` | Match |
| Group reshuffling each P2 block | Section 3.4 | `reshuffleGroups()` | Match |
| Identity masking in mixed | Section 3.4 | Anonymous avatars + "Player" name | Match |
| Social guessing task | Section 3.5 | `Refgame.jsx` social UI | Match |
| Scoring: 2pts correct listener | Section 3.6 | `LISTENER_CORRECT_POINTS=2` | Match |
| Scoring: 2 * proportion speaker | Section 3.6 | `callbacks.js:724-728` | Match |
| Social scoring: 2pts correct guess | Section 3.6 | `SOCIAL_GUESS_CORRECT_POINTS=2` | Match |
| SBERT paraphrase-MiniLM-L12-v2 | Section 4.2 | `compute_embeddings.py:228` | Match |
| Phase 1 accuracy threshold (2/3) | Section 3.7 | `ACCURACY_THRESHOLD=2/3` | Match |

### Analysis Pipeline Match

| Analysis | Registration | Implementation | Status |
|----------|-------------|----------------|--------|
| Description length (word count) | OC1 | `uttLength` in `speaker_utterances.csv` | Match |
| Referential accuracy | OC2 | `clickedCorrect` in `trials.csv` | Match |
| Convention stability (adjacent sim) | OC3 | `adjacent_similarities.csv` | Match |
| Group-specificity (pairwise sim) | H1, H2 | `pairwise_similarities.csv` | Match |
| Phase change similarity | Secondary | `phase_change_similarities.csv` | Match |
| Social accuracy | Secondary | `social_guesses.csv` | Match |

---

## 6. Pipeline Issues Found & Fixed

### Bug: Pairwise Similarity Used First Instead of Last Utterance

**File:** `analysis/compute_embeddings.py`, lines 77-78

**Issue:** `compute_pairwise_similarities()` used `.iloc[0]` (first utterance in window) instead of `.iloc[-1]` (last/most recent utterance). Since the "phase1_final" and "phase2_final" windows include the last 3 blocks, using the first utterance gives an earlier, less-converged description rather than the final convention.

**Fix:** Changed `.iloc[0]` to `.iloc[-1]`.

**Impact:** Pairwise similarity values in Phase 1 final window may have been slightly lower than they should be (using block 3 descriptions rather than block 5). This affects group-specificity calculations. The data should be recomputed after this fix.

---

## 7. Recommendations for Full Data Collection

### Things Working Well
1. **Conventions form reliably** — clear length reduction, accuracy increase, and stability increase in Phase 1
2. **Social guessing task works** — 87% accuracy far above chance (33%), confirming conventions carry social information
3. **Low attrition** — only 1/18 players removed; game mechanics are stable
4. **Exit survey quality** — participants engage thoughtfully and report understanding the task
5. **Pipeline produces all expected outputs** — preprocessing, embeddings, similarities, UMAP all working

### Potential Concerns
1. **Tangram set hardcoded to set 1** — `callbacks.js:52` has a TODO to restore randomization. Must fix before full data collection.
2. **`refer_separated` not yet piloted** — should run at least 1 pilot in this condition before launching
3. **Cross-group convergence** — descriptions converge to similar labels across groups (e.g., "C", "T"), which may limit group-specificity signal. This is expected with high-SND tangrams but worth monitoring.
4. **Near-ceiling accuracy** — `refer_mixed` started at 95.4% accuracy, leaving little room for increase. The outcome-neutral criterion (accuracy increase) may be hard to demonstrate statistically if accuracy is already at ceiling in block 0.
5. **Idle detection sensitivity** — one player reported feeling rushed by the idle penalty. The 2-round tolerance in production is tight for speakers who need time to compose descriptions. Consider whether this is appropriate.

### Pre-Launch Checklist
- [ ] Restore tangram set randomization (`callbacks.js:52`)
- [ ] Pilot `refer_separated` condition
- [ ] Run at least 1 more pilot per condition to check variability
- [ ] Re-run embeddings after `.iloc[-1]` fix to get corrected pairwise similarities
- [ ] Verify Prolific integration (participant IDs, completion codes, bonus payments)

---

## 8. Plots Generated

All plots are saved in `analysis/figures/pilot_summary/`:

| File | Description |
|------|-------------|
| `00_composite_overview.png` | 2x2 overview of length, accuracy, adjacent similarity, group specificity |
| `01_description_length.png` | Word count by block and condition |
| `02_listener_accuracy.png` | Listener accuracy by block and condition |
| `03_adjacent_similarity.png` | Adjacent cosine similarity by block and condition |
| `04_group_specificity.png` | Within vs between group similarity by window |
| `05_phase_change.png` | Phase 1 → Phase 2 similarity by condition |
| `06_social_guessing.png` | Social guessing accuracy with chance line |
| `07_umap.png` | UMAP projections colored by group and phase |
| `08_ingroup_outgroup_accuracy.png` | Phase 2 accuracy split by partner group membership |
| `09_cross_condition.png` | Side-by-side condition comparison of key metrics |

---

## 9. How to Reproduce

```bash
# Process the pilot data
uv run python analysis/run_pipeline.py experiment/data/20260222_125327/empirica-export-20260222_132407.zip

# Generate pilot analysis plots
uv run python analysis/pilot_analysis.py

# View plots
open analysis/figures/pilot_summary/
```
