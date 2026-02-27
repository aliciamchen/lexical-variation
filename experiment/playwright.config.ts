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
 * Run holistic test standalone (always uses production timing):
 *   npx playwright test --project=setup-5 --project=group-holistic --reporter=list
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['html'], ['list']],
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
      // dependencies: ['group-4'], // Uncomment to chain after group-4 in full suite
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
