import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectFeedbackVisible,
} from '../helpers/assertions';
import { FEEDBACK_INDICATOR } from '../helpers/selectors';
import { GROUP_NAMES } from '../helpers/constants';

/**
 * TEST_PLAN 5.4: Feedback stage shows correct/incorrect messages.
 *
 * Completes rounds with both correct and incorrect answers, then
 * verifies that:
 * - Speaker sees "You earned X points"
 * - Correct listener sees "Correct! You earned 2 points"
 * - Wrong listener sees "Ooops"
 */
test.describe.serial('UI Verification: Feedback Screens (5.4)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('feedback shows correct message for correct listener', async () => {
    const pages = pm.getPages();

    // Play one round with all groups answering correctly
    await playRound(pages);

    // Wait for feedback stage
    await pages[0].waitForTimeout(2000);

    // Check that we are in Feedback stage
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.stageName === 'Feedback' && info.role === 'listener') {
        const bodyText = await page.textContent('body');
        // Correct listener should see "Correct! You earned 2 points"
        expect(bodyText).toContain('Correct!');
        expect(bodyText).toContain('2 points');
        break;
      }
    }
  });

  test('feedback shows speaker points message', async () => {
    const pages = pm.getPages();

    // Check speaker feedback from the round we just played
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.stageName === 'Feedback' && info.role === 'speaker') {
        const bodyText = await page.textContent('body');
        // Speaker should see "You earned X points this round"
        expect(bodyText).toContain('You earned');
        expect(bodyText).toContain('points');
        break;
      }
    }
  });

  test('feedback indicator element is visible during Feedback stage', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.stageName === 'Feedback') {
        const feedbackEl = page.locator(FEEDBACK_INDICATOR);
        await expect(feedbackEl).toBeVisible({ timeout: 5_000 });
        await expectFeedbackVisible(page);
        break;
      }
    }
  });

  test('feedback shows "Ooops" for incorrect listener', async () => {
    const pages = pm.getPages();

    // Play a round where one group answers incorrectly
    // Pick the first group name to be wrong
    const wrongGroup = GROUP_NAMES[0];
    await playRound(pages, { wrongGroups: [wrongGroup] });

    // Wait for feedback stage
    await pages[0].waitForTimeout(2000);

    // Find a listener from the wrong group and check for "Ooops"
    let foundWrongFeedback = false;
    let foundCorrectFeedback = false;

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.stageName === 'Feedback' && info.role === 'listener') {
        const bodyText = await page.textContent('body');

        if (info.originalGroup === wrongGroup) {
          // Wrong group listener should see "Ooops"
          if (bodyText?.includes('Ooops')) {
            foundWrongFeedback = true;
            expect(bodyText).toContain('Ooops');
            expect(bodyText).toContain('no points');
          }
        } else {
          // Correct group listener should see "Correct!"
          if (bodyText?.includes('Correct!')) {
            foundCorrectFeedback = true;
          }
        }
      }
    }

    // We should have found at least one wrong feedback
    expect(foundWrongFeedback).toBe(true);
    // And at least one correct feedback from other groups
    expect(foundCorrectFeedback).toBe(true);
  });

  test('Continue button is present during Feedback stage', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.stageName === 'Feedback') {
        const continueBtn = page.getByRole('button', { name: /continue/i });
        await expect(continueBtn).toBeVisible({ timeout: 5_000 });
        break;
      }
    }
  });
});
