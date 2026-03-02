/**
 * TEST: Phase 1 Accuracy Threshold
 *
 * Tests that groups failing the accuracy threshold in Phase 1 are removed
 * at the Phase 1 → Phase 2 transition.
 *
 * Strategy:
 * - Set up refer_separated game with 9 players.
 * - Play Phase 1 with one group deliberately clicking wrong tangrams
 *   (using wrongGroups option in playRound).
 * - At the Phase 1 → Phase 2 transition, the accuracy check runs.
 * - The low-accuracy group should be removed (all 3 members see sorry screen
 *   with "low accuracy" exit reason).
 * - Remaining 6 players continue into Phase 2.
 *
 * The accuracy threshold is ACCURACY_THRESHOLD (2/3) — a player must get
 * at least 2/3 correct across the last ACCURACY_CHECK_BLOCKS (3) blocks.
 * PLAYER_ACCURACY_THRESHOLD (2/3) of the group's players must meet this.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  playBlock,
  handleTransition,
  getActivePlayers,
  getRemovedPlayers,
  getPlayersByGroup,
  waitForStage,
  waitForExitScreen,
  isInGame,
  clickContinue,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  MIN_GROUP_SIZE,
} from '../helpers/constants';

test.describe.serial('Edge Case: Phase 1 Accuracy Threshold', () => {
  let pm: PlayerManager;
  let targetGroupName: string;

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

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('identify the target group that will click wrong', async () => {
    const pages = pm.getPages();
    const groups = await getPlayersByGroup(pages);
    const groupNames = Object.keys(groups);
    expect(groupNames.length).toBe(3);

    // Pick the first group to be the "bad accuracy" group
    targetGroupName = groupNames[0];
  });

  test('complete Phase 1 with one group clicking wrong tangrams', async () => {
    test.slow(); // Phase 1 is 18 rounds
    const pages = pm.getPages();

    // Play all Phase 1 blocks. The target group's listeners always click
    // the wrong tangram, giving them 0% accuracy.
    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
        await playRound(pages, { wrongGroups: [targetGroupName] });
      }
    }

    // All 9 players should still be active during Phase 1
    const active = await getActivePlayers(pages);
    expect(active.length).toBe(9);
  });

  test('accuracy check removes the low-accuracy group at transition', async () => {
    test.slow();
    const pages = pm.getPages();

    // Handle the Phase 1 → Phase 2 transition.
    // The accuracy check runs at this point on the server.
    await handleTransition(pages);

    // Wait for the transition to propagate. The low-accuracy group's players
    // should see sorry screens. Give ample time for Empirica to process.
    await pages[0].waitForTimeout(10_000);

    // Check that the target group members are removed
    const removed = await getRemovedPlayers(pages);
    const targetGroupRemoved = removed.filter(({ page }) => {
      const idx = pages.indexOf(page);
      return idx >= 0;
    });

    // Find which removed players belong to the target group
    let targetRemovedCount = 0;
    for (const { page, info } of removed) {
      // The sorry screen should indicate "low accuracy" as exit reason
      if (info.exitReason === 'low accuracy') {
        targetRemovedCount++;
      }
    }

    // All 3 members of the target group should be removed
    expect(targetRemovedCount).toBe(3);
  });

  test('remaining 6 players continue into Phase 2', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // 9 - 3 removed = 6 remaining
    expect(active.length).toBe(6);

    // Wait for Phase 2 Selection stage
    const phase2Started = await waitForStage(active[0], 'Selection', 120_000);
    expect(phase2Started).toBe(true);

    // Verify remaining players are in Phase 2
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info) {
        expect(info.phase).toBe(2);
      }
    }

    // Verify the remaining groups have at least MIN_GROUP_SIZE players
    const groups = await getPlayersByGroup(active);
    for (const [groupName, members] of Object.entries(groups)) {
      expect(members.length).toBeGreaterThanOrEqual(MIN_GROUP_SIZE);
    }
  });

  test('remaining players can complete rounds in Phase 2', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    await playRound(active);
    await playRound(active);

    // Still 6 active
    const stillActive = await getActivePlayers(pages);
    expect(stillActive.length).toBe(6);
  });
});
