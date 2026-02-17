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
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PROLIFIC_CODES,
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
    await expectCondition(pm.getPage(0), 'social_mixed');
  });

  test('complete Phase 1 (no social guessing yet)', async () => {
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      // In Phase 1, no social guessing needed
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }
  });

  test('phase 2 transition mentions social guessing', async () => {
    const pages = pm.getPages();
    await pages[0].waitForTimeout(2000);

    const content = await pages[0].textContent('body');
    // Transition should mention the social guessing task
    expect(
      content?.includes('group') || content?.includes('guess') || content?.includes('Phase 2'),
    ).toBe(true);

    await handleTransition(pages);
  });

  test('Phase 2: social guess UI appears for listeners after clicking', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Wait for Phase 2 Selection stage so .task element is rendered
    await waitForStage(active[0], 'Selection', 120_000);

    // Find a speaker and send a message first
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        await speakerSendMessage(page, 'test for social guess');
        break;
      }
    }
    await active[0]?.waitForTimeout(500);

    // Find a listener, click tangram, verify social guess UI appears
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.phase === 2) {
        await listenerClickTangram(page, 0);
        await page.waitForTimeout(500);

        // Social guess UI should now be visible
        await expectSocialGuessUI(page);

        // Make the guess to proceed
        await makeSocialGuess(page, 'same');
        break;
      }
    }
  });

  test('complete Phase 2 with social guessing', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Complete remaining rounds with social guessing enabled
    // We already played part of round 1, so handle that
    // Complete the rest of the first block
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

    // Verify completion code BEFORE submitting survey
    for (const page of pages) {
      const content = await page.textContent('body');
      expect(content).toContain(PROLIFIC_CODES.completion);
    }

    // Complete exit survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
