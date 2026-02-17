/**
 * TEST_PLAN 8.2: Refer Mixed Specific
 *
 * Verifies refer_mixed condition specifics:
 * (a) Phase 1: groups same, real names shown
 * (b) Phase 2: groups reshuffled at block boundaries (current_group may differ from original_group)
 * (c) Phase 2: identities masked ("Player" shown instead of real names)
 * (d) No social guess UI ever
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
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectCondition,
  expectGroupUnchanged,
  expectIdentityMasked,
  expectNoSocialGuessUI,
  expectOneSpeakerPerGroup,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PLAYER_NAMES,
} from '../helpers/constants';

test.describe.serial('Condition-Specific: refer_mixed (TEST_PLAN 8.2)', () => {
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

  test('condition is refer_mixed', async () => {
    await expectCondition(pm.getPage(0), 'refer_mixed');
  });

  test('(a) Phase 1: groups are same (original_group === current_group)', async () => {
    const pages = pm.getPages();

    // Record original groups
    const originalGroups: Record<number, string> = {};
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      expect(info).not.toBeNull();
      originalGroups[i] = info!.originalGroup!;
    }

    // Verify groups unchanged at start
    await expectGroupUnchanged(pages);

    // Play Phase 1
    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);

      // After each block, verify groups unchanged
      for (let i = 0; i < pages.length; i++) {
        const info = await getPlayerInfo(pages[i]);
        if (info) {
          expect(info.currentGroup).toBe(info.originalGroup);
          expect(info.originalGroup).toBe(originalGroups[i]);
        }
      }
    }
  });

  test('(a) Phase 1: real names shown (not "Player")', async () => {
    // At end of Phase 1, names should still be real names
    const pages = pm.getPages();
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info) {
        expect(info.name).not.toBeNull();
        expect(info.name).not.toBe('Player');
        expect(info.name!.length).toBeGreaterThan(0);
      }
    }

    // Check group display shows real names
    for (const page of pages) {
      const groupDisplay = page.locator('.player-group');
      if (await groupDisplay.count() > 0) {
        const text = await groupDisplay.textContent();
        const hasRealName = PLAYER_NAMES.some(name => text?.includes(name));
        expect(hasRealName).toBe(true);
      }
    }
  });

  test('(d) no social guess UI during Phase 1', async () => {
    const pages = pm.getPages();
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener') {
        await expectNoSocialGuessUI(page);
        break;
      }
    }
  });

  test('transition to Phase 2', async () => {
    const pages = pm.getPages();
    await pages[0].waitForTimeout(2000);
    await handleTransition(pages);
  });

  test('(b) Phase 2: groups reshuffled - current_group may differ from original_group', async () => {
    const pages = pm.getPages();

    // Wait for Phase 2 Selection stage BEFORE getting active players
    // (during transition, .task element may not exist, causing getActivePlayers issues)
    await waitForStage(pages[0], 'Selection', 120_000);

    const active = await getActivePlayers(pages);

    // Record original and current groups for all players at start of Phase 2
    const groupData: { originalGroup: string; currentGroup: string }[] = [];
    for (const page of active) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      expect(info!.originalGroup).not.toBeNull();
      expect(info!.currentGroup).not.toBeNull();
      groupData.push({
        originalGroup: info!.originalGroup!,
        currentGroup: info!.currentGroup!,
      });
    }

    // In Phase 2 of refer_mixed, at least some players should have
    // current_group !== original_group (groups are reshuffled)
    const reshuffled = groupData.filter(d => d.currentGroup !== d.originalGroup);
    expect(reshuffled.length).toBeGreaterThan(0);

    // Verify mixed group composition: each current group should have players
    // from different original groups
    const currentGroups: Record<string, string[]> = {};
    for (const d of groupData) {
      if (!currentGroups[d.currentGroup]) currentGroups[d.currentGroup] = [];
      currentGroups[d.currentGroup].push(d.originalGroup);
    }

    for (const [group, originals] of Object.entries(currentGroups)) {
      // Each shuffled group should have players from multiple original groups
      const uniqueOriginals = new Set(originals);
      expect(
        uniqueOriginals.size,
        `Shuffled group ${group} should have players from multiple original groups`,
      ).toBeGreaterThan(1);
    }
  });

  test('(c) Phase 2: identities masked - "Player" shown instead of real names', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Identity should be masked in Phase 2 for refer_mixed
    for (const page of active) {
      await expectIdentityMasked(page);
    }
  });

  test('(b) Phase 2: reshuffling happens at block boundaries', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play Phase 2 blocks and track group assignments at block boundaries
    const blockGroupAssignments: Record<number, Record<number, string>> = {};

    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      // Record current groups at start of each block
      blockGroupAssignments[block] = {};
      for (let i = 0; i < active.length; i++) {
        const info = await getPlayerInfo(active[i]);
        if (info?.currentGroup) {
          blockGroupAssignments[block][i] = info.currentGroup;
        }
      }

      // Play rounds within this block
      for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
        await playRound(active);

        // Within a block, groups should NOT change
        for (let i = 0; i < active.length; i++) {
          const info = await getPlayerInfo(active[i]);
          if (info?.currentGroup && blockGroupAssignments[block][i]) {
            expect(info.currentGroup).toBe(blockGroupAssignments[block][i]);
          }
        }
      }
    }

    // Verify that groups changed between at least some block boundaries
    // (reshuffling should happen between blocks)
    if (PHASE_2_BLOCKS > 1) {
      let anyGroupChanged = false;
      for (let i = 0; i < active.length; i++) {
        if (
          blockGroupAssignments[0]?.[i] &&
          blockGroupAssignments[1]?.[i] &&
          blockGroupAssignments[0][i] !== blockGroupAssignments[1][i]
        ) {
          anyGroupChanged = true;
          break;
        }
      }
      // It is possible (but extremely unlikely with 9 players) that reshuffling
      // produces the same assignment. We expect at least some change.
      expect(anyGroupChanged).toBe(true);
    }
  });

  test('(d) no social guess UI during Phase 2', async () => {
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
