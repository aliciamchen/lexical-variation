/**
 * TEST_PLAN 10.1: Full Completion Compensation
 *
 * Players who complete the full game get the completion code C3OIIB3N.
 * Set up and complete a full refer_separated game. Verify all 9 players
 * see the completion code on the exit/finished screen.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  playBlock,
  handleTransition,
  clickContinue,
  completeExitSurvey,
  getActivePlayers,
  waitForStage,
} from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PROLIFIC_CODES,
} from '../helpers/constants';

test.describe.serial('Compensation: Full Completion (TEST_PLAN 10.1)', () => {
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

    const pages = pm.getPages();
    for (const page of pages) {
      await expectPlayerInGame(page);
    }
  });

  test('complete Phase 1', async () => {
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);

      const active = await getActivePlayers(pages);
      expect(active.length).toBe(9);
    }
  });

  test('handle phase transition', async () => {
    const pages = pm.getPages();
    await pages[0].waitForTimeout(2000);
    await handleTransition(pages);
  });

  test('complete Phase 2', async () => {
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      const active = await getActivePlayers(pages);
      expect(active.length).toBe(9);
      await playBlock(active, ROUNDS_PER_BLOCK);
    }
  });

  test('handle bonus info screen', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

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
  });

  test('complete exit survey and verify completion code C3OIIB3N', async () => {
    const pages = pm.getPages();

    // Wait for exit survey to load
    for (const page of pages) {
      try {
        await page.getByText('Exit Survey').waitFor({ state: 'visible', timeout: 30_000 });
      } catch {
        // May already be past this point
      }
    }

    // Verify all 9 players see the completion code BEFORE submitting survey
    for (let i = 0; i < pages.length; i++) {
      const page = pages[i];
      const content = await page.textContent('body');
      expect(
        content,
        `Player ${i + 1} should see completion code ${PROLIFIC_CODES.completion}`,
      ).toContain('C3OIIB3N');
    }

    // Complete exit survey for all players
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
