import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  waitForGameStart,
  getActivePlayers,
  waitForStage,
  speakerSendMessage,
  listenerClickTangram,
  clickContinue,
} from '../helpers/game-actions';
import { SELECTION_DURATION, FEEDBACK_DURATION } from '../helpers/constants';
import {
  expectPlayerInGame,
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
    await createBatch(adminPage, 'exp1_refer_separated');
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
    test.slow(); // Idle round requires SELECTION_DURATION timeout (~120s)
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

    // Manually orchestrate 1 round with the speaker idle.
    // We do NOT use playRound({ skipIndices }) because it waits through
    // the entire Feedback stage — we need to check the warning DURING Feedback.

    // Ensure we're in Selection
    await waitForStage(pages[0], 'Selection', 15_000);

    // Non-idle speakers send messages
    for (let i = 0; i < pages.length; i++) {
      if (i === idleSpeakerIndex) continue;
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        await speakerSendMessage(pages[i], 'round message');
      }
    }
    await pages[0].waitForTimeout(500);

    // Non-idle listeners click tangrams
    for (let i = 0; i < pages.length; i++) {
      if (i === idleSpeakerIndex) continue;
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'listener') {
        const clickIdx = info.targetIndex >= 0 ? info.targetIndex : 0;
        await listenerClickTangram(pages[i], clickIdx);
      }
    }

    // Wait for Selection timer to expire and Feedback to appear on the idle page.
    // The idle speaker's group won't submit, so SELECTION_DURATION must run out.
    const feedbackReached = await waitForStage(
      idlePage,
      'Feedback',
      (SELECTION_DURATION + 15) * 1000,
    );
    expect(feedbackReached).toBe(true);

    // Check for warning text NOW, while still in Feedback stage.
    // Refgame.jsx shows "Warning: You were inactive last round." when idle_rounds === 1.
    const warningText = 'Warning: You were inactive';
    const bodyContent = await idlePage.textContent('body');
    expect(
      bodyContent,
      'Expected idle warning text to be visible on the idle player page during Feedback',
    ).toContain(warningText);

    // Now wait for Feedback to end so the game can proceed
    const startWait = Date.now();
    while (Date.now() - startWait < (FEEDBACK_DURATION + 10) * 1000) {
      const info = await getPlayerInfo(idlePage);
      if (!info || info.stageName !== 'Feedback') break;
      await idlePage.waitForTimeout(1000);
    }
  });

  test('idle player is still in the game after warning', async () => {
    const pages = pm.getPages();

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
