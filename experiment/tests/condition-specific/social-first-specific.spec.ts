/**
 * Condition-specific: social_first (test-mode counterpart of the production-
 * timing holistic spec). Verifies what distinguishes this condition:
 *  - the comprehension quiz has the seventh, social_first-only question
 *    (completeIntro answers it; a missing question fails the intro)
 *  - Phase 1 is a plain reference game: no social guess UI, groups unchanged
 *  - Phase 2 matches social_mixed: reshuffled, masked, social guess UI shown
 *    to listeners alongside the tangram grid, and scores accumulate
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  playBlock,
  handleTransition,
  getActivePlayers,
  waitForStage,
  readScore,
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
import { PHASE_1_BLOCKS, PHASE_2_BLOCKS, ROUNDS_PER_BLOCK } from '../helpers/constants';

test.describe.serial('Condition-specific: social_first', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'social_first');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('all 9 players pass the intro, including the social_first quiz question', async () => {
    await pm.registerAllPlayers();
    // completeIntro answers the seventh question only for social_first; it
    // fails with a timeout if the question is not rendered.
    await pm.completeAllIntros('social_first');
    expect(await pm.waitForGameStart()).toBe(true);
    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
    await expectCondition(pm.getPage(0), 'social_first');
  });

  test('Phase 1: no social guess UI and groups unchanged', async () => {
    test.slow();
    const pages = pm.getPages();
    await expectGroupUnchanged(pages);
    await expectOneSpeakerPerGroup(pages);

    for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
      await playRound(pages);
      for (const page of pages) {
        const info = await getPlayerInfo(page);
        if (info?.role === 'listener') await expectNoSocialGuessUI(page);
      }
    }
    for (let block = 1; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }
    await expectGroupUnchanged(pages);
  });

  test('transition describes the social identification task', async () => {
    const pages = pm.getPages();
    expect(await waitForStage(pages[0], 'Phase 2 transition', 60_000)).toBe(true);
    const content = (await pages[0].textContent('body')) ?? '';
    expect(content).toContain('End of Phase 1');
    expect(content).toMatch(/group/i);
    await handleTransition(pages);
  });

  test('Phase 2: reshuffled, masked, and listeners see the social guess UI with the grid', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);
    expect(await waitForStage(active[0], 'Selection', 120_000)).toBe(true);

    let reshuffled = 0;
    let listenersChecked = 0;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      if (info!.currentGroup !== info!.originalGroup) reshuffled++;
      await expectIdentityMasked(page);
      if (info!.role === 'listener') {
        await expectSocialGuessUI(page);
        listenersChecked++;
      }
    }
    expect(reshuffled, 'some players should be in a different current group').toBeGreaterThan(0);
    expect(listenersChecked).toBeGreaterThan(0);
  });

  test('Phase 2: rounds with social guessing complete and scores grow', async () => {
    test.slow();
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);
    const before = await Promise.all(active.map((p) => readScore(p)));

    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      await playBlock(active, ROUNDS_PER_BLOCK, { doSocialGuess: true });
    }

    const after = await Promise.all(active.map((p) => readScore(p)));
    const gained = after.filter((s, i) => s > before[i]).length;
    expect(gained, 'most players should have scored during Phase 2').toBeGreaterThan(active.length / 2);
  });
});
