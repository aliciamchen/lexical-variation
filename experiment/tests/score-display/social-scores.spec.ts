/**
 * TEST_PLAN 11.2: Social Mixed Score Display
 *
 * In social_mixed, social guessing scores are NOT shown during the game,
 * only at the end. Set up a social_mixed game, play into Phase 2 with social
 * guessing. Verify that "social" score or "guess" score is not displayed
 * during gameplay. After the game ends (bonus_info stage), verify the social
 * guessing summary IS shown (text like "Social Guessing Summary").
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
import { expectPlayerInGame, expectCondition } from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
} from '../helpers/constants';

test.describe.serial('Score Display: Social Mixed Scores (TEST_PLAN 11.2)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'social_mixed');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('all 9 players complete intro and enter game', async () => {
    test.slow(); // May need extra time if server is degraded from accumulated state
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    const pages = pm.getPages();
    for (const page of pages) {
      await expectPlayerInGame(page);
    }

    await expectCondition(pages[0], 'social_mixed');
  });

  test('complete Phase 1', async () => {
    test.slow();
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }
  });

  test('handle phase transition', async () => {
    const pages = pm.getPages();
    await pages[0].waitForTimeout(2000);
    await handleTransition(pages);
  });

  test('social guessing scores are NOT shown during Phase 2 gameplay', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play one round with social guessing
    await playRound(active, { doSocialGuess: true });

    // Wait for feedback stage
    await active[0].waitForTimeout(2000);

    // Check that during gameplay, social guessing scores are not displayed
    // in the Profile section. The Profile component shows "Score" with a number,
    // but this should only be the referential score, not social guess scores.
    // There should be no "social" or "guess" score label visible during gameplay.
    for (const page of active) {
      const bodyContent = await page.textContent('body');

      // The feedback text says "Total in-group guessing score will be shown at
      // the end of the experiment" - this confirms scores are hidden during gameplay.
      // Verify there is no separate "social score" or "guess score" counter visible.
      // The Profile section only shows a single "Score" label.
      const profileSection = page.locator('[data-player-name]').locator('..');
      const profileText = await profileSection.textContent();

      // The profile should have exactly one "Score" label - no "Social Score" etc.
      const socialScoreVisible =
        profileText?.toLowerCase().includes('social score') ||
        profileText?.toLowerCase().includes('guess score') ||
        profileText?.toLowerCase().includes('social points');
      expect(
        socialScoreVisible,
        'Social guessing score should NOT be displayed during gameplay',
      ).toBeFalsy();
    }
  });

  test('complete remaining Phase 2 rounds with social guessing', async () => {
    test.slow();
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Complete the rest of the first block (we already played 1 round)
    for (let r = 1; r < ROUNDS_PER_BLOCK; r++) {
      await playRound(active, { doSocialGuess: true });
    }

    // Play remaining blocks
    for (let block = 1; block < PHASE_2_BLOCKS; block++) {
      await playBlock(active, ROUNDS_PER_BLOCK, { doSocialGuess: true });
    }
  });

  test('bonus_info stage shows Social Guessing Summary', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Click Continue to exit last Feedback stage
    for (const page of active) {
      await clickContinue(page, 5000);
    }

    // Wait for bonus_info stage
    await waitForStage(active[0], 'bonus_info', 120_000);

    // Verify the bonus info stage displays the social guessing summary.
    // The Transition component renders "Social Guessing Summary:" text
    // when condition is social_mixed and there are social guess totals.
    let foundSocialSummary = false;

    for (const page of pages) {
      const bodyContent = await page.textContent('body');

      if (
        bodyContent?.includes('Social Guessing Summary') ||
        bodyContent?.includes('correctly guessed') ||
        bodyContent?.includes('correct guesses')
      ) {
        foundSocialSummary = true;
        break;
      }
    }

    expect(
      foundSocialSummary,
      'Social Guessing Summary should be shown on the bonus_info stage',
    ).toBe(true);

    // Also verify that specific summary elements are present:
    // - "correctly guessed the speaker's group"
    // - Numbers like "X out of Y times"
    const firstPage = pages[0];
    const bonusContent = await firstPage.textContent('body');
    expect(
      bonusContent?.includes('out of') || bonusContent?.includes('Social Guessing Summary'),
      'Bonus info should contain social guessing statistics',
    ).toBe(true);

    // Click Continue for each player after they reach bonus_info
    for (const page of active) {
      await waitForStage(page, 'bonus_info', 30_000);
      await clickContinue(page, 5000);
    }
    await active[0].waitForTimeout(3000);
  });

  test('exit survey and completion', async () => {
    const pages = pm.getPages();

    // Wait for exit survey to load
    for (const page of pages) {
      try {
        await page.getByText('Exit Survey').waitFor({ state: 'visible', timeout: 30_000 });
      } catch {
        // May already be past this point
      }
    }

    // Verify all players see completion code BEFORE submitting survey
    for (const page of pages) {
      const content = await page.textContent('body');
      expect(content).toContain('C3OIIB3N');
    }

    // Complete exit survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
