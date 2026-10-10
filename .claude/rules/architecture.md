---
paths:
  - "experiment/**"
---

# Experiment architecture

The experiment code is the record of what ran for the full sample. Change it for documentation, tests or a future deployment, never to tidy behavior the collected data depend on, and say in the report when a change would have altered a game. `.claude/rules/testing.md` covers the test suite and `.claude/rules/sentry.md` the error monitoring.

## Where the logic is

- `shared/constants.js` is the configuration: player counts, blocks, timing, scoring, `EXIT_REASONS`, `PROLIFIC_CODES`, avatar seeds. `tests/helpers/constants.ts` re-exports it and `operations/game_constants.py` parses it. `LOBBY_TIMEOUT_MINUTES` must equal `duration` in `.empirica/lobbies.yaml`. Treatments are in `.empirica/treatments.yaml`, two per condition, one per tangram set (`server/src/tangrams.js` resolves the set).
- `server/src/callbacks.js`: `onGameStart` assigns players and groups and creates the rounds; `onRoundStart` reshuffles in mixed Phase 2 (`reshuffling.js`; the outcome is recorded on the round as `reshuffle_mode` and counts, and each player-round gets `speaker_id`, `group_size`, `speaker_reassigned` and `in_group_listener`) and masks identities; `onStageEnded` scores at the end of Selection from a snapshot of who had clicked, and at the end of Feedback runs idle detection, late-click flagging and the group-viability check. `scoring.js`, `compensation.js`, `idle.js`, `accuracy.js` and `tangrams.js` are pure modules with vitest tests beside them.
- **Every callback is wrapped in `guard(name, fn)`** (`guard.js`). Empirica does not catch what a callback throws: the writes already made stay, the callback stays eligible to run again, and one group plays on half-updated. `guard` logs one `CALLBACK ERROR in <name>` line with game, condition, phase, block, target and stage, swallows the error so the other players can finish, and counts it on the game (`callbackErrors`, `lastCallbackError`), which reach `games.csv`, where the integrity suite requires zero. The Playwright teardown and `operations/copy_tajriba.sh` grep for that line. Do not unwrap a callback.
- Client: `App.jsx` routes the intro and exit steps and supplies the screens Empirica would otherwise draw itself (`NoGames`, `LobbyWait`, `LoadingScreen`; `EmpiricaMenu` is deliberately absent because its logo opens empirica.ly). `Game.jsx` lays out Profile, Task and Chat and hides the chat once everyone has responded (`groupResponse.js` is the one such rule, also used for the per-player auto-submit, which is an effect and not a render-time write). `Task.jsx` dispatches to `Refgame.jsx` or the transition screens, `Tangram.jsx` handles clicks, `Chat.jsx` the chat, and `instrumentation.js` the device, connection and engagement records.

## Exit routing (`App.jsx` `exitSteps`, `Sorry.jsx`)

Compare reasons against `EXIT_REASONS`, never string literals, and read `exitReason` before `ended`, which Empirica overwrites itself (`"game ended"`, `"game failed"` for a lobby timeout, `"game terminated"` when the admin stops the batch).

| Reason | Steps | Sorry shows |
|--------|-------|-------------|
| `quizFailed` | `[Sorry]` | no code, return the study |
| `playerTimeout` | `[Sorry]` | partial code, prorated base pay, no bonus |
| `gameTerminated` with no `gameStartTime` | `[Sorry]` | lobby-timeout code and pay |
| `groupDisbanded`, `insufficientGroups`, `lowAccuracy`, `insufficientGroupsAccuracy`, `gameTerminated` (`PARTIAL_PAY_SURVEY_REASONS`) | `[ExitSurvey, Sorry]` | partial code, prorated base pay plus bonus; the survey header explains the reason |
| `ended === "game ended"` | `[ExitSurvey]` | the survey's confirmation page shows the completion code |
| anything else | `[Sorry]` | lobby timeout without `gameStartTime`; otherwise the partial code when `partialPay` is set |

`Sorry.jsx` decides "never played" on the absence of `gameStartTime` alone. That is what routes a stopped batch's waiting players to the lobby-timeout screen: Empirica writes `game terminated` to every assigned player, but `onGameEnded` never fires for a game that never started, so nothing computes their pay, and `make payments` finds them by the lobby code. The exit survey's confirmation page has no Finish button: it shows the completion code (`data-prolific-code`) and a "Return to Prolific" link (`ProlificCompletion.jsx`, `prolificCompletionUrl()`), whose navigation closes the websocket that would otherwise keep a server subscription alive. The three completion paths on the Prolific study must match `PROLIFIC_CODES`.

## Invariants to keep

- **Identity masking.** In the three mixed conditions' Phase 2, groups reshuffle every trial, chat names are masked, and anonymous avatars are re-seeded per trial (`anon_block${blockNum}_trial${targetNum}_player${anonIndex}`; `player.round` holds `display_avatar/name`, `player.avatar/name` is overwritten for the chat, `original_avatar/name` is kept). Avatars are served from `client/public/avatars/`, downloaded once by `scripts/fetch-avatars.mjs`; `avatars.test.js` fails if a seed the server can generate has no file, so rerun the script after changing blocks, roster or style. A missing avatar falls back to `AVATAR_PLACEHOLDER`. **Never seed a fallback on the player id**: a persistent seed would show one stable image per player while the anonymous ones change, a tracking cue in the condition whose manipulation is masking.
- **The missing-player guard.** `usePlayer()` is a subscription, empty on the first render and again whenever the websocket drops, and the parent's check does not protect a child's own re-render. `Sorry`, `ExitSurvey`, `Quiz`, `Game` and `Profile` return `Loading` when the player is missing. The guard goes below every hook, and a player read that must sit above a hook is written `player?.get(...)`, with `useState`'s lazy initializer when the read is a hook argument. `CrashFallback.jsx` is what `Sentry.ErrorBoundary` renders when a render throws.
- **Chat.** `isSendKey` (`shared/chat-input.js`) refuses the Enter an input method editor uses to commit a character; sending on it would broadcast a half-written description, and the message text is the primary measure. `Chat.jsx` stamps `composeStartedAt` on the first character and flags `pasted`. Typing writes are throttled (`TYPING_WRITE_INTERVAL_MS`, `TYPING_STOP_MS`, `TYPING_STALE_MS`).
- **Gating.** Tangram clicks and the social-guess buttons are locked until the speaker's message has arrived, and the deadline auto-commit never commits before it either: the server does not score a guess about a speaker who said nothing.
- **Instrumentation.** `ConnectionLog` is mounted beside `EmpiricaContext`, not inside it, because the context unmounts the game while the websocket is down. A disconnect is written on reconnect with its duration, never at the time, since an append made while the socket is down is lost; do not "simplify" it into an immediate write. The recording and counting rules are in `shared/engagement.js`, unit tested, and the engagement cap is per player, seeded from what the player already holds, so a reload continues the count. `selection_rendered_at` is stamped once per player-round, and `tangram_selected_at` is written by both `Tangram.jsx` and `Refgame.jsx`'s `commitLocalSelections`; keep those two paths in step, because they are what makes response times comparable between the referential and social conditions. `recordClientContext` writes the device blob and the raw user agent, which is stripped at anonymization.
- **Exit survey** pages are derived from what `player.get("exitSurvey")` already holds, so a reload resumes at the first unanswered page and nothing submitted is lost.
- **Styling.** UnoCSS merges `theme` directly and ignores Tailwind's `extend`, so the Empirica palette sits at `theme.colors` in `uno.config.ts`. With `presetAttributify` on, a typo such as `m-x-auto` is a valid attribute and a dead class, and a color outside a generated palette silently renders the reset's gray; grep the built CSS in `client/dist/assets/` before suspecting specificity.
- **Loading screen.** A spinner for 15 s, a request to wait until 30 s, and a reload suggestion only after that: on a busy server a stage change can take several seconds, and a reload discards the update already on its way while the stage timer keeps running.
- **Sounds** play once per `game.id` and `round.id`, tracked in refs; no client writes back the server's `justStarted` flags, because a shared flag reset by one client silences the others.

## Quiz answers (for automation)

1. Speaker's job: "Describe the target picture"
2. Inactive penalty: "Removed from the game"
3. Chat restrictions: "Only topics related to picking out the correct target picture"
4. Listener waiting: "Listeners must wait for speaker"
5. Phase 2 groups: "Mixed up"
6. Tangram positions: "Different positions for each player"

`social_first` adds a seventh question about the identification reward; the exact strings are in `client/src/intro-exit/Quiz.jsx`.
