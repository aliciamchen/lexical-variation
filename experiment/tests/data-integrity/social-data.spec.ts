/**
 * TEST_PLAN 7.4: Social Guess Data for social_mixed Condition
 *
 * Goal: Verify that in the social_mixed condition, after a listener makes
 * a social guess in Phase 2, the guess confirmation text appears on the page
 * ("You guessed: Same group" or "You guessed: Different group").
 *
 * Strategy:
 * - Set up a full game with social_mixed condition.
 * - Complete Phase 1 to reach Phase 2.
 * - In Phase 2, have the speaker send a message, then have a listener click
 *   a tangram and make a social guess.
 * - Verify the confirmation text appears on the page.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playBlock,
  playRound,
  handleTransition,
  speakerSendMessage,
  listenerClickTangram,
  makeSocialGuess,
  waitForStage,
  getActivePlayers,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectSocialGuessUI,
} from '../helpers/assertions';
import { SIMULTANEOUS_SUBMIT } from '../helpers/selectors';
import {
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
} from '../helpers/constants';

test.describe.serial('Data Integrity: Social Guess Data (TEST_PLAN 7.4)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'exp1_social_mixed');
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

  test('complete Phase 1 and transition to Phase 2', async () => {
    test.slow(); // Phase 1 completion + transition can take a while
    const pages = pm.getPages();

    // Complete all Phase 1 blocks (no social guessing in Phase 1)
    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    // Wait for transition and handle it
    await pages[0].waitForTimeout(3000);
    await handleTransition(pages);

    // Wait for Phase 2 Selection (transition takes ~60s, so need ample timeout)
    const phase2Reached = await waitForStage(pages[0], 'Selection', 120_000);
    expect(phase2Reached).toBe(true);

    // Verify we are in Phase 2
    const info = await getPlayerInfo(pages[0]);
    expect(info).not.toBeNull();
    expect(info!.phase).toBe(2);
  });

  test('listener social guess "same group" shows confirmation text', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Find a speaker and send a message
    let speakerGroup: string | null = null;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.phase === 2) {
        await speakerSendMessage(page, 'social guess test message');
        speakerGroup = info.currentGroup;
        break;
      }
    }
    expect(speakerGroup).not.toBeNull();
    await active[0].waitForTimeout(500);

    // Find a listener in the same group, click a tangram, then make social guess
    let listenerPage = null;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.currentGroup === speakerGroup && info.phase === 2) {
        listenerPage = page;
        break;
      }
    }
    expect(listenerPage).not.toBeNull();

    // Social guess UI should already be visible (simultaneous mode)
    await expectSocialGuessUI(listenerPage!);

    // Click a tangram (local selection)
    await listenerClickTangram(listenerPage!, 0);
    await listenerPage!.waitForTimeout(300);

    // Make the guess: "same group" (local selection)
    const guessed = await makeSocialGuess(listenerPage!, 'same');
    expect(guessed).toBe(true);

    // Submit both selections
    await listenerPage!.locator(SIMULTANEOUS_SUBMIT).click({ timeout: 2000 });

    // Wait for confirmation to render
    await listenerPage!.waitForTimeout(1000);

    // Verify the confirmation text appears on the page
    const bodyText = await listenerPage!.textContent('body');
    expect(bodyText).toContain('You guessed:');
    expect(bodyText).toContain('Same group');
  });

  test('listener social guess "different group" shows confirmation text', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Use playRound to properly advance the game past the current round.
    // playRound handles all players (speakers send, listeners click) and
    // waits for stage transitions including Feedback → next Selection.
    // doSocialGuess: true so listeners also make social guesses to complete the round.
    await playRound(active, { doSocialGuess: true });

    // Wait for the next round's Selection stage
    await waitForStage(active[0], 'Selection', 60_000);

    // Now play a fresh round manually to test "different group" guess
    // Find a speaker and send a message
    let speakerGroup2: string | null = null;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.phase === 2 && info.stageName === 'Selection') {
        await speakerSendMessage(page, 'second social guess test');
        speakerGroup2 = info.currentGroup;
        break;
      }
    }
    expect(speakerGroup2).not.toBeNull();
    await active[0].waitForTimeout(500);

    // Find a listener in the same group and make a "different group" guess
    let foundListener = false;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.currentGroup === speakerGroup2 && info.phase === 2) {
        await listenerClickTangram(page, 1);
        await page.waitForTimeout(300);

        const guessed = await makeSocialGuess(page, 'different');
        expect(guessed).toBe(true);

        // Submit both selections
        await page.locator(SIMULTANEOUS_SUBMIT).click({ timeout: 2000 });
        await page.waitForTimeout(1000);

        // Verify the confirmation text for "Different group"
        const bodyText = await page.textContent('body');
        expect(bodyText).toContain('You guessed:');
        expect(bodyText).toContain('Different group');
        foundListener = true;
        break;
      }
    }
    expect(foundListener).toBe(true);
  });
});
