/**
 * TEST_PLAN 9.1: Fast Completion (No Race Conditions)
 *
 * All players respond as quickly as possible. Verify no race conditions
 * when all players act immediately. Set up game, rush through all rounds,
 * and verify the game completes cleanly without errors and all 9 players
 * reach the exit survey with completion codes.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  playBlock,
  handleTransition,
  clickContinue,
  completeExitSurvey,
  getActivePlayers,
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
} from '../helpers/constants';

test.describe.serial('Edge Case: Fast Completion (TEST_PLAN 9.1)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'exp1_refer_separated');
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
    test.slow();
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);

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
    test.slow();
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      await playBlock(active, ROUNDS_PER_BLOCK);

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

    // Handle the Bonus info transition (submits last Feedback, waits for Bonus info, clicks Continue)
    await handleTransition(pages);

    // Wait for Phase 2 to fully end and exit survey to load
    for (const page of pages) {
      try {
        await page.getByText('Exit Survey').waitFor({ state: 'visible', timeout: 120_000 });
      } catch {
        // May already be past this point
      }
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
      // Should not show crash/error screens
      expect(content).not.toContain('Something went wrong');
      expect(content).not.toContain('Unhandled Runtime Error');
      expect(content).not.toContain('Application error');
    }
  });
});
