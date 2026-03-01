import { test, expect } from '@playwright/test';
import { createBatch } from '../helpers/admin';
import { waitForExitScreen, getExitInfo } from '../helpers/game-actions';
import { PROLIFIC_CODES } from '../helpers/constants';
import { SORRY_SCREEN } from '../helpers/selectors';

// TEST_PLAN 4.1: Lobby timeout when not enough players join
// The default lobby config ("Default shared fail") has a 5-minute timeout.
// This test requires the lobby to actually time out, so it takes a long time.
test.describe.serial('Lobby: timeout with insufficient players', () => {
  test.skip(true, 'Requires specific lobby timeout settings; takes 5+ minutes to run');

  test('players see lobby timeout sorry screen when game cannot start', async ({ browser }) => {
    // Increase timeout for this test since we need to wait for lobby timeout (5 minutes)
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

    // Complete intro for each player (enter identifier, consent, instructions, quiz)
    for (let i = 0; i < playerPages.length; i++) {
      const page = playerPages[i];

      // Enter identifier
      const textbox = page.getByRole('textbox');
      await textbox.fill(`lobby_player${i + 1}`);
      await page.getByRole('button', { name: /enter/i }).click();
      await page.waitForTimeout(300);

      // Consent
      await page.getByRole('button', { name: /consent/i }).click();
      await page.waitForTimeout(300);

      // 5 intro pages
      for (let j = 0; j < 5; j++) {
        await page.getByRole('button', { name: /next/i }).click();
        await page.waitForTimeout(200);
      }

      // Quiz - answer correctly
      await page.getByRole('radio', { name: /describe the target picture/i }).click();
      await page.getByRole('radio', { name: /removed from the game/i }).click();
      await page.getByRole('radio', { name: /only topics related to picking out/i }).click();
      await page.getByRole('radio', { name: /listeners must wait/i }).click();
      await page.getByRole('radio', { name: /mixed up/i }).click();
      await page.getByRole('radio', { name: /different positions for each player/i }).click();

      // Handle quiz success dialog
      page.once('dialog', async (dialog) => await dialog.accept());
      await page.getByRole('button', { name: /submit/i }).click();
      await page.waitForTimeout(500);
    }

    // Players should now be in the lobby waiting for more players.
    // Wait for the lobby timeout (up to 6 minutes to allow buffer beyond 5-minute config).
    for (const page of playerPages) {
      const exitInfo = await waitForExitScreen(page, 360_000);
      expect(exitInfo).not.toBeNull();
    }

    // Verify each player sees the sorry screen with lobby timeout info
    for (const page of playerPages) {
      const sorryScreen = page.locator(SORRY_SCREEN);
      await expect(sorryScreen).toBeVisible({ timeout: 10_000 });

      const prolificCode = await sorryScreen.getAttribute('data-prolific-code');
      expect(prolificCode).toBe(PROLIFIC_CODES.lobbyTimeout);
    }

    // Cleanup
    for (const context of playerContexts) {
      await context.close().catch(() => {});
    }
  });
});
