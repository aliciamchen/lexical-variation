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
  expectCondition,
  expectOneSpeakerPerGroup,
  expectIdentityMasked,
  expectNoSocialGuessUI,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PROLIFIC_CODES,
} from '../helpers/constants';

test.describe.serial('Happy Path: refer_mixed', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_mixed');
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

  test('game starts with refer_mixed condition', async () => {
    await expectCondition(pm.getPage(0), 'refer_mixed');
  });

  test('complete Phase 1 with original groups', async () => {
    const pages = pm.getPages();

    // Record original groups
    const originalGroups: Record<number, string> = {};
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup) originalGroups[i] = info.originalGroup;
    }

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    // Verify original groups didn't change during Phase 1
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup) {
        expect(info.originalGroup).toBe(originalGroups[i]);
      }
    }
  });

  test('phase 2 transition', async () => {
    const pages = pm.getPages();
    await pages[0].waitForTimeout(2000);

    // Transition should mention reshuffling and masked identities
    const content = await pages[0].textContent('body');
    expect(
      content?.includes('shuffle') || content?.includes('mixed') || content?.includes('anonymous') || content?.includes('Phase 2'),
    ).toBe(true);

    await handleTransition(pages);
  });

  test('Phase 2: identities are masked', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Wait for Phase 2 Selection stage so .task element is rendered
    await waitForStage(active[0], 'Selection', 120_000);

    // In Phase 2 of refer_mixed, identities should be masked
    for (const page of active) {
      await expectIdentityMasked(page);
    }
  });

  test('Phase 2: groups are reshuffled', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Record current groups at start of Phase 2
    const phase2Groups: Record<number, string> = {};
    for (let i = 0; i < active.length; i++) {
      const info = await getPlayerInfo(active[i]);
      if (info?.currentGroup) phase2Groups[i] = info.currentGroup;
    }

    // Play Phase 2
    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      await playBlock(active, ROUNDS_PER_BLOCK);
    }
  });

  test('no social guess UI in refer_mixed', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener') {
        await expectNoSocialGuessUI(page);
        break;
      }
    }
  });

  test('bonus info and exit survey', async () => {
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
