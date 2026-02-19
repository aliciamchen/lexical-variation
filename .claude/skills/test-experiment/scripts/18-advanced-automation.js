/**
 * Advanced Multi-Player Automation Script
 * Enhanced with parallel processing, retry logic, social guessing, and reporting
 *
 * UPDATED 2026-01-07: Added parallel intro processing, social guess verification
 */

const { withRetry, detectGameState, detectPlayerRole, getPlayerPages } = require('./utils.js');
const { TestReporter } = require('./test-reporter.js');

// ============ CONFIGURATION ============

const CONFIG = {
  // Test modes
  FAST: {
    waitBetweenSteps: 100,
    waitAfterClick: 150,
    waitAfterSubmit: 400,
    messageText: 't',
    parallelIntro: true
  },
  NORMAL: {
    waitBetweenSteps: 300,
    waitAfterClick: 300,
    waitAfterSubmit: 700,
    messageText: 'test',
    parallelIntro: true
  },
  VERBOSE: {
    waitBetweenSteps: 500,
    waitAfterClick: 500,
    waitAfterSubmit: 1000,
    messageText: 'testing tangram game',
    parallelIntro: false,
    takeScreenshots: true
  }
};

// ============ PARALLEL INTRO PROCESSING ============

/**
 * Complete intro flow for a single player
 * @param {Page} p - Player page
 * @param {number} playerNum - Player number (1-indexed)
 * @param {object} config - Configuration options
 */
async function completeIntroForPlayer(p, playerNum, config = CONFIG.NORMAL) {
  const { waitBetweenSteps, waitAfterClick, waitAfterSubmit } = config;

  // Enter identifier
  await p.getByRole('textbox').fill(`player${playerNum}`);
  await p.waitForTimeout(waitBetweenSteps);
  await p.getByRole('button', { name: /enter/i }).click();
  await p.waitForTimeout(waitAfterClick);

  // Consent
  await p.getByRole('button', { name: /consent/i }).click();
  await p.waitForTimeout(waitAfterClick);

  // 5 intro pages
  for (let j = 0; j < 5; j++) {
    await p.getByRole('button', { name: /next/i }).click();
    await p.waitForTimeout(waitBetweenSteps);
  }

  // Quiz answers (Updated 2026-01-08 for new questions)
  await p.getByRole('radio', { name: /describe the target picture/i }).click();
  await p.waitForTimeout(waitBetweenSteps / 2);

  await p.getByRole('radio', { name: /removed from the game/i }).click();
  await p.waitForTimeout(waitBetweenSteps / 2);

  await p.getByRole('radio', { name: /only descriptions of the current/i }).click();
  await p.waitForTimeout(waitBetweenSteps / 2);

  await p.getByRole('radio', { name: /listeners must wait/i }).click();
  await p.waitForTimeout(waitBetweenSteps / 2);

  await p.getByRole('radio', { name: /mixed up/i }).click();
  await p.waitForTimeout(waitBetweenSteps / 2);

  await p.getByRole('radio', { name: /different positions for each player/i }).click();
  await p.waitForTimeout(waitBetweenSteps / 2);

  // Submit with dialog handler
  p.once('dialog', async dialog => await dialog.accept());
  await p.getByRole('button', { name: /submit/i }).click();
  await p.waitForTimeout(waitAfterSubmit);

  return `Player ${playerNum} completed intro`;
}

/**
 * Complete intro for all players in PARALLEL
 * Much faster than sequential processing
 * @param {Page} page - Any page in the context
 * @param {object} config - Configuration options
 */
async function completeIntroForAllPlayersParallel(page, config = CONFIG.NORMAL) {
  const playerPages = await getPlayerPages(page);

  if (config.parallelIntro) {
    // Process all players in parallel
    const results = await Promise.allSettled(
      playerPages.map((p, i) =>
        withRetry(() => completeIntroForPlayer(p, i + 1, config), 2)
      )
    );

    const completed = results.filter(r => r.status === 'fulfilled').length;
    const failed = results.filter(r => r.status === 'rejected');

    if (failed.length > 0) {
      console.log(`Failed players: ${failed.map(f => f.reason?.message).join(', ')}`);
    }

    return `Completed intro for ${completed}/${playerPages.length} players (parallel)`;
  } else {
    // Sequential processing (for verbose mode with screenshots)
    let completed = 0;
    for (let i = 0; i < playerPages.length; i++) {
      try {
        await completeIntroForPlayer(playerPages[i], i + 1, config);
        completed++;
      } catch (e) {
        console.log(`Player ${i + 1} error: ${e.message}`);
      }
    }
    return `Completed intro for ${completed}/${playerPages.length} players (sequential)`;
  }
}

// ============ ROUND COMPLETION WITH SOCIAL GUESSING ============

/**
 * Complete one round with social guessing support
 * @param {Page} page - Any page in the context
 * @param {object} options - Options
 */
async function completeRoundWithSocialGuessing(page, options = {}) {
  const {
    config = CONFIG.NORMAL,
    isSocialMixed = false,
    isPhase2 = false
  } = options;

  const playerPages = await getPlayerPages(page);
  const { waitBetweenSteps, waitAfterClick, messageText } = config;

  // Step 1: Click Continue buttons if in feedback stage
  await Promise.all(playerPages.map(async (p) => {
    try {
      const continueBtn = p.getByRole('button', { name: /continue/i });
      if (await continueBtn.count() > 0) {
        await continueBtn.click();
      }
    } catch (e) {}
  }));
  await page.waitForTimeout(waitBetweenSteps);

  // Step 2: Speaker sends message
  let speakerSent = false;
  for (const p of playerPages) {
    try {
      const role = await detectPlayerRole(p);
      if (role === 'speaker') {
        const chatInput = p.getByRole('textbox', { name: 'Say something' });
        if (await chatInput.count() > 0) {
          await chatInput.fill(messageText);
          await chatInput.press('Enter');
          speakerSent = true;
          break;
        }
      }
    } catch (e) {}
  }
  await page.waitForTimeout(waitAfterClick);

  // Step 3: Listeners click tangrams
  let listenersClicked = 0;
  for (const p of playerPages) {
    try {
      const role = await detectPlayerRole(p);
      if (role === 'listener') {
        const tangrams = p.locator('.tangrams.grid > div');
        if (await tangrams.count() > 0) {
          await tangrams.first().click();
          listenersClicked++;
          await p.waitForTimeout(waitBetweenSteps);

          // Step 4: Social guessing (if social_mixed and Phase 2)
          if (isSocialMixed && isPhase2) {
            try {
              // Look for social guess buttons (Group A, Group B, Group C)
              const socialGuessButtons = p.locator('button:has-text("Group")');
              const buttonCount = await socialGuessButtons.count();
              if (buttonCount > 0) {
                // Click a random group button
                const randomIndex = Math.floor(Math.random() * buttonCount);
                await socialGuessButtons.nth(randomIndex).click();
                await p.waitForTimeout(waitBetweenSteps);
              }
            } catch (e) {
              // Social guess buttons might not be visible yet
            }
          }
        }
      }
    } catch (e) {}
  }
  await page.waitForTimeout(waitAfterClick);

  return {
    speakerSent,
    listenersClicked,
    socialGuessHandled: isSocialMixed && isPhase2
  };
}

/**
 * Complete multiple rounds efficiently
 * @param {Page} page - Any page in the context
 * @param {number} numRounds - Number of rounds to complete
 * @param {object} options - Options
 */
async function completeMultipleRounds(page, numRounds, options = {}) {
  const results = [];

  for (let i = 0; i < numRounds; i++) {
    const roundResult = await completeRoundWithSocialGuessing(page, options);
    results.push(roundResult);

    // Log progress every 6 rounds (one block)
    if ((i + 1) % 6 === 0) {
      console.log(`Completed ${i + 1}/${numRounds} rounds`);
    }
  }

  return {
    totalRounds: numRounds,
    completedRounds: results.length,
    speakerMessages: results.filter(r => r.speakerSent).length,
    listenerClicks: results.reduce((sum, r) => sum + r.listenersClicked, 0)
  };
}

// ============ FULL TEST ORCHESTRATION ============

/**
 * Run a complete test with reporting
 * @param {Page} page - Any page in the context
 * @param {object} testOptions - Test configuration
 */
async function runFullTestWithReporting(page, testOptions = {}) {
  const {
    testName = 'Unnamed Test',
    numPlayers = 3,
    condition = 'refer_separated',
    mode = 'NORMAL',
    takeScreenshots = false
  } = testOptions;

  const config = CONFIG[mode] || CONFIG.NORMAL;
  const reporter = new TestReporter(testName);
  const isSocialMixed = condition === 'social_mixed';

  try {
    // Phase 1: Intro
    await reporter.checkpoint('Starting intro flow');
    const introResult = await completeIntroForAllPlayersParallel(page, config);
    await reporter.checkpoint('Intro complete', page, takeScreenshots);
    reporter.verify('All players completed intro', introResult.includes(`${numPlayers}/${numPlayers}`));

    // Wait for game to start
    await page.waitForTimeout(2000);
    await reporter.checkpoint('Game started', page, takeScreenshots);

    // Phase 1: Play rounds (2 blocks = 12 rounds in test mode)
    const phase1Blocks = 2;
    const roundsPerBlock = 6;
    const phase1Rounds = phase1Blocks * roundsPerBlock;

    await reporter.checkpoint('Starting Phase 1');
    const phase1Result = await completeMultipleRounds(page, phase1Rounds, {
      config,
      isSocialMixed,
      isPhase2: false
    });
    await reporter.checkpoint('Phase 1 complete', page, takeScreenshots);
    reporter.verify('Phase 1 rounds completed', phase1Result.completedRounds === phase1Rounds);

    // Handle phase transition
    await reporter.checkpoint('Phase transition');
    const playerPages = await getPlayerPages(page);
    for (const p of playerPages) {
      try {
        const continueBtn = p.getByRole('button', { name: /continue/i });
        if (await continueBtn.count() > 0) await continueBtn.click();
      } catch (e) {}
    }
    await page.waitForTimeout(1000);

    // Phase 2: Play rounds
    const phase2Blocks = 2;
    const phase2Rounds = phase2Blocks * roundsPerBlock;

    await reporter.checkpoint('Starting Phase 2');
    const phase2Result = await completeMultipleRounds(page, phase2Rounds, {
      config,
      isSocialMixed,
      isPhase2: true
    });
    await reporter.checkpoint('Phase 2 complete', page, takeScreenshots);
    reporter.verify('Phase 2 rounds completed', phase2Result.completedRounds === phase2Rounds);

    // Check for game completion
    await page.waitForTimeout(1000);
    const finalState = await detectGameState(playerPages[0]);
    reporter.verify('Game completed', finalState === 'exit_survey' || finalState === 'game_complete');

    await reporter.checkpoint('Test complete', page, takeScreenshots);

  } catch (error) {
    reporter.error('Test failed', error);
  }

  return reporter.printSummary();
}

// ============ EDGE CASE HELPERS ============

/**
 * Simulate player dropout by closing a tab
 * @param {Page} page - Any page in the context
 * @param {number} playerIndex - Which player to drop (0-indexed)
 */
async function simulatePlayerDropout(page, playerIndex = 0) {
  const playerPages = await getPlayerPages(page);
  if (playerIndex < playerPages.length) {
    await playerPages[playerIndex].close();
    return `Closed player ${playerIndex + 1} tab`;
  }
  return 'No player to close';
}

/**
 * Make a player go idle (don't respond for multiple rounds)
 * @param {Page} page - Any page in the context
 * @param {number} playerIndex - Which player should be idle
 * @param {number} numRounds - How many rounds to skip
 */
async function simulateIdlePlayer(page, playerIndex, numRounds = 2) {
  const playerPages = await getPlayerPages(page);
  const idlePage = playerPages[playerIndex];

  // Just complete rounds for other players, not the idle one
  for (let i = 0; i < numRounds; i++) {
    const activePlayers = playerPages.filter((_, idx) => idx !== playerIndex);

    // Speaker sends if not idle
    for (const p of activePlayers) {
      try {
        const role = await detectPlayerRole(p);
        if (role === 'speaker') {
          const chatInput = p.getByRole('textbox', { name: 'Say something' });
          if (await chatInput.count() > 0) {
            await chatInput.fill('t');
            await chatInput.press('Enter');
          }
        }
      } catch (e) {}
    }

    await page.waitForTimeout(500);

    // Listeners click (except idle player)
    for (const p of activePlayers) {
      try {
        const role = await detectPlayerRole(p);
        if (role === 'listener') {
          const tangrams = p.locator('.tangrams.grid > div');
          if (await tangrams.count() > 0) {
            await tangrams.first().click();
          }
        }
      } catch (e) {}
    }

    // Wait for timeout or continue
    await page.waitForTimeout(5000);
  }

  return `Player ${playerIndex + 1} was idle for ${numRounds} rounds`;
}

// ============ EXPORTS ============

module.exports = {
  CONFIG,
  completeIntroForPlayer,
  completeIntroForAllPlayersParallel,
  completeRoundWithSocialGuessing,
  completeMultipleRounds,
  runFullTestWithReporting,
  simulatePlayerDropout,
  simulateIdlePlayer
};

/**
 * MCP USAGE - Fast 3-Player Test:
 *
 * browser_run_code with:
 * async (page) => {
 *   // Complete intro in parallel
 *   const context = page.context();
 *   const playerPages = context.pages().filter(p => p.url().includes('participantKey'));
 *
 *   const introPromises = playerPages.map(async (p, i) => {
 *     try {
 *       await p.getByRole('textbox').fill(`player${i + 1}`);
 *       await p.waitForTimeout(100);
 *       await p.getByRole('button', { name: /enter/i }).click();
 *       await p.waitForTimeout(200);
 *       await p.getByRole('button', { name: /consent/i }).click();
 *       await p.waitForTimeout(200);
 *       for (let j = 0; j < 5; j++) {
 *         await p.getByRole('button', { name: /next/i }).click();
 *         await p.waitForTimeout(100);
 *       }
 *       // Quiz answers (Updated 2026-01-08)
 *       await p.getByRole('radio', { name: /describe the target picture/i }).click();
 *       await p.getByRole('radio', { name: /removed from the game/i }).click();
 *       await p.getByRole('radio', { name: /only descriptions of the current/i }).click();
 *       await p.getByRole('radio', { name: /listeners must wait/i }).click();
 *       await p.getByRole('radio', { name: /mixed up/i }).click();
 *       await p.getByRole('radio', { name: /different positions for each player/i }).click();
 *       p.once('dialog', async dialog => await dialog.accept());
 *       await p.getByRole('button', { name: /submit/i }).click();
 *       await p.waitForTimeout(400);
 *       return 'done';
 *     } catch (e) { return e.message; }
 *   });
 *
 *   const results = await Promise.allSettled(introPromises);
 *   return `Intro complete: ${results.filter(r => r.value === 'done').length}/${playerPages.length}`;
 * }
 */
