/**
 * TEST_PLAN 6.3: Transition Stage Timing
 *
 * Goal: Verify that the Transition screen lasts TRANSITION_DURATION seconds
 * and auto-advances even if no player clicks Continue.
 *
 * Strategy:
 * - Set up a full game with 9 players.
 * - Complete all Phase 1 blocks to reach the Phase 1 -> Phase 2 transition.
 * - Do NOT click Continue on the transition screen.
 * - Wait for TRANSITION_DURATION + 5 seconds.
 * - Verify the stage has advanced past the Transition.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playBlock,
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  TRANSITION_DURATION,
} from '../helpers/constants';

test.describe.serial('Timing: Transition Stage Timing (TEST_PLAN 6.3)', () => {
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

  test('complete Phase 1 to reach Transition', async () => {
    test.slow(); // Phase 1 is 18 rounds, takes several minutes
    const pages = pm.getPages();

    // Play all Phase 1 blocks
    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    // Wait for the Phase 2 transition stage to appear
    const transitionReached = await waitForStage(pages[0], 'Phase 2 transition', 60_000);
    expect(transitionReached).toBe(true);

    // Confirm we are on the Transition stage
    const info = await getPlayerInfo(pages[0]);
    expect(info).not.toBeNull();
    expect(info!.stageName).toBe('Phase 2 transition');
  });

  test('Transition auto-advances after TRANSITION_DURATION seconds', async () => {
    test.slow();
    const pages = pm.getPages();

    // Do NOT click Continue -- let the timer expire.
    // Wait for TRANSITION_DURATION + 5 seconds.
    const waitMs = (TRANSITION_DURATION + 5) * 1000;
    await pages[0].waitForTimeout(waitMs);

    // Verify the stage has advanced past Transition.
    // It should now be on Selection (first round of Phase 2).
    const infoAfter = await getPlayerInfo(pages[0]);
    expect(infoAfter).not.toBeNull();
    expect(infoAfter!.stageName).not.toBe('Phase 2 transition');
    // Should be in Phase 2 Selection
    expect(infoAfter!.stageName).toBe('Selection');
    expect(infoAfter!.phase).toBe(2);
  });
});
