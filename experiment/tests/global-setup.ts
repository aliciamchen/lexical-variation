/**
 * Global setup: refuse to start while another Playwright run on this machine
 * holds the Empirica server (see helpers/run-lock.ts). Runs once in the runner
 * process before any project, including `--no-deps` single-file runs.
 */
import { acquireRunLock } from './helpers/run-lock';

export default async function globalSetup() {
  acquireRunLock();
}
