import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  waitForGameStart,
  getActivePlayers,
  getRemovedPlayers,
  waitForExitScreen,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  MAX_IDLE_ROUNDS,
} from '../helpers/constants';

/**
 * TEST_PLAN 3.2: Listener Idle Detection
 *
 * A listener who does not click a tangram for MAX_IDLE_ROUNDS consecutive rounds
 * (after the speaker has sent a message each round) should be kicked from the game.
 * The kicked listener sees the sorry screen with exit_reason="player timeout" and
 * prolific_code="none". Other players (including the other listener who did respond)
 * continue playing.
 *
 * Strategy:
 * - Identify a listener player page index.
 * - Use `skipIndices` in playRound so that listener does not click.
 * - The speaker still sends messages normally (so the listener's idleness counts).
 * - After MAX_IDLE_ROUNDS rounds, verify the listener is removed.
 * - Verify remaining players are still active.
 */
test.describe.serial('Idle Detection: Listener Idle (TEST_PLAN 3.2)', () => {
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

  test(`listener is kicked after ${MAX_IDLE_ROUNDS} idle rounds`, async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each (~120s * 5 rounds)
    const pages = pm.getPages();

    // Identify a listener to make idle. Find the first player who is a listener.
    let idleListenerIndex = -1;
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'listener') {
        idleListenerIndex = i;
        break;
      }
    }
    expect(idleListenerIndex).toBeGreaterThanOrEqual(0);

    const idleListenerPage = pages[idleListenerIndex];

    // Play MAX_IDLE_ROUNDS rounds with the listener skipped (idle).
    // The speaker sends messages normally, so the listener's inaction counts as idle.
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [idleListenerIndex] });
    }

    // Wait for the idle listener to see the sorry screen
    const exitInfo = await waitForExitScreen(idleListenerPage, 60_000);
    expect(exitInfo).not.toBeNull();
    expect(exitInfo!.type).toBe('sorry');
    expect(exitInfo!.exitReason).toBe('player timeout');
    expect(exitInfo!.prolificCode).toBe('none');
  });

  test('remaining players are still in the game', async () => {
    const pages = pm.getPages();

    // Allow game state to stabilize after the kick (Empirica state propagation)
    await pages[0].waitForTimeout(3000);

    const active = await getActivePlayers(pages);

    // One listener was kicked, so 8 should remain
    expect(active.length).toBe(8);

    for (const page of active) {
      await expectPlayerInGame(page);
    }
  });

  test('only the idle listener was removed, not the other listener', async () => {
    const pages = pm.getPages();
    const removed = await getRemovedPlayers(pages);

    // Exactly one player should have been removed
    expect(removed.length).toBe(1);
    expect(removed[0].info.exitReason).toBe('player timeout');
    expect(removed[0].info.prolificCode).toBe('none');
  });
});
