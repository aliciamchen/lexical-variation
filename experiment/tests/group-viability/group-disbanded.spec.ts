/**
 * TEST_PLAN 3.4: Two Players Drop from Same Group (Group Disbanded)
 *
 * Goal: When 2 players from the same original group go idle and get kicked,
 * the remaining player sees "group disbanded" with code CFTYDMIY
 * and receives partial pay > 0.
 *
 * IMPORTANT: The 2 idle players must be LISTENERS (not the speaker).
 * See group-disbanded-pay.spec.ts for detailed explanation of why.
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
  completeDisbandedExitSurveys,
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
  let idlePageIndices: number[] = [];
  let targetGroupName: string;

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

  test('identify target group and play initial round normally', async () => {
    const pages = pm.getPages();

    // Identify which page indices belong to each original group
    const groups = await getPlayersByGroup(pages);
    const groupNames = Object.keys(groups);
    expect(groupNames.length).toBe(3);

    // Play 1 round so all players participate (building up game time).
    // Only 1 round so MAX_IDLE_ROUNDS idle rounds fit in the same block.
    await playRound(pages);
  });

  test('two listeners from one group go idle and get kicked', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();

    // Find players by original group so we can target two from the same group
    const groups = await getPlayersByGroup(pages);
    targetGroupName = Object.keys(groups)[0]; // Pick the first group
    const targetGroupPlayers = groups[targetGroupName];
    expect(targetGroupPlayers.length).toBe(3);

    // Find the 2 LISTENERS in the target group (not the speaker!).
    // The speaker is fixed per block, so within a single block both listeners
    // consistently accumulate idle_rounds when the active speaker sends.
    idlePageIndices = [];
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup === targetGroupName && info.role === 'listener') {
        idlePageIndices.push(i);
      }
    }
    expect(idlePageIndices.length).toBe(2); // 3-player group has exactly 2 listeners

    // Play MAX_IDLE_ROUNDS rounds with the 2 listeners idling.
    // The active speaker sends messages each round, so both idle listeners
    // are detected as idle (didn't click after speaker sent).
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: idlePageIndices });
    }

    // Wait for idle detection to process and propagate
    await pages[0].waitForTimeout(5000);
  });

  test('idle players are on exit screen with "player timeout"', async () => {
    const pages = pm.getPages();

    // Wait for sorry screens on the specific idle players (more reliable than polling all 9)
    for (const idx of idlePageIndices) {
      const exitInfo = await waitForExitScreen(pages[idx], 60_000);
      expect(exitInfo).not.toBeNull();
      expect(exitInfo!.exitReason).toBe('player timeout');
      expect(exitInfo!.prolificCode).toBe('none');
    }
  });

  test('remaining group member sees "group disbanded" with CFTYDMIY and partial pay > 0', async () => {
    const pages = pm.getPages();

    // Find the remaining player from the disbanded group
    const removed = await getRemovedPlayers(pages);
    const disbandedPlayers = removed.filter(
      (r) => r.info.exitReason === 'group disbanded',
    );

    // There should be at least 1 disbanded player (the remaining member of the group)
    expect(disbandedPlayers.length).toBeGreaterThanOrEqual(1);

    // Disbanded players are on ExitSurvey — complete it so they reach Sorry
    await completeDisbandedExitSurveys(pages);

    // Now verify the Sorry screen for each disbanded player
    for (const { page } of disbandedPlayers) {
      const info = await getExitInfo(page);
      expect(info).not.toBeNull();
      expect(info!.type).toBe('sorry');
      expect(info!.exitReason).toBe('group disbanded');

      // Verify the prolific code is CFTYDMIY
      expect(info!.prolificCode).toBe(PROLIFIC_CODES.disbanded);

      // Verify partial pay is greater than 0 (proportional compensation)
      const partialPay = parseFloat(info!.partialPay || '0');
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
