import { test, expect, Page } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import { getPlayerInfo, playRound, waitForFeedback } from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectFeedbackVisible,
} from '../helpers/assertions';
import { FEEDBACK_INDICATOR } from '../helpers/selectors';
import { GROUP_NAMES, LISTENER_CORRECT_POINTS } from '../helpers/constants';

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

  // Feedback lasts FEEDBACK_DURATION seconds, so each check below reads one
  // page per role and fails if that role is not found in Feedback.
  async function pagesInFeedbackByRole(pages: Page[]) {
    const found: Record<string, Page> = {};
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (!info) continue;
      expect(info.stageName, 'every player should be in the Feedback stage').toBe('Feedback');
      if (info.role && !found[info.role]) found[info.role] = page;
      if (found.listener && found.speaker) break;
    }
    expect(found.listener, 'expected at least one listener in Feedback').toBeTruthy();
    expect(found.speaker, 'expected at least one speaker in Feedback').toBeTruthy();
    return found as { listener: Page; speaker: Page };
  }

  test('feedback shows correct message for correct listener and points message for speaker', async () => {
    const pages = pm.getPages();

    // Play one round with all groups answering correctly
    await playRound(pages);
    expect(await waitForFeedback(pages[0], 30_000), 'expected the Feedback stage').toBe(true);

    const { listener, speaker } = await pagesInFeedbackByRole(pages);
    // Correct listener sees "Correct! You earned 2 points"
    await expect(listener.locator('body')).toContainText('Correct!');
    await expect(listener.locator('body')).toContainText(`${LISTENER_CORRECT_POINTS} points`);
    // Speaker sees "You earned X points this round"
    await expect(speaker.locator('body')).toContainText('You earned');
    await expect(speaker.locator('body')).toContainText('points');
  });

  test('feedback indicator element is visible during Feedback stage', async () => {
    const pages = pm.getPages();
    const { listener } = await pagesInFeedbackByRole(pages);
    await expect(listener.locator(FEEDBACK_INDICATOR)).toBeVisible({ timeout: 5_000 });
    await expectFeedbackVisible(listener);
  });

  test('feedback shows "Ooops" for incorrect listener', async () => {
    const pages = pm.getPages();

    // Play a round where one group answers incorrectly
    // Pick the first group name to be wrong
    const wrongGroup = GROUP_NAMES[0];
    await playRound(pages, { wrongGroups: [wrongGroup] });
    expect(await waitForFeedback(pages[0], 30_000), 'expected the Feedback stage').toBe(true);

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
    const { listener } = await pagesInFeedbackByRole(pages);
    await expect(listener.getByRole('button', { name: /continue/i })).toBeVisible({ timeout: 5_000 });
  });
});
