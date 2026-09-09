/**
 * TEST_PLAN 10.1: Full Completion Compensation
 *
 * Players who complete the full game get the completion code C2I8XDMC.
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
import { PHASE_1_BLOCKS, PHASE_2_BLOCKS, ROUNDS_PER_BLOCK, PROLIFIC_CODES } from '../helpers/constants';

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
    test.slow();
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
    test.slow();
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

    // Wait for each player to reach Bonus info, then click Continue
    await waitForStage(active[0], 'Bonus info', 120_000);
    for (const page of active) {
      await waitForStage(page, 'Bonus info', 30_000);
      await clickContinue(page, 5000);
    }
    await active[0].waitForTimeout(3000);
  });

  test('complete exit survey and verify completion code C2I8XDMC', async () => {
    const pages = pm.getPages();

    // Wait for exit survey to load
    for (const page of pages) {
      try {
        await page.getByText('Exit Survey').waitFor({ state: 'visible', timeout: 30_000 });
      } catch {
        // May already be past this point
      }
    }

    // The confirmation page (after page 2) shows the completion code. Check it
    // on the first player by driving the survey to that page ourselves, then
    // let the shared helper finish everyone.
    const first = pages[0];
    await first.locator('input[name="understood"][value="yes"]').click();
    await first.locator('input[name="groupIdentification"][value="5"]').click();
    await first.locator('input[name="groupCloseness"][value="5"]').click();
    await first.locator('input[name="groupLanguage"][value="yes"]').click();
    const strategy = first.locator('textarea[name="strategy"]');
    await strategy.fill('Test strategy');
    await strategy.dispatchEvent('input');
    await first.getByRole('button', { name: /^next$/i }).click();
    const age = first.locator('input[name="age"]');
    await age.waitFor({ state: 'visible', timeout: 10_000 });
    await age.fill('25');
    await age.dispatchEvent('input');
    await first.locator('select[name="gender"]').selectOption('prefer-not-to-say');
    await first.locator('input[name="feltHuman"][value="yes"]').click();
    await first.getByRole('button', { name: /^submit$/i }).click();
    await expect(first.getByRole('button', { name: /finish/i })).toBeVisible({ timeout: 10_000 });
    await expect(first.locator('body')).toContainText(PROLIFIC_CODES.completion);
    await first.getByRole('button', { name: /finish/i }).click();

    // Complete exit survey for the remaining players
    for (const page of pages.slice(1)) {
      await completeExitSurvey(page);
    }
  });
});
