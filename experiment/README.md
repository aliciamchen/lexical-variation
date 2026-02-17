# Interactive experiment

## Custom Chat Component

This project uses a custom Chat component (`client/src/components/Chat.jsx`) instead of the default Empirica Chat. This eliminates the need for any `node_modules` patches.

The custom Chat component provides:
- **Role labels**: Shows "(Speaker)" or "(Listener)" after player names
- **Identity masking**: Uses `display_name` and `display_avatar` in Phase 2 mixed conditions
- **Timestamps**: Shows 5-second increments (5s, 10s, 15s...) instead of "now" for recent messages
- **Square avatars**: Matches the UI style of other avatars in the game
- **DiceBear fallback**: Uses identicon avatars when player avatar is not set

No `node_modules` patches are required.

## Running the experiment

### Local Development

```bash
cd experiment
rm .empirica/local/tajriba.json  # Fresh database
empirica
```

- Admin: http://localhost:3000/admin
- Players: http://localhost:3000/

### Production Deployment

```bash
empirica bundle
scp prod-comp.tar.zst root@45.55.59.202:~
empirica serve prod-comp.tar.zst
```

Production URL: http://45.55.59.202:3000/

### Data Backup

Periodically copy the tajriba file: `sh copy_tajriba.sh`

## Playwright Tests

The test suite covers the full experiment lifecycle: happy paths for all 3 conditions, idle detection, group viability, lobby edge cases, UI verification, timing, data integrity, condition-specific behavior, compensation, and score display. There are 250 tests across 44 spec files.

### Prerequisites

```bash
cd experiment
npm install
npx playwright install chromium
```

The Empirica server must be running before you start the tests:

```bash
rm .empirica/local/tajriba.json   # fresh database
empirica
```

### Running Tests

```bash
# Run the full suite
npx playwright test

# Run a single spec file
npx playwright test tests/happy-path/refer-separated.spec.ts

# Run a category of tests
npx playwright test tests/idle-detection/
npx playwright test tests/happy-path/

# Run tests matching a name pattern
npx playwright test -g "social_mixed"

# View the HTML report after a run
npx playwright show-report
```

### Test Categories

| Category | Files | What it tests |
|---|---|---|
| `happy-path/` | 3 | Full game completion for each condition |
| `communication/` | 2 | Chat messaging and identity masking |
| `idle-detection/` | 4 | Speaker/listener idle kicks and warnings |
| `group-viability/` | 5 | Group disbanding, game termination, dropouts |
| `lobby/` | 2 | Lobby timeout, quiz failure |
| `ui-verification/` | 8 | Intro, game screen, feedback, transitions, exit survey, sorry pages |
| `timing/` | 3 | Selection, feedback, and transition auto-advance |
| `data-integrity/` | 5 | Player, round, chat, social, and game data attributes |
| `condition-specific/` | 3 | Detailed checks for each experimental condition |
| `edge-cases/` | 3 | Fast completion, tangram randomization, multiple batches |
| `compensation/` | 4 | Prolific codes and partial pay for each exit path |
| `score-display/` | 2 | Real-time scores and social guessing summary |

### Configuration

Tests are configured in `playwright.config.ts`:

- **Workers:** 1 (serial execution — multiplayer games are stateful)
- **Timeout:** 10 minutes per test (games involve many rounds)
- **Retries:** 0 (game state is not resumable)
- **Browser:** Chromium only
- **Artifacts:** Screenshots, traces, and video are saved on failure

The game uses `TEST_MODE = true` in `shared/constants.js` which shortens phases to 3 + 2 blocks (instead of 6 + 6) and reduces idle thresholds.

### Writing New Tests

Test helpers are in `tests/helpers/`:

- **`player-manager.ts`** — Manages 9 browser contexts/pages for multiplayer testing
- **`admin.ts`** — Creates batches via the admin interface
- **`game-actions.ts`** — High-level actions: `playRound()`, `playBlock()`, `handleTransition()`, `completeExitSurvey()`
- **`assertions.ts`** — Custom assertions: `expectPlayerInGame()`, `expectCondition()`, `expectSocialGuessUI()`
- **`constants.ts`** — Game config values mirrored from `shared/constants.js`
- **`selectors.ts`** — Centralized DOM selectors
- **`server-manager.ts`** — Server lifecycle (start/stop/reset)

Typical test structure:

```typescript
test.describe.serial('My Test Suite', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('all 9 players join', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();
    const started = await pm.waitForGameStart();
    expect(started).toBe(true);
  });
});
```
