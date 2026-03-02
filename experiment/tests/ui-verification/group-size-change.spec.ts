import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  getActivePlayers,
  waitForExitScreen,
} from '../helpers/game-actions';
import { MAX_IDLE_ROUNDS } from '../helpers/constants';

/**
 * TEST_PLAN 5.8: When group becomes smaller, message appears.
 *
 * Sets up a 9-player game, makes one player idle until kicked,
 * then verifies remaining group members see the message:
 * "Your group is smaller because a player left or was inactive."
 */
test.describe.serial('UI Verification: Group Size Change (5.8)', () => {
  let pm: PlayerManager;
  let idlePlayerGroup: string | null = null;
  let sameGroupIndices: number[] = [];

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'exp1_refer_separated');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('identify player to make idle and their group members', async () => {
    const pages = pm.getPages();

    // Get the group membership so we can check the right pages later
    const groupMap: Record<string, number[]> = {};
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup) {
        if (!groupMap[info.originalGroup]) groupMap[info.originalGroup] = [];
        groupMap[info.originalGroup].push(i);
      }
    }

    // Verify we have 3 groups of 3
    const groupNames = Object.keys(groupMap);
    expect(groupNames.length).toBe(3);
    for (const indices of Object.values(groupMap)) {
      expect(indices.length).toBe(3);
    }
  });

  test('make player idle until kicked and verify group size message', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();

    // Find out which group player 0 is in
    const idlePlayerIndex = 0;
    const idleInfo = await getPlayerInfo(pages[idlePlayerIndex]);
    expect(idleInfo).not.toBeNull();
    idlePlayerGroup = idleInfo!.originalGroup;

    // Find the other players in the same group
    sameGroupIndices = [];
    for (let i = 0; i < pages.length; i++) {
      if (i === idlePlayerIndex) continue;
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup === idlePlayerGroup) {
        sameGroupIndices.push(i);
      }
    }
    expect(sameGroupIndices.length).toBe(2);

    // Play rounds while skipping the idle player
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [idlePlayerIndex] });
    }

    // Wait for the kick to process
    await pages[idlePlayerIndex].waitForTimeout(3000);

    // Verify idle player is on sorry screen
    const exitInfo = await waitForExitScreen(pages[idlePlayerIndex], 30_000);
    expect(exitInfo).not.toBeNull();

    // Now play at least one more round so the remaining group members
    // are in a new round and see the smaller group message
    const remainingPages = pages.filter((_, i) => i !== idlePlayerIndex);
    const active = await getActivePlayers(remainingPages);
    await playRound(active);

    // Wait for UI to update
    await active[0].waitForTimeout(2000);

    // Check that remaining group members see the smaller group message
    let foundMessage = false;
    for (const idx of sameGroupIndices) {
      const page = pages[idx];
      const info = await getPlayerInfo(page);
      if (info) {
        const bodyText = await page.textContent('body');
        if (bodyText?.includes('Your group is smaller because a player left or was inactive')) {
          foundMessage = true;
          break;
        }
      }
    }
    expect(foundMessage).toBe(true);
  });

  test('group member display shows fewer players after dropout', async () => {
    const pages = pm.getPages();
    expect(idlePlayerGroup).not.toBeNull();

    // Find a remaining player from the affected group using saved group info
    for (const idx of sameGroupIndices) {
      const info = await getPlayerInfo(pages[idx]);
      if (info) {
        // This player should see only 2 players in their group display
        const playerElements = pages[idx].locator('.player-group .player');
        const count = await playerElements.count();
        expect(count).toBe(2); // Only 2 players remain
        break;
      }
    }
  });

  test('other groups still show 3 players', async () => {
    const pages = pm.getPages();
    expect(idlePlayerGroup).not.toBeNull();

    // Find a player NOT in the affected group using saved group info
    for (let i = 1; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info && info.originalGroup !== idlePlayerGroup) {
        // This player should see 3 players in their group display
        const playerElements = pages[i].locator('.player-group .player');
        const count = await playerElements.count();
        expect(count).toBe(3);

        // And should NOT see the smaller group message
        const bodyText = await pages[i].textContent('body');
        expect(bodyText).not.toContain('Your group is smaller');
        break;
      }
    }
  });
});
