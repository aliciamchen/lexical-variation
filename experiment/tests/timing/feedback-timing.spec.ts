/**
 * TEST_PLAN 6.2: Feedback Stage Timing
 *
 * Goal: Verify that the Feedback stage lasts FEEDBACK_DURATION seconds and
 * auto-advances even if no player clicks Continue.
 *
 * Strategy:
 * - Set up a full game with 9 players.
 * - Complete one round so we enter the Feedback stage.
 * - Note when Feedback starts. Do NOT click Continue.
 * - Wait for FEEDBACK_DURATION + 5 seconds.
 * - Verify the stage has advanced (next Selection or Transition).
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  waitForFeedback,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  FEEDBACK_DURATION,
} from '../helpers/constants';

test.describe.serial('Timing: Feedback Stage Timing (TEST_PLAN 6.2)', () => {
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

  test('Feedback stage auto-advances after FEEDBACK_DURATION seconds', async () => {
    test.slow();
    const pages = pm.getPages();

    // Complete one round to reach the Feedback stage
    await playRound(pages, { message: 'testing feedback timing' });

    // Wait for Feedback to appear
    const feedbackReached = await waitForFeedback(pages[0], 30_000);
    expect(feedbackReached).toBe(true);

    // Confirm we are on the Feedback stage
    const feedbackInfo = await getPlayerInfo(pages[0]);
    expect(feedbackInfo).not.toBeNull();
    expect(feedbackInfo!.stageName).toBe('Feedback');

    // Do NOT click Continue -- let the timer expire.
    // Wait for FEEDBACK_DURATION + 5 seconds.
    const waitMs = (FEEDBACK_DURATION + 5) * 1000;
    await pages[0].waitForTimeout(waitMs);

    // Verify the stage has advanced past Feedback.
    // It should now be on Selection (next round) or Transition (if block ended).
    const infoAfter = await getPlayerInfo(pages[0]);
    expect(infoAfter).not.toBeNull();
    expect(infoAfter!.stageName).not.toBe('Feedback');
    // Stage should be Selection or Transition
    expect(['Selection', 'Transition']).toContain(infoAfter!.stageName);
  });
});
