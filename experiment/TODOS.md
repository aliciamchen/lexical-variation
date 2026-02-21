# Empirica experiment todos

This document tracks the changes needed to make the web experiment.

NOTE for claude: If you need it to figure out how to do something, the docs for empirica are here: https://docs.empirica.ly/ and the source code for empirica is at https://github.com/empiricaly/empirica

---

## Incomplete Tasks

### Blockers (must fix before pilot)

- [ ] Figure out appointment slot thing - Use Optimeet for scheduling (external)
- [ ] Figure out how optimeet works with the prolific max time
  - 9 concurrent players must arrive together; need synchronous scheduling
- [ ] Full end-to-end test + data export verification
  - Run once using Playwright and then test once manually to make sure everything is working correctly
  - Export all the data and test it to make sure all the reshuffling assignments, fields, etc., are saving correctly
  - Run a full game (all 3 conditions), `empirica export`, run `preprocessing.py` + `compute_embeddings.py`, render Qmd files
  - Verify: reshuffling assignments, chat timestamps, social guess data, compensation amounts
  - Do this on the production server (not just localhost) with real browser tabs

### Important (should fix before pilot)

- [ ] Check the numbers are correct: number of blocks, money, timing, etc.
  - [x] Particularly check if the pay is correct for the various ways that people exit the experiment (idle, group disbanded, etc.) For group disbanded, it should be proportional to the amount of time they spent in the experiment. For idle, they do not get paid anything.
- [ ] What if a player drops DURING the accuracy check blocks? Does their 0% accuracy count against the group? Answer: no, it should just be for the trials that are completed in general, dropouts should not count in the accuracy percentages

### Nice to have

- [ ] DiceBear API dependency
  - Avatars are fetched from `https://api.dicebear.com` at runtime
  - If API is down, avatars won't render
  - Consider: bundle a few fallback SVGs, or pre-generate avatars at build time
  - Low risk for pilot but worth monitoring
- [ ] React error boundary
  - No top-level error boundary in the React app
  - If a component crashes, participants see a white screen with no guidance
  - Add an error boundary component wrapping `<App>` that shows a friendly message + the game error completion code (C7F5I0Y9)
- [ ] Chat message length limit UX
  - `Chat.jsx` silently drops messages over 1024 characters
  - Add a character counter or warning near the input
- [x] Monitoring dashboard
  - Set up a Sentry alert for error spikes during pilot sessions
  - Watch for: client errors, slow page loads, websocket disconnections
  - Have the Sentry dashboard open during pilot
- [x] Data backup strategy
  - `copy_tajriba.sh` copies data from the production server every 5 minutes
  - Export data (`empirica export`) after each pilot session completes
  - Store exports in version control or cloud storage

### For next experiment

- [ ] Add thing robert said for increasing minimal group solidarity: "You and your partner have been working together as a team. Teams that successfully develop a shared communication system earn a $X team bonus!" Something like that

---

## Pre-session checklist for pilot day

Before each pilot session:
1. Verify production server is running (`empirica` process alive)
2. Check tajriba.json isn't corrupted / server starts clean
3. Open Sentry dashboard
4. Open admin panel at production URL `/admin`
5. Create batch with correct treatment (condition)
6. Monitor lobby for player arrivals
7. Have Prolific open to monitor submissions

## Pilot-specific considerations

- Run 1 game per condition (3 pilot sessions, 9 participants each = 27 participants)
- After pilot, run outcome-neutral criteria (01_outcome_neutral.qmd) to verify:
  - Description length decreases over Phase 1 blocks
  - Listener accuracy increases over Phase 1 blocks
  - Adjacent similarity increases (conventions forming)
  - Group-specificity exceeds chance at end of Phase 1
- Review exit survey feedback for confusion or UX issues
- Check Sentry for any errors participants experienced
- Debrief: were 45s selection stages long enough? Did participants understand instructions?

---

## Timing Reference

| Stage       | Duration |
| ----------- | -------- |
| Selection   | 45s      |
| Feedback    | 15s      |
| Transitions | 30s      |

**Estimated Duration:**

- Test mode (2+2 blocks): ~15-20 min
- Production (6+6 blocks): ~30-45 min (plus intro/exit)

---

## Design Decisions

- **No distinct group colors**: Groups should not be visually differentiated by color
- **Identity masking in mixed conditions**: Other players' identities are fully hidden
- **Anonymous avatars**: In mixed conditions, players get new anonymous avatars each block
- **Timer duration**: Selection 45s, Feedback 15s, Transitions 30s
- **DiceBear avatars**: Using identicon style (blue) for regular, shapes style (gray) for anonymous

---

## Implementation Summary

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
- Chat.jsx: Custom chat component (replaces Empirica Chat) with role labels, identity masking, timestamps

### Data Collection

- Fields: original_group, current_group, idle_rounds, display_avatar/name, social_guess

### Configuration

- treatments.yaml: 3 condition treatments
- TEST_MODE: 3 players, 1 group, 2+2 blocks

---

## Completed Tasks

### Pre-Launch (Code/Testing)

- [x] Waiting room timeout: 5 minutes max, then remove and compensate $2
- [x] Choose the two tangram sets based on Robert's feedback in slack
- [x] Set and check final constants: money, timing, etc (revert to the non-testing timing)
- [x] Check social goal points don't increment during experiment, shown at end
- [x] Reshuffling in phase 2 after each BLOCK not each round
  - Fixed (2026-01-08): Changed callbacks.js to only reshuffle when `target_num === 0`
- [x] Test that in each block, the order of target tangrams is randomized
- [x] Idle reminder in feedback + removal after 2 rounds
- [x] Remove "shuffling players for the next block..." from last feedback screen
- [x] Test with listener messages too
- [x] Social+mixed speaker prompt and feedback text
- [x] Social+mixed listener feedback text
- [x] Standardize text: use "picture" everywhere
- [x] "You earned no points this round." instead of tangram bonus
- [x] Check and screenshot idle warning message
- [x] Make transition UIs slightly better (padding)
- [x] Mid-block Phase 2 dropout: solo player continues alone, fixed
- [x] 36 rounds in phase 1 (not 30)
- [x] Social guess proportional to number of listeners in group
- [x] End-of-phase-1 accuracy check: remove groups below two-thirds accuracy
- [x] Inactive.jsx vs Sorry.jsx clarification
- [x] Test solo player reassignment in phase 2 mixed
- [x] Implement Robert's slack suggestions
- [x] Reshuffle until mixing happens (avoid same-group assignments with 2 groups)
- [x] Make transition screen scale by window size

### Pre-Launch (Verification)

- [x] Read through all text in the experiment (instructions, etc.) and check
- [x] Pay is correct for various exit paths (idle, group disbanded, etc.)

### External/Manual Tasks

- [x] Set up DigitalOcean server and figure out billing
- [x] Get IRB approval from Mitchell
- [x] Put in Saxelab consent form
- [x] Standardize language in the RR
- [x] Check completion codes are correct on Prolific
- [x] Set up Sentry for error tracking
- [x] Check on production server (custom Chat component replaces chunk-J6LPACOK.js patch)
- [x] Sentry `tracePropagationTargets` updated to `tangramcommunication.empirica.app`
- [x] Feedback duration increased from 10s to 15s

### Stimuli & Game Setup

- [x] Two tangram sets (high SND) with random 50/50 assignment
- [x] Tangram grid order randomized per participant
- [x] Speaker rotation with balanced reshuffling

### Data Collection

- [x] Chat timestamps saved
- [x] `clicked_correct` field added
- [x] Reassigned groups saved correctly
- [x] All required fields verified (chat, block_num, phase_num, target, original_group, current_group, clicked, social_guess, role)

### Participant-Facing Content

- [x] Consent.jsx: time estimate, compensation info
- [x] Introduction.jsx: all 5 instruction pages
- [x] Comprehension Quiz: updated questions, 3-attempt limit
- [x] ExitSurvey.jsx: updated bonus display, base pay
- [x] Kicked-out pages: idle, group disbanded, lobby timeout with separate Prolific codes
- [x] Transition screens: condition-specific Phase 2 instructions

### Game Logic

- [x] In-game exclusion: quiz failure after 3 attempts, idle after 2 rounds
- [x] Social guessing: per-trial UI, scoring, data saving
- [x] Dropout: group viability checks, speaker reassignment, MIN_GROUP_SIZE=2, MIN_ACTIVE_GROUPS=2
- [x] Sentry configuration tuning
- [x] Lobby timeout for 9 players

### UI/UX Polish

- [x] Group-smaller message when player leaves
- [x] Feedback icon spacing
- [x] Idle speaker feedback message
- [x] Anonymous avatars change each block in mixed conditions
- [x] Square avatars (not circles)
- [x] Phase 2 masked identities ("Player" instead of names)
- [x] Chat role indicators "(Speaker)" / "(Listener)"
- [x] Exit survey data verified
- [x] Waiting screens display correctly for 9 players
- [x] Social guessing feedback aggregated at end

### Bugs Fixed

- [x] Role display bug (Groups B and C): GROUP_COUNT derived dynamically from player count
- [x] TEST_MODE/treatment mismatch: TEST_MODE only controls timing now

---

## Automated Testing Log

### 2026-01-07

- **Full 9-player social_mixed test** via Playwright MCP:
  - Phase 1 completion (2 blocks)
  - Phase 2 reshuffling: "Reshuffled 9 players into 3 groups (3 complete)"
  - Masked identities, anonymous avatars, social guessing UI all verified
  - Speaker dropout + reassignment tested
  - Adaptive reshuffling: 8 players distributed into 3,3,2 groups after dropout
  - Idle detection fix: Listeners NOT kicked when speaker didn't send message

### 2026-01-06

- 9-player social_mixed game via Playwright MCP
- Verified data export, chat timestamps, Phase 2 identity masking, group reshuffling, dropout handling

### Manual Testing Completed

- Phase 1 + Phase 2 for all 3 conditions
- Reshuffling (round-robin, uneven players)
- Speaker rotation, scoring, chat masking, block counter, feedback timing
