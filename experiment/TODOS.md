# Empirica experiment todos

This document tracks the changes needed to make the web experiment.

NOTE for claude: If you need it to figure out how to do something, the docs for empirica are here: https://docs.empirica.ly/ and the source code for empirica is at https://github.com/empiricaly/empirica

---

### Timing

| Stage       | Duration |
| ----------- | -------- |
| Selection   | 45s      |
| Feedback    | 10s      |
| Transitions | 30s      |

**Estimated Duration:**

- Test mode (2+2 blocks): ~15-20 min
- Production (6+6 blocks): ~30-45 min (plus intro/exit)

---

## Remaining Todos

### 1. Data Collection Improvements

- [x] For the chat, save timestamps of messages sent
  - [ ] I did this by changing the chunk-J6LPACOK.js file, see README.md for details. It works locally but we need to test it on the server.
- [x] In player rounds, also save whether clicked tangram was correct
- [ ] For the idle/reassignment cases, check that the reassigned groups are saved correctly in the data
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

### 5. Testing

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
- [ ] What happens when someone leaves in the middle of block? Should reassign to another speaker to finish the tangrams left to be described

#### Production Mode (9 players)

- [ ] Come up with a list of things to test for 9 players
- [ ] Is the idling logic working correctly?
- [ ] Check listener guessing speaker group logic

### 7. Optional / Nice-to-Have

- [ ] MAYBE: Let games start if there are fewer than 9 people in the waiting room
- [ ] MAYBE: Set up Jest unit tests for callbacks

---

## Completed

### Design Decisions

- **No distinct group colors**: Groups should not be visually differentiated by color
- **Identity masking in mixed conditions**: Other players' identities are fully hidden
- **Anonymous avatars**: In mixed conditions, players get new anonymous avatars each block
- **Timer duration**: Selection 45s, Feedback 10s, Transitions 30s
- **DiceBear avatars**: Using identicon style (blue) for regular, shapes style (gray) for anonymous

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
