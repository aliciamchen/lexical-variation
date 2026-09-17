# Interactive experiment

## Recruiting participants and running experiment

The game needs nine people online at once, so participants are recruited in two stages: a
short screening and scheduling form, then a session at an announced time. Around 75% of the
people who say on the form that they can make it actually show up, so plan on inviting
roughly twice the number of players you need.

The full procedure, the messages sent to participants on Prolific, the per-session show-up
numbers from the pilots, and the operational gotchas are in
[`operations/procedures.md`](../operations/procedures.md).

`session.py` drives the Prolific side of a session through the API -- reading the screening
survey, building the allowlist group from the eligible respondents, sending the reminder,
and publishing the study at the announced time. It needs `PROLIFIC_TOKEN` and
`PROLIFIC_WORKSPACE` in the repository-root `.env`, and every command that changes anything
prints its plan and asks before acting.

```bash
uv run python operations/session.py --help              # the seven session steps, in order
uv run python operations/session.py surveys --counts    # survey ids, with response counts
uv run python operations/session.py studies             # study ids, newest first
```



## Local development

```bash
cd experiment
rm .empirica/local/tajriba.json  # fresh database
empirica
```

- Admin: http://localhost:3000/admin
- Players: http://localhost:3000/

Click "New Batch" in admin, select a treatment, then open 9 player tabs. Each player goes through consent → identifier → instructions → quiz before entering the lobby. On Prolific the study link carries `PROLIFIC_PID`, and the identifier field is filled from it and locked so that ids cannot be mistyped; without that parameter, as in local testing and the Playwright suite, the field is editable and any identifier can be typed.

There are 4 between-subjects conditions (treatments): `refer_separated`, `refer_mixed`, `social_mixed`, `social_first`.

## Production deployment

The production server hostname is set via `EMPIRICA_SERVER` in `.env` (see `.env.example`). Deployment follows the [Empirica Ubuntu deployment guide](https://docs.empirica.ly/guides/deploying-my-experiment/ubuntu-tutorial).

### Deploying a new build

```bash
cd experiment
empirica bundle
scp lexical-variation.tar.zst root@$EMPIRICA_SERVER:~/empirica/empirica.tar.zst
```

The Sentry DSN is compiled into the client bundle when you build, so it has to be available on the machine that runs `empirica bundle`, not on the server. The client build reads it from the `.env` file at the repository root (Vite is pointed there with `envDir`), and a production build fails with a clear message if the DSN is missing; set `ALLOW_NO_SENTRY=1` to build without Sentry on purpose. The server itself reads none of the `.env` values.

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

The step-by-step runbook for a session, from creating the screening survey through paying
bonuses, is in [`operations/procedures.md`](../operations/procedures.md). The Empirica side of
it is: verify the server process is alive, open the admin panel at
`https://$EMPIRICA_SERVER/admin` and Sentry at `https://$SENTRY_ORG.sentry.io/`, create and
start the batch before any participant can arrive, and run `operations/copy_tajriba.sh` locally to back
up data every five minutes (see below). Participants reach the game through Prolific rather
than a shared link.

When creating the batch, pick the treatment for the session: there are two per condition, one
per tangram set (names without a suffix use set 0, the "tangram set 1" variants use set 1).
Alternate the sets across sessions within a condition so they are counterbalanced, 10 games
per set per condition in the full sample.

## Copying data locally

The `copy_tajriba.sh` script SSHs into the production server, runs `empirica export` to produce a CSV zip, and copies it into `experiment/data/<timestamp>/`. It is safe to run while the experiment is live. To process the exported zip, run `analysis/extract_run.py`.

```bash
bash operations/copy_tajriba.sh            # loop every 5 minutes (default)
bash operations/copy_tajriba.sh --once     # single backup and exit
bash operations/copy_tajriba.sh --help     # show usage
```

The script exits automatically after 3 consecutive failures. Press Ctrl-C to stop the loop.

## Error monitoring (Sentry)

Client errors are reported to Sentry via `@sentry/react` (configured in `client/src/index.jsx`).

- **Organization**: set via `SENTRY_ORG` in `.env`
- **Project**: `javascript-react`
- **Dashboard**: `https://$SENTRY_ORG.sentry.io/`
- **Features**: error tracking, session replays for sessions that hit an error (text and inputs masked), browser tracing, structured logs

Every URL that Sentry reports is cut at the `?` before it leaves the browser (`beforeSend`, `beforeSendTransaction`, and `beforeBreadcrumb` in `index.jsx`), so the Prolific ids in the study link's query string never reach Sentry; the Sentry user is the Empirica player id only.

During pilot sessions, keep the Sentry dashboard open to watch for client errors, slow page loads, and websocket disconnections.

## Playwright tests

The test suite contains 45 spec files across 13 categories, covering all 4 conditions, idle detection, group viability, compensation (including the researcher stopping a batch mid-game), UI, timing, and more. The Empirica server is managed automatically by the test framework.

### Setup

```bash
cd experiment
npm install
npx playwright install chromium
```

### Running tests

The test groups are chained via Playwright project dependencies, and Playwright runs dependencies unfiltered — a bare `npx playwright test <file>` or `--project=group-N` replays every earlier group in full first. The npm scripts avoid this by pairing each group with its server-reset setup and passing `--no-deps`:

Only one run can use the Empirica server at a time, because every run binds ports 3000 and 8844 and resets the server's state. The harness therefore takes a lock file (`.empirica/local/playwright-run.lock`) in its global setup and refuses to start while another run on the machine holds it; a lock left behind by a run that crashed is cleared automatically. To free the ports before a run, use `npm run test:free-ports`, which does the same check first. Avoid editing files under `server/src` while a run is in progress, since the dev server restarts on every change and the running stage never ends.

```bash
# Full suite (test mode: 3+2 blocks at production timers)
npm test

# One group only
npm run test:group1       # happy-path, communication, lobby, edge-cases
npm run test:group2       # ui-verification, timing
npm run test:group3       # data-integrity, condition-specific, score-display
npm run test:group4       # idle-detection, group-viability, compensation
npm run test:group4:fast  # group 4 with shortened idle timers (IDLE_TEST_TIMING=true)
npm run test:holistic     # holistic end-to-end games at production timing

# Server unit tests (scoring and reshuffling logic; fast, no browser)
npm run test:unit

# A single spec file (include its group's reset setup, skip earlier groups)
npx playwright test reset-server.setup tests/idle-detection/speaker-idle.spec.ts \
  --project=setup-4 --project=group-4 --no-deps

# Full-length games (6+6 blocks; timers are always the production values)
TEST_MODE=false npm test

# Quick smoke subset (tests tagged @smoke)
npm run test:smoke

# Visible browser (append flags after --)
npm run test:group2 -- --headed

# View report
npm run test:report
```

### Test architecture

Tests are split into 5 project groups in `playwright.config.ts`. Between each group, the server is restarted (tajriba.json deleted) to prevent state accumulation.

| Group | Categories | Description |
|-------|-----------|-------------|
| group-1 | happy-path, communication, lobby, edge-cases | Core game flow |
| group-2 | ui-verification, timing | UI and timing checks |
| group-3 | data-integrity, condition-specific, score-display | Data and conditions |
| group-4 | idle-detection, group-viability, compensation | Dropout handling |
| group-holistic | holistic | Full end-to-end games at production timing |

Unit tests for the server's scoring and reshuffling logic are in `server/src/*.test.js` (vitest); they import the production modules (`scoring.js`, `reshuffling.js`) directly, so they run in milliseconds without a browser or server.

### Writing new tests

Test helpers in `tests/helpers/`:

- **`player-manager.ts`** — manages 9 browser contexts/pages
- **`admin.ts`** — `createBatch()` creates and starts a batch via the admin UI; `stopAllBatches()` stops every running batch, which is how a researcher ends a session early and what `compensation/batch-terminated.spec.ts` exercises
- **`game-actions.ts`** — `playRound()`, `playBlock()`, `handleTransition()`, `completeExitSurvey()`. The exit survey's confirmation page has no Finish button (the completion code stays on screen until the participant closes the tab), so `completeExitSurvey()` ends by waiting for that page, identified by its `data-prolific-code` attribute, or for the Sorry screen that removed players are routed to instead
- **`assertions.ts`** — `expectPlayerInGame()`, `expectCondition()`, `expectSocialGuessUI()`
- **`constants.ts`** — re-exports `shared/constants.js` (use `EXIT_REASONS` and `PROLIFIC_CODES` rather than string literals) plus test-only values such as the player count and quiz answers
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
