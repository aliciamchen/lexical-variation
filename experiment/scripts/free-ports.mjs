#!/usr/bin/env node
// Free the Empirica ports (3000, 8844) for a fresh test run, unless a live
// Playwright run holds the run lock, in which case killing the ports would
// destroy that run's game. Use this instead of `lsof ... | xargs kill -9`.
//
//   npm run test:free-ports
import { execSync } from 'node:child_process';
import { existsSync, readFileSync, unlinkSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const experimentDir = join(dirname(fileURLToPath(import.meta.url)), '..');
const lockPath = join(experimentDir, '.empirica/local/playwright-run.lock');
const ports = [3000, 8844];

function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err.code === 'EPERM';
  }
}

if (existsSync(lockPath)) {
  const lock = JSON.parse(readFileSync(lockPath, 'utf8'));
  if (alive(lock.pid)) {
    console.error(
      `Not freeing ports: a Playwright run is active (pid ${lock.pid}, started ${lock.startedAt}, ${lock.command}).\n` +
        `Wait for it to finish or stop it first.`,
    );
    process.exit(1);
  }
  console.log(`Removing stale lock left by pid ${lock.pid}`);
  unlinkSync(lockPath);
}

for (const port of ports) {
  try {
    execSync(`lsof -ti:${port} | xargs kill -9`, { stdio: 'ignore' });
  } catch {
    // nothing was listening
  }
}
console.log(`Ports ${ports.join(' and ')} are free.`);
