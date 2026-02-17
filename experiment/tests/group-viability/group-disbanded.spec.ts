/**
 * TEST_PLAN 3.4: Two Players Drop from Same Group (Group Disbanded)
 *
 * Goal: When 2 players from the same original group go idle and get kicked,
 * the remaining player sees "group disbanded" with code DISBANDED2026
 * and receives partial pay > 0.
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
  playBlock,
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
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  PROLIFIC_CODES,
  MIN_GROUP_SIZE,
} from '../helpers/constants';

test.describe.serial('Group Viability: Group Disbanded (3.4)', () => {
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

  test('all 9 players join and start the game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('identify target group and play initial rounds normally', async () => {
    const pages = pm.getPages();

    // Identify which page indices belong to each original group
    const groups = await getPlayersByGroup(pages);
    const groupNames = Object.keys(groups);
    expect(groupNames.length).toBe(3);

    // Play a couple of rounds so all players participate (building up game time)
    await playRound(pages);
    await playRound(pages);
  });

  test('two players from one group go idle and get kicked', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();

    // Find players by original group so we can target two from the same group
    const groups = await getPlayersByGroup(pages);
    const targetGroupName = Object.keys(groups)[0]; // Pick the first group
    const targetGroupPlayers = groups[targetGroupName];
    expect(targetGroupPlayers.length).toBe(3);

    // Determine page indices for the two players who will idle
    const idlePageIndices: number[] = [];
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup === targetGroupName && idlePageIndices.length < 2) {
        idlePageIndices.push(i);
      }
    }
    expect(idlePageIndices.length).toBe(2);

    // Play rounds with the two target players idling (not sending messages or clicking)
    // They need MAX_IDLE_ROUNDS consecutive idle rounds to get kicked.
    // Always pass full pages array so skipIndices (which reference positions in pages) stay valid.
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: idlePageIndices });
    }

    // Wait for idle detection to process
    await pages[0].waitForTimeout(3000);
  });

  test('idle players are on exit screen with "player timeout"', async () => {
    const pages = pm.getPages();

    // Wait for exit screens to render (sorry screens may not appear immediately)
    // Find the two idle players by waiting for their exit screens
    const groups = await getPlayersByGroup(pages);
    const targetGroupName = Object.keys(groups)[0];

    // Wait for each page to potentially show an exit screen
    for (const page of pages) {
      await waitForExitScreen(page, 30_000);
    }

    const removed = await getRemovedPlayers(pages);
    expect(removed.length).toBeGreaterThanOrEqual(2);

    // Verify the idle players see the sorry/exit screen
    const timeoutPlayers = removed.filter(
      (r) => r.info.exitReason === 'player timeout',
    );
    expect(timeoutPlayers.length).toBeGreaterThanOrEqual(2);

    // Idle players should get NO compensation
    for (const { info } of timeoutPlayers) {
      expect(info.partialPay).toBe('0');
    }
  });

  test('remaining group member sees "group disbanded" with DISBANDED2026 and partial pay > 0', async () => {
    const pages = pm.getPages();

    // Find the remaining player from the disbanded group
    const removed = await getRemovedPlayers(pages);
    const disbandedPlayers = removed.filter(
      (r) => r.info.exitReason === 'group disbanded',
    );

    // There should be at least 1 disbanded player (the remaining member of the group)
    expect(disbandedPlayers.length).toBeGreaterThanOrEqual(1);

    for (const { page, info } of disbandedPlayers) {
      // Verify they see the exit screen
      expect(await isOnExitScreen(page)).toBe(true);

      // Verify the prolific code is DISBANDED2026
      expect(info.prolificCode).toBe(PROLIFIC_CODES.disbanded);

      // Verify partial pay is greater than 0 (proportional compensation)
      const partialPay = parseFloat(info.partialPay || '0');
      expect(partialPay).toBeGreaterThan(0);
    }
  });

  test('game continues with remaining groups (6 players)', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Two groups should still be viable (6 players)
    expect(active.length).toBe(6);

    // Verify remaining players are still in the game
    for (const page of active) {
      expect(await isInGame(page)).toBe(true);
    }

    // Verify the remaining players can continue playing
    await playRound(active);
  });
});
