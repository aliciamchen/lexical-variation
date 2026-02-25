/**
 * Setup test that resets the Empirica server in PRODUCTION mode.
 *
 * Used by the holistic test group so the server uses production timing
 * (45s selection, 3 idle rounds, 6+6 blocks) instead of test timing.
 */
import { test as setup } from '@playwright/test';
import './helpers/set-production-mode';
import { resetServer } from './helpers/server-manager';

setup('reset empirica server (production mode)', async () => {
  console.log('[setup] Resetting Empirica server (production mode, TEST_MODE=false)...');
  await resetServer();
  console.log('[setup] Server is ready (production mode).');
});
