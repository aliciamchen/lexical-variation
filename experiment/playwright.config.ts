import { defineConfig, devices } from '@playwright/test';

/**
 * Single setup project starts the Empirica server, then a single test project
 * runs ALL test files sequentially (workers: 1, fullyParallel: false).
 *
 * No group separation or server resets between test categories. This ensures
 * that failures in one category never prevent other categories from running.
 * The Empirica server can handle many batches in a single session.
 *
 * The `previous-batch.spec.ts` test is excluded because it creates multiple
 * batches that leave stale running batches, causing cascading failures in
 * subsequent tests that share the same server.
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
    {
      name: 'setup',
      testMatch: 'reset-server.setup.ts',
    },
    {
      name: 'tests',
      dependencies: ['setup'],
      testIgnore: /previous-batch\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
