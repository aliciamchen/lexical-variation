/**
 * Setup test that resets the Empirica server between test groups.
 *
 * Deletes tajriba.json (accumulated game state) and restarts the server
 * so each group of test files starts with a fresh, fast server.
 */
import { test as setup } from '@playwright/test';
import { resetServer } from './helpers/server-manager';

setup('reset empirica server', async () => {
  console.log('[setup] Resetting Empirica server (clearing tajriba.json)...');
  await resetServer();
  console.log('[setup] Server is ready.');
});
