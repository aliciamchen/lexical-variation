/**
 * Pre-flight Check Script
 * Verifies server health and cleans up stale processes before testing
 */

const { exec } = require('child_process');
const util = require('util');
const execAsync = util.promisify(exec);

// ============ PORT CLEANUP ============

/**
 * Kill processes on specified ports
 * @param {number[]} ports - Ports to clean up
 * @returns {Promise<{port: number, killed: boolean}[]>}
 */
async function cleanupPorts(ports = [3000, 8844]) {
  const results = [];

  for (const port of ports) {
    try {
      await execAsync(`lsof -ti:${port} | xargs kill -9 2>/dev/null`);
      results.push({ port, killed: true });
    } catch (e) {
      // No process on this port - that's fine
      results.push({ port, killed: false });
    }
  }

  // Wait for ports to be released
  await new Promise(r => setTimeout(r, 1000));

  return results;
}

/**
 * Check if a port is available
 * @param {number} port - Port to check
 * @returns {Promise<boolean>}
 */
async function isPortAvailable(port) {
  try {
    const { stdout } = await execAsync(`lsof -ti:${port} 2>/dev/null`);
    return !stdout.trim();
  } catch (e) {
    return true; // No process found = port is available
  }
}

// ============ SERVER HEALTH ============

/**
 * Check if Empirica server is responding
 * @param {string} baseUrl - Server URL (default: http://localhost:3000)
 * @param {number} timeoutMs - Timeout in ms
 * @returns {Promise<{healthy: boolean, latencyMs: number, error?: string}>}
 */
async function checkServerHealth(baseUrl = 'http://localhost:3000', timeoutMs = 5000) {
  const start = Date.now();

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    const response = await fetch(baseUrl, { signal: controller.signal });
    clearTimeout(timeout);

    const latencyMs = Date.now() - start;

    return {
      healthy: response.ok,
      latencyMs,
      statusCode: response.status
    };
  } catch (e) {
    return {
      healthy: false,
      latencyMs: Date.now() - start,
      error: e.message
    };
  }
}

/**
 * Check if admin console is accessible
 * @param {string} baseUrl - Server URL
 * @returns {Promise<boolean>}
 */
async function checkAdminAccess(baseUrl = 'http://localhost:3000') {
  try {
    const response = await fetch(`${baseUrl}/admin`, { redirect: 'follow' });
    return response.ok;
  } catch (e) {
    return false;
  }
}

/**
 * Wait for server to become healthy
 * @param {number} maxWaitMs - Maximum wait time
 * @param {number} checkIntervalMs - Check interval
 * @returns {Promise<boolean>}
 */
async function waitForServerHealth(maxWaitMs = 30000, checkIntervalMs = 1000) {
  const start = Date.now();

  while (Date.now() - start < maxWaitMs) {
    const health = await checkServerHealth();
    if (health.healthy) return true;
    await new Promise(r => setTimeout(r, checkIntervalMs));
  }

  return false;
}

// ============ FULL PREFLIGHT ============

/**
 * Run complete preflight checks
 * @param {object} options - Check options
 * @returns {Promise<{ready: boolean, checks: object}>}
 */
async function runPreflightChecks(options = {}) {
  const {
    cleanPorts = true,
    requireServer = true,
    ports = [3000, 8844],
    baseUrl = 'http://localhost:3000'
  } = options;

  const checks = {
    timestamp: new Date().toISOString(),
    portCleanup: null,
    portsAvailable: null,
    serverHealth: null,
    adminAccess: null
  };

  // Step 1: Clean up ports if requested
  if (cleanPorts) {
    checks.portCleanup = await cleanupPorts(ports);
  }

  // Step 2: Verify ports are available
  const portChecks = await Promise.all(
    ports.map(async port => ({
      port,
      available: await isPortAvailable(port)
    }))
  );
  checks.portsAvailable = portChecks;

  // Step 3: Check server health
  checks.serverHealth = await checkServerHealth(baseUrl);

  // Step 4: Check admin access
  if (checks.serverHealth.healthy) {
    checks.adminAccess = await checkAdminAccess(baseUrl);
  }

  // Determine overall readiness
  const ready = requireServer
    ? checks.serverHealth.healthy && checks.adminAccess
    : portChecks.every(p => p.available);

  return { ready, checks };
}

/**
 * Print preflight results to console
 * @param {object} results - Results from runPreflightChecks
 */
function printPreflightResults(results) {
  console.log('\n=== PREFLIGHT CHECK RESULTS ===\n');

  const { ready, checks } = results;

  // Port cleanup
  if (checks.portCleanup) {
    console.log('Port Cleanup:');
    for (const { port, killed } of checks.portCleanup) {
      console.log(`  Port ${port}: ${killed ? 'Cleaned' : 'Already free'}`);
    }
  }

  // Ports available
  console.log('\nPort Availability:');
  for (const { port, available } of checks.portsAvailable) {
    console.log(`  Port ${port}: ${available ? 'Available' : 'IN USE'}`);
  }

  // Server health
  console.log('\nServer Health:');
  const { healthy, latencyMs, error, statusCode } = checks.serverHealth;
  if (healthy) {
    console.log(`  Status: Healthy (${statusCode})`);
    console.log(`  Latency: ${latencyMs}ms`);
  } else {
    console.log(`  Status: UNHEALTHY`);
    console.log(`  Error: ${error || 'Unknown'}`);
  }

  // Admin access
  if (checks.adminAccess !== null) {
    console.log(`\nAdmin Console: ${checks.adminAccess ? 'Accessible' : 'NOT ACCESSIBLE'}`);
  }

  // Overall
  console.log(`\n=== ${ready ? 'READY TO TEST' : 'NOT READY'} ===\n`);

  return ready;
}

// ============ EXPORTS ============

module.exports = {
  cleanupPorts,
  isPortAvailable,
  checkServerHealth,
  checkAdminAccess,
  waitForServerHealth,
  runPreflightChecks,
  printPreflightResults
};

/**
 * MCP Usage Example:
 *
 * // Run preflight checks before testing
 * Bash: node -e "
 *   const { runPreflightChecks, printPreflightResults } = require('./.claude/skills/test-experiment/scripts/00-preflight-check.js');
 *   runPreflightChecks({ cleanPorts: true }).then(r => {
 *     printPreflightResults(r);
 *     process.exit(r.ready ? 0 : 1);
 *   });
 * "
 *
 * // Or via browser_run_code after navigating:
 * browser_run_code:
 * async (page) => {
 *   const response = await fetch('http://localhost:3000');
 *   const adminResponse = await fetch('http://localhost:3000/admin');
 *   return {
 *     serverOk: response.ok,
 *     adminOk: adminResponse.ok
 *   };
 * }
 */
