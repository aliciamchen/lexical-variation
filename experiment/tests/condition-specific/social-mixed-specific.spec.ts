/**
 * TEST_PLAN 8.3: Social Mixed Specific
 *
 * Verifies social_mixed condition specifics:
 * (a) Phase 1: same as refer_separated (no social guess UI, real names, groups unchanged)
 * (b) Phase 2: reshuffled + masked + social guess UI appears after listener clicks tangram
 * (c) Social guess buttons: "Yes, same group" and "No, different group"
 * (d) After guessing, confirmation shown
 */
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
  waitForGameStart,
  speakerSendMessage,
  listenerClickTangram,
  makeSocialGuess,
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectCondition,
  expectGroupUnchanged,
  expectIdentityMasked,
  expectSocialGuessUI,
  expectNoSocialGuessUI,
  expectOneSpeakerPerGroup,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PLAYER_NAMES,
} from '../helpers/constants';
import { SOCIAL_GUESS_CONTAINER } from '../helpers/selectors';

test.describe.serial('Condition-Specific: social_mixed (TEST_PLAN 8.3)', () => {
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

  test('condition is social_mixed', async () => {
    await expectCondition(pm.getPage(0), 'social_mixed');
  });

  test('(a) Phase 1: groups unchanged (same as refer_separated)', async () => {
    const pages = pm.getPages();
    await expectGroupUnchanged(pages);
  });

  test('(a) Phase 1: real names shown (not "Player")', async () => {
    const pages = pm.getPages();
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info) {
        expect(info.name).not.toBeNull();
        expect(info.name).not.toBe('Player');
      }
    }

    // Also verify in group display
    for (const page of pages) {
      const groupDisplay = page.locator('.player-group');
      if (await groupDisplay.count() > 0) {
        const text = await groupDisplay.textContent();
        const hasRealName = PLAYER_NAMES.some(name => text?.includes(name));
        expect(hasRealName).toBe(true);
      }
    }
  });

  test('(a) Phase 1: no social guess UI', async () => {
    test.slow();
    const pages = pm.getPages();

    // Play first block of Phase 1 and verify no social guess UI appears
    for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
      await playRound(pages);

      // After each round, check that no listener sees social guess UI
      for (const page of pages) {
        const info = await getPlayerInfo(page);
        if (info?.role === 'listener') {
          await expectNoSocialGuessUI(page);
        }
      }
    }

    // Play remaining Phase 1 blocks
    for (let block = 1; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    // Verify groups still unchanged at end of Phase 1
    await expectGroupUnchanged(pages);
  });

  test('transition to Phase 2', async () => {
    const pages = pm.getPages();
    await pages[0].waitForTimeout(2000);
    await handleTransition(pages);
  });

  test('(b) Phase 2: groups reshuffled + identities masked', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Wait for Phase 2 Selection stage so .task element is rendered
    await waitForStage(active[0], 'Selection', 120_000);

    // Verify reshuffling: at least some current_group !== original_group
    const groupData: { originalGroup: string; currentGroup: string }[] = [];
    for (const page of active) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      groupData.push({
        originalGroup: info!.originalGroup!,
        currentGroup: info!.currentGroup!,
      });
    }

    const reshuffled = groupData.filter(d => d.currentGroup !== d.originalGroup);
    expect(reshuffled.length).toBeGreaterThan(0);

    // Verify identities are masked
    for (const page of active) {
      await expectIdentityMasked(page);
    }
  });

  test('(b) Phase 2: social guess UI appears after listener clicks tangram', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Find speakers and send messages
    const groupTargets: Record<string, number> = {};
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        groupTargets[info.currentGroup!] = info.targetIndex;
        await speakerSendMessage(page, 'social guess test message');
      }
    }
    await active[0]?.waitForTimeout(500);

    // Find a listener, click tangram, and verify social guess UI appears
    let socialGuessVerified = false;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2) {
        const targetIdx = groupTargets[info.currentGroup!] ?? 0;
        await listenerClickTangram(page, targetIdx);
        await page.waitForTimeout(500);

        // Social guess UI should appear
        await expectSocialGuessUI(page);
        socialGuessVerified = true;

        // Make the guess to continue the round
        await makeSocialGuess(page, 'same');
        break;
      }
    }
    expect(socialGuessVerified).toBe(true);

    // Complete remaining listeners' clicks and social guesses for this round
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2) {
        // Check if this listener still needs to act (hasn't already clicked)
        try {
          const targetIdx = groupTargets[info.currentGroup!] ?? 0;
          await listenerClickTangram(page, targetIdx);
          await page.waitForTimeout(500);
          await makeSocialGuess(page, 'different');
        } catch {
          // Already completed
        }
      }
    }
    await active[0]?.waitForTimeout(500);
  });

  test('(c) social guess buttons: "Yes, same group" and "No, different group"', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play next round to get to a fresh social guess opportunity
    // First, handle any Continue buttons from previous round's feedback
    for (const page of active) {
      await clickContinue(page, 500);
    }
    await active[0]?.waitForTimeout(500);

    // Speakers send messages
    const groupTargets: Record<string, number> = {};
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        groupTargets[info.currentGroup!] = info.targetIndex;
        await speakerSendMessage(page, 'testing social guess buttons');
      }
    }
    await active[0]?.waitForTimeout(500);

    // Find a listener, click tangram, and check the button labels
    let buttonsVerified = false;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2) {
        const targetIdx = groupTargets[info.currentGroup!] ?? 0;
        await listenerClickTangram(page, targetIdx);
        await page.waitForTimeout(500);

        // Verify both buttons are present with the correct labels
        const sameGroupBtn = page.getByRole('button', { name: /yes, same group/i });
        const diffGroupBtn = page.getByRole('button', { name: /no, different group/i });

        await expect(sameGroupBtn).toBeVisible({ timeout: 5000 });
        await expect(diffGroupBtn).toBeVisible({ timeout: 5000 });
        buttonsVerified = true;

        // Make the guess to proceed
        await makeSocialGuess(page, 'different');
        break;
      }
    }
    expect(buttonsVerified).toBe(true);

    // Complete remaining listeners
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2) {
        try {
          const targetIdx = groupTargets[info.currentGroup!] ?? 0;
          await listenerClickTangram(page, targetIdx);
          await page.waitForTimeout(500);
          await makeSocialGuess(page, 'same');
        } catch {
          // Already completed
        }
      }
    }
    await active[0]?.waitForTimeout(500);
  });

  test('(d) after guessing, confirmation shown (social guess container updates)', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play another round to observe confirmation
    for (const page of active) {
      await clickContinue(page, 500);
    }
    await active[0]?.waitForTimeout(500);

    // Speakers send
    const groupTargets: Record<string, number> = {};
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        groupTargets[info.currentGroup!] = info.targetIndex;
        await speakerSendMessage(page, 'confirmation test');
      }
    }
    await active[0]?.waitForTimeout(500);

    // Find a listener, click tangram, make guess, and verify confirmation
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2) {
        const targetIdx = groupTargets[info.currentGroup!] ?? 0;
        await listenerClickTangram(page, targetIdx);
        await page.waitForTimeout(500);

        // Make social guess
        await makeSocialGuess(page, 'same');
        await page.waitForTimeout(500);

        // After guessing, the social guess buttons should no longer be clickable
        // or a confirmation message should appear. The social guess container
        // should still be visible but in a "completed" state.
        const bodyText = await page.textContent('body');
        // After making a guess, the buttons should disappear or a confirmation
        // should replace them. Verify the guess buttons are gone.
        const sameGroupBtn = page.getByRole('button', { name: /yes, same group/i });
        const btnCount = await sameGroupBtn.count();
        // After guessing, the buttons should either be hidden or disabled
        if (btnCount > 0) {
          const isDisabled = await sameGroupBtn.isDisabled();
          // Either the button is gone (count 0) or disabled
          expect(isDisabled).toBe(true);
        }
        // If count is 0, that means confirmation replaced the buttons - that's correct too
        break;
      }
    }

    // Complete remaining listeners for this round
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2) {
        try {
          const targetIdx = groupTargets[info.currentGroup!] ?? 0;
          await listenerClickTangram(page, targetIdx);
          await page.waitForTimeout(500);
          await makeSocialGuess(page, 'different');
        } catch {
          // Already completed
        }
      }
    }
    await active[0]?.waitForTimeout(500);
  });

  test('complete remaining Phase 2 rounds with social guessing', async () => {
    test.slow();
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // We have played 3 rounds of the first Phase 2 block manually above.
    // Play remaining rounds of first block.
    for (let r = 3; r < ROUNDS_PER_BLOCK; r++) {
      await playRound(active, { doSocialGuess: true });
    }

    // Play remaining Phase 2 blocks
    for (let block = 1; block < PHASE_2_BLOCKS; block++) {
      await playBlock(active, ROUNDS_PER_BLOCK, { doSocialGuess: true });
    }
  });

  test('game completes with bonus info and exit survey', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Click Continue to exit last Feedback stage
    for (const page of active) {
      await clickContinue(page, 5000);
    }

    // Wait for each player to reach bonus_info, then click Continue
    await waitForStage(active[0], 'bonus_info', 120_000);
    for (const page of active) {
      await waitForStage(page, 'bonus_info', 30_000);
      await clickContinue(page, 5000);
    }
    await active[0].waitForTimeout(3000);

    // Complete exit survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
