/**
 * Global teardown: stops the Empirica server after all tests complete and
 * releases the run lock taken in global-setup.ts.
 */
import { stopServer } from './helpers/server-manager';
import { releaseRunLock } from './helpers/run-lock';

export default async function globalTeardown() {
  console.log('[teardown] Stopping Empirica server...');
  await stopServer();
  releaseRunLock();
  console.log('[teardown] Server stopped.');
}
