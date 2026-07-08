---
paths:
  - "experiment/tests/**"
  - "experiment/playwright.config.ts"
---

# Testing

## Testing the Experiment Manually

How to test the experiment locally by hand:

```bash
cd experiment
rm .empirica/local/tajriba.json
empirica
```

This starts both server and client. Admin interface at `localhost:3000/admin`, players at `localhost:3000/`. Press "new player" on the player interface to start a new player.

To test:
- click "new batch" on the admin console. "complete" refers to the assignment method, we want to do complete assignment. we can select treatment on the dropdown, lobby config is default shared fail. then click "create"
- open player interface at `localhost:3000/`
  - press "new player" to start a new player, we need to click this 9 times to get 9 players

## Testing with Playwright MCP (interactive)

You can use the Playwright MCP browser tools to manually test the experiment with multiple simulated players. This is useful for verifying UI changes without running the full test suite.

**Setup:**
1. Start the server in background: `cd experiment && rm .empirica/local/tajriba.json && empirica`
2. Navigate to `http://localhost:3000/admin` and create+start a batch
3. Use `browser_run_code` to create 9 player contexts and walk them through the intro

**Key lessons:**
- **Dialog handler first**: The quiz uses `window.alert()` which blocks Playwright. Register `page.on('dialog', async d => await d.accept())` on each player page *before* submitting the quiz, not after.
- **Player intro flow**: I AGREE → Enter identifier → I consent → 5x Next → Quiz (6 radio answers) → Submit. See exact quiz answer text in `experiment/client/src/intro-exit/Quiz.jsx`.
- **Globals don't persist**: `globalThis.__var` set in one `browser_run_code` call is NOT available in the next. Instead, access player pages via `browser.contexts()` (admin is `contexts[0]`, players are `contexts[1..9]`, each has `.pages()[0]`).
- **Inactivity kicks**: The selection timer runs during testing. If you spend too long inspecting state between actions, players get kicked for inactivity. Work quickly or use TEST_MODE (longer timeouts).
- **`fill()` vs real typing**: Playwright's `fill()` sets the value but doesn't fire React `onChange`. Follow `fill()` with `dispatchEvent('input')` to trigger typing indicators and other onChange-dependent state.
- **Killing the server**: Use `lsof -ti :3000 -ti :8844 | xargs kill -9` to free both the Empirica server port (3000) and Vite dev server port (8844) before restarting.
- **Finding players by role**: Use `.task` element's data attributes: `data-role` (speaker/listener), `data-current-group` (A/B/C) to identify which browser context belongs to which role/group.

## Playwright Tests

Tests live in `experiment/tests/` and use `@playwright/test`. The server is managed automatically by the test framework (no need to start it manually).

**Running tests:**

IMPORTANT: the test groups are chained via Playwright project dependencies, and Playwright runs dependencies UNFILTERED. A bare `npx playwright test <file>` or `--project=group-N` therefore replays every earlier group in full first (a group-4 file runs all of groups 1-3 before it). Use the npm scripts, which pair each group with its server-reset setup and pass `--no-deps`:

```bash
cd experiment

# Full suite in order (test mode; the production-timing holistic group runs last)
npm test

# One group only (server reset + that group, nothing else)
npm run test:group1       # happy-path, communication, lobby, edge-cases
npm run test:group2       # ui-verification, timing
npm run test:group3       # data-integrity, condition-specific, score-display
npm run test:group4       # idle-detection, group-viability, compensation
npm run test:group4:fast  # same as group4 with IDLE_TEST_TIMING=true (30s timers,
                          # 2 idle rounds instead of 120s x 5 -- idle tests wait out
                          # full timers, so this is several times faster)
npm run test:holistic     # holistic end-to-end, production timing

# Server unit tests (fast, no browser or server needed)
npm run test:unit

# A single spec file: include its group's reset setup and skip earlier groups
npx playwright test reset-server.setup tests/idle-detection/speaker-idle.spec.ts \
  --project=setup-4 --project=group-4 --no-deps

# Production timing for everything (6+6 blocks, 45s/25s selection, 3 idle rounds)
TEST_MODE=false npm test

# Run with visible browser: append flags after --
npm run test:group2 -- --headed

# View the HTML report (reports no longer auto-open on failure)
npm run test:report
```

Pipe long runs through `tee` to a stable file so results can be read without re-running: `npm run test:group4 2>&1 | tee /tmp/test-results.txt`

**Test architecture:**

Tests are split into 5 project groups in `playwright.config.ts`. Between each group, the Empirica server is restarted (tajriba.json deleted) to prevent state accumulation. Full-suite execution order: `setup-1 → group-1 → ... → setup-4 → group-4 → setup-5 → group-holistic`.

| Group | Categories | Description |
|-------|-----------|-------------|
| group-1 | happy-path, communication, lobby, edge-cases | Core game flow |
| group-2 | ui-verification, timing | UI and timing checks |
| group-3 | data-integrity, condition-specific, score-display | Data and conditions |
| group-4 | idle-detection, group-viability, compensation | Dropout handling |
| group-holistic | holistic | Full end-to-end games at production timing |

**Writing a new test:**

1. Create a `.spec.ts` file in the appropriate category directory under `experiment/tests/` (e.g., `tests/ui-verification/my-test.spec.ts`). The file must be in a directory matching one of the group patterns above so the config picks it up.

2. Use the shared helpers:
   - `tests/helpers/admin.ts` — `createBatch(page, condition)` to set up a game via the admin UI
   - `tests/helpers/player-manager.ts` — `PlayerManager` class to create and manage multiple browser contexts (one per player)
   - `tests/helpers/game-actions.ts` — `completeIntro(page)` to walk a player through consent, instructions, and quiz
   - `tests/helpers/constants.ts` — all game constants (player count, timing, quiz answers, etc.)
   - `tests/helpers/selectors.ts` — shared CSS selectors

3. Typical test setup pattern:
   ```typescript
   import { test, expect } from '@playwright/test';
   import { createBatch } from '../helpers/admin';
   import { PlayerManager } from '../helpers/player-manager';

   test.describe.serial('My Test Suite', () => {
     let pm: PlayerManager;

     test.beforeAll(async ({ browser }) => {
       // Create batch via admin
       const adminPage = await browser.newPage();
       await createBatch(adminPage, 'refer_separated');
       await adminPage.close();

       // Set up 9 players
       pm = new PlayerManager(browser);
       await pm.initialize();
       await pm.registerAllPlayers();
       await pm.completeAllIntros();
       await pm.waitForGameStart();
     });

     test.afterAll(async () => {
       await pm.cleanup();
     });

     test('my test case', async () => {
       const pages = pm.getPages();
       // ... assertions
     });
   });
   ```

4. Tests run sequentially (`workers: 1`, `fullyParallel: false`) because they share a single Empirica server. Use `test.describe.serial` for tests that depend on ordering within a file.

**Key config values** (from `experiment/shared/constants.js`, mirrored in `tests/helpers/constants.ts`):
- `TEST_MODE` — controlled by `TEST_MODE` env var (defaults to `false` for production, `server-manager.ts` sets `true` for tests)
- Test mode: 3+2 blocks, 120s selection, 5 idle rounds, 600s timeout
- Production mode (`TEST_MODE=false`): 6+6 blocks, 45s/25s selection (Phase 1/2), 3 idle rounds, 5400s timeout
- `IDLE_TEST_TIMING=true` (used by `npm run test:group4:fast`): 30s selection, 2 idle rounds — for suites whose tests wait out full idle timers
