# Architecture

## Server (`experiment/server/src/`)

- **constants.js**: Central configuration - player counts, phase blocks, scoring, avatar generation (DiceBear API)
- **callbacks.js**: Game logic via Empirica callbacks:
  - `onGameStart`: Player/group assignment, round/stage creation
  - `onRoundStart`: Group reshuffling in mixed Phase 2 (`reshuffling.js` enumerates every one-player-per-index assignment, keeps the best under the one-in-group-listener rule, and the outcome is recorded on the round as `reshuffle_mode` and counts), role assignment (each player-round gets `speaker_id`, `group_size`, `speaker_reassigned`, and for listeners `in_group_listener`), identity masking
  - `onStageEnded`: Scoring at the end of Selection (snapshotting which listeners had clicked); idle detection, late-click flagging, and group viability checks at the end of Feedback

## Client (`experiment/client/src/`)

- **App.jsx**: Root with intro/exit step routing
- **Game.jsx**: Layout (Profile + Task + Chat), chat visibility logic
- **Task.jsx**: Phase dispatcher → Refgame, Transition, or Inactive
- **stages/Refgame.jsx**: Main game UI with tangram grid, social guessing UI
- **components/Tangram.jsx**: Click handling with auto-submit logic

## Session instrumentation (`experiment/client/src/instrumentation.js`)

- `recordClientContext(player)`: called once from `Introduction.jsx`, beside the Prolific URL params. Writes the coarse device/viewport blob `client_context` and the raw `userAgent` (stripped at anonymization).
- `useEngagementLog(player)`: mounted from `Game.jsx`, so it covers gameplay. Appends `{t, type}` to the player's `engagement_events` for tab visibility, connectivity, and debounced resize. The counting rules are in `shared/engagement.js` (cap of 200 with `engagement_log_truncated`, resize de-duplication, and the offline deferral), unit tested by the server's vitest; the hook is only the browser wiring. It returns the event count, which `Game.jsx` puts on `data-engagement-count` for the end-to-end spec.
- Going offline writes **nothing** at the time: an append made while the socket is down never reaches the server, and an early version of this code lost exactly that event. The drop time is held and written on reconnect, ahead of the `online` event, so the length of an outage survives it. Do not "simplify" this back into an immediate write.
- Response-time anchors: `Refgame.jsx` stamps `selection_rendered_at` once per player-round; `Tangram.jsx` and `Refgame.jsx`'s `commitLocalSelections` both write `tangram_selected_at`. Keep those two paths in step -- they are what makes the measure comparable between the referential and social conditions.
- `Chat.jsx` stamps `composeStartedAt` on the first character of a message and flags `pasted`; both ride on the appended message object.

## Configuration (`experiment/.empirica/`)

- **treatments.yaml**: Experimental factors and 4 treatment combinations
- **lobbies.yaml**: Participant grouping strategies
- **empirica.toml**: Auth and project metadata

## Key Patterns

### Quiz Answers (for Playwright automation)

1. Speaker's job → "Describe the target picture"
2. Inactive penalty → "Removed from the game"
3. Chat restrictions → "Only topics related to picking out the correct target picture"
4. Listener waiting → "Listeners must wait for speaker"
5. Phase 2 groups → "Mixed up"
6. Tangram positions → "Different positions for each player"

### Identity Masking (Phase 2 Mixed Conditions)

In `refer_mixed` and `social_mixed`, groups are reshuffled every trial (not per-block). Anonymous avatars are seeded per trial (`anon_block${blockNum}_trial${targetNum}_player${anonIndex}`) so the same player gets different avatars each round:
- `player.round.set("display_avatar/name")` for UI display
- `player.set("avatar/name")` overwritten for chat masking
- `player.get("original_avatar/name")` preserved for restoration

### Group Tracking

- `original_group`: Persists throughout game (A, B, C)
- `current_group`: Changes every trial in Phase 2 of the mixed conditions
