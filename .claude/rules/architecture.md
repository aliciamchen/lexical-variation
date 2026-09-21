# Architecture

## Server (`experiment/server/src/`)

- **constants.js**: Central configuration - player counts, phase blocks, scoring, avatar generation (DiceBear API)
- **callbacks.js**: Game logic via Empirica callbacks:
  - `onGameStart`: Player/group assignment, round/stage creation
  - `onRoundStart`: Group reshuffling in mixed Phase 2 (`reshuffling.js` enumerates every one-player-per-index assignment, keeps the best under the one-in-group-listener rule, and the outcome is recorded on the round as `reshuffle_mode` and counts), role assignment (each player-round gets `speaker_id`, `group_size`, `speaker_reassigned`, and for listeners `in_group_listener`), identity masking
  - `onStageEnded`: Scoring at the end of Selection (snapshotting which listeners had clicked); idle detection, late-click flagging, and group viability checks at the end of Feedback

## Client (`experiment/client/src/`)

- **App.jsx**: Root with intro/exit step routing (see Exit routing below). Also supplies the four screens Empirica would otherwise draw itself: `NoGames` (the session is full; asks the participant to return the submission, because they hold no completion code and appear in no export), `LobbyWait`, and `LoadingScreen` for both the `loading` and `connecting` slots. `EmpiricaMenu` is deliberately absent -- at `bottom-left` its logo button is not treated as development-only and opens empirica.ly in a new tab
- **intro-exit/NoGames.jsx**, **intro-exit/LobbyWait.jsx**, **components/LoadingScreen.jsx**: those replacements. The lobby counts up rather than down, because the shared lobby timer starts with the first ready player and not with each arrival
- **components/CrashFallback.jsx**: what `Sentry.ErrorBoundary` in `index.jsx` renders when a render throws. Without the boundary React unmounts the whole tree, which is how a momentarily empty player subscription blanked the exit screen in production on 2026-09-19
- **Game.jsx**: Layout (Profile + Task + Chat), chat visibility logic; plays the game and round start sounds once per `game.id` / `round.id`, tracked in refs (the server sets `justStarted` on both scopes but no client writes it back, since a shared flag reset by one client silenced the others)
- **Profile.jsx**: the stage header. Width is `w-full max-w-2xl mx-auto`, a cap and not a floor: it shares the flex row with the chat, so the old `min-w-lg md:min-w-2xl` stopped the game column shrinking below 672px and every pixel a narrow window lost came out of the chat instead (342px of chat at a 1024px window, 128px at 800px). Two of its classes were dead and are gone -- `m-x-auto` and `border-.5` are not classes UnoCSS generates, so the bar was never centered and never had a border
- **Task.jsx**: Phase dispatcher → Refgame or Transition; a removed player never reaches it because Empirica shows the exit steps as soon as `ended` is set
- **groupResponse.js**: the one "everyone in the group has responded" rule (a listener in social Phase 2 needs both the tangram and the social guess), used by `Game.jsx` to hide the chat and by `Refgame.jsx` for the waiting message and the per-player stage auto-submit (an effect, not a render-time write)
- **stages/Refgame.jsx**: Main game UI with tangram grid, social guessing UI. The social-guess buttons are locked until the speaker has sent a message, the same gate `Tangram.jsx` applies to clicks, with a "Waiting for the speaker's description" line; the panel stays visible. The timer-expiry auto-commit never commits before that message either (the server does not score a guess about a speaker who said nothing).
- **components/Tangram.jsx**: Click handling; clicks are ignored until the speaker's message has arrived
- **components/Chat.jsx**: Chat with a typing indicator. Whether a keystroke sends is `isSendKey` in `shared/chat-input.js`, which refuses the Enter an input method editor uses to commit a character (`isComposing`, or `keyCode` 229 on older browsers); sending on it would broadcast a half-written description and reset the composition timer, and the message text is the study's primary measure. `${group}_typing` writes are throttled to one per `TYPING_WRITE_INTERVAL_MS` (1500 ms) per player (first keystroke writes at once), the "stopped" write goes out after `TYPING_STOP_MS` (2 s) of silence, and readers ignore timestamps older than `TYPING_STALE_MS` (3 s)
- **intro-exit/PlayerCreate.jsx**: the identifier form. With `PROLIFIC_PID` in the URL the field is prefilled and read-only ("Your Prolific ID was filled in from the study link."); without it (local testing, Playwright) it is editable
- **intro-exit/ExitSurvey.jsx**: three pages. The current page is derived from what `player.get("exitSurvey")` already holds (page 1 saved → page 2; both saved → confirmation, or `next()` to Sorry for removed players) and each submit merges into that object, so a reload resumes at the first unanswered page and never loses submitted answers. The confirmation page has no Finish button and never calls `next()`: the completion code stays on screen (also on `data-prolific-code`) until the tab is closed.

### Exit routing (`App.jsx` `exitSteps`, `Sorry.jsx`)

All reasons come from `EXIT_REASONS` in `shared/constants.js`; never compare against string literals. `exitReason` is read before `ended`, because Empirica overwrites `ended` itself ("game ended", "game failed" for a lobby timeout, "game terminated" when the admin stops the batch).

| Reason | Steps | Sorry shows |
|--------|-------|-------------|
| `quizFailed` | `[Sorry]` | no code, return the study |
| `playerTimeout` | `[Sorry]` | partial code, prorated base pay, no bonus |
| `gameTerminated` with no `gameStartTime` | `[Sorry]` | lobby-timeout code and pay (see below) |
| `groupDisbanded`, `insufficientGroups`, `lowAccuracy`, `insufficientGroupsAccuracy`, `gameTerminated` (`PARTIAL_PAY_SURVEY_REASONS` in `client/src/constants.js`) | `[ExitSurvey, Sorry]` | partial code, prorated base + bonus; the survey header explains the reason |
| `ended === "game ended"` (finished) | `[ExitSurvey]` | (the survey's confirmation page shows the completion code) |
| anything else | `[Sorry]` | lobby timeout if there is no `gameStartTime`; otherwise the partial code and pay when `partialPay` is set, and the no-compensation text only when it is not |

`insufficientGroups` (too few viable groups remain mid-game) and `gameTerminated` (the researcher stopped the batch; set by `onGameEnded`) are distinct from `groupDisbanded` so the participant text can say what happened.

`Sorry.jsx` decides "never played" on the absence of `gameStartTime` alone, which is
what routes a stopped batch's waiting players to the lobby-timeout screen. Empirica writes
`ended = "game terminated"` to every player assigned to a game in the batch, started or
not, but `game.end()` returns before ending a stage when no stage is running, so
`onGameEnded` never fires for a game that never started and nothing computes those
players' pay. Routing them like a mid-game termination asked them to rate a group they
never met and then showed them the partial code beside $0.00, which `pay` cannot act on
either: it finds that population by the lobby completion code.
`tests/compensation/batch-terminated-lobby.spec.ts` covers it, beside
`batch-terminated.spec.ts` for the mid-game case.

### The missing-player guard (client)

`usePlayer()` is a subscription: empty on the first render, and empty again whenever the
participant context tears down, which a dropped websocket does. `EmpiricaContext` checks
for a missing player, but that check is in the parent, and each component's own
subscription re-renders it alone without consulting the parent, so the check does not
protect it. `Sorry.jsx`, `ExitSurvey.jsx`, `Quiz.jsx`, `Game.jsx` and `Profile.jsx`
therefore return `Loading` when the player is missing, as Empirica's own components do.

Two rules when adding another: the guard goes **below every hook**, or React sees a
different number of hooks between renders and throws for that instead; and a player read
that must sit above a hook (`ExitSurvey`'s derived page, `Quiz`'s attempt count) is
written with `player?.get(...)`, using `useState`'s lazy initializer where the read is a
hook argument, since that argument is evaluated on every render even though only the
first is kept.

### Styling: a class that does not exist fails silently

`uno.config.ts` used to put the empirica palette under `theme.extend.colors`.
That is a Tailwind convention; UnoCSS merges `theme` directly and ignores an
`extend` key, so **not one `*-empirica-*` utility was generated from it**. The
only ones that worked were those `@empirica/core`'s own stylesheet ships, and
`text-empirica-400/700/800` and a bare `border-empirica-500` fell back to the
reset's grey. The palette now sits at `theme.colors`, and its values match the
ones that stylesheet was built from, so nothing already covered moved.

Two things to keep in mind when adding UI. `presetAttributify` is on, so a
name like `m-x-auto` is a valid *attribute* and a dead *class*: a typo of that
shape generates nothing and reports nothing. And a color class outside a
generated palette does not error, it just renders the reset's grey -- when a
color looks wrong, grep the built CSS in `client/dist/assets/` for the class
before assuming a specificity problem.

`components/Alert.jsx` also hardcoded `text-yellow-700` on its children
element, which beat the per-kind color it computes, so every alert body in
the study rendered amber whatever its kind -- error panels included. Both are
fixed; the alert's own colors had never once rendered as written.

## Callback errors (`experiment/server/src/guard.js`)

Empirica does not catch what a callback throws. Its dispatch wrapper awaits the
callback and only then sets the "already ran" sentinel, so a throw leaves the
writes it had already made in place **and** leaves the callback eligible to run
again; the exception becomes an unhandled rejection that `index.js` logs. For a
nine-player synchronous game that is the worst shape of failure: not a crash,
but one group with half-assigned roles while everyone else plays on.

Every callback is therefore wrapped in `guard(name, fn)`, which logs one
greppable `CALLBACK ERROR in <name>` line with the game, condition, active
player count, phase, block, target and stage, swallows the error so the other
players can finish, and counts it on the game as `callbackErrors` with
`lastCallbackError`. Those two reach `games.csv`, and the integrity suite
asserts the count is zero, because a contained error is invisible everywhere
else. Do not "simplify" a callback by unwrapping it.

Three places read those errors: the test harness writes the server's output to
`test-results/empirica-server.log` and the Playwright teardown fails a run whose
log contains one (without this the suite passed while the server threw);
`operations/copy_tajriba.sh` fetches the server log beside each export and
flags any it finds; and `games.csv` carries the count into the analysis.

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

### Avatars

Served from `client/public/avatars/`, not fetched from DiceBear at play time. The anonymous
seed changes every trial in the mixed conditions, so the old `<img src>` pointing at
api.dicebear.com meant nine players each requesting a fresh avatar on all 36 Phase 2 trials:
hundreds of third-party requests per game, on the critical path, in the condition where
identity is the manipulation. Every seed is deterministic, so the set is downloaded once by
`scripts/fetch-avatars.mjs` and committed; `anonymousAvatarSeeds()` enumerates them from the
production block count and roster, and `server/src/avatars.test.js` fails if a seed the
server can generate has no file. The DiceBear URLs remain in `shared/constants.js` as the
record of how each file was made. Re-run the script after changing the block count, the
roster size or the style.

A missing `avatar` attribute falls back to `AVATAR_PLACEHOLDER`, a neutral local SVG.
**Never seed a fallback on the player.** The chat used to fall back to a DiceBear identicon
seeded on `msg.sender.id`, which is persistent: had it rendered during mixed Phase 2 it would
have shown one stable image per player while the anonymous avatars around it change every
trial, which is a tracking cue in the condition whose whole purpose is masking identity. It
was also the last third-party request in the game loop, and the one the pre-generated set
could not cover, because the seed is an Empirica id rather than a known seed.

### Identity Masking (Phase 2 Mixed Conditions)

In `refer_mixed` and `social_mixed`, groups are reshuffled every trial (not per-block). Anonymous avatars are seeded per trial (`anon_block${blockNum}_trial${targetNum}_player${anonIndex}`) so the same player gets different avatars each round:
- `player.round.set("display_avatar/name")` for UI display
- `player.set("avatar/name")` overwritten for chat masking
- `player.get("original_avatar/name")` preserved for restoration

### Group Tracking

- `original_group`: Persists throughout game (A, B, C)
- `current_group`: Changes every trial in Phase 2 of the mixed conditions
