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
  clickContinue,
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
    test.slow();
    const pages = pm.getPages();

    // Previous test played round 0 and verified Feedback. We may still be in
    // Feedback or it may have auto-advanced to next Selection. Navigate to
    // a known state (Selection) to read target_num reliably.
    for (const page of pages) {
      await clickContinue(page, 2000);
    }
    await waitForStage(pages[0], 'Selection', 30_000);

    // Record the current block and read target_nums at each Selection stage
    const startInfo = await getPlayerInfo(pages[0]);
    expect(startInfo).not.toBeNull();
    const currentBlock = startInfo!.block;
    const targetNums: number[] = [];

    // Read target_num at Selection, then play round, until block changes
    for (let r = 0; r < ROUNDS_PER_BLOCK; r++) {
      await waitForStage(pages[0], 'Selection', 30_000);
      const info = await getPlayerInfo(pages[0]);
      if (!info || info.block !== currentBlock) break;
      targetNums.push(info.round);
      await playRound(pages, { message: `target cycle round ${r}` });
    }

    // Verify we saw unique target_nums in range 0-5.
    // We may have captured 5 or 6 depending on whether we started mid-block.
    expect(targetNums.length).toBeGreaterThanOrEqual(5);
    const uniqueNums = new Set(targetNums);
    expect(uniqueNums.size).toBe(targetNums.length); // no duplicates
    for (const t of targetNums) {
      expect(t).toBeGreaterThanOrEqual(0);
      expect(t).toBeLessThan(NUM_TANGRAMS);
    }
  });

  test('block_num increments at block boundaries', async () => {
    const pages = pm.getPages();

    // After the target_num test, we should be past the initial block
    const selectionReached = await waitForStage(pages[0], 'Selection', 30_000);
    expect(selectionReached).toBe(true);

    const info = await getPlayerInfo(pages[0]);
    expect(info).not.toBeNull();
    // Block should have incremented from 0
    expect(info!.block).toBeGreaterThan(0);
    expect(info!.phase).toBe(1);
  });

  test('phase increments from 1 to 2 after Phase 1 blocks', async () => {
    test.slow();
    const pages = pm.getPages();

    // Determine how many blocks remain in Phase 1
    const info = await getPlayerInfo(pages[0]);
    const currentBlock = info!.block;
    const remainingBlocks = PHASE_1_BLOCKS - currentBlock;

    // Complete remaining Phase 1 blocks
    for (let b = 0; b < remainingBlocks; b++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    // Wait for and handle transition to Phase 2
    await pages[0].waitForTimeout(3000);
    await handleTransition(pages);

    // Wait for Phase 2 Selection (transition takes ~60s)
    const phase2Selection = await waitForStage(pages[0], 'Selection', 120_000);
    expect(phase2Selection).toBe(true);

    // Verify Phase 2
    const phase2Info = await getPlayerInfo(pages[0]);
    expect(phase2Info).not.toBeNull();
    expect(phase2Info!.phase).toBe(2);

    // Verify block is a valid number
    expect(phase2Info!.block).toBeGreaterThanOrEqual(0);
  });
});
