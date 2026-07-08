import { defineConfig, devices } from '@playwright/test';

const isTestMode = process.env.TEST_MODE !== 'false';

/**
 * 4 test groups with server resets between each group.
 *
 * Execution order: setup-1 → group-1 → setup-2 → group-2 → setup-3 → group-3 → setup-4 → group-4 → setup-5 → group-holistic
 *
 * Each setup project resets the Empirica server (deletes tajriba.json) to prevent
 * state accumulation from previous test groups. This keeps the server fast and
 * prevents batch contamination between groups.
 *
 * By default, tests run in TEST_MODE (3+2 blocks, 120s selection, 5 idle rounds).
 * Run with TEST_MODE=false for production timing (6+6 blocks, 45s selection, 2 idle rounds):
 *   TEST_MODE=false npx playwright test
 *
 * | Group   | Categories                                        |
 * |---------|---------------------------------------------------|
 * | group-1 | happy-path, communication, lobby, edge-cases      |
 * | group-2 | ui-verification, timing                           |
 * | group-3 | data-integrity, condition-specific, score-display  |
 * | group-4 | idle-detection, group-viability, compensation     |
 * | group-holistic | holistic end-to-end (social_mixed, 15 players) |
 *
 * Groups are chained via project dependencies so a bare `npx playwright test`
 * runs them in order on the shared server. Playwright runs dependencies
 * UNFILTERED, so a bare single-file or --project run replays every earlier
 * group first. For selective runs, use the npm scripts (package.json), which
 * pair each group with its server-reset setup and pass --no-deps:
 *   npm run test:group4
 *   npm run test:group4:fast   (IDLE_TEST_TIMING=true - short timers for idle suites)
 *   npm run test:holistic      (production timing)
 * Single file (setup + file, skipping earlier groups):
 *   npx playwright test reset-server.setup tests/idle-detection/speaker-idle.spec.ts \
 *     --project=setup-4 --project=group-4 --no-deps
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  // open: 'never' so a failed run doesn't spawn a blocking report server;
  // view reports with `npm run test:report`
  reporter: [['html', { open: 'never' }], ['list']],
  // Test mode: 10 min per test. Production: 90 min (72 rounds * ~55s each + overhead).
  timeout: isTestMode ? 600_000 : 5_400_000,
  globalTeardown: './tests/global-teardown.ts',
  expect: {
    timeout: 30_000,
  },
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    // ── Group 1: happy-path, communication, lobby, edge-cases ──
    {
      name: 'setup-1',
      testMatch: 'reset-server.setup.ts',
    },
    {
      name: 'group-1',
      dependencies: ['setup-1'],
      testMatch: /\/(happy-path|communication|lobby|edge-cases)\/.+\.spec\.ts$/,
      testIgnore: /previous-batch\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },

    // ── Group 2: ui-verification, timing ──
    {
      name: 'setup-2',
      dependencies: ['group-1'],
      testMatch: 'reset-server.setup.ts',
    },
    {
      name: 'group-2',
      dependencies: ['setup-2'],
      testMatch: /\/(ui-verification|timing)\/.+\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] },
    },

    // ── Group 3: data-integrity, condition-specific, score-display ──
    {
      name: 'setup-3',
      dependencies: ['group-2'],
      testMatch: 'reset-server.setup.ts',
    },
    {
      name: 'group-3',
      dependencies: ['setup-3'],
      testMatch: /\/(data-integrity|condition-specific|score-display)\/.+\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] },
    },

    // ── Group 4: idle-detection, group-viability, compensation ──
    {
      name: 'setup-4',
      dependencies: ['group-3'],
      testMatch: 'reset-server.setup.ts',
    },
    {
      name: 'group-4',
      dependencies: ['setup-4'],
      testMatch: /\/(idle-detection|group-viability|compensation)\/.+\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] },
    },

    // ── Holistic end-to-end test (production timing) ──
    {
      name: 'setup-5',
      // Chained after group-4 so a full run can't start the holistic group
      // early: set-production-mode.ts flips TEST_MODE for the whole runner
      // process, which would corrupt groups 1-4 if it ran first. Standalone
      // runs skip the chain via --no-deps (see `npm run test:holistic`).
      dependencies: ['group-4'],
      testMatch: 'reset-server-production.setup.ts',
    },
    {
      name: 'group-holistic',
      dependencies: ['setup-5'],
      testMatch: /\/holistic\/.+\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
