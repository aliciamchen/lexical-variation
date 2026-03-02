/**
 * TEST_PLAN 10.3: Group Disbanded Compensation
 *
 * Group-disbanded players get proportional pay and CFTYDMIY code.
 * Make 2 LISTENERS from the same group idle until kicked. The remaining
 * group member (speaker) gets "group disbanded". Verify data-prolific-code="CFTYDMIY"
 * and data-partial-pay is > "0.00".
 *
 * IMPORTANT: The 2 idle players must be LISTENERS (not the speaker).
 * If an idle player is the speaker, they don't send messages, which causes
 * the idle detection to NOT penalize the other idle player (listener) since
 * "speaker didn't send". The listener's idle counter then RESETS to 0.
 * By choosing both idle players as listeners, the active speaker sends
 * messages every round, so both idle listeners are consistently detected
 * as idle (didn't click after speaker sent).
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  getActivePlayers,
  getRemovedPlayers,
  getPlayersByGroup,
  waitForExitScreen,
  isOnExitScreen,
  isInGame,
  getExitInfo,
  completeDisbandedExitSurveys,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  MAX_IDLE_ROUNDS,
  PROLIFIC_CODES,
} from '../helpers/constants';
import { SORRY_SCREEN, PROLIFIC_CODE, PARTIAL_PAY } from '../helpers/selectors';

test.describe.serial('Compensation: Group Disbanded (TEST_PLAN 10.3)', () => {
  let pm: PlayerManager;

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

  test('all 9 players join and start the game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('play initial round so players accumulate game time', async () => {
    const pages = pm.getPages();
    // Play 1 round so all players participate (building up time for partial pay).
    // Only 1 round so we have room for MAX_IDLE_ROUNDS rounds in the same block.
    await playRound(pages);
  });

  test('two listeners from same group go idle and get kicked, disbanding the group', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();

    // Find players by original group so we can target two from the same group
    const groups = await getPlayersByGroup(pages);
    const targetGroupName = Object.keys(groups)[0]; // Pick the first group
    const targetGroupPlayers = groups[targetGroupName];
    expect(targetGroupPlayers.length).toBe(3);

    // Find the 2 LISTENERS in the target group (not the speaker!).
    // The speaker is fixed per block, so within a single block both listeners
    // consistently accumulate idle_rounds when the active speaker sends messages.
    const idlePageIndices: number[] = [];
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

    // Wait for idle detection to process and propagate to clients
    await pages[0].waitForTimeout(5000);
  });

  test('disbanded player sees CFTYDMIY code and partial pay > 0.00', async () => {
    const pages = pm.getPages();

    // Wait until we have at least 3 removed players (2 idle + 1 disbanded).
    // Disbanded players now see ExitSurvey first (type: 'exit-survey'), then Sorry.
    let removed = await getRemovedPlayers(pages);
    const start = Date.now();
    while (removed.length < 3 && Date.now() - start < 120_000) {
      await pages[0].waitForTimeout(2000);
      removed = await getRemovedPlayers(pages);
    }

    // Find the player(s) with "group disbanded" exit reason
    const disbandedPlayers = removed.filter(
      (r) => r.info.exitReason === 'group disbanded',
    );

    // There should be at least 1 disbanded player (the remaining member of the group)
    expect(disbandedPlayers.length).toBeGreaterThanOrEqual(1);

    // Disbanded players are on ExitSurvey — complete it so they reach Sorry
    await completeDisbandedExitSurveys(pages);

    // Now verify the Sorry screen for each disbanded player
    for (const { page } of disbandedPlayers) {
      const sorryScreen = page.locator(SORRY_SCREEN);
      await expect(sorryScreen).toBeVisible({ timeout: 10_000 });

      // Verify data-prolific-code is CFTYDMIY
      const codeAttr = await sorryScreen.getAttribute('data-prolific-code');
      expect(codeAttr).toBe('CFTYDMIY');

      // Verify data-partial-pay is greater than "0.00"
      const partialPayAttr = await sorryScreen.getAttribute('data-partial-pay');
      expect(partialPayAttr).not.toBeNull();
      const partialPayValue = parseFloat(partialPayAttr || '0');
      expect(partialPayValue).toBeGreaterThan(0);
    }
  });

  test('idle players get no compensation (prolific code "none")', async () => {
    const pages = pm.getPages();
    const removed = await getRemovedPlayers(pages);

    const timeoutPlayers = removed.filter(
      (r) => r.info.exitReason === 'player timeout',
    );
    expect(timeoutPlayers.length).toBeGreaterThanOrEqual(2);

    for (const { info } of timeoutPlayers) {
      expect(info.prolificCode).toBe('none');
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
