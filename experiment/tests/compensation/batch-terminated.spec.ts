/**
 * Compensation: the researcher stops the batch mid-game.
 *
 * Stopping a batch from the admin panel is the one emergency lever during a
 * live session. Empirica ends every game in the batch and writes
 * "game terminated" to each player's `ended`; the server's onGameEnded then
 * treats those players like a disbanded group (base pay prorated to the time
 * spent, plus the bonus earned so far) and the client routes them through the
 * exit survey to the Sorry page with the partial completion code.
 *
 * This spec plays two rounds of a refer_separated game so everyone has some
 * time on task, stops the batch, and checks that all nine players land there.
 *
 * Condition: refer_separated (no reshuffling to think about).
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch, stopAllBatches } from '../helpers/admin';
import {
  playRound,
  waitForExitScreen,
  completeExitSurvey,
} from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';
import { EXIT_REASONS, PROLIFIC_CODES } from '../helpers/constants';
import { EXIT_SURVEY, SORRY_SCREEN } from '../helpers/selectors';

test.describe.serial('Compensation: batch stopped by the researcher', () => {
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

  test('all 9 players join and start the game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('play two rounds so players accumulate time on task', async () => {
    const pages = pm.getPages();
    // Partial pay is proportional to the time since the game started, so a
    // little play is what makes "pay > 0" a real check below.
    await playRound(pages);
    await playRound(pages);
  });

  test('the researcher stops the batch', async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await stopAllBatches(adminPage);
    await adminContext.close();
  });

  test('every player reaches the exit survey with "game terminated"', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const exitInfo = await waitForExitScreen(page, 60_000);
      expect(exitInfo).not.toBeNull();
      // Terminated players see the survey first, like a disbanded group
      expect(exitInfo!.type).toBe('exit-survey');
      expect(exitInfo!.exitReason).toBe(EXIT_REASONS.gameTerminated);

      // The header explains what happened and promises the prorated pay
      const survey = page.locator(EXIT_SURVEY);
      await expect(survey).toContainText('stop this session early');
      await expect(survey).toContainText('This is not your fault');
    }
  });

  test('completing both survey pages lands on Sorry with the partial code and pay > 0', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      await completeExitSurvey(page);

      const sorry = page.locator(SORRY_SCREEN);
      await expect(sorry).toBeVisible({ timeout: 10_000 });
      await expect(sorry).toHaveAttribute('data-exit-reason', EXIT_REASONS.gameTerminated);
      await expect(sorry).toHaveAttribute('data-prolific-code', PROLIFIC_CODES.partial);

      // Base pay prorated to the two rounds played (plus any bonus earned)
      const partialPay = parseFloat((await sorry.getAttribute('data-partial-pay')) || '0');
      expect(partialPay).toBeGreaterThan(0);
      await expect(sorry).toContainText(PROLIFIC_CODES.partial);
    }
  });
});
