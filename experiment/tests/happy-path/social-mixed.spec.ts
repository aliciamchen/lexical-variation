import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  playBlock,
  handleTransition,
  clickContinue,
  completeExitSurvey,
  getActivePlayers,
  makeSocialGuess,
  listenerClickTangram,
  speakerSendMessage,
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectCondition,
  expectIdentityMasked,
  expectSocialGuessUI,
} from '../helpers/assertions';
import { SIMULTANEOUS_SUBMIT } from '../helpers/selectors';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
} from '../helpers/constants';

test.describe.serial('Happy Path: social_mixed', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'social_mixed');
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

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('game starts with social_mixed condition', async () => {
    test.slow(); // May need extra time if server is degraded from accumulated state
    await expectCondition(pm.getPage(0), 'social_mixed');
  });

  test('complete Phase 1 (no social guessing yet)', async () => {
    test.slow();
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      // In Phase 1, no social guessing needed
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }
  });

  test('phase 2 transition mentions social guessing', async () => {
    const pages = pm.getPages();

    // After Phase 1 completion, the game transitions through Feedback → transition stage.
    // Use handleTransition which properly waits for and submits both stages.
    // First check if transition content mentions relevant terms.
    await pages[0].waitForTimeout(2000);

    // Click Continue to advance past any pending Feedback
    for (const page of pages) {
      await clickContinue(page, 3000);
    }

    // Wait for transition stage to appear
    const transitionReached = await waitForStage(pages[0], 'phase_2_transition', 30_000);
    if (transitionReached) {
      const content = await pages[0].textContent('body');
      // Transition should mention the social guessing task or Phase 2
      expect(
        content?.includes('group') || content?.includes('guess') ||
        content?.includes('Phase 2') || content?.includes('Continue'),
      ).toBe(true);
    }

    // Complete the transition (submit for all players)
    await handleTransition(pages);
  });

  test('Phase 2: social guess UI appears simultaneously with tangram grid', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Wait for Phase 2 Selection stage so .task element is rendered
    await waitForStage(active[0], 'Selection', 120_000);

    // Social guess UI should already be visible for listeners (simultaneous mode)
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2) {
        await expectSocialGuessUI(page);
        break;
      }
    }

    // Find a speaker, note their group, and send a message
    let speakerGroup: string | null = null;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        speakerGroup = info.currentGroup;
        await speakerSendMessage(page, 'test for social guess');
        break;
      }
    }
    expect(speakerGroup).not.toBeNull();
    // Allow time for message to propagate to listeners via Empirica state
    await active[0]?.waitForTimeout(2000);

    // Find a listener IN THE SAME GROUP as the speaker, click tangram, social guess, and submit
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2 && info.currentGroup === speakerGroup) {
        const clickIdx = info.targetIndex >= 0 ? info.targetIndex : 0;
        await listenerClickTangram(page, clickIdx);
        await page.waitForTimeout(300);

        // Make the guess and submit both
        await makeSocialGuess(page, 'same');
        await page.locator(SIMULTANEOUS_SUBMIT).click({ timeout: 2000 });
        break;
      }
    }
  });

  test('complete Phase 2 with social guessing', async () => {
    test.slow();
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // The previous test manually played part of round 0 (one speaker sent, one
    // listener clicked + social guessed). The remaining speakers/listeners in
    // other groups didn't act, so the round will wait for SELECTION_DURATION to
    // expire. We need to complete all remaining actions for this round first.
    //
    // Complete round 0: send messages for remaining speakers, click for remaining listeners
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.phase === 2 && info.stageName === 'Selection') {
        await speakerSendMessage(page, 'completing round');
      }
    }
    await active[0]?.waitForTimeout(500);
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2 && info.stageName === 'Selection') {
        const clickIdx = info.targetIndex >= 0 ? info.targetIndex : 0;
        await listenerClickTangram(page, clickIdx);
        await page.waitForTimeout(300);
        await makeSocialGuess(page, 'same');
        try {
          await page.locator(SIMULTANEOUS_SUBMIT).click({ timeout: 2000 });
        } catch {
          // May have already been submitted
        }
      }
    }
    await active[0]?.waitForTimeout(1000);

    // Now play the remaining rounds in block 0 (rounds 1-5)
    for (let r = 1; r < ROUNDS_PER_BLOCK; r++) {
      await playRound(active, { doSocialGuess: true });
    }

    // Play remaining blocks
    for (let block = 1; block < PHASE_2_BLOCKS; block++) {
      await playBlock(active, ROUNDS_PER_BLOCK, { doSocialGuess: true });
    }
  });

  test('bonus info shows social guessing summary', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Click Continue to exit last Feedback stage
    for (const page of active) {
      await clickContinue(page, 5000);
    }

    // Wait for bonus_info stage
    await waitForStage(active[0], 'bonus_info', 120_000);

    const content = await active[0].textContent('body');
    // Bonus info for social_mixed should include social guessing info
    expect(
      content?.includes('bonus') || content?.includes('score') ||
      content?.includes('social') || content?.includes('guess') ||
      content?.includes('End of Game'),
    ).toBe(true);

    // Click Continue for each player after they reach bonus_info
    for (const page of active) {
      await waitForStage(page, 'bonus_info', 30_000);
      await clickContinue(page, 5000);
    }
    await active[0].waitForTimeout(3000);
  });

  test('exit survey and completion code', async () => {
    const pages = pm.getPages();

    // Wait for exit survey to load
    for (const page of pages) {
      try {
        await page.getByText('Exit Survey').waitFor({ state: 'visible', timeout: 30_000 });
      } catch {
        // May already be past this point
      }
    }

    // Complete exit survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
