/**
 * Test Experiment Utilities
 * Common functions for retry logic, state detection, and helpers
 */

// ============ RETRY LOGIC ============

/**
 * Execute a function with retry logic
 * @param {Function} fn - Async function to execute
 * @param {number} maxAttempts - Maximum retry attempts (default: 3)
 * @param {number} delayMs - Delay between retries in ms (default: 500)
 * @returns {Promise<any>} - Result of the function
 */
async function withRetry(fn, maxAttempts = 3, delayMs = 500) {
  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        console.log(`Attempt ${attempt} failed, retrying in ${delayMs}ms...`);
        await new Promise(r => setTimeout(r, delayMs));
      }
    }
  }
  throw lastError;
}

// ============ STATE DETECTION ============

/**
 * Detect current game state from page content
 * @param {Page} page - Playwright page object
 * @returns {Promise<string>} - Current state
 */
async function detectGameState(page) {
  try {
    const content = await page.content();
    const url = page.url();

    // Check URL first
    if (!url.includes('participantKey')) {
      return 'no_participant';
    }

    // Check page content for state indicators
    if (content.includes('Exit Survey')) return 'exit_survey';
    if (content.includes('Game Complete')) return 'game_complete';
    if (content.includes('bonus_info')) return 'bonus_info';
    if (content.includes('Removed for Inactivity')) return 'kicked_idle';
    if (content.includes('group disbanded')) return 'kicked_disbanded';
    if (content.includes('QUIZFAIL')) return 'quiz_failed';
    if (content.includes('Phase 2') && content.includes('Transition')) return 'phase2_transition';
    if (content.includes('Phase 2')) return 'phase2_game';
    if (content.includes('Phase 1') && content.includes('Transition')) return 'phase1_transition';
    if (content.includes('Phase 1')) return 'phase1_game';
    if (content.includes('Waiting for other players')) return 'lobby';
    if (content.includes('Submit') && content.includes('quiz')) return 'quiz';
    if (content.includes('Next') && content.includes('Introduction')) return 'introduction';
    if (content.includes('I consent')) return 'consent';
    if (content.includes('Enter your Player Identifier')) return 'identifier';

    return 'unknown';
  } catch (e) {
    return 'error';
  }
}

/**
 * Detect player role from page content
 * @param {Page} page - Playwright page object
 * @returns {Promise<string>} - 'speaker', 'listener', or 'unknown'
 */
async function detectPlayerRole(page) {
  try {
    const content = await page.content();
    if (content.includes('You are the speaker')) return 'speaker';
    if (content.includes('You are a listener')) return 'listener';
    return 'unknown';
  } catch (e) {
    return 'error';
  }
}

/**
 * Detect current phase and block from page
 * @param {Page} page - Playwright page object
 * @returns {Promise<{phase: number, block: number}>}
 */
async function detectPhaseAndBlock(page) {
  try {
    const content = await page.content();
    const phaseMatch = content.match(/Phase (\d+)/);
    const blockMatch = content.match(/Block (\d+)/);
    return {
      phase: phaseMatch ? parseInt(phaseMatch[1]) : 0,
      block: blockMatch ? parseInt(blockMatch[1]) : 0
    };
  } catch (e) {
    return { phase: 0, block: 0 };
  }
}

/**
 * Detect current stage from page
 * @param {Page} page - Playwright page object
 * @returns {Promise<string>} - 'selection', 'feedback', 'transition', or 'unknown'
 */
async function detectStage(page) {
  try {
    const content = await page.content();
    if (content.includes('Selection')) return 'selection';
    if (content.includes('Feedback')) return 'feedback';
    if (content.includes('Transition')) return 'transition';
    return 'unknown';
  } catch (e) {
    return 'error';
  }
}

// ============ PLAYER HELPERS ============

/**
 * Get all player pages from browser context
 * @param {Page} page - Any page in the context
 * @returns {Promise<Page[]>} - Array of player pages
 */
async function getPlayerPages(page) {
  const context = page.context();
  const allPages = context.pages();
  return allPages.filter(p => p.url().includes('participantKey'));
}

/**
 * Get player info from page
 * @param {Page} page - Player page
 * @returns {Promise<{name: string, role: string, score: number}>}
 */
async function getPlayerInfo(page) {
  try {
    const content = await page.content();

    // Extract player name
    const nameMatch = content.match(/(\w+) \(You\)/);
    const name = nameMatch ? nameMatch[1] : 'Unknown';

    // Get role
    const role = await detectPlayerRole(page);

    // Extract score
    const scoreMatch = content.match(/Score.*?(\d+)/s);
    const score = scoreMatch ? parseInt(scoreMatch[1]) : 0;

    return { name, role, score };
  } catch (e) {
    return { name: 'Error', role: 'error', score: 0 };
  }
}

// ============ WAIT HELPERS ============

/**
 * Wait for a specific game state
 * @param {Page} page - Player page
 * @param {string} targetState - State to wait for
 * @param {number} timeoutMs - Timeout in ms (default: 30000)
 * @returns {Promise<boolean>} - True if state reached
 */
async function waitForState(page, targetState, timeoutMs = 30000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    const currentState = await detectGameState(page);
    if (currentState === targetState) return true;
    await new Promise(r => setTimeout(r, 500));
  }
  return false;
}

/**
 * Wait for element to be clickable
 * @param {Page} page - Player page
 * @param {string} selector - Element selector
 * @param {number} timeoutMs - Timeout in ms (default: 10000)
 */
async function waitForClickable(page, selector, timeoutMs = 10000) {
  await page.waitForSelector(selector, { state: 'visible', timeout: timeoutMs });
  await page.waitForSelector(selector, { state: 'attached', timeout: timeoutMs });
}

// ============ TANGRAM DETECTION ============

/**
 * Verify tangrams are loaded on the page
 * @param {Page} page - Player page
 * @param {number} expectedCount - Expected tangram count (default: 6)
 * @param {number} timeoutMs - Timeout in ms (default: 5000)
 * @returns {Promise<{loaded: boolean, count: number, error?: string}>}
 */
async function verifyTangramsLoaded(page, expectedCount = 6, timeoutMs = 5000) {
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    try {
      // Try multiple selectors for tangrams
      const selectors = [
        '.tangrams.grid > div',
        '.tangrams.grid img',
        'div[style*="tangram"]',
        '.all-tangrams img'
      ];

      for (const selector of selectors) {
        const count = await page.locator(selector).count();
        if (count >= expectedCount) {
          return { loaded: true, count, selector };
        }
      }

      await page.waitForTimeout(200);
    } catch (e) {
      // Continue trying
    }
  }

  return {
    loaded: false,
    count: 0,
    error: `Tangrams failed to load within ${timeoutMs}ms - check server logs for errors`
  };
}

/**
 * Click a tangram by index
 * @param {Page} page - Player page
 * @param {number} index - Tangram index (0-5)
 * @returns {Promise<boolean>}
 */
async function clickTangram(page, index = 0) {
  const selectors = [
    '.tangrams.grid > div',
    'div[style*="tangram"]'
  ];

  for (const selector of selectors) {
    try {
      const tangrams = page.locator(selector);
      const count = await tangrams.count();
      if (count > index) {
        await tangrams.nth(index).click();
        return true;
      }
    } catch (e) {
      // Try next selector
    }
  }

  return false;
}

// ============ SCREENSHOT ON FAILURE ============

/**
 * Execute a function and capture screenshot on failure
 * @param {Page} page - Player page
 * @param {Function} fn - Async function to execute
 * @param {string} name - Test name for screenshot filename
 * @param {string} screenshotDir - Directory for screenshots (default: /tmp)
 * @returns {Promise<any>}
 */
async function withScreenshotOnError(page, fn, name = 'test', screenshotDir = '/tmp') {
  try {
    return await fn();
  } catch (error) {
    const timestamp = Date.now();
    const filename = `${screenshotDir}/test-failure-${name}-${timestamp}.png`;

    try {
      await page.screenshot({ path: filename, fullPage: true });
      console.error(`Screenshot saved: ${filename}`);
    } catch (screenshotError) {
      console.error(`Failed to capture screenshot: ${screenshotError.message}`);
    }

    // Re-throw original error with screenshot info
    error.screenshot = filename;
    throw error;
  }
}

/**
 * Capture a checkpoint screenshot
 * @param {Page} page - Player page
 * @param {string} checkpointName - Name for the checkpoint
 * @param {string} screenshotDir - Directory for screenshots
 * @returns {Promise<string>} - Screenshot path
 */
async function captureCheckpoint(page, checkpointName, screenshotDir = '/tmp/test-checkpoints') {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `${screenshotDir}/${checkpointName}-${timestamp}.png`;

  try {
    await page.screenshot({ path: filename, fullPage: true });
    return filename;
  } catch (e) {
    console.error(`Failed to capture checkpoint ${checkpointName}: ${e.message}`);
    return null;
  }
}

// ============ TEST MODE VALIDATION ============

/**
 * Verify server is running with expected configuration
 * @param {Page} page - Admin page
 * @returns {Promise<{valid: boolean, config: object}>}
 */
async function verifyServerConfig(page) {
  try {
    // Navigate to admin if not already there
    if (!page.url().includes('/admin')) {
      await page.goto('http://localhost:3000/admin');
      await page.waitForTimeout(500);
    }

    // Check for treatment info
    const content = await page.content();

    // Look for treatments
    const hasTreatments = content.includes('9 players');

    // Check if batches are visible
    const hasBatches = content.includes('Batches');

    return {
      valid: hasBatches,
      config: {
        hasTreatments,
        adminAccessible: true
      }
    };
  } catch (e) {
    return {
      valid: false,
      config: {
        error: e.message,
        adminAccessible: false
      }
    };
  }
}

/**
 * Verify game timing matches expected test mode
 * Checks the selection stage duration to determine if TEST_MODE is enabled
 * @param {Page} page - Player page (must be in game)
 * @returns {Promise<{testMode: boolean, selectionDuration: number}>}
 */
async function detectTestMode(page) {
  try {
    const content = await page.content();

    // Look for timer in format "MM:SS" or "M:SS"
    const timerMatch = content.match(/(\d{1,2}):(\d{2})/);
    if (timerMatch) {
      const minutes = parseInt(timerMatch[1]);
      const seconds = parseInt(timerMatch[2]);
      const totalSeconds = minutes * 60 + seconds;

      // TEST_MODE has 120s selection, production has 45s
      // If timer shows > 60s, likely TEST_MODE
      return {
        testMode: totalSeconds > 60,
        observedTimer: totalSeconds,
        note: totalSeconds > 60 ? 'Long timer suggests TEST_MODE=true' : 'Short timer suggests production mode'
      };
    }

    return { testMode: null, observedTimer: null, note: 'Could not detect timer' };
  } catch (e) {
    return { testMode: null, error: e.message };
  }
}

// ============ EXPORTS ============

module.exports = {
  // Retry logic
  withRetry,

  // State detection
  detectGameState,
  detectPlayerRole,
  detectPhaseAndBlock,
  detectStage,

  // Player helpers
  getPlayerPages,
  getPlayerInfo,

  // Wait helpers
  waitForState,
  waitForClickable,

  // Tangram detection (NEW)
  verifyTangramsLoaded,
  clickTangram,

  // Screenshot on failure (NEW)
  withScreenshotOnError,
  captureCheckpoint,

  // Test mode validation (NEW)
  verifyServerConfig,
  detectTestMode
};
