/**
 * TEST_PLAN 3.8: Multiple Simultaneous Dropouts from Different Groups
 *
 * Goal: When multiple players from different groups go idle simultaneously,
 * verify correct handling: each group's viability is checked independently,
 * and the game continues if viable groups remain.
 *
 * Condition: refer_separated (simpler, no reshuffling)
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  getExitInfo,
  playRound,
  getActivePlayers,
  getRemovedPlayers,
  getPlayersByGroup,
  waitForExitScreen,
  isOnExitScreen,
  isInGame,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectOneSpeakerPerGroup,
} from '../helpers/assertions';
import {
  MAX_IDLE_ROUNDS,
  PROLIFIC_CODES,
  MIN_GROUP_SIZE,
} from '../helpers/constants';

test.describe.serial('Group Viability: Simultaneous Dropouts from Different Groups (3.8)', () => {
  let pm: PlayerManager;
  // Track which page indices belong to each original group
  let groupPageIndices: Record<string, number[]>;

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

  test('all 9 players join and start the game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('map players to groups', async () => {
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

    const groupNames = Object.keys(groupPageIndices);
    expect(groupNames.length).toBe(3);
    for (const indices of Object.values(groupPageIndices)) {
      expect(indices.length).toBe(3);
    }
  });

  test('play a few normal rounds', async () => {
    const pages = pm.getPages();
    await playRound(pages);
    await playRound(pages);
  });

  test('one player from each of two different groups goes idle simultaneously', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);

    // Pick one player from group A and one from group B to idle simultaneously
    const idleFromGroupA = groupPageIndices[groupNames[0]][0];
    const idleFromGroupB = groupPageIndices[groupNames[1]][0];
    const idleIndices = [idleFromGroupA, idleFromGroupB];

    // Both players idle at the same time for MAX_IDLE_ROUNDS
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: idleIndices });
    }

    await pages[0].waitForTimeout(3000);
  });

  test('both idle players are kicked with "player timeout"', async () => {
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);

    const idleFromGroupA = groupPageIndices[groupNames[0]][0];
    const idleFromGroupB = groupPageIndices[groupNames[1]][0];

    // Wait for exit screens to render (may not appear immediately after idle kicks)
    const exitInfoA = await waitForExitScreen(pages[idleFromGroupA], 30_000);
    expect(exitInfoA).not.toBeNull();
    expect(exitInfoA!.exitReason).toBe('player timeout');
    expect(exitInfoA!.partialPay).toBe('0.00');

    const exitInfoB = await waitForExitScreen(pages[idleFromGroupB], 30_000);
    expect(exitInfoB).not.toBeNull();
    expect(exitInfoB!.exitReason).toBe('player timeout');
    expect(exitInfoB!.partialPay).toBe('0.00');
  });

  test('each group viability is checked independently', async () => {
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);

    // Group A lost 1 player: 2 remaining >= MIN_GROUP_SIZE (2), still viable
    const groupAActive = [];
    for (const idx of groupPageIndices[groupNames[0]]) {
      if (await isInGame(pages[idx])) groupAActive.push(idx);
    }
    expect(groupAActive.length).toBe(2);

    // Group B lost 1 player: 2 remaining >= MIN_GROUP_SIZE (2), still viable
    const groupBActive = [];
    for (const idx of groupPageIndices[groupNames[1]]) {
      if (await isInGame(pages[idx])) groupBActive.push(idx);
    }
    expect(groupBActive.length).toBe(2);

    // Group C: 3 remaining (untouched), still viable
    const groupCActive = [];
    for (const idx of groupPageIndices[groupNames[2]]) {
      if (await isInGame(pages[idx])) groupCActive.push(idx);
    }
    expect(groupCActive.length).toBe(3);
  });

  test('game continues with 7 active players across 3 viable groups', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // 9 - 2 kicked = 7 remaining
    expect(active.length).toBe(7);

    // All three groups should still be viable
    const groups = await getPlayersByGroup(pages);
    const viableGroupNames = Object.keys(groups);
    expect(viableGroupNames.length).toBe(3);

    // Each group should have at least MIN_GROUP_SIZE active members
    for (const [groupName, members] of Object.entries(groups)) {
      expect(
        members.length,
        `Group ${groupName} should have >= ${MIN_GROUP_SIZE} members`,
      ).toBeGreaterThanOrEqual(MIN_GROUP_SIZE);
    }
  });

  test('each group has exactly one speaker after dropout', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    await expectOneSpeakerPerGroup(active);
  });

  test('game continues to function with rounds completing normally', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play multiple rounds to confirm stability
    await playRound(active);
    await playRound(active);
    await playRound(active);

    // Verify player count is still 7
    const stillActive = await getActivePlayers(pages);
    expect(stillActive.length).toBe(7);

    // Verify roles are correctly assigned
    await expectOneSpeakerPerGroup(stillActive);
  });
});
