---
paths:
  - "experiment/tests/**"
  - "experiment/playwright.config.ts"
---

# Testing

Facts about the suites. The `run-playwright-tests` skill is the procedure for running them and triaging a failure.

## Suites

Run everything from `experiment/`, through the npm scripts:

| Script | What it runs |
|--------|--------------|
| `npm run test:unit` | vitest on the pure server modules and the tests in `shared/`, where client logic worth unit testing goes (the client has no test runner: it is pinned to Vite 5 and every installable vitest needs Vite 6). Never a bare `npx vitest`, which finds no config and globs the Playwright specs |
| `npm run test:group1` to `test:group4` | one Playwright group with its server reset and `--no-deps` |
| `npm run test:group4:fast` | group 4 with `IDLE_TEST_TIMING=true` (30 s timers, 2 idle rounds) |
| `npm run test:smoke` | the `@smoke` specs plus the `@setup` resets |
| `npm run test:holistic` | full games at production timing |
| `npm test` | every group in order, holistic last |
| `npm run test:report`, `npm run test:free-ports` | the HTML report (it does not open itself); free ports 3000 and 8844 |

Groups: 1 happy-path, communication, lobby, edge-cases; 2 ui-verification, timing; 3 data-integrity, condition-specific, score-display; 4 idle-detection, group-viability, compensation; then holistic. The groups are chained as Playwright project dependencies and Playwright runs dependencies unfiltered, so a bare `npx playwright test <file>` or `--project=group-N` replays every earlier group first. One file: `npx playwright test reset-server.setup tests/<dir>/<file>.spec.ts --project=setup-N --project=group-N --no-deps`. Append `-- --headed` to watch.

## Harness facts

- **One run at a time.** Every run binds ports 3000 and 8844 and resets the same server. The global setup takes `.empirica/local/playwright-run.lock` and refuses to start while another run holds it (a dead process's lock is cleared automatically); `test:free-ports` refuses while a live run holds the lock. Never `lsof ... | xargs kill -9`, and do not edit anything under `server/src` during a run, which restarts the dev server and freezes the running stage.
- **Modes.** `TEST_MODE` (default `false`; `server-manager.ts` and `tests/helpers/set-default-test-mode.ts` set it `true` for tests) gives 3+2 blocks. Timers and the idle threshold are always the production values (45 s and 25 s selection, 15 s feedback, 3 idle rounds); the per-test timeout is 600 s, or 5400 s in production mode. `tests/helpers/set-production-mode.ts` flips to production only inside a worker (`TEST_WORKER_INDEX`), because Playwright loads every spec in the runner process when it collects a multi-project run and a flip there would be inherited by every group; `reset-server.setup.ts` refuses to start in that state and `server-manager.ts` logs the mode it spawns with. `LOBBY_TESTS=true` un-skips the lobby-timeout test, which waits out the ten-minute lobby.
- **Server errors are visible only in the log.** The harness writes the server's output to `test-results/empirica-server.log` and the global teardown fails the run if it contains a `CALLBACK ERROR` or an unhandled rejection, because `guard.js` contains callback errors and the browser looks healthy. A run that fails only in teardown means the game played and the server threw.
- **Concurrency.** `communication/chat-concurrent.spec.ts` is the only spec where players act at once; keep its `Promise.all`, which is what tests the chat's atomic `append`.
- Specs run with `workers: 1` on one shared server; use `test.describe.serial` within a file. Between groups the server is restarted with `tajriba.json` deleted.

## Writing a spec

Put it under a category directory the config maps to a group, and copy the setup of an existing spec in that group. Helpers: `tests/helpers/admin.ts` (`createBatch(page, condition)`, `stopAllBatches(page)`, which ends a session the way a researcher does), `player-manager.ts` (`PlayerManager`, one browser context per player; `registerAllPlayers` opens `/` without `PROLIFIC_PID`, so the identifier field is editable), `game-actions.ts` (`completeIntro`, `completeExitSurvey`, which waits for the confirmation page or the Sorry screen, `getExitInfo`, `getPlayerInfo`), `constants.ts` (re-exports `shared/constants.js`; compare against `EXIT_REASONS.*` and `PROLIFIC_CODES.*`, never literals) and `selectors.ts`.

Things specs get wrong: the quiz uses `window.alert()`, so register a dialog handler before submitting; `fill()` does not fire React `onChange`, so follow it with `dispatchEvent('input')`; each listener's `data-target-index` is the target's position in that player's own shuffled grid, so read it from each page; `.task` carries `data-role` and `data-current-group` and renders only during gameplay; a transition or bonus screen advances when every player has pressed Continue and otherwise after its full timer (60 s), so wait for each player to reach it and allow about 120 s for the next stage; a spec that idles players for exactly `MAX_IDLE_ROUNDS` and asserts removal is fragile, because a round whose speaker stayed silent resets the counter by design.

## By hand

`cd experiment && rm .empirica/local/tajriba.json && empirica` starts server and client: admin at `localhost:3000/admin` (new batch, assignment "complete", pick the treatment, default lobby, create, start), players at `localhost:3000/` ("new player", nine times). With the Playwright MCP tools, create the player contexts in `browser_run_code` and reach them again through `browser.contexts()` (admin first, then the players), since globals do not persist between calls; the production selection timer runs, so work quickly or in `TEST_MODE`.
