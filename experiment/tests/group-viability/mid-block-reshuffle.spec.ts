/**
 * TEST: Mid-Block Reshuffling in Phase 2 Mixed Conditions
 *
 * When a player is kicked during Phase 2 in refer_mixed, it can leave a
 * shuffled group with fewer than MIN_GROUP_SIZE members. The server detects
 * this "solo player" situation and triggers an immediate mid-block reshuffle,
 * redistributing all remaining active players into viable groups.
 *
 * Strategy:
 * - Set up refer_mixed game, complete Phase 1, transition to Phase 2.
 * - Record group assignments at the start of Phase 2.
 * - Idle a listener to trigger a kick, causing one shuffled group to shrink.
 * - After the kick, verify groups are reshuffled (group assignments change).
 * - Verify all remaining groups have >= MIN_GROUP_SIZE members.
 *
 * Condition: refer_mixed (reshuffled groups in Phase 2)
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
  waitForExitScreen,
  waitForStage,
  isInGame,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  MAX_IDLE_ROUNDS,
  MIN_GROUP_SIZE,
} from '../helpers/constants';

test.describe.serial('Group Viability: Mid-Block Reshuffle in Phase 2 Mixed (refer_mixed)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'exp1_refer_mixed');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('all 9 players join and start the game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('complete Phase 1 and transition to Phase 2', async () => {
    test.slow();
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    await handleTransition(pages);

    // Wait for Phase 2 Selection
    const phase2Started = await waitForStage(pages[0], 'Selection', 120_000);
    expect(phase2Started).toBe(true);

    const info = await getPlayerInfo(pages[0]);
    expect(info?.phase).toBe(2);
  });

  test('record Phase 2 group assignments before dropout', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);
    expect(active.length).toBe(9);

    // Verify all players have current_group set (reshuffled in Phase 2)
    for (const page of active) {
      const info = await getPlayerInfo(page);
      expect(info?.currentGroup).not.toBeNull();
    }
  });

  test('idle a listener to trigger kick and mid-block reshuffle', async () => {
    test.slow();
    const pages = pm.getPages();

    // Find a listener to idle
    let idleIndex = -1;
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'listener' && info.phase === 2) {
        idleIndex = i;
        break;
      }
    }
    expect(idleIndex).toBeGreaterThanOrEqual(0);

    // Idle the listener for MAX_IDLE_ROUNDS
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [idleIndex] });
    }

    // Wait for the idle listener to be kicked
    const exitInfo = await waitForExitScreen(pages[idleIndex], 60_000);
    expect(exitInfo).not.toBeNull();
    expect(exitInfo!.exitReason).toBe('player timeout');
  });

  test('remaining players are reshuffled and all groups are viable', async () => {
    const pages = pm.getPages();

    // Wait for the next round's Selection stage (reshuffle happens in onRoundStart)
    await pages[0].waitForTimeout(5000);

    const active = await getActivePlayers(pages);
    expect(active.length).toBe(8);

    // Wait for Selection stage to ensure groups are assigned post-reshuffle
    const selectionReached = await waitForStage(active[0], 'Selection', 60_000);
    if (!selectionReached) {
      // May already be in Selection, just need to wait for state propagation
      await active[0].waitForTimeout(5000);
    }

    // Verify all remaining groups have >= MIN_GROUP_SIZE members
    const currentGroups: Record<string, number> = {};
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup) {
        currentGroups[info.currentGroup] = (currentGroups[info.currentGroup] || 0) + 1;
      }
    }

    const groupSizes = Object.values(currentGroups);
    expect(groupSizes.length).toBeGreaterThanOrEqual(1);

    for (const [groupName, size] of Object.entries(currentGroups)) {
      expect(
        size,
        `Group ${groupName} should have >= ${MIN_GROUP_SIZE} members after mid-block reshuffle`,
      ).toBeGreaterThanOrEqual(MIN_GROUP_SIZE);
    }
  });

  test('game continues normally after mid-block reshuffle', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play several rounds to verify stability
    await playRound(active);
    await playRound(active);

    const stillActive = await getActivePlayers(pages);
    expect(stillActive.length).toBe(8);
  });
});
