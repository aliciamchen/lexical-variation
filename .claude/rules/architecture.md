# Architecture

## Server (`experiment/server/src/`)

- **constants.js**: Central configuration - player counts, phase blocks, scoring, avatar generation (DiceBear API)
- **callbacks.js**: Game logic via Empirica callbacks:
  - `onGameStart`: Player/group assignment, round/stage creation
  - `onRoundStart`: Role assignment, group reshuffling (mixed conditions), identity masking
  - `onStageEnded`: Scoring, idle player detection, group viability checks

## Client (`experiment/client/src/`)

- **App.jsx**: Root with intro/exit step routing
- **Game.jsx**: Layout (Profile + Task + Chat), chat visibility logic
- **Task.jsx**: Phase dispatcher → Refgame, Transition, or Inactive
- **stages/Refgame.jsx**: Main game UI with tangram grid, social guessing UI
- **components/Tangram.jsx**: Click handling with auto-submit logic

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
- `current_group`: Changes each block in mixed conditions
