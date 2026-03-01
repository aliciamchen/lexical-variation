/**
 * TEST_PLAN 11.2: Social Mixed Score Display
 *
 * In social_mixed, social guessing feedback is shown per-trial during Phase 2.
 * Set up a social_mixed game, play into Phase 2 with social guessing. Verify
 * that listeners see "identity guess" feedback and speakers see "recognized you"
 * feedback during gameplay. After the game ends (Bonus info stage), verify the
 * social guessing summary IS shown (text like "Social Guessing Summary").
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

  test('social guessing feedback IS shown during Phase 2 gameplay', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play one round with social guessing
    await playRound(active, { doSocialGuess: true });

    // Wait for feedback stage
    await active[0].waitForTimeout(2000);

    // Check that during gameplay, social guessing feedback is displayed.
    // Listeners should see "identity guess" text and speakers should see "recognized you" text.
    let foundListenerFeedback = false;
    let foundSpeakerFeedback = false;

    for (const page of active) {
      const bodyContent = await page.textContent('body');

      if (bodyContent?.includes('identity guess')) {
        foundListenerFeedback = true;
      }
      if (bodyContent?.includes('recognized you') || bodyContent?.includes('No members from your original group')) {
        foundSpeakerFeedback = true;
      }
    }

    expect(
      foundListenerFeedback,
      'Listener social feedback should be shown during Phase 2 gameplay',
    ).toBe(true);
    expect(
      foundSpeakerFeedback,
      'Speaker social feedback should be shown during Phase 2 gameplay',
    ).toBe(true);
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

  test('Bonus info stage shows Social Guessing Summary', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Click Continue to exit last Feedback stage
    for (const page of active) {
      await clickContinue(page, 5000);
    }

    // Wait for Bonus info stage
    await waitForStage(active[0], 'Bonus info', 120_000);

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
      'Social Guessing Summary should be shown on the Bonus info stage',
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

    // Click Continue for each player after they reach Bonus info
    for (const page of active) {
      await waitForStage(page, 'Bonus info', 30_000);
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

    // Complete exit survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
