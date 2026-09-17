/**
 * Setup test that resets the Empirica server between test groups.
 *
 * Deletes tajriba.json (accumulated game state) and restarts the server
 * so each group of test files starts with a fresh, fast server.
 */
import { test as setup } from '@playwright/test';
import { resetServer } from './helpers/server-manager';

setup('reset empirica server', async () => {
  // The groups this setup serves are written for TEST_MODE (3+2 blocks). If
  // the environment says otherwise the whole group would play production-length
  // games and fail late and confusingly, so refuse up front.
  if (process.env.TEST_MODE === 'false') {
    throw new Error(
      'reset-server.setup: TEST_MODE=false in this worker, but groups 1-4 need test mode. ' +
        'Run the holistic group through `npm run test:holistic` and the others through their npm scripts.',
    );
  }
  console.log('[setup] Resetting Empirica server (clearing tajriba.json)...');
  await resetServer();
  console.log('[setup] Server is ready.');
});
