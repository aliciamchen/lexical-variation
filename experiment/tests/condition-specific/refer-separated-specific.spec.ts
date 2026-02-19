/**
 * TEST_PLAN 8.1: Refer Separated Specific
 *
 * Verifies refer_separated condition specifics:
 * (a) Groups never change (original_group === current_group always)
 * (b) Real names shown throughout (not "Player")
 * (c) No social guess UI ever
 * (d) One speaker per group per round
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
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectPhase,
  expectCondition,
  expectGroupUnchanged,
  expectNoSocialGuessUI,
  expectOneSpeakerPerGroup,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PLAYER_COUNT,
  PLAYER_NAMES,
} from '../helpers/constants';

test.describe.serial('Condition-Specific: refer_separated (TEST_PLAN 8.1)', () => {
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

  test('condition is refer_separated', async () => {
    await expectCondition(pm.getPage(0), 'refer_separated');
  });

  test('(a) groups never change during Phase 1 - original_group === current_group', async () => {
    test.slow();
    const pages = pm.getPages();

    // Record original groups for all players
    const originalGroups: Record<number, string> = {};
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      expect(info).not.toBeNull();
      expect(info!.originalGroup).not.toBeNull();
      originalGroups[i] = info!.originalGroup!;
    }

    // Play through Phase 1, checking groups after every block
    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      // Verify groups unchanged before each block
      await expectGroupUnchanged(pages);

      for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
        await playRound(pages);

        // Spot-check: verify original_group === current_group for all active players
        for (let i = 0; i < pages.length; i++) {
          const info = await getPlayerInfo(pages[i]);
          if (info) {
            expect(info.currentGroup).toBe(info.originalGroup);
            expect(info.originalGroup).toBe(originalGroups[i]);
          }
        }
      }
    }
  });

  test('(d) one speaker per group per round at end of Phase 1', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);
    await expectOneSpeakerPerGroup(active);
  });

  test('handle Phase 1 to Phase 2 transition', async () => {
    const pages = pm.getPages();
    await pages[0].waitForTimeout(2000);
    await handleTransition(pages);
  });

  test('(a) groups still unchanged after transition to Phase 2', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Wait for Phase 2 Selection stage so .task element is rendered
    await waitForStage(active[0], 'Selection', 120_000);

    await expectGroupUnchanged(active);
  });

  test('(b) real names shown throughout Phase 2 (not "Player")', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    for (const page of active) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      // The player's own name should be visible and should NOT be the generic "Player"
      expect(info!.name).not.toBeNull();
      expect(info!.name).not.toBe('Player');
      expect(info!.name!.length).toBeGreaterThan(0);
    }

    // Also verify in the group display area that real names (not "Player") appear
    for (const page of active) {
      const groupDisplay = page.locator('.player-group');
      if (await groupDisplay.count() > 0) {
        const text = await groupDisplay.textContent();
        // In refer_separated, real assigned names should appear, not generic "Player"
        // At least one of the assigned player names should be visible
        const hasRealName = PLAYER_NAMES.some(name => text?.includes(name));
        expect(hasRealName).toBe(true);
      }
    }
  });

  test('(c) no social guess UI during Phase 2 rounds', async () => {
    test.slow();
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play Phase 2 and check for social guess UI after each round
    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
        await playRound(active);

        // After each round, verify no social guess UI for any listener
        for (const page of active) {
          const info = await getPlayerInfo(page);
          if (info?.role === 'listener') {
            await expectNoSocialGuessUI(page);
          }
        }
      }

      // Verify groups still unchanged after each Phase 2 block
      await expectGroupUnchanged(active);
    }
  });

  test('(d) one speaker per group per round throughout Phase 2', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);
    await expectOneSpeakerPerGroup(active);
  });

  test('(a) groups unchanged at end of game', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);
    // Final verification that groups never changed
    await expectGroupUnchanged(active);
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
