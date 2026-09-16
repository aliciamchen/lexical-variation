/**
 * One Playwright run at a time.
 *
 * Every run binds the same Empirica ports (3000 and 8844) and resets the
 * server's state, so two runs on one machine destroy each other's games. The
 * runner takes a lock file in global setup and releases it in global teardown;
 * a second run finds the lock, sees that the owning process is still alive,
 * and stops before touching the server. A lock whose owner has exited (a run
 * that crashed or was killed) is treated as stale and replaced.
 */
import * as fs from 'fs';
import * as path from 'path';

const EXPERIMENT_DIR = path.resolve(__dirname, '../..');
export const LOCK_PATH = path.join(EXPERIMENT_DIR, '.empirica/local/playwright-run.lock');

interface RunLock {
  pid: number;
  startedAt: string;
  command: string;
}

function processAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    // EPERM means the process exists but belongs to another user
    return (err as NodeJS.ErrnoException).code === 'EPERM';
  }
}

function readLock(): RunLock | null {
  try {
    return JSON.parse(fs.readFileSync(LOCK_PATH, 'utf8')) as RunLock;
  } catch {
    return null;
  }
}

/** The lock's owner, if it belongs to a live run other than this process. */
export function liveForeignLock(): RunLock | null {
  const existing = readLock();
  if (!existing || existing.pid === process.pid) return null;
  return processAlive(existing.pid) ? existing : null;
}

function conflictMessage(lock: RunLock): string {
  return (
    `Another Playwright run is using the Empirica server on ports 3000 and 8844:\n` +
    `  pid ${lock.pid}, started ${lock.startedAt}\n` +
    `  ${lock.command}\n` +
    `Wait for it to finish or stop it, then rerun. If that process is gone but the ` +
    `lock remains, delete ${LOCK_PATH}.`
  );
}

/**
 * Throw if a live run holds the lock. Called from playwright.config.ts in the
 * runner process, because Playwright clears test-results before global setup
 * runs, and the runner must not do even that while another run's traces are
 * being written there. Workers load the config too but must not check: the
 * lock then belongs to their own runner.
 */
export function assertNoOtherRun(): void {
  if (process.env.TEST_WORKER_INDEX !== undefined) return;
  const lock = liveForeignLock();
  if (lock) throw new Error(conflictMessage(lock));
}

/** Take the lock for this runner process, or throw if a live run holds it. */
export function acquireRunLock(): void {
  const existing = readLock();
  if (existing) {
    if (existing.pid === process.pid) return;
    if (processAlive(existing.pid)) throw new Error(conflictMessage(existing));
    console.log(`[run-lock] Removing stale lock left by pid ${existing.pid} (${existing.startedAt})`);
  }
  const lock: RunLock = {
    pid: process.pid,
    startedAt: new Date().toISOString(),
    // `npm run <script>` names the script; `npx playwright ...` sets the
    // lifecycle event to "npx", where the argv is the informative part.
    command:
      process.env.npm_lifecycle_event && process.env.npm_lifecycle_event !== 'npx'
        ? `npm run ${process.env.npm_lifecycle_event}`
        : `playwright ${process.argv.slice(2).join(' ')}`,
  };
  fs.mkdirSync(path.dirname(LOCK_PATH), { recursive: true });
  fs.writeFileSync(LOCK_PATH, JSON.stringify(lock, null, 2));
}

/** Release the lock if this runner process holds it. */
export function releaseRunLock(): void {
  const existing = readLock();
  if (existing && existing.pid === process.pid) {
    try {
      fs.unlinkSync(LOCK_PATH);
    } catch {
      // Already gone
    }
  }
}
