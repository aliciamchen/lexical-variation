import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  waitForGameStart,
  getActivePlayers,
  waitForFeedback,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectFeedbackVisible,
} from '../helpers/assertions';

/**
 * TEST_PLAN 3.9: Idle Warning Display
 *
 * After a player's first idle round (idle_rounds === 1), the feedback screen
 * should display a warning message: "Warning: You were inactive last round."
 * The player should NOT be kicked yet -- the warning is just a heads-up.
 *
 * Strategy:
 * - Identify a speaker to make idle for exactly 1 round.
 * - After that round, during the feedback stage (or the next round's display),
 *   check that the warning text appears on the idle player's page.
 * - Verify the player is still in the game (not removed).
 * - Then have the player participate normally to confirm recovery.
 */
test.describe.serial('Idle Detection: Idle Warning Display (TEST_PLAN 3.9)', () => {
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

  test('idle warning appears after first idle round', async () => {
    const pages = pm.getPages();

    // Identify a speaker to make idle for exactly 1 round
    let idleSpeakerIndex = -1;
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'speaker') {
        idleSpeakerIndex = i;
        break;
      }
    }
    expect(idleSpeakerIndex).toBeGreaterThanOrEqual(0);

    const idlePage = pages[idleSpeakerIndex];

    // Play 1 round with the speaker idle (skipped)
    await playRound(pages, { skipIndices: [idleSpeakerIndex] });

    // After the idle round, wait for feedback to appear on the idle player's page.
    // The warning text shows up during the Feedback stage or at the start of
    // the next Selection stage when idle_rounds === 1.
    // Wait a moment for the feedback/next stage to render.
    await idlePage.waitForTimeout(2000);

    // The warning message should appear on the idle player's page.
    // The text in Refgame.jsx: "Warning: You were inactive last round."
    const warningText = 'Warning: You were inactive';
    const bodyContent = await idlePage.textContent('body');
    expect(
      bodyContent,
      'Expected idle warning text to be visible on the idle player page',
    ).toContain(warningText);
  });

  test('idle player is still in the game after warning', async () => {
    const pages = pm.getPages();
    const idlePage = pages.find(async (page) => {
      const content = await page.textContent('body');
      return content?.includes('Warning: You were inactive');
    });

    // All 9 players should still be active (no one kicked after just 1 idle round)
    const active = await getActivePlayers(pages);
    expect(active.length).toBe(9);

    for (const page of active) {
      await expectPlayerInGame(page);
    }
  });

  test('player can recover by participating in next round', async () => {
    const pages = pm.getPages();

    // Play the next round with all players participating (no skips)
    await playRound(pages);

    // All 9 players should still be active after the recovery round
    const active = await getActivePlayers(pages);
    expect(active.length).toBe(9);
  });
});
