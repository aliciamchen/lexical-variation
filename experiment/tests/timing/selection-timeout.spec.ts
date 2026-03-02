/**
 * TEST_PLAN 6.1: Selection Stage Timeout
 *
 * Goal: Verify that the Selection stage automatically times out after
 * SELECTION_DURATION seconds when no player acts. After the timeout,
 * the stage should advance to Feedback.
 *
 * Strategy:
 * - Set up a full game with 9 players.
 * - Once the game starts on the Selection stage, do NOT have any player
 *   send a message or click a tangram.
 * - Wait for SELECTION_DURATION + 5 seconds.
 * - Verify the stage has advanced to Feedback.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectStage,
} from '../helpers/assertions';
import {
  SELECTION_DURATION,
} from '../helpers/constants';

test.describe.serial('Timing: Selection Stage Timeout (TEST_PLAN 6.1)', () => {
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

    const pages = pm.getPages();
    for (const page of pages) {
      await expectPlayerInGame(page);
    }
  });

  test('Selection stage times out and advances to Feedback', async () => {
    test.slow();
    const pages = pm.getPages();

    // Confirm we are on the Selection stage
    const info = await getPlayerInfo(pages[0]);
    expect(info).not.toBeNull();
    expect(info!.stageName).toBe('Selection');

    // Do NOT perform any actions -- let the timer expire.
    // Wait for SELECTION_DURATION + 5 seconds (extra buffer for processing).
    const waitMs = (SELECTION_DURATION + 5) * 1000;
    await pages[0].waitForTimeout(waitMs);

    // Verify the stage has advanced to Feedback for at least one player
    const infoAfter = await getPlayerInfo(pages[0]);
    expect(infoAfter).not.toBeNull();
    expect(infoAfter!.stageName).toBe('Feedback');

    // Verify Feedback stage for all players
    for (const page of pages) {
      await expectStage(page, 'Feedback');
    }
  });
});
