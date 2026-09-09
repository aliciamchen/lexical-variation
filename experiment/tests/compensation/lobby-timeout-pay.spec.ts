/**
 * TEST_PLAN 10.4: Lobby Timeout Compensation
 *
 * Lobby timeout players get the CMZUY3MK code.
 * Create just 3 players for a 9-player game, wait for lobby timeout,
 * verify they see the correct code.
 *
 * The only lobby configuration offered in production is the 10-minute shared
 * "fail" lobby (.empirica/lobbies.yaml), so this test has to wait out those ten
 * minutes. It is skipped unless LOBBY_TESTS=true so a routine run stays fast:
 *   LOBBY_TESTS=true npx playwright test reset-server.setup tests/compensation/lobby-timeout-pay.spec.ts --project=setup-4 --project=group-4 --no-deps
 */
import { test, expect } from '@playwright/test';
import { createBatch } from '../helpers/admin';
import { completeIntro, waitForExitScreen, getExitInfo } from '../helpers/game-actions';
import { PROLIFIC_CODES, LOBBY_TIMEOUT_PAY } from '../helpers/constants';
import { SORRY_SCREEN, PROLIFIC_CODE } from '../helpers/selectors';

test.describe.serial('Compensation: Lobby Timeout (TEST_PLAN 10.4)', () => {
  test.skip(process.env.LOBBY_TESTS !== 'true', 'waits out the 10-minute production lobby; run with LOBBY_TESTS=true');

  test('players see CMZUY3MK code when game cannot start', async ({ browser }) => {
    // The lobby times out after 10 minutes; allow for that plus the intro.
    test.setTimeout(15 * 60_000);

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

    // Players are now in the lobby waiting for more players. Wait for the
    // 10-minute lobby timeout (plus a buffer).
    for (const page of playerPages) {
      const exitInfo = await waitForExitScreen(page, 12 * 60_000);
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
      expect(content).toContain(PROLIFIC_CODES.lobbyTimeout);

      // Verify that the compensation amount is mentioned ($2 for lobby timeout)
      expect(content).toContain(`$${LOBBY_TIMEOUT_PAY.toFixed(2)}`);
    }

    // Cleanup
    for (const context of playerContexts) {
      await context.close().catch(() => {});
    }
  });
});
