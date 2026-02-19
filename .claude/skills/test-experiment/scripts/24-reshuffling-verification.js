/**
 * 24-reshuffling-verification.js
 *
 * Verifies that group reshuffling in mixed conditions happens at block boundaries only.
 *
 * Expected behavior:
 * - Phase 1: No reshuffling (6 blocks × 6 rounds = 36 rounds)
 * - Phase 2: Reshuffle at start of each block (6 blocks × 6 rounds = 36 rounds)
 */

// Configuration
const CONFIG = {
  ADMIN_URL: 'http://localhost:3000/admin',
  PLAYER_URL: 'http://localhost:3000',
  TREATMENT: 'Refer Mixed (9 players)',
  NUM_PLAYERS: 9,
  PHASE_1_ROUNDS: 36,  // 6 blocks × 6 rounds
  PHASE_2_ROUNDS: 36,  // 6 blocks × 6 rounds
  TOTAL_ROUNDS: 72,
  EXPECTED_RESHUFFLES: 6,  // Once per block in Phase 2
};

/**
 * Track reshuffling events from server logs
 */
class ReshufflingTracker {
  constructor() {
    this.reshuffleEvents = [];
    this.roundData = [];
  }

  recordReshuffle(roundNum, phase, block) {
    this.reshuffleEvents.push({
      roundNum,
      phase,
      block,
      timestamp: Date.now(),
    });
  }

  recordRound(roundNum, phase, block, targetNum) {
    this.roundData.push({
      roundNum,
      phase,
      block,
      targetNum,
      shouldReshuffle: phase === 2 && targetNum === 0,
    });
  }

  verify() {
    const results = {
      totalReshuffles: this.reshuffleEvents.length,
      expectedReshuffles: CONFIG.EXPECTED_RESHUFFLES,
      passed: this.reshuffleEvents.length === CONFIG.EXPECTED_RESHUFFLES,
      events: this.reshuffleEvents,
      errors: [],
    };

    // Check that reshuffles only happened at block boundaries
    for (const event of this.reshuffleEvents) {
      const round = this.roundData.find(r => r.roundNum === event.roundNum);
      if (round && !round.shouldReshuffle) {
        results.errors.push(
          `Unexpected reshuffle at round ${event.roundNum} (Phase ${event.phase}, Block ${event.block}, TargetNum ${round.targetNum})`
        );
        results.passed = false;
      }
    }

    // Check that no reshuffles were missed
    const expectedReshuffleRounds = this.roundData
      .filter(r => r.shouldReshuffle)
      .map(r => r.roundNum);

    const actualReshuffleRounds = this.reshuffleEvents.map(e => e.roundNum);

    for (const expected of expectedReshuffleRounds) {
      if (!actualReshuffleRounds.includes(expected)) {
        results.errors.push(`Missing reshuffle at expected round ${expected}`);
        results.passed = false;
      }
    }

    return results;
  }

  printReport() {
    const results = this.verify();
    console.log('\n========== RESHUFFLING VERIFICATION REPORT ==========\n');
    console.log(`Total reshuffles detected: ${results.totalReshuffles}`);
    console.log(`Expected reshuffles: ${results.expectedReshuffles}`);
    console.log(`Status: ${results.passed ? 'PASSED ✅' : 'FAILED ❌'}`);

    if (results.events.length > 0) {
      console.log('\nReshuffle events:');
      for (const event of results.events) {
        console.log(`  - Round ${event.roundNum}: Phase ${event.phase}, Block ${event.block}`);
      }
    }

    if (results.errors.length > 0) {
      console.log('\nErrors:');
      for (const error of results.errors) {
        console.log(`  ❌ ${error}`);
      }
    }

    console.log('\n' + '='.repeat(50) + '\n');
    return results;
  }
}

/**
 * Parse server log output to detect reshuffling events
 */
function parseServerLog(logContent) {
  const reshufflePattern = /Reshuffling groups for mixed condition/g;
  const matches = logContent.match(reshufflePattern) || [];
  return matches.length;
}

/**
 * Complete intro flow for a single player page
 */
async function completeIntroForPlayer(playerPage, playerNum) {
  // Enter identifier
  await playerPage.getByRole('textbox').fill(`player${playerNum}`);
  await playerPage.waitForTimeout(100);
  await playerPage.getByRole('button', { name: /enter/i }).click();
  await playerPage.waitForTimeout(200);

  // Consent
  await playerPage.getByRole('button', { name: /consent/i }).click();
  await playerPage.waitForTimeout(200);

  // 5 intro pages
  for (let i = 0; i < 5; i++) {
    await playerPage.getByRole('button', { name: /next/i }).click();
    await playerPage.waitForTimeout(100);
  }

  // Quiz answers (Updated 2026-01-08 for new questions)
  await playerPage.getByRole('radio', { name: /describe the target picture/i }).click();
  await playerPage.getByRole('radio', { name: /removed from the game/i }).click();
  await playerPage.getByRole('radio', { name: /only descriptions of the current/i }).click();
  await playerPage.getByRole('radio', { name: /listeners must wait/i }).click();
  await playerPage.getByRole('radio', { name: /mixed up/i }).click();
  await playerPage.getByRole('radio', { name: /different positions for each player/i }).click();

  // Handle dialog and submit
  playerPage.once('dialog', async dialog => await dialog.accept());
  await playerPage.getByRole('button', { name: /submit/i }).click();
  await playerPage.waitForTimeout(400);
}

/**
 * Complete a single round of the game
 */
async function completeRound(playerPages, roundNum) {
  // Click Continue buttons if present
  await Promise.all(playerPages.map(async p => {
    try {
      await p.getByRole('button', { name: /continue/i }).click({ timeout: 1000 });
    } catch {}
  }));
  await playerPages[0].waitForTimeout(300);

  // Find and act as speaker
  for (const p of playerPages) {
    const content = await p.content();
    if (content.includes('You are the speaker')) {
      const input = p.getByRole('textbox', { name: 'Say something' });
      if (await input.count() > 0) {
        await input.fill(`round${roundNum}`);
        await input.press('Enter');
      }
      break;
    }
  }
  await playerPages[0].waitForTimeout(300);

  // Listeners click tangrams
  for (const p of playerPages) {
    const content = await p.content();
    if (content.includes('You are a listener')) {
      const tangrams = p.locator('.tangrams.grid > div');
      if (await tangrams.count() > 0) {
        await tangrams.first().click();
      }
    }
  }
  await playerPages[0].waitForTimeout(500);
}

/**
 * Handle phase transition
 */
async function handlePhaseTransition(playerPages) {
  await playerPages[0].waitForTimeout(2000);
  await Promise.all(playerPages.map(async p => {
    try {
      await p.getByRole('button', { name: /continue/i }).click({ timeout: 5000 });
    } catch {}
  }));
  await playerPages[0].waitForTimeout(1000);
}

/**
 * Main test function - run in browser context
 * Usage: browser_run_code with this function body
 */
async function runReshufflingTest(page) {
  const context = page.context();

  // Create player pages
  const playerPages = [];
  for (let i = 0; i < CONFIG.NUM_PLAYERS; i++) {
    const newPage = await context.newPage();
    await newPage.goto(CONFIG.PLAYER_URL);
    await newPage.waitForTimeout(200);
    await newPage.getByRole('button', { name: /new participant/i }).click();
    await newPage.waitForTimeout(500);
    playerPages.push(newPage);
  }

  // Complete intro for all players
  await Promise.all(playerPages.map((p, i) => completeIntroForPlayer(p, i + 1)));

  // Wait for game to start
  await playerPages[0].waitForTimeout(2000);

  // Play through all rounds
  for (let r = 1; r <= CONFIG.TOTAL_ROUNDS; r++) {
    await completeRound(playerPages, r);
    console.log(`Completed round ${r}`);

    // Handle transition between phases
    if (r === CONFIG.PHASE_1_ROUNDS) {
      console.log('Handling phase transition...');
      await handlePhaseTransition(playerPages);
    }
  }

  return 'Reshuffling test completed - check server logs for verification';
}

// Export for use in browser_run_code or Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    CONFIG,
    ReshufflingTracker,
    parseServerLog,
    completeIntroForPlayer,
    completeRound,
    handlePhaseTransition,
    runReshufflingTest,
  };
}
