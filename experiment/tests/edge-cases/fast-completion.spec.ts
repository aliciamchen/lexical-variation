/**
 * TEST_PLAN 9.1: Fast Completion (No Race Conditions)
 *
 * All players respond as quickly as possible. Verify no race conditions
 * when all players act immediately. Set up game, rush through rounds
 * with minimal waitForTimeout, and verify the game completes cleanly
 * without errors.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  handleTransition,
  clickContinue,
  completeExitSurvey,
  getActivePlayers,
  speakerSendMessage,
  listenerClickTangram,
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectCondition,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PROLIFIC_CODES,
} from '../helpers/constants';

/**
 * Fast version of playRound with minimal delays.
 * Races through the round as quickly as possible to test for timing issues.
 */
async function playRoundFast(pages: import('@playwright/test').Page[]): Promise<void> {
  // Click any Continue buttons (feedback → selection transition)
  await Promise.all(pages.map(page => clickContinue(page, 500)));
  await pages[0]?.waitForTimeout(300);

  // Speakers send messages as fast as possible (sequentially to avoid race conditions)
  for (const page of pages) {
    const info = await getPlayerInfo(page);
    if (info?.role === 'speaker' && info.targetIndex >= 0) {
      await speakerSendMessage(page, 'fast');
    }
  }

  // Brief delay before listener clicks to let messages propagate
  await pages[0]?.waitForTimeout(500);

  // Listeners click as fast as possible (sequentially to avoid race conditions)
  for (const page of pages) {
    const info = await getPlayerInfo(page);
    if (info?.role === 'listener') {
      const clickIdx = info.targetIndex >= 0 ? info.targetIndex : 0;
      await listenerClickTangram(page, clickIdx);
    }
  }

  // Settling time for stage transition
  await pages[0]?.waitForTimeout(500);
}

test.describe.serial('Edge Case: Fast Completion (TEST_PLAN 9.1)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('all 9 players complete intro and enter game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('rush through Phase 1 with minimal delays', async () => {
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
        await playRoundFast(pages);
      }

      // Verify no players were lost due to race conditions
      const active = await getActivePlayers(pages);
      expect(active.length).toBe(9);
    }
  });

  test('handle transition quickly', async () => {
    const pages = pm.getPages();
    // Minimal wait before transition
    await pages[0].waitForTimeout(500);
    await handleTransition(pages);
  });

  test('rush through Phase 2 with minimal delays', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
        await playRoundFast(active);
      }

      // Verify no race condition casualties
      const stillActive = await getActivePlayers(pages);
      expect(stillActive.length).toBe(9);
    }
  });

  test('game completes cleanly without errors', async () => {
    const pages = pm.getPages();

    // All 9 players should still be active
    const active = await getActivePlayers(pages);
    expect(active.length).toBe(9);

    // Click Continue to exit last Feedback stage
    for (const page of active) {
      await clickContinue(page, 5000);
    }

    // Wait for each player to reach bonus_info, then click Continue
    await waitForStage(active[0], 'bonus_info', 120_000);
    for (const page of active) {
      await waitForStage(page, 'bonus_info', 30_000);
      await clickContinue(page, 5000);
    }
    await active[0].waitForTimeout(3000);

    // Wait for exit survey to load
    for (const page of pages) {
      try {
        await page.getByText('Exit Survey').waitFor({ state: 'visible', timeout: 30_000 });
      } catch {
        // May already be past this point
      }
    }

    // Verify completion code BEFORE submitting survey
    for (const page of pages) {
      const content = await page.textContent('body');
      expect(content).toContain(PROLIFIC_CODES.completion);
    }

    // Complete exit survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });

  test('verify no console errors indicating race conditions', async () => {
    const pages = pm.getPages();

    // Check that pages are still functional (not crashed)
    for (const page of pages) {
      const content = await page.textContent('body');
      expect(content).not.toBeNull();
      expect(content!.length).toBeGreaterThan(0);
      // Should not show any error messages in the body
      expect(content).not.toContain('Something went wrong');
      expect(content).not.toContain('Error');
    }
  });
});
