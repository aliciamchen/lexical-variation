# Architecture

## Server (`experiment/server/src/`)

- **constants.js**: Central configuration - player counts, phase blocks, scoring, avatar generation (DiceBear API)
- **callbacks.js**: Game logic via Empirica callbacks:
  - `onGameStart`: Player/group assignment, round/stage creation
  - `onRoundStart`: Group reshuffling in mixed Phase 2 (`reshuffling.js` enumerates every one-player-per-index assignment, keeps the best under the one-in-group-listener rule, and the outcome is recorded on the round as `reshuffle_mode` and counts), role assignment (each player-round gets `speaker_id`, `group_size`, `speaker_reassigned`, and for listeners `in_group_listener`), identity masking
  - `onStageEnded`: Scoring at the end of Selection (snapshotting which listeners had clicked); idle detection, late-click flagging, and group viability checks at the end of Feedback

## Client (`experiment/client/src/`)

- **App.jsx**: Root with intro/exit step routing (see Exit routing below)
- **Game.jsx**: Layout (Profile + Task + Chat), chat visibility logic; plays the game and round start sounds once per `game.id` / `round.id`, tracked in refs (the server sets `justStarted` on both scopes but no client writes it back, since a shared flag reset by one client silenced the others)
- **Task.jsx**: Phase dispatcher → Refgame or Transition; a removed player never reaches it because Empirica shows the exit steps as soon as `ended` is set
- **groupResponse.js**: the one "everyone in the group has responded" rule (a listener in social Phase 2 needs both the tangram and the social guess), used by `Game.jsx` to hide the chat and by `Refgame.jsx` for the waiting message and the per-player stage auto-submit (an effect, not a render-time write)
- **stages/Refgame.jsx**: Main game UI with tangram grid, social guessing UI. The social-guess buttons are locked until the speaker has sent a message, the same gate `Tangram.jsx` applies to clicks, with a "Waiting for the speaker's description" line; the panel stays visible. The timer-expiry auto-commit never commits before that message either (the server does not score a guess about a speaker who said nothing).
- **components/Tangram.jsx**: Click handling; clicks are ignored until the speaker's message has arrived
- **components/Chat.jsx**: Chat with a typing indicator. `${group}_typing` writes are throttled to one per `TYPING_WRITE_INTERVAL_MS` (1500 ms) per player (first keystroke writes at once), the "stopped" write goes out after `TYPING_STOP_MS` (2 s) of silence, and readers ignore timestamps older than `TYPING_STALE_MS` (3 s)
- **intro-exit/PlayerCreate.jsx**: the identifier form. With `PROLIFIC_PID` in the URL the field is prefilled and read-only ("Your Prolific ID was filled in from the study link."); without it (local testing, Playwright) it is editable
- **intro-exit/ExitSurvey.jsx**: three pages. The current page is derived from what `player.get("exitSurvey")` already holds (page 1 saved → page 2; both saved → confirmation, or `next()` to Sorry for removed players) and each submit merges into that object, so a reload resumes at the first unanswered page and never loses submitted answers. The confirmation page has no Finish button and never calls `next()`: the completion code stays on screen (also on `data-prolific-code`) until the tab is closed.

### Exit routing (`App.jsx` `exitSteps`, `Sorry.jsx`)

All reasons come from `EXIT_REASONS` in `shared/constants.js`; never compare against string literals. `exitReason` is read before `ended`, because Empirica overwrites `ended` itself ("game ended", "game failed" for a lobby timeout, "game terminated" when the admin stops the batch).

| Reason | Steps | Sorry shows |
|--------|-------|-------------|
| `quizFailed` | `[Sorry]` | no code, return the study |
| `playerTimeout` | `[Sorry]` | partial code, prorated base pay, no bonus |
| `groupDisbanded`, `insufficientGroups`, `lowAccuracy`, `insufficientGroupsAccuracy`, `gameTerminated` (`PARTIAL_PAY_SURVEY_REASONS` in `client/src/constants.js`) | `[ExitSurvey, Sorry]` | partial code, prorated base + bonus; the survey header explains the reason |
| `ended === "game ended"` (finished) | `[ExitSurvey]` | (the survey's confirmation page shows the completion code) |
| anything else | `[Sorry]` | lobby timeout if there is no `gameStartTime` and no server reason; otherwise the partial code and pay when `partialPay` is set, and the no-compensation text only when it is not |

`insufficientGroups` (too few viable groups remain mid-game) and `gameTerminated` (the researcher stopped the batch; set by `onGameEnded`) are distinct from `groupDisbanded` so the participant text can say what happened.

## Session instrumentation (`experiment/client/src/instrumentation.js`)

- `recordClientContext(player)`: called once from `Introduction.jsx`, beside the Prolific URL params. Writes the coarse device/viewport blob `client_context` and the raw `userAgent` (stripped at anonymization).
- `useEngagementLog(player)`: mounted from `Game.jsx`, so it covers gameplay. Appends `{t, type}` to the player's `engagement_events` for tab visibility, connectivity, and debounced resize. The counting rules are in `shared/engagement.js` (cap of 200 with `engagement_log_truncated`, resize de-duplication, and the offline deferral), unit tested by the server's vitest; the hook is only the browser wiring. It returns the event count, which `Game.jsx` puts on `data-engagement-count` for the end-to-end spec.
- Going offline writes **nothing** at the time: an append made while the socket is down never reaches the server, and an early version of this code lost exactly that event. The drop time is held and written on reconnect, ahead of the `online` event, so the length of an outage survives it. Do not "simplify" this back into an immediate write.
- Response-time anchors: `Refgame.jsx` stamps `selection_rendered_at` once per player-round; `Tangram.jsx` and `Refgame.jsx`'s `commitLocalSelections` both write `tangram_selected_at`. Keep those two paths in step -- they are what makes the measure comparable between the referential and social conditions.
- `Chat.jsx` stamps `composeStartedAt` on the first character of a message and flags `pasted`; both ride on the appended message object.
- The engagement cap is per player, not per mount: `useEngagementLog` seeds the recorder from `player.get("engagement_events").length` and from `engagement_log_truncated`, so a reload continues the count rather than granting another 200 events.

## Sentry (`experiment/client/src/index.jsx`)

`beforeSend`, `beforeSendTransaction`, and `beforeBreadcrumb` cut every URL field at the `?` (`request.url`, `transaction`, `contexts.trace.data.url`, span `data.url`, breadcrumb `data.url` / `data.from` / `data.to`), so the Prolific ids in the study link's query string never reach Sentry. `window.location` is not rewritten, because Empirica's `ns` parameter must survive a reload. Replays are recorded only for sessions that hit an error (`replaysSessionSampleRate: 0`, `replaysOnErrorSampleRate: 1.0`, all text and inputs masked). `Introduction.jsx` sets the Sentry user to the Empirica player id only.

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
