# Systematic Test Plan for Lexical Variation Experiment

This document outlines comprehensive tests for the final version of the experiment before piloting. Tests are designed to cover normal participant behavior, edge cases, and various failure modes.

---

## Test Configuration

Before running tests, ensure:
- `TEST_MODE = false` in `constants.js` (or use production settings)
- Timeouts may need to be extended for Playwright automation
- Clear `tajriba.json` before each test session

---

## 1. Happy Path Tests (Full Completion)

### 1.1 `refer_separated` - 9 Players Complete Game
**Goal:** Verify basic game flow when all players complete without issues

**Setup:** 9 players, `refer_separated` condition

**Actions:**
- [ ] All 9 players join and pass comprehension quiz
- [ ] Complete Phase 1 (6 blocks): each group plays independently
- [ ] Transition screen shows correct condition-specific text
- [ ] Complete Phase 2 (6 blocks): groups remain the same
- [ ] All players reach exit survey and submit

**Verify:**
- [ ] Each player is speaker twice in Phase 1, twice in Phase 2
- [ ] Groups A, B, C remain unchanged throughout
- [ ] Chat messages display with role indicators "(Speaker)" / "(Listener)"
- [ ] Feedback shows correct/incorrect with avatar icons
- [ ] Scores accumulate correctly (2 pts listener correct, 1 pt speaker per correct)
- [ ] Final bonus calculated correctly ($0.05 per point)
- [ ] Completion code displayed correctly
- [ ] All data fields saved (see Data Verification section)

---

### 1.2 `refer_mixed` - 9 Players Complete Game
**Goal:** Verify group reshuffling and identity masking in Phase 2

**Setup:** 9 players, `refer_mixed` condition

**Actions:**
- [ ] All 9 players complete Phase 1 normally
- [ ] Transition screen explains reshuffling and masked identities
- [ ] Complete Phase 2 with reshuffling at each block boundary

**Verify:**
- [ ] Phase 2: Identities masked as "Player" (not "Player 1", etc.)
- [ ] Phase 2: Anonymous avatars (shapes style, gray) change each block
- [ ] Phase 2: `current_group` changes while `original_group` preserved
- [ ] Phase 2: Reshuffling happens only at block boundaries (every 6 rounds)
- [ ] Phase 2: Each reshuffled group has one player from each original group (balanced)
- [ ] Phase 2: Speaker rotation follows same schedule as separated condition
- [ ] Chat shows "Player (Speaker)" / "Player (Listener)" in Phase 2
- [ ] No social guessing UI appears (this is refer-only)

---

### 1.3 `social_mixed` - 9 Players Complete Game
**Goal:** Verify social guessing task and scoring in addition to reshuffling

**Setup:** 9 players, `social_mixed` condition

**Actions:**
- [ ] Complete Phase 1 normally
- [ ] Transition screen explains social guessing task
- [ ] Complete Phase 2 with social guessing after each tangram selection

**Verify:**
- [ ] Social guessing UI appears after listener clicks tangram
- [ ] Social guess options: "Same group as me" vs "Different group"
- [ ] Social guess data saved: `social_guess`, `social_guess_correct`
- [ ] No per-trial feedback for social guessing (only aggregated at end)
- [ ] Bonus info stage shows aggregated social guessing performance
- [ ] Social scoring: 2 pts for correct listener guess, 1 pt for speaker per correct guess
- [ ] Total score includes both referential and social points

---

## 2. Chat and Communication Tests

### 2.1 Speaker Sends Description, Listeners Click
**Goal:** Test basic communication flow

**Setup:** Any condition

**Actions:**
- [ ] Speaker sends a description message
- [ ] Listeners receive message and can click tangrams

**Verify:**
- [ ] Tangrams become clickable ONLY after speaker sends message
- [ ] Message appears in chat for all group members
- [ ] Role indicator shows "(Speaker)" next to sender name
- [ ] Timestamp displays correctly (5-second increments, not all "now")

---

### 2.2 Listener Sends Messages (Back-and-Forth Chat)
**Goal:** Test that listeners can communicate in chat

**Setup:** Any condition

**Actions:**
- [ ] Speaker sends initial description
- [ ] Listener sends clarifying question (e.g., "the one with arms?")
- [ ] Speaker responds
- [ ] Listeners click tangrams

**Verify:**
- [ ] Listener messages appear in chat
- [ ] Listener messages show "(Listener)" role indicator
- [ ] All group members see all messages
- [ ] Messages saved with correct sender info
- [ ] Timestamps accurate for all messages

---

### 2.3 Multiple Messages Per Round
**Goal:** Verify chat handles multiple messages

**Setup:** Any condition

**Actions:**
- [ ] Speaker sends 3+ messages describing tangram
- [ ] Listeners respond

**Verify:**
- [ ] All messages saved in order
- [ ] Chat scrolls/displays all messages
- [ ] No message loss or duplication

---

### 2.4 Chat in Phase 2 Mixed Conditions
**Goal:** Verify chat works with masked identities

**Setup:** `refer_mixed` or `social_mixed`

**Actions:**
- [ ] Chat during Phase 2 with masked identities

**Verify:**
- [ ] Sender names show as "Player" (masked)
- [ ] Role indicators still work: "Player (Speaker)", "Player (Listener)"
- [ ] Anonymous avatars appear correctly in chat
- [ ] Messages attributed to correct (masked) sender

---

## 3. Dropout and Attrition Tests

### 3.1 Single Player Idle (Speaker) - Kicked After 2 Rounds
**Goal:** Test idle detection and removal for speakers

**Setup:** 9 players, any condition

**Actions:**
- [ ] In Phase 1, one speaker sends no messages for 2 consecutive rounds
- [ ] Other players in group wait for timeout

**Verify:**
- [ ] After round 1: `idle_rounds` increments to 1
- [ ] After round 2: Player marked `is_active=false`, `ended="player timeout"`
- [ ] Idle player sees Sorry.jsx with correct message and Prolific code
- [ ] Idle player receives NO compensation
- [ ] Feedback screen shows "The speaker did not send a message this round"
- [ ] Remaining 2 players in group continue
- [ ] Speaker role reassigned for remaining rounds in block

---

### 3.2 Single Player Idle (Listener) - Kicked After 2 Rounds
**Goal:** Test idle detection for listeners

**Setup:** 9 players, any condition

**Actions:**
- [ ] Speaker sends message normally
- [ ] One listener sends no message AND clicks no tangram for 2 rounds

**Verify:**
- [ ] Listener kicked after 2 idle rounds
- [ ] Other listener who did respond is NOT kicked
- [ ] Game continues with 2 players in that group
- [ ] Listener who just didn't click but DID send a message: verify behavior

---

### 3.3 Listener NOT Kicked When Speaker Idles
**Goal:** Listeners shouldn't be penalized when speaker fails to send message

**Setup:** 9 players, any condition

**Actions:**
- [ ] Speaker sends no message (idles)
- [ ] Listeners cannot click (tangrams disabled without speaker message)
- [ ] This happens for 2 rounds (speaker gets kicked)

**Verify:**
- [ ] Listeners' `idle_rounds` does NOT increment
- [ ] Listeners remain in game
- [ ] Only the speaker is removed

---

### 3.4 Two Players Drop from Same Group (Group Disbanded)
**Goal:** Test group dissolution when only 1 member remains

**Setup:** 9 players, any condition

**Actions:**
- [ ] Two players from Group A idle out (sequentially or near-simultaneously)
- [ ] Only 1 player remains in Group A

**Verify:**
- [ ] Remaining player marked with `ended="group disbanded"`
- [ ] Remaining player sees Sorry.jsx with group disbanded message
- [ ] Compensation: proportional to time spent in experiment
- [ ] Game continues with Groups B and C (6 players)
- [ ] `MIN_ACTIVE_GROUPS` check passes (2 groups still active)

---

### 3.5 Too Many Groups Fail (Game Ends)
**Goal:** Test game termination when fewer than 2 active groups

**Setup:** 9 players, any condition

**Actions:**
- [ ] Groups A and B both lose too many members
- [ ] Only Group C remains viable

**Verify:**
- [ ] Game ends for all remaining players
- [ ] All remaining players see appropriate exit with compensation
- [ ] Data saved up to point of termination

---

### 3.6 Dropout During Phase 2 Mixed Conditions
**Goal:** Test reshuffling adaptation when player count changes

**Setup:** 9 players, `refer_mixed` or `social_mixed`

**Actions:**
- [ ] Complete Phase 1 with all 9 players
- [ ] One player idles out early in Phase 2
- [ ] Continue with 8 players

**Verify:**
- [ ] Reshuffling adapts to 8 players (e.g., 3,3,2 distribution)
- [ ] Balanced composition maintained (one from each original group per shuffled group)
- [ ] Speaker rotation continues correctly
- [ ] Game completes successfully with 8 players

---

### 3.7 Speaker Drops Mid-Block
**Goal:** Test speaker reassignment within a block

**Setup:** 9 players, any condition

**Actions:**
- [ ] Current speaker idles out after describing 3 of 6 tangrams
- [ ] Block is incomplete

**Verify:**
- [ ] Speaker role reassigned to next available player in group
- [ ] Server logs show "SPEAKER REASSIGNMENT" message
- [ ] Block continues and completes
- [ ] Data correctly reflects the speaker change mid-block

---

### 3.8 Multiple Simultaneous Dropouts
**Goal:** Test handling of multiple players dropping at once

**Setup:** 9 players, any condition

**Actions:**
- [ ] Two players from different groups idle simultaneously

**Verify:**
- [ ] Both handled correctly
- [ ] Viability checks run for both affected groups
- [ ] Game continues if viable groups remain

---

### 3.9 Idle Warning Display
**Goal:** Test that idle warning appears after first idle round

**Setup:** 9 players, any condition

**Actions:**
- [ ] Player idles for 1 round (but not removed yet)

**Verify:**
- [ ] Feedback shows reminder about inactivity
- [ ] Warning indicates removal if idle again
- [ ] Player can recover by participating in next round

---

## 4. Lobby and Pre-Game Tests

### 4.1 Lobby Timeout (Not Enough Players)
**Goal:** Test waiting room timeout behavior

**Setup:** Start with fewer than 9 players

**Actions:**
- [ ] Players wait in lobby for 5 minutes
- [ ] Game does not start (needs 9 players)

**Verify:**
- [ ] After 5 minutes, waiting players removed
- [ ] Players see Sorry.jsx with lobby timeout message
- [ ] Compensation: $2 for waiting
- [ ] Correct Prolific completion code displayed

---

### 4.2 Comprehension Quiz Failure (3 Attempts)
**Goal:** Test removal after quiz failures

**Setup:** Single player

**Actions:**
- [ ] Player fails comprehension quiz 3 times

**Verify:**
- [ ] After 3rd failure, player sees failure message
- [ ] Player cannot proceed to game
- [ ] Correct Prolific code for quiz failure
- [ ] Player compensated appropriately (or not, per design)

---

## 5. UI/UX Verification Tests

### 5.1 Introduction and Instructions
**Actions:**
- [ ] Read through all instruction pages
- [ ] Verify visual examples show 3-person groups
- [ ] Check that tangram images display correctly
- [ ] Verify all text is accurate for the 3-condition design

---

### 5.2 Game Screen Elements
**Verify for each role/phase:**
- [ ] Profile shows: score, group indicator, avatar
- [ ] Tangram grid displays 6 tangrams in randomized order
- [ ] Target tangram highlighted for speaker only
- [ ] Chat area functional with send button
- [ ] Timer displays and counts down
- [ ] Group members display shows correct avatars and names
- [ ] Role labels: "(Speaker)" / "(Listener)" appear correctly

---

### 5.3 Waiting Screens
**Verify:**
- [ ] "Waiting for the players in your group to respond..." (within-group)
- [ ] "All players in group responded! Waiting for members of other groups to respond..." (cross-group)
- [ ] Transitions happen automatically when all respond

---

### 5.4 Feedback Screens
**Verify:**
- [ ] Correct answer: shows success message
- [ ] Incorrect answer: shows "Ooops, that wasn't the target!"
- [ ] Speaker idle: shows "The speaker did not send a message this round"
- [ ] Avatar icons appear on clicked tangrams
- [ ] Player avatars are squares (not circles)
- [ ] Points awarded message displayed
- [ ] Phase 2 mixed: no "shuffling players" on final feedback screen

---

### 5.5 Transition Screens (Phase 1 -> Phase 2)
**Verify for each condition:**
- [ ] `refer_separated`: "same group members"
- [ ] `refer_mixed`: explains reshuffling, masked identities
- [ ] `social_mixed`: explains social guessing task + reshuffling
- [ ] Block counter resets/continues correctly

---

### 5.6 Exit Survey and Completion
**Verify:**
- [ ] Exit survey fields: age, gender, strength, fair, feedback, education, understood
- [ ] Bonus display shows correct calculation
- [ ] Total compensation displayed
- [ ] Completion code correct and visible
- [ ] For `social_mixed`: aggregated social guessing performance shown

---

### 5.7 Sorry/Kicked Pages
**Verify each termination type:**
- [ ] Idle timeout: correct message, no compensation, correct Prolific code
- [ ] Group disbanded: correct message, proportional compensation, correct code
- [ ] Lobby timeout: correct message, $2 compensation, correct code
- [ ] Quiz failure: correct message, correct code

---

### 5.8 Group Size Change Display
**Verify:**
- [ ] When player leaves, remaining members see: "Your group is smaller because a player left or was inactive."
- [ ] Group member display updates to show fewer members

---

## 6. Timing and Timeout Tests

### 6.1 Selection Stage Timeout (45s)
**Actions:**
- [ ] Let selection timer expire without clicking

**Verify:**
- [ ] Stage advances after 45 seconds
- [ ] Player who didn't click: idle count increments
- [ ] Other players proceed normally

---

### 6.2 Feedback Stage Timing (10s)
**Verify:**
- [ ] Feedback displays for 10 seconds
- [ ] Auto-advances to next round

---

### 6.3 Transition Stage Timing (30s)
**Verify:**
- [ ] Transition screen displays for 30 seconds
- [ ] Auto-advances to next phase/block

---

## 7. Data Integrity Tests

### 7.1 Player-Level Data
**Export data and verify these fields exist and are correct:**
- [ ] `player.id`
- [ ] `player.name`
- [ ] `player.avatar`
- [ ] `player.original_group` (A, B, or C)
- [ ] `player.player_index` (0, 1, or 2)
- [ ] `player.is_active`
- [ ] `player.ended` (if applicable)
- [ ] `player.idle_rounds`
- [ ] `player.exitSurvey` (JSON with all fields)

---

### 7.2 Round-Level Data
**Verify for each player-round:**
- [ ] `role` (speaker/listener)
- [ ] `target` (tangram ID)
- [ ] `clicked` (tangram ID, for listeners)
- [ ] `clicked_correct` (boolean)
- [ ] `block_num`
- [ ] `phase_num` (1 or 2)
- [ ] `original_group`
- [ ] `current_group`
- [ ] `display_name` (masked in Phase 2 mixed)
- [ ] `display_avatar` (anonymous in Phase 2 mixed)

---

### 7.3 Chat Data
**Verify:**
- [ ] Messages saved in `playerRound.chat` or stage-level chat
- [ ] Each message has: `text`, `timestamp`, `sender.id`, `sender.name`, `sender.avatar`
- [ ] Timestamps are accurate (within seconds of send)

---

### 7.4 Social Guessing Data (social_mixed only)
**Verify:**
- [ ] `social_guess` (same_group / different_group)
- [ ] `social_guess_correct` (boolean)
- [ ] `social_round_score` (0, 1, or 2)
- [ ] Cumulative fields: `social_guess_total`, `social_guess_correct_total`
- [ ] Speaker fields: `social_guessed_about_total`, `social_guessed_about_correct`

---

### 7.5 Game-Level Data
**Verify:**
- [ ] `condition` (refer_separated, refer_mixed, social_mixed)
- [ ] `tangram_set` (0 or 1)
- [ ] Game timestamps (start, end)

---

## 8. Condition-Specific Tests

### 8.1 Refer_Separated Specific
- [ ] Groups never change throughout game
- [ ] Player names/avatars remain the same in Phase 2
- [ ] No social guessing UI

---

### 8.2 Refer_Mixed Specific
- [ ] Reshuffling only at block boundaries (not every round)
- [ ] Balanced reshuffling (one from each original group)
- [ ] Anonymous avatars use different seeds per block
- [ ] `current_group` correctly tracks shuffled assignment
- [ ] No social guessing UI

---

### 8.3 Social_Mixed Specific
- [ ] Same reshuffling behavior as refer_mixed
- [ ] Social guessing UI appears ONLY in Phase 2
- [ ] Social guessing appears after tangram click, before round ends
- [ ] No per-trial feedback for social guessing
- [ ] Aggregated social feedback shown at experiment end
- [ ] Both referential and social scores tracked

---

## 9. Edge Cases

### 9.1 Very Fast Completion
**Actions:**
- [ ] All players respond as quickly as possible

**Verify:**
- [ ] No race conditions
- [ ] All data saved correctly
- [ ] Stages advance properly

---

### 9.2 Target Tangram Order Randomization
**Verify:**
- [ ] Order of target tangrams randomized within each block
- [ ] Check if order is same or different across groups

---

### 9.3 Tangram Grid Randomization
**Verify:**
- [ ] Each player has different tangram grid order
- [ ] Grid order persists within game for each player

---

### 9.4 Previously Ended Batch Present
**Actions:**
- [ ] Start new batch while old completed batch exists

**Verify:**
- [ ] New batch starts correctly
- [ ] No interference from old batch

---

## 10. Compensation Verification

### 10.1 Full Completion
- [ ] Base pay: $10
- [ ] Bonus: $0.05 per point (max $5.40 for perfect score)
- [ ] Total compensation displays correctly

---

### 10.2 Idle Removal
- [ ] Player receives NO compensation
- [ ] Correct Prolific code displayed

---

### 10.3 Group Disbanded
- [ ] Proportional compensation based on time/progress
- [ ] Correct Prolific code displayed

---

### 10.4 Lobby Timeout
- [ ] $2 compensation for waiting
- [ ] Correct Prolific code displayed

---

## 11. Score Display Tests

### 11.1 Refer Conditions (separated and mixed)
- [ ] Score increments in real-time during game
- [ ] Score visible in Profile component

---

### 11.2 Social_Mixed Condition
- [ ] Verify: scores should NOT increment during experiment (per TODO)
- [ ] Performance shown only at end (bonus_info stage)
- [ ] Both referential and social scores shown in final summary

---

## Test Execution Checklist

### Pre-Test
- [ ] Clear `tajriba.json`
- [ ] Verify correct constants (TEST_MODE, timing, pay)
- [ ] Start Empirica server
- [ ] Verify admin interface accessible

### During Test
- [ ] Take screenshots at key points
- [ ] Note any unexpected behavior
- [ ] Monitor server logs for errors

### Post-Test
- [ ] Export data (`empirica export`)
- [ ] Verify all expected files generated
- [ ] Spot-check data integrity
- [ ] Document any issues found

---

## Test Priority

**High Priority (Must Pass):**
1. Happy path tests (all 3 conditions)
2. Chat and communication tests
3. Idle detection and removal
4. Group disbanded handling
5. Data integrity verification
6. Compensation codes

**Medium Priority:**
7. Phase 2 reshuffling (mixed conditions)
8. Social guessing (social_mixed)
9. UI/UX verification
10. Timing tests

**Lower Priority:**
11. Edge cases
12. Multiple simultaneous dropouts

---

## Notes for Playwright Automation

- Increase timeouts for slower automated interaction
- Use `mcp__playwright__browser_wait_for` between actions
- Take snapshots at each major screen for verification
- Consider running parallel browser sessions for 9 players
- Handle async timing carefully (waiting screens, stage transitions)
