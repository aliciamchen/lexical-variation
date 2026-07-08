import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  getActivePlayers,
  waitForExitScreen,
} from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';
import { SORRY_SCREEN } from '../helpers/selectors';
import { MAX_IDLE_ROUNDS } from '../helpers/constants';

/**
 * TEST_PLAN 5.7 + 5.8: Sorry/exit page and group-size-change message.
 *
 * Both suites need the same destructive setup — one player (index 0) made idle
 * until kicked in a refer_separated game — so they share a single game and idle
 * that player out once. The 5.7 checks then inspect the kicked player's Sorry
 * screen, and the 5.8 checks inspect the smaller-group message and reduced
 * player display seen by the remaining members of that group.
 */
test.describe.serial('UI Verification: Idle Removal (5.7, 5.8)', () => {
  let pm: PlayerManager;
  let idlePlayerGroup: string | null = null;
  let sameGroupIndices: number[] = [];
  const idlePlayerIndex = 0;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
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

  test('(5.8) identify idle player group and its members', async () => {
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

    // Record the idle player's group and its other members for later checks
    const idleInfo = await getPlayerInfo(pages[idlePlayerIndex]);
    expect(idleInfo).not.toBeNull();
    idlePlayerGroup = idleInfo!.originalGroup;

    sameGroupIndices = [];
    for (let i = 0; i < pages.length; i++) {
      if (i === idlePlayerIndex) continue;
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup === idlePlayerGroup) {
        sameGroupIndices.push(i);
      }
    }
    expect(sameGroupIndices.length).toBe(2);
  });

  test('(5.7) idle player is removed and sees sorry screen with correct attributes', async () => {
    test.slow(); // Idle rounds require SELECTION_DURATION timeout each
    const pages = pm.getPages();

    // Play rounds while skipping the idle player until it is kicked
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [idlePlayerIndex] });
    }

    // Wait for the kick to process
    await pages[idlePlayerIndex].waitForTimeout(3000);

    // Idle player should now be on the sorry screen
    const exitInfo = await waitForExitScreen(pages[idlePlayerIndex], 30_000);
    expect(exitInfo).not.toBeNull();
    expect(exitInfo!.type).toBe('sorry');
  });

  test('(5.7) sorry screen has data-testid attribute', async () => {
    const idlePage = pm.getPage(idlePlayerIndex);

    const sorryEl = idlePage.locator(SORRY_SCREEN);
    await expect(sorryEl).toBeVisible({ timeout: 10_000 });
  });

  test('(5.7) sorry screen has data-exit-reason attribute', async () => {
    const idlePage = pm.getPage(idlePlayerIndex);

    const sorryEl = idlePage.locator(SORRY_SCREEN);
    const exitReason = await sorryEl.getAttribute('data-exit-reason');
    expect(exitReason).not.toBeNull();
    expect(exitReason).toBe('player timeout');
  });

  test('(5.7) sorry screen has data-prolific-code attribute', async () => {
    const idlePage = pm.getPage(idlePlayerIndex);

    const sorryEl = idlePage.locator(SORRY_SCREEN);
    const prolificCode = await sorryEl.getAttribute('data-prolific-code');
    expect(prolificCode).not.toBeNull();
    // Idle players do NOT receive compensation, so code should be "none"
    expect(prolificCode).toBe('none');
  });

  test('(5.7) sorry screen has data-player-id attribute', async () => {
    const idlePage = pm.getPage(idlePlayerIndex);

    const sorryEl = idlePage.locator(SORRY_SCREEN);
    const playerId = await sorryEl.getAttribute('data-player-id');
    expect(playerId).not.toBeNull();
    expect(playerId).not.toBe('unknown');
  });

  test('(5.7) sorry screen shows "Removed for Inactivity" title', async () => {
    const idlePage = pm.getPage(idlePlayerIndex);

    const bodyText = await idlePage.textContent('body');
    expect(bodyText).toContain('Removed for Inactivity');
  });

  test('(5.7) sorry screen shows no compensation message for idle player', async () => {
    const idlePage = pm.getPage(idlePlayerIndex);

    const bodyText = await idlePage.textContent('body');
    // Idle players should see message about no compensation
    expect(bodyText).toContain('will not receive compensation');
  });

  test('(5.7) remaining players are still in the game', async () => {
    const pages = pm.getPages();

    // All other players should still be in the game
    const activePages = await getActivePlayers(pages.slice(1));
    expect(activePages.length).toBeGreaterThanOrEqual(6);

    for (const page of activePages) {
      await expectPlayerInGame(page);
    }
  });

  test('(5.8) remaining group members see the smaller group message', async () => {
    const pages = pm.getPages();
    expect(idlePlayerGroup).not.toBeNull();

    // Play at least one more round so the remaining group members are in a new
    // round and see the smaller group message
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

  test('(5.8) group member display shows fewer players after dropout', async () => {
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

  test('(5.8) other groups still show 3 players', async () => {
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
