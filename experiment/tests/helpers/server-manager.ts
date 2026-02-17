import { execSync, spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

const EXPERIMENT_DIR = path.resolve(__dirname, '../..');
const TAJRIBA_PATH = path.join(EXPERIMENT_DIR, '.empirica/local/tajriba.json');
const SERVER_URL = 'http://localhost:3000';
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

export async function waitForReady(timeout = 60_000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const res = await fetch(SERVER_URL);
      if (res.ok || res.status === 200) return true;
    } catch {
      // Server not ready yet
    }
    await new Promise(r => setTimeout(r, 1000));
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
  await new Promise(r => setTimeout(r, 1000));

  // Spawn empirica server
  serverProcess = spawn('empirica', [], {
    cwd: EXPERIMENT_DIR,
    stdio: 'pipe',
    detached: false,
  });

  serverProcess.stdout?.on('data', (data) => {
    if (process.env.DEBUG) {
      process.stdout.write(`[server] ${data}`);
    }
  });

  serverProcess.stderr?.on('data', (data) => {
    if (process.env.DEBUG) {
      process.stderr.write(`[server:err] ${data}`);
    }
  });

  serverProcess.on('error', (err) => {
    console.error('Server process error:', err);
  });

  // Wait for server to be ready
  const ready = await waitForReady(90_000);
  if (!ready) {
    throw new Error('Server failed to start within 90 seconds');
  }
}

export async function stopServer(): Promise<void> {
  if (serverProcess) {
    serverProcess.kill('SIGTERM');
    serverProcess = null;
  }

  // Also kill any lingering processes on ports
  for (const port of PORTS) {
    killPort(port);
  }

  // Wait for ports to free
  const start = Date.now();
  while (Date.now() - start < 10_000) {
    const anyInUse = PORTS.some(isPortInUse);
    if (!anyInUse) return;
    await new Promise(r => setTimeout(r, 500));
  }
}

export async function resetServer(): Promise<void> {
  await stopServer();
  await new Promise(r => setTimeout(r, 1000));
  await startServer();
}

export function getServerProcess(): ChildProcess | null {
  return serverProcess;
}
