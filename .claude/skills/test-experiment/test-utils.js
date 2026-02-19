/**
 * Test Utilities for Empirica Experiment
 *
 * Copy-paste these helpers into browser_run_code blocks for Playwright MCP testing.
 * Each function is self-contained and can be used independently.
 */

// ============ PLAYER INFO HELPERS ============

/**
 * Get comprehensive player info from data attributes
 * Works during active gameplay
 */
async function getPlayerInfo(page) {
  return await page.evaluate(() => {
    const profile = document.querySelector('[data-player-name]');
    const task = document.querySelector('.task');
    const game = document.querySelector('[data-testid="game-container"]');
    return {
      name: profile?.getAttribute('data-player-name'),
      originalGroup: profile?.getAttribute('data-player-group'),
      currentGroup: task?.getAttribute('data-current-group'),
      role: task?.getAttribute('data-role'),
      targetIndex: parseInt(task?.getAttribute('data-target-index') ?? '-1', 10),
      phase: parseInt(game?.getAttribute('data-game-phase') ?? '0', 10),
      block: parseInt(game?.getAttribute('data-game-block') ?? '-1', 10),
      round: parseInt(game?.getAttribute('data-game-round') ?? '-1', 10),
      stageName: game?.getAttribute('data-stage-name'),
      condition: game?.getAttribute('data-condition')
    };
  });
}

/**
 * Get exit screen info (for removed/finished players)
 * Returns null if not on an exit screen
 */
async function getExitInfo(page) {
  return await page.evaluate(() => {
    const sorry = document.querySelector('[data-testid="sorry-screen"]');
    const quizFailed = document.querySelector('[data-testid="quiz-failed-screen"]');
    const el = sorry || quizFailed;
    if (!el) return null;
    return {
      type: sorry ? 'sorry' : 'quiz-failed',
      exitReason: el.getAttribute('data-exit-reason'),
      prolificCode: el.getAttribute('data-prolific-code'),
      partialPay: el.getAttribute('data-partial-pay'),
      playerId: el.getAttribute('data-player-id')
    };
  });
}

/**
 * Detect what screen/state a player is on
 */
async function getPlayerState(page) {
  const exitInfo = await getExitInfo(page);
  if (exitInfo) return { state: 'exit', ...exitInfo };

  const playerInfo = await getPlayerInfo(page);
  if (playerInfo.stageName) {
    return { state: 'game', ...playerInfo };
  }

  const content = await page.content();
  if (content.includes('Waiting')) return { state: 'lobby' };
  if (content.includes('Consent')) return { state: 'consent' };
  if (content.includes('Comprehension Quiz')) return { state: 'quiz' };
  if (content.includes('Exit Survey')) return { state: 'exit-survey' };
  if (content.includes('End of Phase 1')) return { state: 'transition' };

  return { state: 'unknown' };
}

// ============ GAME ACTION HELPERS ============

/**
 * Complete intro for a player page
 * Call after navigating to player URL
 */
async function completeIntro(page, playerName) {
  // Enter identifier
  await page.getByRole('textbox').fill(playerName);
  await page.getByRole('button', { name: /enter/i }).click();
  await page.waitForTimeout(200);

  // Consent
  await page.getByRole('button', { name: /consent/i }).click();
  await page.waitForTimeout(200);

  // 5 intro pages
  for (let j = 0; j < 5; j++) {
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(100);
  }

  // Quiz answers
  await page.getByRole('radio', { name: /describe the target picture/i }).click();
  await page.getByRole('radio', { name: /removed from the game/i }).click();
  await page.getByRole('radio', { name: /only descriptions of the current/i }).click();
  await page.getByRole('radio', { name: /listeners must wait/i }).click();
  await page.getByRole('radio', { name: /mixed up/i }).click();
  await page.getByRole('radio', { name: /different positions for each player/i }).click();

  // Handle quiz success dialog
  page.once('dialog', async dialog => await dialog.accept());
  await page.getByRole('button', { name: /submit/i }).click();
  await page.waitForTimeout(400);
}

/**
 * Speaker sends a message
 */
async function speakerSendMessage(page, message) {
  const input = page.getByRole('textbox', { name: 'Say something' });
  if (await input.count() > 0) {
    await input.fill(message);
    await input.press('Enter');
    return true;
  }
  return false;
}

/**
 * Listener clicks a tangram
 * @param {number} index - Tangram index (0-5), or -1 for first available
 */
async function listenerClickTangram(page, index = -1) {
  const tangrams = page.locator('.tangrams.grid > div');
  const count = await tangrams.count();
  if (count === 0) return false;

  const clickIndex = index >= 0 && index < count ? index : 0;
  await tangrams.nth(clickIndex).click();
  return true;
}

/**
 * Click Continue button if present
 */
async function clickContinue(page, timeout = 500) {
  try {
    await page.getByRole('button', { name: /continue/i }).click({ timeout });
    return true;
  } catch {
    return false;
  }
}

/**
 * Make social guess (for social_mixed Phase 2)
 * @param {string} guess - 'same' or 'different'
 */
async function makeSocialGuess(page, guess = 'same') {
  try {
    if (guess === 'same') {
      await page.getByRole('button', { name: /yes, same group/i }).click({ timeout: 1000 });
    } else {
      await page.getByRole('button', { name: /no, different group/i }).click({ timeout: 1000 });
    }
    return true;
  } catch {
    return false;
  }
}

// ============ ROUND COMPLETION HELPERS ============

/**
 * Complete a single round for all players
 * @param {Page[]} playerPages - Array of Playwright page objects
 * @param {Object} options - Configuration options
 * @param {number[]} options.skipIndices - Player indices to skip (for idle testing)
 * @param {string[]} options.wrongGroups - Groups that should click wrong tangram
 * @param {boolean} options.makeSocialGuess - Whether to make social guesses
 */
async function completeRound(playerPages, options = {}) {
  const { skipIndices = [], wrongGroups = [], makeSocialGuess: doSocialGuess = false } = options;

  // Click Continue buttons
  for (const p of playerPages) {
    await clickContinue(p);
  }
  await playerPages[0].waitForTimeout(300);

  // Build group → target mapping from speakers
  const groupTargets = {};

  // Speakers send messages
  for (let i = 0; i < playerPages.length; i++) {
    if (skipIndices.includes(i)) continue;
    const p = playerPages[i];
    const info = await getPlayerInfo(p);

    if (info?.role === 'speaker' && info.targetIndex >= 0) {
      groupTargets[info.currentGroup] = info.targetIndex;
      await speakerSendMessage(p, `round message`);
    }
  }
  await playerPages[0].waitForTimeout(300);

  // Listeners click tangrams
  for (let i = 0; i < playerPages.length; i++) {
    if (skipIndices.includes(i)) continue;
    const p = playerPages[i];
    const info = await getPlayerInfo(p);

    if (info?.role === 'listener') {
      const targetIdx = groupTargets[info.currentGroup] ?? 0;
      let clickIdx = targetIdx;

      // Wrong groups click wrong tangram
      if (wrongGroups.includes(info.originalGroup)) {
        clickIdx = (targetIdx + 3) % 6;
      }

      await listenerClickTangram(p, clickIdx);

      // Social guess if needed
      if (doSocialGuess) {
        await p.waitForTimeout(300);
        await makeSocialGuess(p, 'same');
      }
    }
  }
  await playerPages[0].waitForTimeout(300);
}

// ============ PLAYER MANAGEMENT HELPERS ============

/**
 * Get all player pages from browser context
 */
function getPlayerPages(context) {
  return context.pages().filter(p => p.url().includes('participantKey'));
}

/**
 * Get active player pages (those still in game)
 */
async function getActivePlayers(playerPages) {
  const active = [];
  for (const p of playerPages) {
    const state = await getPlayerState(p);
    if (state.state === 'game') {
      active.push(p);
    }
  }
  return active;
}

/**
 * Get players grouped by their original group
 */
async function getPlayersByGroup(playerPages) {
  const groups = { A: [], B: [], C: [] };
  for (const p of playerPages) {
    const info = await getPlayerInfo(p);
    if (info?.originalGroup && groups[info.originalGroup]) {
      groups[info.originalGroup].push({ page: p, ...info });
    }
  }
  return groups;
}

/**
 * Get removed players (on exit screens)
 */
async function getRemovedPlayers(playerPages) {
  const removed = [];
  for (const p of playerPages) {
    const exitInfo = await getExitInfo(p);
    if (exitInfo) {
      removed.push({ page: p, ...exitInfo });
    }
  }
  return removed;
}

// ============ WAIT HELPERS ============

/**
 * Wait for a specific stage
 */
async function waitForStage(page, stageName, timeout = 30000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    const info = await getPlayerInfo(page);
    if (info?.stageName === stageName) return true;
    await page.waitForTimeout(500);
  }
  return false;
}

/**
 * Wait for feedback stage content
 */
async function waitForFeedback(page, timeout = 30000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    const content = await page.content();
    if (content.includes('Correct!') || content.includes('Ooops') ||
        content.includes('You earned') || content.includes('points this round')) {
      return true;
    }
    await page.waitForTimeout(500);
  }
  return false;
}

/**
 * Wait for any player to reach exit screen
 */
async function waitForAnyExit(playerPages, timeout = 60000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    for (const p of playerPages) {
      const exitInfo = await getExitInfo(p);
      if (exitInfo) {
        return { found: true, page: p, ...exitInfo };
      }
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  return { found: false };
}

/**
 * Wait for game to start (players in Selection stage)
 */
async function waitForGameStart(playerPages, timeout = 60000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    for (const p of playerPages) {
      const info = await getPlayerInfo(p);
      if (info?.stageName === 'Selection') {
        return true;
      }
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  return false;
}

// ============ VERIFICATION HELPERS ============

/**
 * Verify all players in a group have consistent state
 */
async function verifyGroupConsistency(playerPages) {
  const groups = await getPlayersByGroup(playerPages);
  const issues = [];

  for (const [groupName, players] of Object.entries(groups)) {
    if (players.length === 0) continue;

    const phases = new Set(players.map(p => p.phase));
    const blocks = new Set(players.map(p => p.block));
    const stages = new Set(players.map(p => p.stageName));

    if (phases.size > 1) issues.push(`Group ${groupName}: inconsistent phases ${[...phases]}`);
    if (blocks.size > 1) issues.push(`Group ${groupName}: inconsistent blocks ${[...blocks]}`);
    if (stages.size > 1) issues.push(`Group ${groupName}: inconsistent stages ${[...stages]}`);

    // Check exactly one speaker
    const speakers = players.filter(p => p.role === 'speaker');
    if (speakers.length !== 1) {
      issues.push(`Group ${groupName}: expected 1 speaker, got ${speakers.length}`);
    }
  }

  return { valid: issues.length === 0, issues };
}

/**
 * Verify no player is alone in their group
 */
async function verifyNoSoloPlayers(playerPages) {
  const groups = await getPlayersByGroup(playerPages);
  const soloPlayers = [];

  for (const [groupName, players] of Object.entries(groups)) {
    const activePlayers = [];
    for (const p of players) {
      const state = await getPlayerState(p.page);
      if (state.state === 'game') {
        activePlayers.push(p);
      }
    }

    if (activePlayers.length === 1) {
      soloPlayers.push({ group: groupName, player: activePlayers[0].name });
    }
  }

  return { valid: soloPlayers.length === 0, soloPlayers };
}

// ============ USAGE EXAMPLES ============
/*
// Example 1: Basic round completion
const playerPages = getPlayerPages(context);
await completeRound(playerPages);

// Example 2: Controlled accuracy test (Group B fails)
await completeRound(playerPages, { wrongGroups: ['B'] });

// Example 3: Idle test (player 0 doesn't act)
await completeRound(playerPages, { skipIndices: [0] });

// Example 4: Check player states after a round
for (const p of playerPages) {
  const state = await getPlayerState(p);
  console.log(state);
}

// Example 5: Wait for and verify exit screen
const exit = await waitForAnyExit(playerPages);
if (exit.found) {
  console.log(`Player exited: ${exit.exitReason}, code: ${exit.prolificCode}`);
}
*/
