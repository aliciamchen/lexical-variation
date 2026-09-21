/**
 * Compensation: the researcher stops the batch before the game starts.
 *
 * The other half of batch-terminated.spec.ts. Stopping a batch is the only
 * emergency lever during a live session, and the likeliest moment to pull it
 * is when too few people have turned up to fill a game -- rather than making
 * them sit out the ten-minute lobby.
 *
 * Empirica writes "game terminated" to every player assigned to a game in the
 * batch, started or not. For a game that never started, `game.end()` returns
 * before it ends a stage, so the server's `onGameEnded` never runs and nobody
 * computes these players' pay. Routed like a mid-game termination they would
 * be asked to rate a group they never met and then shown the partial code
 * beside "$0.00", which is both wrong and unpayable: `pay` finds this
 * population by the lobby completion code.
 *
 * They waited and nothing else, so they get the lobby-timeout screen, code
 * and payment. That is what this spec pins.
 *
 * Condition: refer_separated (nothing here depends on the condition).
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch, stopAllBatches } from '../helpers/admin';
import { waitForExitScreen } from '../helpers/game-actions';
import { PROLIFIC_CODES } from '../helpers/constants';
import { SORRY_SCREEN, EXIT_SURVEY } from '../helpers/selectors';

// Fewer than a game needs, so no game can start and everyone waits.
const WAITING_PLAYERS = 3;

test.describe.serial('Compensation: batch stopped while players wait in the lobby', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    pm = new PlayerManager(browser, WAITING_PLAYERS);
    await pm.initialize();
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('three players finish the intro and wait in the lobby', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    for (const page of pm.getPages()) {
      const lobby = page.locator('[data-testid="lobby-screen"]');
      await expect(lobby).toBeVisible({ timeout: 30_000 });
      // The waiting screen has to say how long the wait can be and that it is
      // paid, because the instructions said so several screens ago.
      await expect(lobby).toContainText('Waiting for other players');
      await expect(lobby).toContainText('10 minutes');
      await expect(lobby).toContainText('$2.00');
    }
  });

  test('the researcher stops the batch', async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await stopAllBatches(adminPage);
    await adminContext.close();
  });

  test('each waiting player gets the lobby code, not a $0.00 partial one', async () => {
    for (const page of pm.getPages()) {
      const exitInfo = await waitForExitScreen(page, 60_000);
      expect(exitInfo).not.toBeNull();
      expect(exitInfo!.type).toBe('sorry');

      // No survey: they were never in a group to be asked about.
      await expect(page.locator(EXIT_SURVEY)).toHaveCount(0);

      const sorry = page.locator(SORRY_SCREEN);
      await expect(sorry).toBeVisible();
      await expect(sorry).toHaveAttribute('data-exit-reason', 'lobby_timeout');
      await expect(sorry).toHaveAttribute('data-prolific-code', PROLIFIC_CODES.lobbyTimeout);
      await expect(sorry).toContainText(PROLIFIC_CODES.lobbyTimeout);
      await expect(sorry).toContainText('$2.00');
      await expect(sorry).not.toContainText('$0.00');
    }
  });
});
