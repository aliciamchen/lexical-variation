import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  getActivePlayers,
  waitForExitScreen,
} from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';
import { SORRY_SCREEN } from '../helpers/selectors';
import { MAX_IDLE_ROUNDS } from '../helpers/constants';

/**
 * TEST_PLAN 5.7: Sorry/exit pages show correct info for each termination type.
 *
 * Tests that the sorry screen structure exists and has the correct data
 * attributes when a player is removed for inactivity. Makes one player
 * idle until kicked, then verifies the sorry screen content.
 */
test.describe.serial('UI Verification: Sorry Pages (5.7)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('idle player is removed and sees sorry screen with correct attributes', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();

    // Identify which player index to make idle (pick the first player, index 0)
    const idlePlayerIndex = 0;
    const idlePage = pages[idlePlayerIndex];
    const idleInfo = await getPlayerInfo(idlePage);
    expect(idleInfo).not.toBeNull();

    // Play rounds while skipping the idle player
    // Need to play MAX_IDLE_ROUNDS rounds for the player to be kicked
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [idlePlayerIndex] });
    }

    // Wait for the idle player to be kicked and see the sorry screen
    await idlePage.waitForTimeout(3000);

    // Check if the idle player is now on the sorry screen
    const exitInfo = await waitForExitScreen(idlePage, 30_000);
    expect(exitInfo).not.toBeNull();
    expect(exitInfo!.type).toBe('sorry');
  });

  test('sorry screen has data-testid attribute', async () => {
    const idlePage = pm.getPage(0);

    const sorryEl = idlePage.locator(SORRY_SCREEN);
    await expect(sorryEl).toBeVisible({ timeout: 10_000 });
  });

  test('sorry screen has data-exit-reason attribute', async () => {
    const idlePage = pm.getPage(0);

    const sorryEl = idlePage.locator(SORRY_SCREEN);
    const exitReason = await sorryEl.getAttribute('data-exit-reason');
    expect(exitReason).not.toBeNull();
    expect(exitReason).toBe('player timeout');
  });

  test('sorry screen has data-prolific-code attribute', async () => {
    const idlePage = pm.getPage(0);

    const sorryEl = idlePage.locator(SORRY_SCREEN);
    const prolificCode = await sorryEl.getAttribute('data-prolific-code');
    expect(prolificCode).not.toBeNull();
    // Idle players do NOT receive compensation, so code should be "none"
    expect(prolificCode).toBe('none');
  });

  test('sorry screen has data-player-id attribute', async () => {
    const idlePage = pm.getPage(0);

    const sorryEl = idlePage.locator(SORRY_SCREEN);
    const playerId = await sorryEl.getAttribute('data-player-id');
    expect(playerId).not.toBeNull();
    expect(playerId).not.toBe('unknown');
  });

  test('sorry screen shows "Removed for Inactivity" title', async () => {
    const idlePage = pm.getPage(0);

    const bodyText = await idlePage.textContent('body');
    expect(bodyText).toContain('Removed for Inactivity');
  });

  test('sorry screen shows no compensation message for idle player', async () => {
    const idlePage = pm.getPage(0);

    const bodyText = await idlePage.textContent('body');
    // Idle players should see message about no compensation
    expect(bodyText).toContain('will not receive compensation');
  });

  test('remaining players are still in the game', async () => {
    const pages = pm.getPages();

    // All other players should still be in the game
    const activePages = await getActivePlayers(pages.slice(1));
    expect(activePages.length).toBeGreaterThanOrEqual(6);

    for (const page of activePages) {
      await expectPlayerInGame(page);
    }
  });
});
