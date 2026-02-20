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

Back up experiment data from the production server:

```bash
cd experiment
bash copy_tajriba.sh            # loop every 5 minutes (default)
bash copy_tajriba.sh --once     # single backup and exit
bash copy_tajriba.sh --help     # show usage
```

The script SSHs into the production server, runs `empirica export` to produce a CSV zip, then copies it locally into `data/<timestamp>/`. Safe to run while the experiment is live. Exits automatically after 3 consecutive failures.

## Playwright Tests

The test suite covers the full experiment lifecycle: happy paths for all 3 conditions, idle detection, group viability, lobby edge cases, UI verification, timing, data integrity, condition-specific behavior, compensation, and score display. There are 46 spec files across 12 categories.

### Prerequisites

```bash
cd experiment
npm install
npx playwright install chromium
```

The Empirica server is managed automatically by the test framework — no need to start it manually.

### Running Tests

```bash
# Run the full suite (test mode: 3+2 blocks, 120s selection, 5 idle rounds)
npx playwright test

# Run with production timing (6+6 blocks, 45s selection, 2 idle rounds)
TEST_MODE=false npx playwright test

# Run a specific test group
npx playwright test --project=group-1

# Run a single spec file
npx playwright test tests/happy-path/refer-separated.spec.ts

# Run a category of tests
npx playwright test tests/idle-detection/
npx playwright test tests/happy-path/

# Run tests matching a name pattern
npx playwright test -g "social_mixed"

# Run with visible browser
npx playwright test --headed

# View the HTML report after a run
npx playwright show-report
```

### Test Architecture

Tests are split into 4 project groups in `playwright.config.ts`. Between each group, the Empirica server is restarted (tajriba.json deleted) to prevent state accumulation. Execution order: `setup-1 → group-1 → setup-2 → group-2 → setup-3 → group-3 → setup-4 → group-4`.

| Group | Categories | Description |
|-------|-----------|-------------|
| group-1 | happy-path, communication, lobby, edge-cases | Core game flow |
| group-2 | ui-verification, timing | UI and timing checks |
| group-3 | data-integrity, condition-specific, score-display | Data and conditions |
| group-4 | idle-detection, group-viability, compensation | Dropout handling |

### Test Categories

| Category | Files | What it tests |
|---|---|---|
| `happy-path/` | 3 | Full game completion for each condition |
| `communication/` | 2 | Chat messaging and identity masking |
| `idle-detection/` | 4 | Speaker/listener idle kicks and warnings |
| `group-viability/` | 6 | Group disbanding, game termination, dropouts, mid-block reshuffle |
| `lobby/` | 2 | Lobby timeout, quiz failure |
| `ui-verification/` | 8 | Intro, game screen, feedback, transitions, exit survey, sorry pages |
| `timing/` | 3 | Selection, feedback, and transition auto-advance |
| `data-integrity/` | 5 | Player, round, chat, social, and game data attributes |
| `condition-specific/` | 3 | Detailed checks for each experimental condition |
| `edge-cases/` | 4 | Fast completion, tangram randomization, accuracy threshold, multiple batches |
| `compensation/` | 4 | Prolific codes and partial pay for each exit path |
| `score-display/` | 2 | Real-time scores and social guessing summary |

### Configuration

Tests are configured in `playwright.config.ts`:

- **Workers:** 1 (serial execution — multiplayer games are stateful)
- **Timeout:** 10 minutes per test in test mode, 90 minutes in production mode
- **Retries:** 0 (game state is not resumable)
- **Browser:** Chromium only
- **Artifacts:** Screenshots, traces, and video are saved on failure

`TEST_MODE` in `shared/constants.js` is controlled by the `TEST_MODE` environment variable (defaults to `false` for production). When `true`, it shortens phases to 3 + 2 blocks (instead of 6 + 6) and increases idle tolerance. The test framework sets `TEST_MODE=true` automatically via `server-manager.ts`.

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
