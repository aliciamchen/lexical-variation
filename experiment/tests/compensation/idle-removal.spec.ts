/**
 * TEST_PLAN 10.2: Idle Removal Compensation
 *
 * Idle-removed players get base pay prorated to time spent, no bonus. Make one
 * player idle for MAX_IDLE_ROUNDS. Verify their sorry screen shows the
 * partial-payment code and a positive amount. Verify remaining players can continue.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  getActivePlayers,
  getRemovedPlayers,
  waitForExitScreen,
  getExitInfo,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectPlayerOnExitScreen,
} from '../helpers/assertions';
import {
  MAX_IDLE_ROUNDS,
  PROLIFIC_CODES,
} from '../helpers/constants';
import { SORRY_SCREEN, PROLIFIC_CODE } from '../helpers/selectors';

test.describe.serial('Compensation: Idle Removal (TEST_PLAN 10.2)', () => {
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

  test('all 9 players complete intro and enter game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    const pages = pm.getPages();
    for (const page of pages) {
      await expectPlayerInGame(page);
    }
  });

  test(`idle player is removed after ${MAX_IDLE_ROUNDS} rounds and gets prorated base pay`, async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();

    // Find a speaker to make idle
    let idlePlayerIndex = -1;
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'speaker') {
        idlePlayerIndex = i;
        break;
      }
    }
    expect(idlePlayerIndex).toBeGreaterThanOrEqual(0);

    const idlePlayerPage = pages[idlePlayerIndex];

    // Play MAX_IDLE_ROUNDS rounds with the player idle (skipped)
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [idlePlayerIndex] });
    }

    // Wait for the idle player to see the sorry screen
    const exitInfo = await waitForExitScreen(idlePlayerPage, 60_000);
    expect(exitInfo).not.toBeNull();
    expect(exitInfo!.type).toBe('sorry');
    expect(exitInfo!.exitReason).toBe('player timeout');

    // Idle players receive prorated base pay (no bonus) with the partial-payment code
    expect(exitInfo!.prolificCode).toBe('CFTYDMIY');

    // Also verify via DOM attribute directly
    const sorryScreen = idlePlayerPage.locator(SORRY_SCREEN);
    await expect(sorryScreen).toBeVisible({ timeout: 10_000 });
    const prolificCodeAttr = await sorryScreen.getAttribute('data-prolific-code');
    expect(prolificCodeAttr).toBe('CFTYDMIY');

    // Idle players receive prorated base pay (no bonus) with the partial-payment code
    expect(prolificCodeAttr).toBe(PROLIFIC_CODES.disbanded);
    const partialPayAttr = await sorryScreen.getAttribute('data-partial-pay');
    expect(parseFloat(partialPayAttr || '0')).toBeGreaterThan(0);
  });

  test('remaining players can continue playing', async () => {
    const pages = pm.getPages();

    // Wait for game state to stabilize after the kick
    await pages[0].waitForTimeout(5000);

    const active = await getActivePlayers(pages);

    // One player was kicked, so 8 should remain
    expect(active.length).toBe(8);
  });
});
