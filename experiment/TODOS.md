# Empirica experiment todos

This document tracks the changes needed to make the web experiment.

NOTE for claude: If you need it to figure out how to do something, the docs for empirica are here: https://docs.empirica.ly/ and the source code for empirica is at https://github.com/empiricaly/empirica

To test the experiment, use the test-experiment skill. 
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

- [x] remove social guessing feedback, change to aggregated social feedback at the end of the experiment, and change that in the instructions too
  - Per-trial feedback removed from Refgame.jsx
  - Aggregated summary shown at end in Transition.jsx (bonus_info stage)
  - Tracks: social_guess_total, social_guess_correct_total, social_guessed_about_total, social_guessed_about_correct
- [x] in phase 2 anonymous condition instead of player numbers just say "Player" so that it's fully anonymous
  - Changed from "Player 1", "Player 2" to just "Player" in callbacks.js

- [x] test cumulative social guesses are saved correctly
  - Verified via 9-player social_mixed test: 26 rows with social_guess data
  - Fields saved: social_guess, social_guess_correct (True/False), social_round_score (0/1/2 points)
- [ ] set and check final constants: money, timing, etc (revert to the non-testing timing)
- [ ] check completion codes are correct and that they are indicated correctly on prolific
- [x] Check that the waiting for other players submit and waiting for your group members to submit screens, are displaying correctly in the 9 person case
  - Verified with 9-player refer_mixed test (2026-01-07):
  - "Waiting for the players in your group to respond..." - shown when group members haven't finished
  - "All players in group responded! Waiting for members of other groups to respond..." - shown when group finished but other groups haven't
  - Screenshots: waiting_screen_speaker_view.png, waiting_screen_multi_group.png
- [ ] When all is ready, switch to final version with all correct timing + lobby config, and then run once using playwright and then test once manually to make sure everything is working correctly.
- [ ] for later (i need to do manually): set up digitalocean server and figure out billing
- [ ] also for later: get IRB approval from mitchell
- [x] make avatars squares, why are they circles
  - **FIXED** (2026-01-07): Changed border-radius from 50% to 6px in index.css:
  - `.player img` (line 196) - group member avatars in game
  - `.feedback img` (line 104) - feedback avatars on tangrams
  - Added `img.rounded-full { border-radius: 6px !important; }` to override Empirica chat avatars
  - Screenshots: avatar_squares_test.png, chat_avatar_square_test.png


- [x] IMPORTANT: make sure the shuffling is happening on each trial in the mixed conditions and that participants know this. Indicate in feedback screens in phase 2, that shuffling is happening each time. Check text, make sure it's clear, say that we are masking group identities
  - Verified: Server logs show "Reshuffling groups for mixed condition (balanced)" on each round
  - Transition screen explains reshuffling and masked identities clearly

# Phase A: Running the Experiment & Collecting Pilot Data

These todos must be completed before collecting pilot data.

## A1. Stimuli & Game Setup

- [x] Add another tangram set. Decide how many tangram sets?
  - [x] Check kilogram dashboard to make sure that the tangrams don't have *too* geometric descriptions (high SND tangrams preferred)
  - [x] Verify each game is assigned to one of the two tangram sets (random 50/50 assignment)
  - Set 0: page1-129, page3-121, page3-182, page4-157, page6-149, page7-81 (SND: 0.960-0.987)
  - Set 1: page3-85, page3-136, page5-64, page9-46, page9-27, page1-128 (SND: 0.978-0.987)
- [x] Tangram grid order should be randomized across participants (to prevent spatial descriptions like "top left")
  - Each player gets their own `shuffled_tangrams` array via `_.shuffle(context)`
- [x] Check rotation of speakers across conditions
  - [x] Implemented balanced reshuffling: each reshuffled group gets one player from each `original_player_index` (0, 1, 2)
  - [x] Speaker rotation uses `blockNum % GROUP_SIZE` matching player's `player_index`
  - [x] Fallback for incomplete groups (due to dropouts) picks speaker based on position
  - [x] Test file: `server/src/test_reshuffling.js` verifies the logic

## A2. Data Collection (what gets saved)

- [x] For the chat, save timestamps of messages sent
  - [x] Verified locally: chat messages include `timestamp` field in JSON
  - [ ] Need to test on production server (chunk-J6LPACOK.js modification)
- [x] In player rounds, also save whether clicked tangram was correct (`clicked_correct` field added)
- [x] For the idle/reassignment cases, check that the reassigned groups are saved correctly in the data
  - Verified: `current_group` changes correctly in Phase 2 mixed conditions, `original_group` preserved
- [x] Verify the following fields are being saved:
  - [x] Speaker utterances (all messages per trial) → `player.round.chat`
  - [x] Block/repetition number → `player.round.block_num`
  - [x] Phase number (1 or 2) → `player.round.phase_num`
  - [x] Tangram identity (which tangram is target) → `player.round.target`
  - [x] Original group (A, B, C) → `player.round.original_group`
  - [x] Current group (for mixed conditions) → `player.round.current_group`
  - [x] Listener selections + correctness → `player.round.clicked` + `player.round.clicked_correct`
  - [x] Social guessing responses (social_mixed only) → `player.round.social_guess` + `player.round.social_guess_correct`
  - [x] Player role (speaker/listener) per round → `player.round.role`

## A3. Participant-Facing Content

### Consent.jsx

- [x] Update time estimate (30-45 minutes)
- [x] Update compensation information ($10 base + up to $5.40 bonus)

### Introduction.jsx

- [x] Part 1: Overview of tangram reference game
- [x] Part 2: Explain groups of 3 (1 speaker, 2 listeners)
- [x] Part 3: Phase 1 explanation (6 blocks within groups)
- [x] Part 4: Phase 2 explanation (deferred to Transition.jsx for condition-specific):
  - [x] For `refer_separated`: Continue with same group
  - [x] For `refer_mixed`: Groups will be shuffled
  - [x] For `social_mixed`: Shuffled + guess speaker's group
- [x] Part 5: Scoring and bonus explanation
- [x] Update visual examples for 3-person groups
- [x] Explain tangrams not clickable until speaker sends message
- [x] Instruction: Restrict chat to tangram-related discussion only (no discussing group identity or using codewords)

### Comprehension Quiz

- [x] Remove questions about old Phase 2/3
- [x] Add questions about group size (3 people)
- [x] Add questions about phase structure (indirectly via intro)
- [x] Add questions about scoring (2 points listener, 1 point speaker)
- [x] Add question about listeners waiting for speaker
- [x] Implement 3-attempt limit, show failure message after 3 failed attempts

### ExitSurvey.jsx

- [x] Update to reflect new experiment
- [x] Update bonus display calculation (shows actual score and bonus)
- [x] Update base pay from $12 to $10
- [x] Shows total compensation

### Kicked-Out Pages

- [x] Page for idle timeout (kicked for inactivity) - Sorry.jsx updated
- [x] Page for group disbanded (other players left) - Sorry.jsx updated
- [x] Page for lobby timeout - Sorry.jsx updated
- [x] Different Prolific codes for each termination reason

## A4. Transition Screens

- [x] Transition screen between Phase 1 and Phase 2 with condition-specific instructions
- [x] Write actual text for transition screens (explain reshuffling to participants)
  - Updated Transition.jsx with proper text (removed placeholders)
  - refer_separated: "same group members"
  - refer_mixed: "mixed together", "Player" with anonymous avatars
  - social_mixed: Explains social guessing task
- [ ] Fix scaling and styling of transition screens

## A5. Waiting Room & Game Start Logic

- [ ] Waiting room timeout: 5 minutes max, then remove and compensate $2, there should be a compensation code for this
- [ ] [CHECK WITH ROBERT AND REBECCA] Games can start with 6+ members (prioritize 9-player games)? Should we do this? 
- [ ] If above: Check that the groups are formed correctly for uneven player counts (6, 7, 8 players) - how are groups formed?

## A6. In-Game Exclusion Criteria (automated)

- [x] Remove participants who fail comprehension quiz after 3 attempts
  - Quiz.jsx shows failure message with Prolific code after 3 failed attempts
- [x] Idle for 2 consecutive rounds → remove participant
  - Implemented in `onStageEnded`: speakers idle if no message, listeners idle if no message AND no click
  - After `MAX_IDLE_ROUNDS` (2), player marked `is_active=false`, `ended="player timeout"`

## A7. Social Guessing Logic (social_mixed only)

- [x] Social guessing implemented (per-trial, confirmed correct)
  - Listeners guess after EACH trial (tangram) in Phase 2
- [x] Scoring: Listeners get 2 points for correct social guess (`SOCIAL_GUESS_CORRECT_POINTS = 2`)
- [x] Scoring: Speakers get 1 point for each correct listener social guess (`SOCIAL_SPEAKER_POINTS_PER_CORRECT = 1`)
- [x] Social guessing UI appears after listener clicks tangram (in Refgame.jsx)
- [x] Social guessing data saved: `player.round.social_guess` and `player.round.social_guess_correct`

## A8. Phase 2 & Dropout Logic

- [x] Verify dropout rule is the same for Phase 1 and Phase 2:
  - [x] Each original group needs at least 2 active members (`MIN_GROUP_SIZE=2`)
  - [x] Game continues as long as at least 2 original groups meet this requirement (`MIN_ACTIVE_GROUPS=2`)
  - [x] Viability check uses `original_group`, not `current_group` (correct for mixed conditions)
  - [x] Remaining member removed with `ended="group disbanded"` when group becomes non-viable
- [x] Speaker role reassignment when someone drops mid-block
  - **IMPLEMENTED AND TESTED** (2026-01-07):
  - Removed dead code that auto-submitted listeners when speaker kicked
  - Added explicit speaker reassignment via fallback logic in onRoundStart
  - Server logs: "SPEAKER REASSIGNMENT: Original speaker (index 0) not available → Reassigning to Player (index 1)"
  - Fixed idle detection: listeners NOT kicked when speaker didn't send message (not their fault)
  - Client shows "Your group's speaker was removed. A new speaker will be assigned next round." 

## A9. UI/UX Polish

- [x] If someone in a group leaves, indicate to participants that the group is now smaller because someone left or idled
  - Added message in Refgame.jsx: "Your group is smaller because a player left or was inactive."
- [x] For the icons for who picked what tangram, add a bit of space between them when they are stacked
  - Updated index.css: .feedback has display:flex, gap:4px, flex-wrap:wrap
- [x] If speaker is idle and listeners aren't able to select, in the feedback indicate that the speaker was idle
  - Added check in Refgame.jsx feedback: "The speaker did not send a message this round. No points were awarded."
- [x] Check that in mixed conditions the icons are different each time so people don't know who they are talking to
  - Verified: Anonymous avatars use different seeds per block (e.g., `anon_block0_player1`, `anon_block1_player2`)

## A10. Testing (before pilot)

### Test Mode (3 players)

- [x] Check data is saving correctly (verified via 9-player automated test export)
- [ ] Test all intro screens and quiz
- [ ] Check that quiz data is saved correctly
- [ ] Test exit survey and debrief
- [x] Check that on admin dashboard, the game marks finished when all players have finished
- [x] Is the idling logic working correctly?
- [x] Check listener guessing speaker group logic (UI and data fields verified; needs human testing for actual button clicks)

### Dropout Testing

- [x] Player removed after 2 idle rounds
- [x] Group continuation with 2 remaining
    - [x] Check in this case the rotation works correctly (i.e. the remaining speakers just end up alternating block after block)
      - Verified: speaker fallback uses `blockNum % sortedPlayers.length` for remaining players
- [x] Check dropout rules make sense and work, with the reshuffling logic in the mixed conditions
  - Verified: 9-player test with dropout showed reshuffling adapted (9→8 players, groups became 3,3,2)
- [x] Final member removal when 2 drop
- [x] Game continuation with 2+ active groups
- [x] Check that when someone leaves in the middle of block, the speaker is reassigned to the next player in the group and they finish up the block and then do the next block.
  - Verified: See A8 speaker role reassignment item above 

## A11. External/Logistics

- [ ] Figure out appointment slot thing (do this externally, this isn't a change in the code.) - Use Optimeet for scheduling

---

# Phase B: Pilot Data Analysis & Go/No-Go Decision 
These todos are for after collecting pilot data, to verify the outcome-neutral criteria before running the full sample.

## B1. Data Export & Verification

- [x] Verify Empirica export contains all required fields
  - Verified: game.csv, player.csv, round.csv, playerRound.csv, stage.csv all contain expected fields
- [x] Check that condition assignment is correctly logged
  - Verified: game.csv contains `condition` field (e.g., "social_mixed")
- [x] Verify speaker utterances are captured per trial
  - Verified: playerRound.csv `chat` field contains JSON with text, timestamp, and sender info
- [x] Verify in-group vs out-group speaker-listener relationships can be computed from exported data
  - Verified: playerRound.csv contains both `original_group` and `current_group` fields

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

### Automated Testing Completed (2026-01-06)

- 9-player social_mixed game via Playwright MCP
- Verified data export: game.csv, player.csv, round.csv, playerRound.csv, stage.csv
- Verified chat messages saved with timestamps
- Verified Phase 2 identity masking (Player 1-9 names, anonymous avatars)
- Verified group reshuffling with balanced composition
- Verified dropout handling (idle detection, group viability checks)
- Note: Social guess buttons not clicked during automated test (data fields exist and are wired up correctly)

### Automated Testing Completed (2026-01-07)

- **Full 9-player social_mixed test** via Playwright MCP:
  - ✅ Phase 1 completion (2 blocks)
  - ✅ Phase 2 reshuffling: "Reshuffled 9 players into 3 groups (3 complete)"
  - ✅ Masked identities: "Player (You)", "Player (Listener)" shown in UI
  - ✅ Anonymous avatars: shapes/svg style used in Phase 2
  - ✅ Social guessing UI: Group buttons appear after tangram click
  - ✅ Social guess data saved: 26 rows with social_guess, social_guess_correct, social_round_score
  - ✅ Speaker dropout tested: "SPEAKER KICKED: Group A has 2 remaining players"
  - ✅ Speaker reassignment: "SPEAKER REASSIGNMENT: Original speaker (index 0) not available → Reassigning to Player (index 1)"
  - ✅ Adaptive reshuffling: 8 players distributed into 3,3,2 groups after dropout
  - ✅ Idle detection fix: Listeners NOT kicked when speaker didn't send message
- Screenshots captured: phase2_transition_social_mixed.png, phase2_masked_identities.png, phase2_social_guessing_ui.png

---

## Bugs Found in Testing (2026-01-07)

### Fixed Bugs

- [x] **Role display bug (Groups B and C)** - **FIXED**: Was caused by TEST_MODE/treatment mismatch. Now GROUP_COUNT and MIN_ACTIVE_GROUPS are derived dynamically from actual player count in callbacks.js (lines 92-99).
  - **Fix applied**: Removed PLAYER_COUNT, GROUP_COUNT, MIN_ACTIVE_GROUPS from TEST_MODE dependency in constants.js
  - **New behavior**: `actualGroupCount = Math.floor(players.length / GROUP_SIZE)` derives group count from actual players

- [x] **TEST_MODE/treatment mismatch** - **FIXED**: TEST_MODE now only controls timing and tolerance settings, not player/group counts.
  - Player count is set in treatments.yaml
  - Group count is derived from `players.length / GROUP_SIZE` in callbacks.js
  - MIN_ACTIVE_GROUPS is set dynamically: 2 for multi-group games, 1 for single-group

### Verified Working

- [x] Speaker sends message → Listeners can click tangrams
- [x] Feedback screen shows "Ooops, that wasn't the target!" for wrong answer
- [x] Feedback screen shows "The speaker did not send a message this round. No points were awarded." for idle speaker
- [x] Feedback shows player avatar icons for who clicked what
- [x] "Waiting for the players in your group to respond..." message appears after clicking
- [x] Game auto-progresses when all group members respond
- [x] Roles display correctly in Group A (speaker's view and listener's view)
- [x] Chat messages appear with timestamps
- [x] **9-player game with dynamic group count**: Server correctly derives 3 groups from 9 players
- [x] **Roles display correctly in ALL groups**: Groups A, B, and C all show correct speaker/listener labels
- [x] **Multi-group waiting message**: Shows "Waiting for members of other groups to respond..." (not just "All players responded!")
- [x] **Idle detection works across all groups**: Players marked idle correctly regardless of group
- [x] **Chat role indicators**: Added "(Speaker)" or "(Listener)" labels next to player names in chat
  - Patched Empirica Chat component in chunk-J6LPACOK.js to accept `customPlayerName` prop
  - Game.jsx passes function that returns name + role label
  - Works in both Phase 1 (regular names) and Phase 2 mixed conditions (masked names)
  - Screenshots: chat_role_indicator_speaker.png, chat_role_indicator_listener.png
- [x] **Phase 2 avatar and chat verification** (2026-01-07):
  - Avatars remain square (not circular) in Phase 2 with anonymous shapes style
  - Chat role indicators work with masked "Player" name: "Player (Speaker)" and "Player (Listener)"
  - Group display shows masked identities: "Player (You)", "Player (Speaker)", "Player (Listener)"
  - Screenshots: phase2_masked_identities_test.png, phase2_chat_role_indicator.png, phase2_chat_both_roles.png
