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
    test.slow(); // Phase 1 is 18 rounds, takes several minutes
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

    // Wait for ALL active pages to have .task element with data-current-group
    // (Empirica state propagation may lag between browser contexts)
    for (const page of active) {
      await page.locator('.task[data-current-group]').waitFor({ state: 'visible', timeout: 15_000 });
    }

    // Poll for Phase 2 on all pages first (Empirica state may lag)
    const phaseStart = Date.now();
    while (Date.now() - phaseStart < 15_000) {
      let allPhase2 = true;
      for (const page of active) {
        const info = await getPlayerInfo(page);
        if (!info || info.phase !== 2) { allPhase2 = false; break; }
      }
      if (allPhase2) break;
      await pages[0].waitForTimeout(1000);
    }

    // Poll for reshuffling to propagate: retry reading group data with short delays
    // The server reshuffles groups in onRoundStart, but clients may take a moment to sync
    let groupData: { originalGroup: string; currentGroup: string }[] = [];
    let reshuffled: typeof groupData = [];
    const pollStart = Date.now();
    const POLL_TIMEOUT = 15_000;

    while (Date.now() - pollStart < POLL_TIMEOUT) {
      groupData = [];
      for (const page of active) {
        const info = await getPlayerInfo(page);
        if (!info || !info.originalGroup || !info.currentGroup) {
          groupData = []; // incomplete data, retry
          break;
        }
        groupData.push({
          originalGroup: info.originalGroup,
          currentGroup: info.currentGroup,
        });
      }

      if (groupData.length === active.length) {
        reshuffled = groupData.filter(d => d.currentGroup !== d.originalGroup);
        if (reshuffled.length > 0) break; // Reshuffling detected
      }

      await pages[0].waitForTimeout(1000);
    }

    // Assert reshuffling occurred
    expect(
      reshuffled.length,
      `Expected some players to have currentGroup !== originalGroup after reshuffling. ` +
      `Got: ${JSON.stringify(groupData)}`,
    ).toBeGreaterThan(0);

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

  test('(b) Phase 2: groups reshuffle every trial with exactly one in-group listener per group', async () => {
    test.slow(); // plays all of Phase 2
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    type Snap = { originalGroup: string; currentGroup: string; role: string }[];
    const snapshot = async (): Promise<Snap> => {
      const snap: Snap = [];
      for (const page of active) {
        const info = await getPlayerInfo(page);
        expect(info?.currentGroup && info.originalGroup && info.role, 'player info during Selection').toBeTruthy();
        snap.push({ originalGroup: info!.originalGroup!, currentGroup: info!.currentGroup!, role: info!.role! });
      }
      return snap;
    };
    // The preregistered constraint: in every three-person current group, one of
    // the two listeners is from the speaker's original group and one is not.
    const checkComposition = (snap: Snap) => {
      const byGroup: Record<string, Snap> = {};
      for (const s of snap) (byGroup[s.currentGroup] ??= []).push(s);
      for (const [group, members] of Object.entries(byGroup)) {
        const speakers = members.filter((m) => m.role === 'speaker');
        expect(speakers.length, `group ${group} should have exactly one speaker`).toBe(1);
        if (members.length !== 3) continue; // constraint applies to full groups only
        const inGroup = members.filter((m) => m.role === 'listener' && m.originalGroup === speakers[0].originalGroup);
        expect(inGroup.length, `group ${group} should have exactly one in-group listener: ${JSON.stringify(members)}`).toBe(1);
      }
    };
    const differs = (a: Snap, b: Snap) => a.some((m, i) => m.currentGroup !== b[i].currentGroup);

    let prev: Snap | null = null;
    let transitions = 0;
    let changed = 0;
    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      for (let round = 0; round < ROUNDS_PER_BLOCK; round++) {
        expect(await waitForStage(active[0], 'Selection', 60_000), 'expected a Selection stage').toBe(true);
        const snap = await snapshot();
        checkComposition(snap);
        if (prev) {
          transitions++;
          if (differs(prev, snap)) changed++;
        }
        prev = snap;
        await playRound(active);
      }
    }

    // Groups are re-randomized at every trial; identical consecutive
    // assignments happen with probability about 1/24 each, so a large majority
    // of transitions must show a change.
    expect(transitions).toBeGreaterThan(0);
    expect(changed / transitions, `only ${changed} of ${transitions} trial transitions changed groups`).toBeGreaterThan(0.5);
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

    // Wait for each player to reach Bonus info, then click Continue
    await waitForStage(active[0], 'Bonus info', 120_000);
    for (const page of active) {
      await waitForStage(page, 'Bonus info', 30_000);
      await clickContinue(page, 5000);
    }
    await active[0].waitForTimeout(3000);

    // Complete exit survey
    for (const page of pages) {
      await completeExitSurvey(page);
    }
  });
});
