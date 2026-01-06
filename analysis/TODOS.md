
## B2. Outcome-Neutral Criteria (from RR - MUST pass before full data collection)

These must be satisfied before running the main experiment:

- [ ] **Description length decreases over blocks** (Phase 1)
  - Model: `utt_length ~ rep_num + (rep_num | participant) + (rep_num | group) + (rep_num | tangram)`
  - Require: significant negative main effect of rep_num
- [ ] **Listener accuracy increases over blocks** (Phase 1)
  - Model: `ref_accuracy ~ rep_num + (rep_num | group) + (rep_num | tangram)`
  - Require: significant positive main effect of rep_num
- [ ] **Conventions are stable** (increasing cosine similarity between successive utterances)
  - Model: `sim_adjacent ~ rep_num + (rep_num | participant) + (rep_num | group) + (rep_num | tangram)`
  - Require: significant positive main effect of rep_num
- [ ] **Group-specificity scores at end of Phase 1 exceed chance levels**
  - Permutation test: permute group assignment 1000 times, compare observed to null
  - Require: at least 80% of games (16/20 per condition) show significant group-specificity (p < .05)

## B3. Analysis Pipeline Setup

- [ ] Set up SBERT embedding generation (paraphrase-MiniLM-L12-v2 model)
- [ ] Compute pairwise cosine similarities between utterances
- [ ] Implement group-specificity metric calculation
  - Formula: `similarity ~ same_group + (1 | tangram) + (1 | participant_pair)`
  - Extract coefficient for same_group as group-specificity score
- [ ] Set up lmer/lmerTest models in R

## B4. Post-Hoc Exclusion Criteria (applied during analysis)

- [ ] Flag groups where <2/3 participants achieved <2/3 accuracy during last 3 blocks of Phase 1
- [ ] Post-hoc inspection: Flag inappropriate, adversarial, or task-irrelevant messages
- [ ] MAYBE: LLM-based classifier to filter out non-referential messages (e.g., "thanks", "good job") for analysis

## B5. Pilot Report

- [ ] Report completion rates
- [ ] Report session duration
- [ ] Report technical issues (if any)
- [ ] Visualize description length over blocks
- [ ] Visualize listener accuracy over blocks
- [ ] Report group-specificity results
- [ ] Go/no-go decision for full data collection