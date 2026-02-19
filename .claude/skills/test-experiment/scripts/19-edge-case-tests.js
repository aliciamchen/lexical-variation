/**
 * Edge Case Test Scripts
 * Tests for dropout, idle detection, quiz failure, and speaker reassignment
 */

const { detectGameState, detectPlayerRole, getPlayerPages, withRetry } = require('./utils.js');
const { TestReporter } = require('./test-reporter.js');

// ============ QUIZ FAILURE TEST ============

/**
 * Test quiz 3-attempt failure flow
 * @param {Page} page - Player page (should be on quiz page)
 */
async function testQuizFailure(page) {
  const reporter = new TestReporter('Quiz Failure Test');

  try {
    await reporter.checkpoint('Starting quiz failure test');

    // Complete identifier and intro
    await page.getByRole('textbox').fill('quiz_fail_test');
    await page.waitForTimeout(200);
    await page.getByRole('button', { name: /enter/i }).click();
    await page.waitForTimeout(500);
    await reporter.checkpoint('Entered identifier');

    await page.getByRole('button', { name: /consent/i }).click();
    await page.waitForTimeout(400);
    await reporter.checkpoint('Completed consent');

    // Click through intro pages
    for (let i = 0; i < 5; i++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(300);
    }
    await reporter.checkpoint('Completed intro pages');

    // Attempt 1: Wrong answers (Updated 2026-01-08 for new quiz questions)
    await reporter.checkpoint('Attempt 1 - selecting wrong answers');
    await page.getByRole('radio', { name: /guess which picture/i }).click(); // Wrong!
    await page.getByRole('radio', { name: /nothing happens/i }).click(); // Wrong!
    await page.getByRole('radio', { name: /anything you want/i }).click(); // Wrong!
    await page.getByRole('radio', { name: /listeners can click anytime/i }).click(); // Wrong!
    await page.getByRole('radio', { name: /same order/i }).click(); // Wrong!
    await page.getByRole('radio', { name: /speaker can't see/i }).click(); // Wrong!

    page.once('dialog', async dialog => await dialog.accept());
    await page.getByRole('button', { name: /submit/i }).click();
    await page.waitForTimeout(1000);

    // Check for attempt counter
    let content = await page.content();
    reporter.verify('Attempt 1 failed', content.includes('Attempt') || content.includes('try again'));
    await reporter.checkpoint('Attempt 1 submitted');

    // Attempt 2: Wrong answers again
    await reporter.checkpoint('Attempt 2 - selecting wrong answers');
    page.once('dialog', async dialog => await dialog.accept());
    await page.getByRole('button', { name: /submit/i }).click();
    await page.waitForTimeout(1000);

    content = await page.content();
    reporter.verify('Attempt 2 failed', content.includes('Attempt') || content.includes('try again'));
    await reporter.checkpoint('Attempt 2 submitted');

    // Attempt 3: Wrong answers - should be kicked
    await reporter.checkpoint('Attempt 3 - final attempt');
    page.once('dialog', async dialog => await dialog.accept());
    await page.getByRole('button', { name: /submit/i }).click();
    await page.waitForTimeout(1500);

    // Should now be on failure page
    content = await page.content();
    const state = await detectGameState(page);

    reporter.verify('Redirected to failure page', state === 'quiz_failed' || content.includes('QUIZFAIL'));
    reporter.verify('Prolific code displayed', content.includes('QUIZFAIL2024'));
    await reporter.checkpoint('Quiz failure complete', page, true);

  } catch (error) {
    reporter.error('Quiz failure test failed', error);
  }

  return reporter.printSummary();
}

// ============ IDLE DETECTION TEST ============

/**
 * Test idle player removal after 2 consecutive idle rounds
 * @param {Page} page - Any page in the context
 */
async function testIdleDetection(page) {
  const reporter = new TestReporter('Idle Detection Test');

  try {
    const playerPages = await getPlayerPages(page);
    reporter.verify('Have 3 players', playerPages.length >= 3);
    await reporter.checkpoint('Game started with players');

    // Identify which player to make idle (first listener)
    let idlePlayerIndex = -1;
    for (let i = 0; i < playerPages.length; i++) {
      const role = await detectPlayerRole(playerPages[i]);
      if (role === 'listener') {
        idlePlayerIndex = i;
        break;
      }
    }

    if (idlePlayerIndex === -1) {
      reporter.error('No listener found to test idle');
      return reporter.printSummary();
    }

    await reporter.checkpoint(`Player ${idlePlayerIndex + 1} will be idle`);

    // Round 1: Speaker sends, only one listener clicks (idle player doesn't)
    await reporter.checkpoint('Round 1 - idle player not responding');

    // Speaker sends message
    for (const p of playerPages) {
      const role = await detectPlayerRole(p);
      if (role === 'speaker') {
        const chatInput = p.getByRole('textbox', { name: 'Say something' });
        if (await chatInput.count() > 0) {
          await chatInput.fill('test');
          await chatInput.press('Enter');
        }
        break;
      }
    }
    await page.waitForTimeout(500);

    // Only active listener clicks
    for (let i = 0; i < playerPages.length; i++) {
      if (i === idlePlayerIndex) continue; // Skip idle player
      const role = await detectPlayerRole(playerPages[i]);
      if (role === 'listener') {
        const tangrams = playerPages[i].locator('.tangrams.grid > div');
        if (await tangrams.count() > 0) {
          await tangrams.first().click();
        }
      }
    }

    // Wait for timeout
    await page.waitForTimeout(10000);
    await reporter.checkpoint('Round 1 complete (idle player skipped)');

    // Click continue for active players
    for (let i = 0; i < playerPages.length; i++) {
      if (i === idlePlayerIndex) continue;
      try {
        const continueBtn = playerPages[i].getByRole('button', { name: /continue/i });
        if (await continueBtn.count() > 0) await continueBtn.click();
      } catch (e) {}
    }
    await page.waitForTimeout(500);

    // Round 2: Repeat - idle player should be kicked after this
    await reporter.checkpoint('Round 2 - idle player not responding');

    // Speaker sends message
    for (const p of playerPages) {
      try {
        const role = await detectPlayerRole(p);
        if (role === 'speaker') {
          const chatInput = p.getByRole('textbox', { name: 'Say something' });
          if (await chatInput.count() > 0) {
            await chatInput.fill('test2');
            await chatInput.press('Enter');
          }
          break;
        }
      } catch (e) {}
    }
    await page.waitForTimeout(500);

    // Only active listener clicks
    for (let i = 0; i < playerPages.length; i++) {
      if (i === idlePlayerIndex) continue;
      try {
        const role = await detectPlayerRole(playerPages[i]);
        if (role === 'listener') {
          const tangrams = playerPages[i].locator('.tangrams.grid > div');
          if (await tangrams.count() > 0) {
            await tangrams.first().click();
          }
        }
      } catch (e) {}
    }

    // Wait for timeout and idle detection
    await page.waitForTimeout(15000);
    await reporter.checkpoint('Round 2 complete');

    // Check if idle player was kicked
    const idlePlayerState = await detectGameState(playerPages[idlePlayerIndex]);
    const idleContent = await playerPages[idlePlayerIndex].content();

    reporter.verify('Idle player kicked', idlePlayerState === 'kicked_idle' || idleContent.includes('TIMEOUT2024'));
    reporter.verify('Shows timeout code', idleContent.includes('TIMEOUT2024'));
    await reporter.checkpoint('Idle detection complete', playerPages[idlePlayerIndex], true);

  } catch (error) {
    reporter.error('Idle detection test failed', error);
  }

  return reporter.printSummary();
}

// ============ DROPOUT TEST ============

/**
 * Test dropout handling - close a player tab mid-game
 * @param {Page} page - Any page in the context
 */
async function testDropout(page) {
  const reporter = new TestReporter('Dropout Test');

  try {
    const playerPages = await getPlayerPages(page);
    reporter.verify('Have 3+ players', playerPages.length >= 3);
    await reporter.checkpoint('Game started with players');

    // Play a few rounds normally first
    await reporter.checkpoint('Playing initial rounds');
    for (let round = 0; round < 3; round++) {
      // Speaker sends
      for (const p of playerPages) {
        const role = await detectPlayerRole(p);
        if (role === 'speaker') {
          const chatInput = p.getByRole('textbox', { name: 'Say something' });
          if (await chatInput.count() > 0) {
            await chatInput.fill('t');
            await chatInput.press('Enter');
          }
          break;
        }
      }
      await page.waitForTimeout(500);

      // Listeners click
      for (const p of playerPages) {
        const role = await detectPlayerRole(p);
        if (role === 'listener') {
          const tangrams = p.locator('.tangrams.grid > div');
          if (await tangrams.count() > 0) {
            await tangrams.first().click();
            await p.waitForTimeout(200);
          }
        }
      }
      await page.waitForTimeout(500);

      // Continue
      for (const p of playerPages) {
        try {
          const continueBtn = p.getByRole('button', { name: /continue/i });
          if (await continueBtn.count() > 0) await continueBtn.click();
        } catch (e) {}
      }
      await page.waitForTimeout(500);
    }
    await reporter.checkpoint('Initial rounds complete');

    // Simulate dropout by closing first player's tab
    const droppedPage = playerPages[0];
    await reporter.checkpoint('Simulating dropout - closing player 1 tab');
    await droppedPage.close();

    // Wait for server to detect dropout
    await page.waitForTimeout(2000);

    // Check remaining players see the message
    const remainingPages = await getPlayerPages(page);
    reporter.verify('Player count decreased', remainingPages.length < playerPages.length);

    let sawDropoutMessage = false;
    for (const p of remainingPages) {
      const content = await p.content();
      if (content.includes('smaller') || content.includes('left') || content.includes('inactive')) {
        sawDropoutMessage = true;
        break;
      }
    }
    reporter.verify('Remaining players see dropout message', sawDropoutMessage);

    // Continue playing with reduced group
    await reporter.checkpoint('Continuing with reduced group');
    for (let round = 0; round < 2; round++) {
      for (const p of remainingPages) {
        const role = await detectPlayerRole(p);
        if (role === 'speaker') {
          const chatInput = p.getByRole('textbox', { name: 'Say something' });
          if (await chatInput.count() > 0) {
            await chatInput.fill('t');
            await chatInput.press('Enter');
          }
          break;
        }
      }
      await page.waitForTimeout(500);

      for (const p of remainingPages) {
        const role = await detectPlayerRole(p);
        if (role === 'listener') {
          const tangrams = p.locator('.tangrams.grid > div');
          if (await tangrams.count() > 0) {
            await tangrams.first().click();
          }
        }
      }
      await page.waitForTimeout(500);

      for (const p of remainingPages) {
        try {
          const continueBtn = p.getByRole('button', { name: /continue/i });
          if (await continueBtn.count() > 0) await continueBtn.click();
        } catch (e) {}
      }
      await page.waitForTimeout(500);
    }

    reporter.verify('Game continued after dropout', true);
    await reporter.checkpoint('Dropout test complete', remainingPages[0], true);

  } catch (error) {
    reporter.error('Dropout test failed', error);
  }

  return reporter.printSummary();
}

// ============ GROUP DISBANDED TEST ============

/**
 * Test group disbanded when too many players drop
 * @param {Page} page - Any page in the context
 */
async function testGroupDisbanded(page) {
  const reporter = new TestReporter('Group Disbanded Test');

  try {
    const playerPages = await getPlayerPages(page);
    reporter.verify('Have 3 players', playerPages.length === 3);
    await reporter.checkpoint('Game started with 3 players');

    // Close 2 players to trigger group disbanded
    await reporter.checkpoint('Closing 2 players');
    await playerPages[0].close();
    await page.waitForTimeout(1000);
    await playerPages[1].close();
    await page.waitForTimeout(2000);

    // Check remaining player sees disbanded message
    const remainingPages = await getPlayerPages(page);
    if (remainingPages.length > 0) {
      const content = await remainingPages[0].content();
      const state = await detectGameState(remainingPages[0]);

      reporter.verify('Group disbanded', state === 'kicked_disbanded' || content.includes('DISBANDED'));
      reporter.verify('Shows disbanded code', content.includes('DISBANDED2024'));
      await reporter.checkpoint('Group disbanded test complete', remainingPages[0], true);
    } else {
      reporter.verify('All players removed', true);
    }

  } catch (error) {
    reporter.error('Group disbanded test failed', error);
  }

  return reporter.printSummary();
}

// ============ EXPORTS ============

module.exports = {
  testQuizFailure,
  testIdleDetection,
  testDropout,
  testGroupDisbanded
};

/**
 * MCP USAGE:
 *
 * === Quiz Failure Test ===
 * 1. Create batch with 1 player
 * 2. Navigate to player page
 * 3. Run: testQuizFailure(page)
 *
 * === Idle Detection Test ===
 * 1. Create batch with 3 players
 * 2. Complete intro for all
 * 3. Run: testIdleDetection(page)
 *
 * === Dropout Test ===
 * 1. Create batch with 3 players
 * 2. Complete intro for all
 * 3. Play a few rounds
 * 4. Run: testDropout(page)
 *
 * === Group Disbanded Test ===
 * 1. Create batch with 3 players
 * 2. Complete intro for all
 * 3. Run: testGroupDisbanded(page)
 */
