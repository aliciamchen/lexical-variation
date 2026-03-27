# Interactive experiment

## Recruiting participants and running experiment

Around 75% of people who take the initial survey end up showing up 

### Templates



## Local development

```bash
cd experiment
rm .empirica/local/tajriba.json  # fresh database
empirica
```

- Admin: http://localhost:3000/admin
- Players: http://localhost:3000/

Click "New Batch" in admin, select a treatment, then open 9 player tabs. Each player goes through consent → identifier → instructions → quiz before entering the lobby.

There are 4 between-subjects conditions (treatments): `refer_separated`, `refer_mixed`, `social_mixed`, `social_first`.

## Production deployment

The production server hostname is set via `EMPIRICA_SERVER` in `.env` (see `.env.example`). Deployment follows the [Empirica Ubuntu deployment guide](https://docs.empirica.ly/guides/deploying-my-experiment/ubuntu-tutorial).

### Deploying a new build

```bash
cd experiment
empirica bundle
scp lexical-variation.tar.zst root@$EMPIRICA_SERVER:~/empirica/empirica.tar.zst
```

The server is configured to automatically restart empirica when the bundle file is updated.

If you want to do it manually:

```bash
ssh root@$EMPIRICA_SERVER
cd ~/empirica
# Remove the tajriba file from the server if needed:
rm .empirica/local/tajriba.json

empirica serve empirica.tar.zst
```

### Running an experiment session

1. **Verify the server is running**: SSH in and check the `empirica` process is alive
2. **Open the admin panel**: `https://$EMPIRICA_SERVER/admin`
3. **Open Sentry**: `https://$SENTRY_ORG.sentry.io/` (monitors client errors, replays, performance)
4. **Create a batch**: click "New Batch", select the treatment (condition), use default lobby config
5. **Start the batch**: click the play button
6. **Share the player URL**: `https://$EMPIRICA_SERVER/` (participants arrive via Prolific)
7. **Monitor**: watch the admin panel for player arrivals and game progress
8. **Start `copy_tajriba.sh`** locally to back up data every 5 minutes (see below)

## Copying data locally

The `copy_tajriba.sh` script SSHs into the production server, runs `empirica export` to produce a CSV zip, and copies it into `experiment/data/<timestamp>/`. It is safe to run while the experiment is live. To process the exported zip, run `analysis/extract_run.py`.

```bash
cd experiment
bash copy_tajriba.sh            # loop every 5 minutes (default)
bash copy_tajriba.sh --once     # single backup and exit
bash copy_tajriba.sh --help     # show usage
```

The script exits automatically after 3 consecutive failures. Press Ctrl-C to stop the loop.

## Error monitoring (Sentry)

Client errors are reported to Sentry via `@sentry/react` (configured in `client/src/index.jsx`).

- **Organization**: set via `SENTRY_ORG` in `.env`
- **Project**: `javascript-react`
- **Dashboard**: `https://$SENTRY_ORG.sentry.io/`
- **Features**: error tracking, session replays (100%), browser tracing, structured logs

During pilot sessions, keep the Sentry dashboard open to watch for client errors, slow page loads, and websocket disconnections.

## Playwright tests

The test suite contains 48 spec files across 12 categories, covering all 4 conditions, idle detection, group viability, UI, timing, and more. The Empirica server is managed automatically by the test framework.

### Setup

```bash
cd experiment
npm install
npx playwright install chromium
```

### Running tests

```bash
# Full suite (test mode: 3+2 blocks, 120s selection, 5 idle rounds)
npx playwright test

# Production timing (6+6 blocks, 45s selection, 2 idle rounds)
TEST_MODE=false npx playwright test

# Specific test group
npx playwright test --project=group-1

# Specific category or file
npx playwright test tests/happy-path/
npx playwright test tests/happy-path/refer-separated.spec.ts

# Visible browser
npx playwright test --headed

# View report
npx playwright show-report
```

### Test architecture

Tests are split into 4 project groups in `playwright.config.ts`. Between each group, the server is restarted (tajriba.json deleted) to prevent state accumulation.

| Group | Categories | Description |
|-------|-----------|-------------|
| group-1 | happy-path, communication, lobby, edge-cases | Core game flow |
| group-2 | ui-verification, timing | UI and timing checks |
| group-3 | data-integrity, condition-specific, score-display | Data and conditions |
| group-4 | idle-detection, group-viability, compensation | Dropout handling |

### Writing new tests

Test helpers in `tests/helpers/`:

- **`player-manager.ts`** — manages 9 browser contexts/pages
- **`admin.ts`** — creates batches via admin UI
- **`game-actions.ts`** — `playRound()`, `playBlock()`, `handleTransition()`, `completeExitSurvey()`
- **`assertions.ts`** — `expectPlayerInGame()`, `expectCondition()`, `expectSocialGuessUI()`
- **`constants.ts`** — game config values mirrored from `shared/constants.js`
- **`selectors.ts`** — centralized DOM selectors
- **`server-manager.ts`** — server lifecycle (start/stop/reset)

Typical pattern:

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

Tests use `workers: 1`, `retries: 0`, and Chromium only. Screenshots, traces, and video are saved on failure. `TEST_MODE` is set automatically by the test framework.
