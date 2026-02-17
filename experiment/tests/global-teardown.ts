/**
 * Global teardown: stops the Empirica server after all tests complete.
 */
import { stopServer } from './helpers/server-manager';

export default async function globalTeardown() {
  console.log('[teardown] Stopping Empirica server...');
  await stopServer();
  console.log('[teardown] Server stopped.');
}
