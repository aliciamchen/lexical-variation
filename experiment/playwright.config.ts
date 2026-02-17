import { defineConfig, devices } from '@playwright/test';

/**
 * Test suite is split into 4 project groups. Between each group, the Empirica
 * server is restarted (tajriba.json deleted) to prevent state accumulation
 * that causes server slowdown after ~20+ batches.
 *
 * Group 1: happy-path, communication, lobby, edge-cases (10 files)
 * Group 2: ui-verification, timing (11 files)
 * Group 3: data-integrity, condition-specific, score-display (10 files)
 * Group 4: idle-detection, group-viability, compensation (13 files)
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['html'], ['list']],
  timeout: 600_000,
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
    // --- Group 1: Happy path + communication + lobby + edge cases ---
    {
      name: 'setup-1',
      testMatch: 'reset-server.setup.ts',
    },
    {
      name: 'group-1',
      dependencies: ['setup-1'],
      testMatch: /(happy-path|communication|lobby|edge-cases)\//,
      use: { ...devices['Desktop Chrome'] },
    },

    // --- Group 2: UI verification + timing ---
    {
      name: 'setup-2',
      testMatch: 'reset-server.setup.ts',
      dependencies: ['group-1'],
    },
    {
      name: 'group-2',
      dependencies: ['setup-2'],
      testMatch: /(ui-verification|timing)\//,
      use: { ...devices['Desktop Chrome'] },
    },

    // --- Group 3: Data integrity + condition-specific + score display ---
    {
      name: 'setup-3',
      testMatch: 'reset-server.setup.ts',
      dependencies: ['group-2'],
    },
    {
      name: 'group-3',
      dependencies: ['setup-3'],
      testMatch: /(data-integrity|condition-specific|score-display)\//,
      use: { ...devices['Desktop Chrome'] },
    },

    // --- Group 4: Idle detection + group viability + compensation ---
    {
      name: 'setup-4',
      testMatch: 'reset-server.setup.ts',
      dependencies: ['group-3'],
    },
    {
      name: 'group-4',
      dependencies: ['setup-4'],
      testMatch: /(idle-detection|group-viability|compensation)\//,
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
