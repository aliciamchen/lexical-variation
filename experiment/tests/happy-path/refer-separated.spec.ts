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
  waitForGameStart,
  getActivePlayers,
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectPhase,
  expectStage,
  expectCondition,
  expectGroupUnchanged,
  expectOneSpeakerPerGroup,
  expectNoSocialGuessUI,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PROLIFIC_CODES,
} from '../helpers/constants';

test.describe.serial('Happy Path: refer_separated', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    // Create admin page to set up batch
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    // Initialize players
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

  test('game starts with correct condition and groups', async () => {
    const pages = pm.getPages();

    // Verify condition
    await expectCondition(pages[0], 'refer_separated');

    // Verify groups - should have 3 groups of 3
    const groups = await pm.getPagesByGroup();
    const groupNames = Object.keys(groups);
    expect(groupNames.length).toBe(3);
    for (const [name, groupPages] of Object.entries(groups)) {
      expect(groupPages.length).toBe(3);
    }

    // Verify one speaker per group
    await expectOneSpeakerPerGroup(pages);
  });

  test('complete Phase 1', async () => {
    const pages = pm.getPages();

    // Phase 1: PHASE_1_BLOCKS blocks of ROUNDS_PER_BLOCK rounds
    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);

      // After each block verify game state
      const active = await getActivePlayers(pages);
      expect(active.length).toBe(9);
    }

    // Verify we're still in Phase 1 or transitioning
    const info = await getPlayerInfo(pages[0]);
    expect(info).not.toBeNull();
  });

  test('transition screen shows correct text', async () => {
    const pages = pm.getPages();

    // Wait for transition screen
    await pages[0].waitForTimeout(2000);

    // Check that transition content is visible
    const content = await pages[0].textContent('body');
    expect(
      content?.includes('Phase 1') || content?.includes('Phase 2') || content?.includes('transition'),
    ).toBe(true);

    // Click Continue for all
    await handleTransition(pages);
  });

  test('groups stay the same throughout (refer_separated)', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Wait for Phase 2 Selection stage so .task element is rendered
    // Transition stage can be up to 60s, so allow ample time
    await waitForStage(active[0], 'Selection', 120_000);

    // In refer_separated, groups should never change
    await expectGroupUnchanged(active);
  });

  test('complete Phase 2', async () => {
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      const active = await getActivePlayers(pages);
      await playBlock(active, ROUNDS_PER_BLOCK);
    }
  });

  test('no social guess UI in refer_separated', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);
    if (active.length > 0) {
      // Check a listener page - social guess UI should NOT be visible
      for (const page of active) {
        const info = await getPlayerInfo(page);
        if (info?.role === 'listener') {
          await expectNoSocialGuessUI(page);
          break;
        }
      }
    }
  });

  test('bonus info screen appears', async () => {
    test.slow(); // May need extra time if server is degraded from accumulated state
    const pages = pm.getPages();

    // Click Continue to exit last Feedback stage
    for (const page of pages) {
      await clickContinue(page, 5000);
    }

    // Wait for bonus_info stage on first active player
    const active = await getActivePlayers(pages);
    await waitForStage(active[0], 'bonus_info', 120_000);

    const content = await active[0].textContent('body');
    expect(
      content?.includes('bonus') || content?.includes('score') || content?.includes('End of Game'),
    ).toBe(true);

    // Click Continue for each player after they reach bonus_info
    for (const page of active) {
      await waitForStage(page, 'bonus_info', 30_000);
      await clickContinue(page, 5000);
    }
    // Wait for the game to end and exit steps to begin
    await active[0].waitForTimeout(3000);
  });

  test('exit survey and completion code', async () => {
    const pages = pm.getPages();

    // Wait for exit survey page to load (look for "Exit Survey" heading)
    for (const page of pages) {
      try {
        await page.getByText('Exit Survey').waitFor({ state: 'visible', timeout: 30_000 });
      } catch {
        // May already be past this point
      }
    }

    // Check for prolific completion code on exit survey page (before submitting)
    for (const page of pages) {
      const content = await page.textContent('body');
      expect(content).toContain(PROLIFIC_CODES.completion);
    }

    // Complete and submit the survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
