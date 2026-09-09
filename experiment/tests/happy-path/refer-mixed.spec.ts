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
    test.slow();
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

    // Wait for transition stage to appear
    await pages[0].waitForTimeout(3000);

    // The transition screen must announce the end of Phase 1 and describe Phase 2
    const transitionReached = await waitForStage(pages[0], 'Phase 2 transition', 60_000);
    expect(transitionReached, 'expected the Phase 2 transition stage').toBe(true);
    const content = (await pages[0].textContent('body')) ?? '';
    expect(content).toContain('End of Phase 1');
    expect(content).toContain('Phase 2');

    await handleTransition(pages);
  });

  test('Phase 2: identities are masked', async () => {
    test.slow();
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Wait for Phase 2 Selection stage so .task element is rendered
    await waitForStage(active[0], 'Selection', 120_000);

    // Wait for ALL active pages to have .task element with data-current-group
    // (Empirica state propagation may lag between browser contexts)
    for (const page of active) {
      await page.locator('.task[data-current-group]').waitFor({ state: 'visible', timeout: 15_000 });
    }

    // Poll to verify all pages are in Phase 2 before checking identities
    const pollStart = Date.now();
    while (Date.now() - pollStart < 10_000) {
      let allPhase2 = true;
      for (const page of active) {
        const info = await getPlayerInfo(page);
        if (!info || info.phase !== 2) { allPhase2 = false; break; }
      }
      if (allPhase2) break;
      await pages[0].waitForTimeout(1000);
    }

    // In Phase 2 of refer_mixed, identities should be masked
    for (const page of active) {
      await expectIdentityMasked(page);
    }
  });

  test('Phase 2: groups are reshuffled between consecutive trials', async () => {
    test.slow();
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    const snapshot = async () => {
      const groups: Record<number, string> = {};
      for (let i = 0; i < active.length; i++) {
        const info = await getPlayerInfo(active[i]);
        if (info?.currentGroup) groups[i] = info.currentGroup;
      }
      return groups;
    };
    const changedBetween = (a: Record<number, string>, b: Record<number, string>) =>
      Object.keys(a).filter((k) => b[+k] !== undefined && a[+k] !== b[+k]).length;

    // Groups are reshuffled at the start of every Phase 2 trial. Compare two
    // consecutive transitions; an identical assignment twice in a row has
    // probability well under one in a hundred.
    await waitForStage(active[0], 'Selection', 60_000);
    const t0 = await snapshot();
    await playRound(active);
    await waitForStage(active[0], 'Selection', 60_000);
    const t1 = await snapshot();
    await playRound(active);
    await waitForStage(active[0], 'Selection', 60_000);
    const t2 = await snapshot();

    expect(Object.keys(t0).length).toBe(active.length);
    expect(
      changedBetween(t0, t1) + changedBetween(t1, t2),
      `expected current groups to change between consecutive trials; got ${JSON.stringify([t0, t1, t2])}`,
    ).toBeGreaterThan(0);

    // Finish Phase 2 (two rounds of the first block already played)
    for (let r = 2; r < ROUNDS_PER_BLOCK; r++) await playRound(active);
    for (let block = 1; block < PHASE_2_BLOCKS; block++) {
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

    // Wait for each player to reach Bonus info, then click Continue
    await waitForStage(active[0], 'Bonus info', 120_000);
    for (const page of active) {
      await waitForStage(page, 'Bonus info', 30_000);
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

    // Complete exit survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
