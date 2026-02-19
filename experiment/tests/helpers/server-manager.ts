import { execSync, spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

const EXPERIMENT_DIR = path.resolve(__dirname, '../..');
const TAJRIBA_PATH = path.join(EXPERIMENT_DIR, '.empirica/local/tajriba.json');
const SERVER_URL = 'http://localhost:3000';
const TAJRIBA_URL = 'http://localhost:8844';
const PORTS = [3000, 8844];

let serverProcess: ChildProcess | null = null;

function isPortInUse(port: number): boolean {
  try {
    execSync(`lsof -ti:${port}`, { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function killPort(port: number): void {
  try {
    execSync(`lsof -ti:${port} | xargs kill -9 2>/dev/null`, { stdio: 'pipe' });
  } catch {
    // Port may not be in use
  }
}

/**
 * Wait for BOTH the Vite frontend (port 3000) AND the tajriba backend (port 8844)
 * to be ready. The frontend can start before the backend, so checking only port 3000
 * is insufficient — players see a loading spinner until the backend is reachable.
 */
export async function waitForReady(timeout = 120_000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      // Check that both ports are listening
      const frontendUp = isPortInUse(3000);
      const backendUp = isPortInUse(8844);
      if (frontendUp && backendUp) {
        // Verify the frontend actually responds
        const res = await fetch(SERVER_URL);
        if (res.ok || res.status === 200) {
          // Give tajriba extra time to finish initialization.
          // The backend may be listening but not fully ready to handle
          // WebSocket connections and game state yet.
          await new Promise(r => setTimeout(r, 10_000));
          // Double-check both endpoints are still responsive
          const check1 = await fetch(SERVER_URL);
          const check2 = await fetch(TAJRIBA_URL).catch(() => null);
          if (check1.ok || check1.status === 200) {
            return true;
          }
        }
      }
    } catch {
      // Server not ready yet
    }
    await new Promise(r => setTimeout(r, 2000));
  }
  return false;
}

export async function startServer(): Promise<void> {
  // Remove stale state
  if (fs.existsSync(TAJRIBA_PATH)) {
    fs.unlinkSync(TAJRIBA_PATH);
  }

  // Kill any existing processes on our ports
  for (const port of PORTS) {
    killPort(port);
  }
  await new Promise(r => setTimeout(r, 2000));

  // Spawn empirica server in its own process group (detached: true)
  // so it survives Playwright worker lifecycle transitions between projects.
  // Pass TEST_MODE=true so the server uses test-friendly timing and block counts.
  serverProcess = spawn('empirica', [], {
    cwd: EXPERIMENT_DIR,
    stdio: 'ignore',
    detached: true,
    env: { ...process.env, TEST_MODE: process.env.TEST_MODE ?? 'true' },
  });

  // Don't keep the parent process alive waiting for this child
  serverProcess.unref();

  serverProcess.on('error', (err) => {
    console.error('Server process error:', err);
  });

  // Wait for both frontend and backend to be ready
  const ready = await waitForReady(120_000);
  if (!ready) {
    throw new Error('Server failed to start within 120 seconds (checked both ports 3000 and 8844)');
  }
  console.log('[server-manager] Both frontend (3000) and backend (8844) are ready');
}

export async function stopServer(): Promise<void> {
  // Try graceful kill via process reference
  if (serverProcess) {
    try {
      // For detached processes, kill the process group
      process.kill(-serverProcess.pid!, 'SIGTERM');
    } catch {
      try {
        serverProcess.kill('SIGTERM');
      } catch {
        // Process may already be dead
      }
    }
    serverProcess = null;
  }

  // Also kill any lingering processes on ports (works even without process reference)
  for (const port of PORTS) {
    killPort(port);
  }

  // Wait for ports to free
  const start = Date.now();
  while (Date.now() - start < 15_000) {
    const anyInUse = PORTS.some(isPortInUse);
    if (!anyInUse) return;
    await new Promise(r => setTimeout(r, 500));
  }
}

export async function resetServer(): Promise<void> {
  await stopServer();
  await new Promise(r => setTimeout(r, 2000));
  await startServer();
}

export function getServerProcess(): ChildProcess | null {
  return serverProcess;
}
