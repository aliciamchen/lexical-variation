/**
 * Global teardown: stops the Empirica server after all tests complete, checks
 * its log for server-side failures, and releases the run lock taken in
 * global-setup.ts.
 *
 * The log check is here rather than in a spec because a server error belongs to
 * the run, not to whichever test happened to be in flight. Empirica does not
 * catch what a callback throws, and guard() deliberately contains the error so
 * the other eight players can finish, so a callback failure leaves the browser
 * looking healthy: without this the suite would pass while the server was
 * throwing on every round.
 */
import { stopServer, serverErrors, SERVER_LOG_PATH } from './helpers/server-manager';
import { releaseRunLock } from './helpers/run-lock';

export default async function globalTeardown() {
  console.log('[teardown] Stopping Empirica server...');
  await stopServer();
  releaseRunLock();
  console.log('[teardown] Server stopped.');

  const errors = serverErrors();
  if (errors.length > 0) {
    const shown = errors.slice(0, 20).join('\n  ');
    throw new Error(
      `The Empirica server reported ${errors.length} error(s) during this run. ` +
        `The game may still have looked fine in the browser; see ${SERVER_LOG_PATH}.\n  ${shown}`,
    );
  }
  console.log('[teardown] No server-side errors in the log.');
}
