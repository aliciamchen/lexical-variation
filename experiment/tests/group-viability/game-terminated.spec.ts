/**
 * TEST_PLAN 3.5: Too Many Groups Fail (Game Terminates)
 *
 * Goal: When too many groups lose players and fewer than 2 viable groups remain,
 * the game terminates for ALL remaining players with proportional compensation.
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
  expectPlayerOnExitScreen,
} from '../helpers/assertions';
import {
  MAX_IDLE_ROUNDS,
  PROLIFIC_CODES,
  MIN_GROUP_SIZE,
} from '../helpers/constants';

test.describe.serial('Group Viability: Game Terminated (3.5)', () => {
  let pm: PlayerManager;
  // Track which page indices belong to each group for targeted idling
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

  test('play a few rounds normally', async () => {
    const pages = pm.getPages();
    // Play a couple rounds so players build some game time (for partial pay)
    await playRound(pages);
    await playRound(pages);
  });

  test('two players from Group A go idle and get kicked', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);
    const groupA = groupNames[0];
    const idleIndicesA = groupPageIndices[groupA].slice(0, 2); // First 2 from group A

    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: idleIndicesA });
    }

    // Wait for exit screens to render for all group A players
    for (const idx of groupPageIndices[groupA]) {
      await waitForExitScreen(pages[idx], 30_000);
    }

    // Verify 2 players from group A are kicked + 1 disbanded
    const removed = await getRemovedPlayers(pages);
    const groupARemoved = removed.filter((r) => {
      // Check if this removed player's page was one of group A's pages
      const pageIdx = pages.indexOf(r.page);
      return groupPageIndices[groupA].includes(pageIdx);
    });
    // 2 idle + 1 disbanded = 3 players from group A should be removed
    expect(groupARemoved.length).toBe(3);
  });

  test('two players from Group B go idle and get kicked, triggering game termination', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);
    const groupB = groupNames[1];
    const idleIndicesB = groupPageIndices[groupB].slice(0, 2); // First 2 from group B

    // Get currently active pages (should be 6: 3 from group B + 3 from group C)
    let active = await getActivePlayers(pages);
    expect(active.length).toBe(6);

    // Make 2 from group B idle
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      // Use the full pages array with skipIndices since indices refer to positions in that array
      active = await getActivePlayers(pages);
      if (active.length === 0) break;
      await playRound(pages, { skipIndices: idleIndicesB });
    }

    await pages[0].waitForTimeout(5000);
  });

  test('ALL remaining players see exit screen when fewer than 2 groups remain', async () => {
    const pages = pm.getPages();

    // After group A disbanded (leaving groups B and C),
    // then group B lost 2 members and disbanded,
    // only group C would remain which is < min_active_groups (2).
    // Therefore the game should terminate for ALL remaining players.

    // Wait for exit screens to propagate
    for (const page of pages) {
      const exitInfo = await waitForExitScreen(page, 60_000);
      expect(exitInfo).not.toBeNull();
    }

    // All 9 players should now be on exit screens
    const removed = await getRemovedPlayers(pages);
    expect(removed.length).toBe(9);
  });

  test('remaining players (from group C) get "group disbanded" with partial pay > 0', async () => {
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);
    const groupC = groupNames[2];
    const groupCIndices = groupPageIndices[groupC];

    // Group C players were never idle - they should have been terminated
    // due to insufficient groups remaining
    for (const idx of groupCIndices) {
      const exitInfo = await getExitInfo(pages[idx]);
      expect(exitInfo).not.toBeNull();

      // They should have "group disbanded" reason (game termination uses same reason)
      expect(exitInfo!.exitReason).toBe('group disbanded');

      // They should get the DISBANDED2026 code
      expect(exitInfo!.prolificCode).toBe(PROLIFIC_CODES.disbanded);

      // They should have partial pay > 0 (they participated but game ended early)
      const partialPay = parseFloat(exitInfo!.partialPay || '0');
      expect(partialPay).toBeGreaterThan(0);
    }
  });

  test('idle players from groups A and B get "player timeout" with no pay', async () => {
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);
    const groupA = groupNames[0];
    const groupB = groupNames[1];

    // Check the 2 idle players from group A
    const idleIndicesA = groupPageIndices[groupA].slice(0, 2);
    for (const idx of idleIndicesA) {
      const exitInfo = await getExitInfo(pages[idx]);
      expect(exitInfo).not.toBeNull();
      expect(exitInfo!.exitReason).toBe('player timeout');
      expect(exitInfo!.partialPay).toBe('0');
    }

    // Check the 2 idle players from group B
    const idleIndicesB = groupPageIndices[groupB].slice(0, 2);
    for (const idx of idleIndicesB) {
      const exitInfo = await getExitInfo(pages[idx]);
      expect(exitInfo).not.toBeNull();
      expect(exitInfo!.exitReason).toBe('player timeout');
      expect(exitInfo!.partialPay).toBe('0');
    }
  });
});
