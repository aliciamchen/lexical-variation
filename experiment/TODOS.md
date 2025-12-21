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

## Remaining Todos (By Implementation Order)

### Phase 1: Quick Cleanup
- [ ] Delete or archive `stages/Production.jsx` file
- [ ] Delete or archive `stages/Comprehension.jsx` file
- [ ] Update base pay from $12 to $10
- [ ] Update max bonus calculation ($5.40 max)

### Phase 2: Core Functionality Fixes
- [ ] Fix "waiting for other group" message in TEST_MODE (only 1 group exists)
- [ ] Check reassignment is correct when speaker leaves (does it reassign someone else as speaker?)
- [ ] Ensure anonymous avatars are unique per block (different seed each reshuffling)

### Phase 3: Transition Screens
- [ ] Add transition screen before each reshuffling (5 second screen, no key press required)
- [ ] Write actual text for transition screens (explain reshuffling to participants)

### Phase 4: Participant-Facing Content
- [ ] Rewrite Introduction.jsx:
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
- [ ] Rewrite Comprehension Quiz:
  - [ ] Remove questions about old Phase 2/3
  - [ ] Add questions about group size (3 people)
  - [ ] Add questions about phase structure
  - [ ] Add questions about scoring (2 points listener, 1 point speaker)
  - [ ] Add condition-specific questions (if applicable)
- [ ] Update Consent.jsx:
  - [ ] Update time estimate
  - [ ] Update compensation information ($10 base + up to $5.40 bonus)
- [ ] Update ExitSurvey.jsx:
  - [ ] Update to reflect new experiment
  - [ ] Add condition-specific questions
  - [ ] Update bonus display calculation
- [ ] Create sorry/kicked-out pages:
  - [ ] Page for idle timeout (kicked for inactivity)
  - [ ] Page for group disbanded (other players left)
  - [ ] Write compensation messages and Prolific payment logic

### Phase 5: Testing
- [ ] Test dropout handling:
  - [ ] Player removed after 2 idle rounds
  - [ ] Group continuation with 2 remaining
  - [ ] Final member removal when 2 drop
  - [ ] Game continuation with 2+ active groups
- [ ] Test all intro screens and quiz
- [ ] Test exit survey and debrief
- [ ] Test with 9 players (production mode)
- [ ] Verify we have the data fields we need

### Phase 6: Nice-to-haves
- [ ] Update to the new tangrams from Ji et al. (2022)
- [ ] Reconsider original group indicator (maybe replace with something else?)
- [ ] Set up Jest unit tests for callbacks (optional)

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

## Completed Todos

### Server Changes (`server/src/`)

#### Constants (`constants.js`)
- [x] Change player count from 8 to 9
- [x] Change group count from 2 to 3
- [x] Change group size from 4 to 3
- [x] Update `names` array (9 player names)
- [x] Update avatar system to use DiceBear API
- [x] Add anonymous avatar generation for mixed conditions (grayscale)
- [x] Add experimental conditions constant
- [x] Change `bonus_per_point` from 0.02 to 0.05
- [x] Update Phase 1 blocks from 8 to 6
- [x] Add Phase 2 blocks constant (6 blocks)
- [x] Remove old conditions array
- [x] Add TEST_MODE flag for reduced player testing

#### Callbacks (`callbacks.js`)
- [x] Update player assignment logic for 9 players in 3 groups
- [x] Add game-level condition setting
- [x] Store `game.set("condition", ...)` for between-subjects condition
- [x] Update group assignment (3 groups: "A", "B", "C")
- [x] Adjust avatar assignment for 3 players per group
- [x] Store phase block counts for client display
- [x] Reduce Phase 1 to 6 blocks
- [x] Update listener count from 3 to 2 per trial
- [x] Adjust speaker rotation (3 speakers × 2 rotations)
- [x] Update scoring (2 pts listener, 1 pt speaker per correct)
- [x] Keep tangram randomization (6 tangrams per block)

#### Condition: `refer_separated`
- [x] Players stay in originally assigned groups
- [x] Continue reference game as in Phase 1
- [x] Same speaker rotation pattern

#### Condition: `refer_mixed`
- [x] Shuffle group assignments randomly each block
- [x] Fully mask player identities (anonymous avatars, hide group membership)
- [x] Implement reshuffling logic

#### Condition: `social_mixed`
- [x] Same interaction structure and identity masking as `refer_mixed`
- [x] Add social signaling question after tangram selection
- [x] Store guess per listener per trial
- [x] Listener: 2 points for correct group identification
- [x] Speaker: 1 point per correct listener identification
- [x] No feedback given for social guessing responses

#### Remove Old Phases
- [x] Delete `createProductionRounds()` logic
- [x] Remove production stage creation
- [x] Remove utterance collection per condition
- [x] Delete condition-specific trial setup
- [x] Delete `createComprehensionRounds()` logic
- [x] Remove Phase 3 trial construction
- [x] Remove matched/unmatched speaker-recipient logic
- [x] Delete `clicked_tangram`, `clicked_group`, `clicked_ingroup` handling
- [x] Remove Phase 3 scoring calculations

#### Dropout Handling
- [x] Remove old inactive player logic
- [x] Track idle rounds per player
- [x] Remove player after 2 consecutive idle rounds
- [x] If 2 members of initial group remain active, continue
- [x] If only 1 member remains, remove final member
- [x] Continue if at least 2 groups remain active
- [x] Each active group must have at least 2 people

#### Stage Transitions
- [x] Update `onRoundStart` for new block/round structure
- [x] Update `onStageStart` for mixed conditions
- [x] Update `onStageEnded` for new scoring
- [x] Add transition screen between Phase 1 and Phase 2

### Client Changes (`client/src/`)

#### Game Component (`Game.jsx`)
- [x] Update to handle new phase structure
- [x] Add condition-aware rendering
- [x] Update chat to use current_group (A, B, C)
- [x] Chat uses masked identities in Phase 2 mixed conditions

#### Task Router (`Task.jsx`)
- [x] Remove Production stage routing
- [x] Remove Comprehension stage routing
- [x] Keep Refgame for both phases
- [x] Add condition-specific UI elements for `social_mixed`
- [x] Handle inactive players and group disbanded states

#### Refgame (`stages/Refgame.jsx`)
- [x] Adjust UI for 2 listeners instead of 3
- [x] Update player status cards layout for 3 players per group
- [x] Add social signaling question UI for `social_mixed` condition
- [x] Use display_avatar and display_name for masked conditions
- [x] Fix block counter to show correct totals based on TEST_MODE
- [x] Fix feedback stage to not auto-advance

#### Tangram (`components/Tangram.jsx`)
- [x] Update for current_group instead of red/blue
- [x] Handle social_mixed condition timing
- [x] Fix auto-submit logic to only run during Selection stage
- [x] Add pointer cursor when hovering over tangrams

#### Transition (`stages/Transition.jsx`)
- [x] Update transition text for new experiment structure
- [x] Add placeholder text for condition-specific instructions

#### Profile (`Profile.jsx`)
- [x] Update score display for new point values
- [x] Show original group indicator
- [x] Consistent text color regardless of phase

#### Avatar (`components/Avatar.jsx`)
- [x] Remove group-based color distinction
- [x] Works with DiceBear API URLs
- [x] Supports both regular and anonymous avatars

### Data Collection
- [x] Add `original_group` field (persists through mixing)
- [x] Track `current_group` (changes in mixed conditions)
- [x] Track `idle_rounds` for dropout handling
- [x] Store `original_name` and `original_avatar` for restoration
- [x] Simplify to reference game data only
- [x] Add `social_guess` and `social_guess_correct` for social_mixed
- [x] Remove Phase 2/3 old data fields

### Configuration
- [x] Add game condition selection at batch creation (treatments.yaml)
- [x] Create treatment types for all 3 conditions

### Test Mode
- [x] Add `TEST_MODE` constant in `constants.js`
- [x] Reduce players from 9 to 3 (1 group only)
- [x] Reduce Phase 1 blocks from 6 to 2
- [x] Reduce Phase 2 blocks from 12 to 2
- [x] Conditionally export constants based on `TEST_MODE`
- [x] Add console warning when running in test mode

### Manual Testing (Completed)
- [x] Test with 3 players in TEST_MODE
- [x] Test Phase 1 (2 blocks in test mode) completion
- [x] Test `refer_separated` condition
- [x] Test `refer_mixed` condition with reshuffling
- [x] Test `social_mixed` condition with group guessing
- [x] Test scoring and bonus calculation
- [x] Test chat masking in Phase 2 mixed conditions
- [x] Test block counter shows correct totals
- [x] Test feedback stage waits for all players
