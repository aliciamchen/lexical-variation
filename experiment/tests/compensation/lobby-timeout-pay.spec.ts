/**
 * TEST_PLAN 10.4: Lobby Timeout Compensation
 *
 * Lobby timeout players get the CMZUY3MK code.
 * Create just 3 players for a 9-player game, wait for lobby timeout,
 * verify they see the correct code.
 *
 * NOTE: This test is skipped by default because it requires waiting for the
 * actual lobby timeout (5+ minutes) and specific lobby timeout settings.
 */
import { test, expect } from '@playwright/test';
import { createBatch } from '../helpers/admin';
import { completeIntro, waitForExitScreen, getExitInfo } from '../helpers/game-actions';
import { PROLIFIC_CODES, LOBBY_TIMEOUT_PAY } from '../helpers/constants';
import { SORRY_SCREEN, PROLIFIC_CODE } from '../helpers/selectors';

test.describe.serial('Compensation: Lobby Timeout (TEST_PLAN 10.4)', () => {
  test.skip(true, 'Requires specific lobby timeout settings; takes 5+ minutes to run');

  test('players see CMZUY3MK code when game cannot start', async ({ browser }) => {
    // Increase timeout since we need to wait for lobby timeout (5 minutes)
    test.setTimeout(600_000);

    // Create batch requiring 9 players
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    // Register only 3 players (not enough to start the 9-player game)
    const playerContexts = [];
    const playerPages = [];
    for (let i = 0; i < 3; i++) {
      const context = await browser.newContext();
      const page = await context.newPage();
      playerContexts.push(context);
      playerPages.push(page);
    }

    // Navigate all players to the experiment
    for (const page of playerPages) {
      await page.goto('/');
      await page.waitForTimeout(300);
    }

    // Complete intro for each player
    for (let i = 0; i < playerPages.length; i++) {
      await completeIntro(playerPages[i], `lobby_timeout_player${i + 1}`);
    }

    // Players should now be in the lobby waiting for more players.
    // Wait for the lobby timeout (up to 6 minutes to allow buffer beyond 5-minute config).
    for (const page of playerPages) {
      const exitInfo = await waitForExitScreen(page, 360_000);
      expect(exitInfo).not.toBeNull();
    }

    // Verify each player sees the sorry screen with CMZUY3MK code
    for (const page of playerPages) {
      const sorryScreen = page.locator(SORRY_SCREEN);
      await expect(sorryScreen).toBeVisible({ timeout: 10_000 });

      // Verify data-prolific-code is CMZUY3MK
      const prolificCode = await sorryScreen.getAttribute('data-prolific-code');
      expect(prolificCode).toBe(PROLIFIC_CODES.lobbyTimeout);

      // Also verify the page content mentions the code
      const content = await page.textContent('body');
      expect(content).toContain('CMZUY3MK');

      // Verify that the compensation amount is mentioned ($2 for lobby timeout)
      expect(content).toContain(`$${LOBBY_TIMEOUT_PAY.toFixed(2)}`);
    }

    // Cleanup
    for (const context of playerContexts) {
      await context.close().catch(() => {});
    }
  });
});
