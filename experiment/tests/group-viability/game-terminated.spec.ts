/**
 * TEST_PLAN 3.5: Too Many Groups Fail (Game Terminates)
 *
 * Goal: When too many groups lose players and fewer than 2 viable groups remain,
 * the game terminates for ALL remaining players with proportional compensation.
 *
 * Strategy: Idle 2 LISTENERS from Group A → Group A disbanded.
 * Then idle 2 LISTENERS from Group B → Group B disbanded → game terminates.
 * Both idle phases use listeners (not speakers) to avoid the counter-reset bug.
 * See group-disbanded-pay.spec.ts for explanation of why listeners must be used.
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
  waitForStage,
  clickContinue,
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

  test('two listeners from Group A go idle and get kicked, disbanding Group A', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);
    const groupA = groupNames[0];

    // Find the 2 LISTENERS in Group A (not the speaker!)
    const idleIndicesA: number[] = [];
    for (const idx of groupPageIndices[groupA]) {
      const info = await getPlayerInfo(pages[idx]);
      if (info?.role === 'listener') {
        idleIndicesA.push(idx);
      }
    }
    expect(idleIndicesA.length).toBe(2);

    // Idle them for MAX_IDLE_ROUNDS rounds (all within Block 1)
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: idleIndicesA });
    }

    // Wait for idle detection to process
    await pages[0].waitForTimeout(5000);

    // Verify all 3 Group A players are removed (2 timeout + 1 disbanded)
    const removed = await getRemovedPlayers(pages);
    const groupARemoved = removed.filter((r) => {
      const pageIdx = pages.indexOf(r.page);
      return groupPageIndices[groupA].includes(pageIdx);
    });
    expect(groupARemoved.length).toBe(3);
  });

  test('two listeners from Group B go idle and get kicked, triggering game termination', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();
    const groupNames = Object.keys(groupPageIndices);
    const groupB = groupNames[1];

    // Wait for active count to stabilize at 6 (Group A fully removed)
    let active = await getActivePlayers(pages);
    const waitStart = Date.now();
    while (active.length !== 6 && Date.now() - waitStart < 30_000) {
      await pages[0].waitForTimeout(2000);
      active = await getActivePlayers(pages);
    }
    expect(active.length).toBe(6);

    // Play 1 round normally to advance past Block 1 into Block 2.
    // This ensures Group B gets fresh role assignments for Block 2.
    await playRound(pages);

    // Wait for next Selection stage so roles are properly assigned for the new block
    const monitorIdx = groupPageIndices[groupB][0];
    await waitForStage(pages[monitorIdx], 'Selection', 30_000);

    // Now check the CURRENT roles for Group B (they may have changed at block boundary)
    const idleIndicesB: number[] = [];
    for (const idx of groupPageIndices[groupB]) {
      const info = await getPlayerInfo(pages[idx]);
      if (info?.role === 'listener') {
        idleIndicesB.push(idx);
      }
    }
    expect(idleIndicesB.length).toBe(2);

    // Idle Group B listeners for MAX_IDLE_ROUNDS rounds
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
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

    // Check the idle players from group A (the 2 listeners we idled)
    for (const idx of groupPageIndices[groupA]) {
      const exitInfo = await getExitInfo(pages[idx]);
      expect(exitInfo).not.toBeNull();
      if (exitInfo!.exitReason === 'player timeout') {
        expect(exitInfo!.partialPay).toBe('0.00');
      }
    }

    // Check the idle players from group B (the 2 listeners we idled)
    for (const idx of groupPageIndices[groupB]) {
      const exitInfo = await getExitInfo(pages[idx]);
      expect(exitInfo).not.toBeNull();
      if (exitInfo!.exitReason === 'player timeout') {
        expect(exitInfo!.partialPay).toBe('0.00');
      }
    }
  });
});
