/**
 * TEST_PLAN 7.2: Round Data Attributes Update Correctly
 *
 * Goal: Verify that round-level data attributes update correctly as the game
 * progresses. Phase should increment from 1 to 2, block_num should change
 * at block boundaries, target_num should cycle 0-5 within a block, and
 * stage should transition between Selection and Feedback.
 *
 * Strategy:
 * - Set up a full game with 9 players.
 * - Play several rounds while checking data attributes at each step.
 * - Complete Phase 1 and verify transition to Phase 2.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  playBlock,
  handleTransition,
  waitForStage,
  waitForFeedback,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectStage,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  NUM_TANGRAMS,
} from '../helpers/constants';

test.describe.serial('Data Integrity: Round Data (TEST_PLAN 7.2)', () => {
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

  test('game starts in Phase 1, block 0, Selection stage', async () => {
    const pages = pm.getPages();
    const info = await getPlayerInfo(pages[0]);
    expect(info).not.toBeNull();
    expect(info!.phase).toBe(1);
    expect(info!.block).toBe(0);
    expect(info!.stageName).toBe('Selection');
    // target_num (round in data attributes) should be 0-5
    expect(info!.round).toBeGreaterThanOrEqual(0);
    expect(info!.round).toBeLessThan(NUM_TANGRAMS);
  });

  test('stage transitions between Selection and Feedback within a round', async () => {
    const pages = pm.getPages();

    // We are on Selection -- verify
    await expectStage(pages[0], 'Selection');

    // Play the round (speaker sends, listeners click)
    await playRound(pages, { message: 'round data test' });

    // Wait for Feedback stage
    const feedbackReached = await waitForFeedback(pages[0], 30_000);
    expect(feedbackReached).toBe(true);

    // Verify Feedback stage
    await expectStage(pages[0], 'Feedback');
  });

  test('target_num cycles through 0-5 within a block', async () => {
    const pages = pm.getPages();

    // We already played round 0. Continue playing the rest of block 0.
    // Track target_nums seen across the block.
    const targetNums: number[] = [];

    // Get the target_num from the round we just played (now in Feedback)
    const firstInfo = await getPlayerInfo(pages[0]);
    expect(firstInfo).not.toBeNull();
    targetNums.push(firstInfo!.round);

    // Play remaining rounds in block 0 (rounds 1-5)
    for (let r = 1; r < ROUNDS_PER_BLOCK; r++) {
      await playRound(pages, { message: `block 0 round ${r}` });

      // Get current target_num
      const info = await getPlayerInfo(pages[0]);
      expect(info).not.toBeNull();
      targetNums.push(info!.round);
    }

    // Verify we saw all target_nums 0-5 (one each, possibly in random order)
    expect(targetNums.length).toBe(ROUNDS_PER_BLOCK);
    const sortedTargets = [...targetNums].sort((a, b) => a - b);
    for (let i = 0; i < NUM_TANGRAMS; i++) {
      expect(sortedTargets).toContain(i);
    }
  });

  test('block_num increments at block boundaries', async () => {
    const pages = pm.getPages();

    // After completing block 0, we should now be in block 1
    // Wait for the next Selection stage
    const selectionReached = await waitForStage(pages[0], 'Selection', 30_000);
    expect(selectionReached).toBe(true);

    const info = await getPlayerInfo(pages[0]);
    expect(info).not.toBeNull();
    expect(info!.block).toBe(1);
    expect(info!.phase).toBe(1);
  });

  test('phase increments from 1 to 2 after Phase 1 blocks', async () => {
    const pages = pm.getPages();

    // Complete remaining Phase 1 blocks (blocks 1 through PHASE_1_BLOCKS-1)
    for (let block = 1; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    // Wait for Transition stage
    const transitionReached = await waitForStage(pages[0], 'Transition', 60_000);
    expect(transitionReached).toBe(true);

    // Handle transition to Phase 2
    await handleTransition(pages);

    // Wait for Phase 2 Selection
    const phase2Selection = await waitForStage(pages[0], 'Selection', 60_000);
    expect(phase2Selection).toBe(true);

    // Verify Phase 2
    const phase2Info = await getPlayerInfo(pages[0]);
    expect(phase2Info).not.toBeNull();
    expect(phase2Info!.phase).toBe(2);

    // Block numbering continues or resets depending on implementation
    // Verify block is a valid number
    expect(phase2Info!.block).toBeGreaterThanOrEqual(0);
  });
});
