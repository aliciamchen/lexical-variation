/**
 * TEST_PLAN 3.6: Dropout During Phase 2 Mixed Conditions
 *
 * Goal: When a player is kicked during Phase 2 in refer_mixed,
 * remaining players should be redistributed (mid-block reshuffle if needed)
 * and the game should continue.
 *
 * Condition: refer_mixed (reshuffled groups in Phase 2, identity masking)
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
  MAX_IDLE_ROUNDS,
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  MIN_GROUP_SIZE,
} from '../helpers/constants';

test.describe.serial('Group Viability: Phase 2 Dropout in Mixed Condition (3.6)', () => {
  let pm: PlayerManager;
  // Track which page indices belong to each original group
  let groupPageIndices: Record<string, number[]>;

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

  test('map players to original groups', async () => {
    const pages = pm.getPages();
    groupPageIndices = {};

    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup) {
        if (!groupPageIndices[info.originalGroup]) {
          groupPageIndices[info.originalGroup] = [];
        }
        groupPageIndices[info.originalGroup].push(i);
      }
    }

    expect(Object.keys(groupPageIndices).length).toBe(3);
  });

  test('complete Phase 1 with all 9 players', async () => {
    test.slow(); // Phase 1 is 18 rounds, takes several minutes
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    // All 9 should still be active
    const active = await getActivePlayers(pages);
    expect(active.length).toBe(9);
  });

  test('transition to Phase 2 and idle a listener until kicked', async () => {
    test.slow(); // Phase 2 transition + idle rounds (~10 min)
    const pages = pm.getPages();

    // Handle transition to Phase 2 (minimize gap before idling to avoid
    // consuming rounds — Selection timer expiring between tests wastes rounds)
    await handleTransition(pages);

    // Wait for Phase 2 Selection stage
    const phase2Started = await waitForStage(pages[0], 'Selection', 120_000);
    expect(phase2Started).toBe(true);

    const info0 = await getPlayerInfo(pages[0]);
    expect(info0?.phase).toBe(2);

    // Pick a LISTENER to idle (must be listener so idle detection triggers
    // when their group's speaker is active)
    let idleIndex = -1;
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'listener' && info.phase === 2) {
        idleIndex = i;
        break;
      }
    }
    expect(idleIndex).toBeGreaterThanOrEqual(0);

    // Play MAX_IDLE_ROUNDS rounds with this player idle.
    // Don't break early — timing glitches in getActivePlayers can cause
    // false positives. The full loop ensures all idle rounds are counted.
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [idleIndex] });
    }

    // Wait for the idle player to see the sorry screen
    const exitInfo = await waitForExitScreen(pages[idleIndex], 60_000);
    expect(exitInfo).not.toBeNull();
    expect(exitInfo!.exitReason).toBe('player timeout');
  });

  test('remaining 8 players are redistributed and continue playing', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Should have 8 active players remaining
    expect(active.length).toBe(8);

    // All active players should still be in the game
    for (const page of active) {
      expect(await isInGame(page)).toBe(true);
    }

    // Check that current groups are assigned (redistribution happened)
    const currentGroups: Record<string, number> = {};
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup) {
        currentGroups[info.currentGroup] = (currentGroups[info.currentGroup] || 0) + 1;
      }
    }

    // With 8 players, groups should be distributed (e.g., 3+3+2 or 4+4)
    // Each group must have at least MIN_GROUP_SIZE players
    const groupSizes = Object.values(currentGroups);
    for (const size of groupSizes) {
      expect(size).toBeGreaterThanOrEqual(MIN_GROUP_SIZE);
    }
  });

  test('game continues and remaining players can complete rounds', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play additional rounds to verify the game functions properly
    await playRound(active);
    await playRound(active);

    // Verify players are still active and in game
    const stillActive = await getActivePlayers(pages);
    expect(stillActive.length).toBe(8);
  });
});
