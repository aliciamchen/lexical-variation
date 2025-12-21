# Todos for Experiment Migration (Old Prereg → New Prereg)

This document tracks the changes needed to migrate from the old prereg (8 players, 2 groups, within-subjects conditions) to the new prereg (9 players, 3 groups, between-subjects conditions).

---

## Overview of Key Changes

| Aspect | Old | New |
|--------|-----|-----|
| Players per game | 8 (2×4) | 9 (3×3) |
| Listeners per trial | 3 | 2 |
| Phase 1 blocks | 8 | 6 |
| Phase 2 | Production task | Continued ref game (12 blocks) |
| Phase 3 | Listener interpretation | Removed |
| Conditions | Within-subjects | Between-subjects |
| Scoring | $0.02/point | $0.05/point |

---

## Server Changes (`server/src/`)

### Constants (`constants.js`)

- [x] Change player count from 8 to 9
- [x] Change group count from 2 to 3
- [x] Change group size from 4 to 3
- [x] Update `names` array (need 9 player names instead of 8)
- [x] Update avatar system to use DiceBear API (no local files)
- [x] Add anonymous avatar generation for mixed conditions (grayscale)
- [x] Add experimental conditions constant: `["refer_separated", "refer_mixed", "social_mixed"]`
- [x] Update scoring constants:
  - [x] Change `bonus_per_point` from 0.02 to 0.05
  - [ ] Update base pay from $12 to $10
  - [ ] Update max bonus calculation ($5.40 max)
- [x] Update Phase 1 blocks from 8 to 6
- [x] Add Phase 2 blocks constant (12 blocks)
- [x] Remove old conditions array (`["social own", "refer own", "refer other"]`)
- [x] Add TEST_MODE flag for reduced player testing

### Callbacks (`callbacks.js`)

#### Game Initialization (`onGameStart`)

- [x] Update player assignment logic for 9 players in 3 groups
- [x] Add game-level condition setting (configurable at game creation)
- [x] Store `game.set("condition", ...)` for the between-subjects condition
- [x] Update group assignment (3 groups: "A", "B", "C" - no color distinction)
- [x] Adjust avatar assignment for 3 players per group
- [x] Store phase block counts for client display

#### Phase 1: Reference Game (Blocks 1-6)

- [x] Reduce Phase 1 to 6 blocks (each player speaks twice)
- [x] Update listener count from 3 to 2 per trial
- [x] Adjust speaker rotation (3 speakers × 2 rotations = 6 blocks)
- [x] Update scoring:
  - [x] Listener: 2 points for correct guess (was 3)
  - [x] Speaker: 1 point per correct listener (max 2)
- [x] Keep tangram randomization (6 tangrams per block)

#### Phase 2: Continued Reference Game (Blocks 7-18)

This is the major structural change. The old Phase 2 (production task) and Phase 3 (listener interpretation) are completely replaced.

##### Condition: `refer_separated`
- [x] Players stay in their originally assigned groups
- [x] Continue reference game as in Phase 1
- [x] Same speaker rotation pattern

##### Condition: `refer_mixed`
- [x] After Phase 1, shuffle group assignments randomly each block
- [x] Fully mask player identities:
  - [x] Assign new anonymous avatars each block
  - [x] Hide original group membership
  - [x] Players cannot identify others across blocks
- [x] Implement reshuffling logic
- [ ] Add transition screen before each reshuffling explaining new group assignment
- [ ] Ensure avatars are different after each reshuffling (unique seed per block)

##### Condition: `social_mixed`
- [x] Same interaction structure and identity masking as `refer_mixed`
- [x] Add social signaling question after tangram selection:
  - [x] Listeners guess: "Was the speaker in your original group?"
  - [x] Store guess per listener per trial
- [x] Additional scoring for social guessing:
  - [x] Listener: 2 points for correct group identification
  - [x] Speaker: 1 point per correct listener identification
- [x] No feedback given for social guessing responses
- [ ] Add transition screen before each reshuffling

#### Remove Old Phase 2 (Production Task)

- [x] Delete `createProductionRounds()` or equivalent logic
- [x] Remove production stage creation (18 trials with conditions)
- [x] Remove utterance collection per condition
- [x] Delete condition-specific trial setup

#### Remove Old Phase 3 (Listener Interpretation)

- [x] Delete `createComprehensionRounds()` or equivalent logic
- [x] Remove Phase 3 trial construction (36 trials)
- [x] Remove matched/unmatched speaker-recipient logic
- [x] Delete `clicked_tangram`, `clicked_group`, `clicked_ingroup` handling
- [x] Remove Phase 3 scoring calculations

#### Dropout Handling (NEW - Replace existing logic)

- [x] Remove old inactive player logic (2 consecutive non-submissions)
- [x] Implement new idle detection:
  - [x] Track idle rounds per player
  - [x] Remove player after 3 consecutive idle rounds
- [x] Implement group continuation rules:
  - [x] If 2 members of initial group remain active, continue
  - [x] If only 1 member remains (2 dropped), remove final member
- [x] Game continuation rules:
  - [x] Continue if at least 2 groups remain active
  - [x] Each active group must have at least 2 people

#### Stage Transitions

- [x] Update `onRoundStart` for new block/round structure
- [x] Update `onStageStart` for mixed conditions (group reassignment)
- [x] Update `onStageEnded` for new scoring
- [x] Add transition screen between Phase 1 and Phase 2 explaining next phase

---

## Client Changes (`client/src/`)

### Game Component (`Game.jsx`)

- [x] Update to handle new phase structure (Phase 1 + Phase 2 only)
- [x] Add condition-aware rendering
- [x] Update chat to use current_group (A, B, C) instead of red/blue
- [x] Chat uses masked identities in Phase 2 mixed conditions

### Task Router (`Task.jsx`)

- [x] Remove Production stage routing
- [x] Remove Comprehension stage routing
- [x] Keep Refgame for both phases
- [x] Add condition-specific UI elements for `social_mixed`
- [x] Handle inactive players and group disbanded states

### Stages

#### Refgame (`stages/Refgame.jsx`)

- [x] Adjust UI for 2 listeners instead of 3
- [x] Update player status cards layout for 3 players per group
- [x] Add social signaling question UI for `social_mixed` condition:
  - [x] After tangram selection, show "Was this speaker in your original group?"
  - [x] Yes/No buttons
  - [x] Only show in `social_mixed` condition during Phase 2
- [x] Use display_avatar and display_name for masked conditions
- [x] Fix block counter to show correct totals based on TEST_MODE
- [x] Fix feedback stage to not auto-advance
- [ ] Fix "waiting for other group" message in TEST_MODE (only 1 group exists)

#### Tangram (`components/Tangram.jsx`)

- [x] Update for current_group instead of red/blue
- [x] Handle social_mixed condition timing
- [x] Fix auto-submit logic to only run during Selection stage
- [ ] Add pointer cursor when hovering over tangrams
- [ ] Disable/gray out tangrams until listener is ready to click (after speaker sends message)

#### Remove Old Stages

- [x] Remove Production stage routing from Task.jsx
- [x] Remove Comprehension stage routing from Task.jsx
- [ ] Delete or archive `stages/Production.jsx` file
- [ ] Delete or archive `stages/Comprehension.jsx` file

#### Transition (`stages/Transition.jsx`)

- [x] Update transition text for new experiment structure
- [x] Add placeholder text for condition-specific instructions:
  - [x] `refer_separated`: [placeholder - continue with group]
  - [x] `refer_mixed`: [placeholder - shuffled groups, masked identities]
  - [x] `social_mixed`: [placeholder - shuffled + social guessing]
- [ ] Add transition screens before each reshuffling in mixed conditions (Phase 2)

### Profile (`Profile.jsx`)

- [x] Update score display for new point values
- [x] Show original group indicator
- [x] Consistent text color regardless of phase

### Components

#### Avatar (`components/Avatar.jsx`)

- [x] Remove group-based color distinction
- [x] Works with DiceBear API URLs
- [x] Supports both regular and anonymous avatars

#### Tangram (`components/Tangram.jsx`)

- [x] Works for both phases
- [x] Updated for current_group
- [ ] Add pointer/cursor style on hover
- [ ] Visual indication that tangram is not yet clickable (before speaker message)

### Intro/Exit (`intro-exit/`)

#### Introduction (`Introduction.jsx`) - FULL REWRITE

- [ ] Rewrite introduction to explain new experiment structure
- [ ] Part 1: Overview of tangram reference game
- [ ] Part 2: Explain groups of 3 (1 speaker, 2 listeners)
- [ ] Part 3: Phase 1 explanation (6 blocks within groups)
- [ ] Part 4: Phase 2 explanation (condition-dependent):
  - [ ] For `refer_separated`: Continue with same group
  - [ ] For `refer_mixed`: Groups will be shuffled
  - [ ] For `social_mixed`: Shuffled + guess speaker's group
- [ ] Part 5: Scoring and bonus explanation
- [ ] Update visual examples for 3-person groups

#### Comprehension Quiz

- [ ] Rewrite quiz questions for new experiment structure
- [ ] Remove questions about old Phase 2/3
- [ ] Add questions about:
  - [ ] Group size (3 people)
  - [ ] Number of listeners (2)
  - [ ] Phase structure
  - [ ] Scoring (2 points listener, 1 point speaker per correct)
  - [ ] Condition-specific questions (if applicable)

#### Exit Survey (`ExitSurvey.jsx`)

- [ ] Update to reflect new experiment
- [ ] Add condition-specific questions
- [ ] Update bonus display calculation

#### Consent (`Consent.jsx`)

- [ ] Update time estimate if changed
- [ ] Update compensation information ($10 base + up to $5.40 bonus)

---

## Data Collection Changes

### Player Data

- [x] Add `original_group` field (persists through mixing)
- [x] Track `current_group` (changes in mixed conditions)
- [x] Track `idle_rounds` for dropout handling
- [x] Store `original_name` and `original_avatar` for restoration

### Trial Data

- [x] Simplify to reference game data only
- [x] For `social_mixed`:
  - [x] Add `social_guess` (listener's guess of speaker group)
  - [x] Add `social_guess_correct` (was the guess correct)

### Remove Old Data Fields

- [x] Remove Phase 2 utterance collection by condition
- [x] Remove Phase 3 matched/unmatched fields
- [x] Remove condition-specific scores (`phase3score`)

---

## Configuration / Admin

- [x] Add game condition selection at batch creation (treatments.yaml)
- [x] Create treatment types for all 3 conditions (production + test mode)

---

## Testing Infrastructure

### Test Mode (Reduced Players)

- [x] Add `TEST_MODE` constant in `constants.js`
- [x] When `TEST_MODE = true`:
  - [x] Reduce players from 9 to 3 (1 group only)
  - [x] Reduce Phase 1 blocks from 6 to 2
  - [x] Reduce Phase 2 blocks from 12 to 4
- [x] Conditionally export constants based on `TEST_MODE`
- [x] Add console warning when running in test mode
- [ ] Fix "waiting for other group" message when only 1 group exists

### Unit Tests for Callbacks

- [ ] Set up Jest or similar test framework in `server/`
- [ ] Create `callbacks.test.js` with tests for:
  - [ ] `assignGroups()` - correct distribution of 9 players into 3 groups
  - [ ] `reshufflePlayers()` - proper mixing in mixed conditions
  - [ ] `calculateScore()` - scoring logic (2 pts listener, 1 pt speaker)
  - [ ] `assignAnonymousAvatars()` - avatar assignment in mixed conditions
  - [ ] `checkDropout()` - idle detection and group continuation rules
- [ ] Mock Empirica player/game/stage objects for testing
- [ ] Add npm script: `npm test` to run unit tests

---

## Testing Checklist (Manual)

- [x] Test with 3 players in TEST_MODE
- [x] Test Phase 1 (2 blocks in test mode) completion
- [x] Test `refer_separated` condition
- [x] Test `refer_mixed` condition with reshuffling
- [x] Test `social_mixed` condition with group guessing
- [x] Test scoring and bonus calculation
- [x] Test chat masking in Phase 2 mixed conditions
- [x] Test block counter shows correct totals
- [x] Test feedback stage waits for all players
- [ ] Test dropout handling:
  - [ ] Player removed after 3 idle rounds
  - [ ] Group continuation with 2 remaining
  - [ ] Final member removal when 2 drop
  - [ ] Game continuation with 2+ active groups
- [ ] Test all intro screens and quiz
- [ ] Test exit survey and debrief
- [ ] Test with 9 players (production mode)

---

## Remaining UI/UX Improvements

- [ ] Add transition screens before each reshuffling in mixed conditions
- [ ] Fix "waiting for other group" in TEST_MODE Phase 2 (only 1 group)
- [ ] Ensure anonymous avatars are unique per block (different each reshuffling)
- [ ] Add pointer cursor when hovering over clickable tangrams
- [ ] Visual feedback: tangrams should appear disabled/unclickable until speaker sends a message

---

## Design Decisions (Clarified)

- **No distinct group colors**: Groups should not be visually differentiated by color
- **Identity masking in mixed conditions**: Other players' identities are fully hidden
- **Anonymous avatars**: In mixed conditions, players get new anonymous avatars each block
- **Timer duration**: Same as Phase 1 for Phase 2 trials
- **Transition screens**: Use filler/placeholder text for now (to be written later)
- **DiceBear avatars**: Using identicon style (blue) for regular, shapes style (gray) for anonymous

---

## Migration Strategy

1. **Phase A**: Update constants and server logic for 9 players / 3 groups ✅
2. **Phase B**: Implement `refer_separated` condition ✅
3. **Phase C**: Implement `refer_mixed` condition with reshuffling ✅
4. **Phase D**: Implement `social_mixed` condition with group guessing ✅
5. **Phase E**: Replace dropout handling ✅
6. **Phase F**: Rewrite instructions and quiz (pending)
7. **Phase G**: Update scoring and bonus calculations ✅
8. **Phase H**: Clean up old Phase 2/3 code ✅
9. **Phase I**: Testing and validation ✅ (basic testing complete)

---

## Notes

- The new experiment focuses on testing whether social signaling goals can resist linguistic convergence when groups mix
- The old explicit goal conditions (social+own, refer+own, refer+other) are replaced by implicit social signaling incentives
- Phase 3 listener interpretation is completely removed - no post-hoc evaluation
- Data analysis will focus on emergent lexicons, group-specificity, and description length
