# Todos for Experiment Migration (Old Prereg → New Prereg)

This document tracks the changes needed to migrate from the old prereg (8 players, 2 groups, within-subjects conditions) to the new prereg (9 players, 3 groups, between-subjects conditions).

---

## Overview of Key Changes

| Aspect | Old | New |
|--------|-----|-----|
| Players per game | 8 (2×4) | 9 (3×3) |
| Listeners per trial | 3 | 2 |
| Phase 1 blocks | 8 | 6 |
| Phase 2 | Production task | Continued ref game (6 blocks) |
| Phase 3 | Listener interpretation | Removed |
| Conditions | Within-subjects | Between-subjects |
| Scoring | $0.02/point | $0.05/point |

### Timing Configuration

| Stage | Duration |
|-------|----------|
| Selection | 45s |
| Feedback | 10s |
| Transitions | 30s |

**Estimated Duration:**
- Test mode (2+2 blocks): ~15-20 min
- Production (6+6 blocks): ~30-45 min (plus intro/exit)

---

## Remaining Todos

### 1. Data Collection Improvements
- [ ] For the chat, save timestamps of messages sent
- [ ] In player rounds, also save whether clicked tangram was correct
- [ ] For the idle/reassignment screens, check that the reassigned groups are saved correctly in the data
- [ ] Verify we have the data fields we need

### 2. Transition Screens
- [ ] Add transition screen before each reshuffling (5 second screen, no key press required)
- [ ] Write actual text for transition screens (explain reshuffling to participants)
- [ ] Fix scaling and styling of transition screens

### 3. Participant-Facing Content

#### Consent.jsx
- [ ] Update time estimate
- [ ] Update compensation information ($10 base + up to $5.40 bonus)

#### Introduction.jsx
- [ ] Part 1: Overview of tangram reference game
- [ ] Part 2: Explain groups of 3 (1 speaker, 2 listeners)
- [ ] Part 3: Phase 1 explanation (6 blocks within groups)
- [ ] Part 4: Phase 2 explanation (condition-dependent):
  - [ ] For `refer_separated`: Continue with same group
  - [ ] For `refer_mixed`: Groups will be shuffled
  - [ ] For `social_mixed`: Shuffled + guess speaker's group
- [ ] Part 5: Scoring and bonus explanation
- [ ] Update visual examples for 3-person groups
- [ ] Explain tangrams not clickable until speaker sends message

#### Comprehension Quiz
- [ ] Remove questions about old Phase 2/3
- [ ] Add questions about group size (3 people)
- [ ] Add questions about phase structure
- [ ] Add questions about scoring (2 points listener, 1 point speaker)
- [ ] Add condition-specific questions (if applicable)

#### ExitSurvey.jsx
- [ ] Update to reflect new experiment
- [ ] Add condition-specific questions
- [ ] Update bonus display calculation
- [ ] Update base pay from $12 to $10
- [ ] Update max bonus calculation ($5.40 max)

#### Kicked-Out Pages
- [ ] Page for idle timeout (kicked for inactivity)
- [ ] Page for group disbanded (other players left)
- [ ] Write compensation messages and Prolific payment logic

### 4. UI/UX Polish
- [ ] If someone in a group leaves, indicate to participants that the group is now smaller because someone left or idled
- [ ] For the icons for who picked what tangram, add a bit of space between them when they are stacked
- [ ] If speaker is idle and listeners aren't able to select, in the feedback indicate that the speaker was idle
- [ ] Check that in mixed conditions the icons are different each time so people don't know who they are talking to

### 5. Dropout Edge Cases
- [ ] What happens when someone leaves in the middle of block? Should reassign to another speaker to finish the tangrams left to be described

### 6. Testing

#### Test Mode (3 players)
- [ ] Check data is saving correctly
- [ ] Test all intro screens and quiz
- [ ] Test exit survey and debrief
- [ ] Generally check timing
- [ ] Check that on admin dashboard, the game marks finished when all players have finished

#### Dropout Testing
- [ ] Player removed after 2 idle rounds
- [ ] Group continuation with 2 remaining
- [ ] Final member removal when 2 drop
- [ ] Game continuation with 2+ active groups

#### Production Mode (9 players)
- [ ] Come up with a list of things to test for 9 players
- [ ] Is the idling logic working correctly?

### 7. Optional / Nice-to-Have
- [ ] MAYBE: Let games start if there are fewer than 9 people in the waiting room
- [ ] Set up Jest unit tests for callbacks

---

## Design Decisions

- **No distinct group colors**: Groups should not be visually differentiated by color
- **Identity masking in mixed conditions**: Other players' identities are fully hidden
- **Anonymous avatars**: In mixed conditions, players get new anonymous avatars each block
- **Timer duration**: Selection 45s, Feedback 10s, Transitions 30s
- **DiceBear avatars**: Using identicon style (blue) for regular, shapes style (gray) for anonymous

---

## Notes

- The new experiment focuses on testing whether social signaling goals can resist linguistic convergence when groups mix
- The old explicit goal conditions (social+own, refer+own, refer+other) are replaced by implicit social signaling incentives
- Phase 3 listener interpretation is completely removed - no post-hoc evaluation
- Data analysis will focus on emergent lexicons, group-specificity, and description length

---

## Completed

### Server (`server/src/`)
- Constants: 9 players, 3 groups of 3, TEST_MODE toggle, DiceBear avatars, updated scoring ($0.05/point)
- Callbacks: Player/group assignment, condition handling, Phase 1+2 structure, speaker rotation, reshuffling
- Conditions: `refer_separated` (same groups), `refer_mixed` (shuffled + masked), `social_mixed` (shuffled + group guessing)
- Removed: Old Phase 2 production, Phase 3 comprehension, old scoring
- Dropout: Idle tracking, removal after 2 rounds, group viability checks, MIN_GROUP_SIZE=2
- Idle detection: Only during Selection stage; speakers idle if no message, listeners idle if no message AND no click

### Client (`client/src/`)
- Game.jsx: Phase-aware rendering, chat per group (A/B/C), masked identities in Phase 2 mixed
- Task.jsx: Refgame + Transition routing, inactive player handling
- Refgame.jsx: 2 listeners UI, social guessing for `social_mixed`, display_avatar/display_name
- Tangram.jsx: Auto-submit logic, click handling
- Profile.jsx: Score display, original group indicator
- Avatar.jsx: DiceBear API support

### Data Collection
- Fields: original_group, current_group, idle_rounds, display_avatar/name, social_guess

### Configuration
- treatments.yaml: 3 condition treatments
- TEST_MODE: 3 players, 1 group, 2+2 blocks

### Manual Testing Completed
- Phase 1 + Phase 2 for all 3 conditions
- Reshuffling (round-robin, uneven players)
- Speaker rotation, scoring, chat masking, block counter, feedback timing
