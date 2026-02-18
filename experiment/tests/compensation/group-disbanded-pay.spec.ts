/**
 * TEST_PLAN 10.3: Group Disbanded Compensation
 *
 * Group-disbanded players get proportional pay and DISBANDED2026 code.
 * Make 2 players from the same group idle until kicked. The remaining
 * group member gets "group disbanded". Verify data-prolific-code="DISBANDED2026"
 * and data-partial-pay is > "0.00".
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

  test('play initial rounds so players accumulate game time', async () => {
    const pages = pm.getPages();
    // Play a couple rounds so all players participate (building up time for partial pay)
    await playRound(pages);
    await playRound(pages);
  });

  test('two players from same group go idle and get kicked, disbanding the group', async () => {
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

    // Play rounds with the two target players idling
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      const active = await getActivePlayers(pages);
      await playRound(active.length === pages.length ? pages : active, {
        skipIndices: idlePageIndices,
      });
    }

    // Wait for idle detection to process
    await pages[0].waitForTimeout(3000);
  });

  test('disbanded player sees DISBANDED2026 code and partial pay > 0.00', async () => {
    const pages = pm.getPages();

    // Wait for exit screens to render on the target group's pages
    const groups = await getPlayersByGroup(pages);
    const targetGroupName = Object.keys(groups)[0];

    // Wait specifically for the target group's pages to show exit screens
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup === targetGroupName) {
        await waitForExitScreen(pages[i], 60_000);
      }
    }

    // Find the player(s) with "group disbanded" exit reason
    const removed = await getRemovedPlayers(pages);
    const disbandedPlayers = removed.filter(
      (r) => r.info.exitReason === 'group disbanded',
    );

    // There should be at least 1 disbanded player (the remaining member of the group)
    expect(disbandedPlayers.length).toBeGreaterThanOrEqual(1);

    for (const { page, info } of disbandedPlayers) {
      // Verify the sorry screen is visible
      expect(await isOnExitScreen(page)).toBe(true);

      // Verify data-prolific-code is DISBANDED2026
      expect(info.prolificCode).toBe(PROLIFIC_CODES.disbanded);

      // Also verify via DOM attribute directly
      const sorryScreen = page.locator(SORRY_SCREEN);
      await expect(sorryScreen).toBeVisible({ timeout: 10_000 });
      const codeAttr = await sorryScreen.getAttribute('data-prolific-code');
      expect(codeAttr).toBe('DISBANDED2026');

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
