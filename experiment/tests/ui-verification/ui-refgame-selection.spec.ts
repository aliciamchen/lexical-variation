import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  speakerSendMessage,
  listenerClickTangram,
} from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';
import {
  GAME_CONTAINER,
  TANGRAM_GRID,
  TANGRAM_ITEMS,
  PLAYER_NAME_ATTR,
  PLAYER_GROUP_ATTR,
} from '../helpers/selectors';
import { NUM_DISPLAY_TANGRAMS } from '../helpers/constants';

/**
 * TEST_PLAN 5.2 + 5.3: Game screen elements and waiting screens.
 *
 * Both suites observe the same opening Phase 1 / Block 0 / Round 0 Selection
 * stage of a refer_separated game, so they share one 9-player game to avoid a
 * second setup. The 5.2 checks are read-only (they inspect the pristine
 * Selection stage) and run first; the 5.3 checks then send messages and make
 * partial listener selections. Those mutations stay within the same Selection
 * stage — the round never completes (only one group fully responds), so no
 * later assertion sees a different block/phase.
 */
test.describe.serial('UI Verification: Refgame Selection (5.2, 5.3)', () => {
  let pm: PlayerManager;

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

  // ─────────────────────────────────────────────────────────────────────────
  // 5.2: Game screen elements (read-only — must run before the 5.3 mutations)
  // ─────────────────────────────────────────────────────────────────────────

  test('(5.2a) game container has correct data attributes', async () => {
    const pages = pm.getPages();
    const page = pages[0];

    await expectPlayerInGame(page);

    const container = page.locator(GAME_CONTAINER);
    await expect(container).toBeVisible();

    // Verify data attributes are set
    const gamePhase = await container.getAttribute('data-game-phase');
    expect(gamePhase).not.toBeNull();
    expect(parseInt(gamePhase!, 10)).toBeGreaterThanOrEqual(1);

    const gameBlock = await container.getAttribute('data-game-block');
    expect(gameBlock).not.toBeNull();

    const gameRound = await container.getAttribute('data-game-round');
    expect(gameRound).not.toBeNull();

    const stageName = await container.getAttribute('data-stage-name');
    expect(stageName).not.toBeNull();
    expect(stageName).toBe('Selection');

    const condition = await container.getAttribute('data-condition');
    expect(condition).toBe('refer_separated');

    const playerGroup = await container.getAttribute('data-player-group');
    expect(playerGroup).not.toBeNull();
    expect(['A', 'B', 'C']).toContain(playerGroup);
  });

  test('(5.2b) tangram grid shows 16 tangrams', async () => {
    const pages = pm.getPages();
    const page = pages[0];

    const grid = page.locator(TANGRAM_GRID);
    await expect(grid).toBeVisible({ timeout: 10_000 });

    const tangrams = page.locator(TANGRAM_ITEMS);
    const count = await tangrams.count();
    expect(count).toBe(NUM_DISPLAY_TANGRAMS);
  });

  test('(5.2c) chat input visible during Selection stage', async () => {
    const pages = pm.getPages();

    // Find a page that is in Selection stage
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.stageName === 'Selection') {
        // Chat textarea should be visible
        const chatInput = page.getByRole('textbox', { name: 'Say something' });
        await expect(chatInput).toBeVisible({ timeout: 10_000 });
        break;
      }
    }
  });

  test('(5.2d) player group display shows player names and avatars', async () => {
    const pages = pm.getPages();
    const page = pages[0];

    // Player group display area
    const playerGroupDisplay = page.locator('.player-group');
    await expect(playerGroupDisplay).toBeVisible({ timeout: 10_000 });

    // Should show player elements with names
    const playerElements = page.locator('.player-group .player');
    const playerCount = await playerElements.count();
    expect(playerCount).toBe(3); // 3 players per group

    // Each player should have a name span
    const nameSpans = page.locator('.player-group .player .name');
    const nameCount = await nameSpans.count();
    expect(nameCount).toBe(3);

    // Check that role labels are shown: (Speaker) or (Listener) or (You)
    const groupText = await playerGroupDisplay.textContent();
    expect(groupText).toContain('(You)');

    // Check avatar images exist
    const avatarImages = page.locator('.player-group .player .image img');
    const avatarCount = await avatarImages.count();
    expect(avatarCount).toBeGreaterThanOrEqual(1);
  });

  test('(5.2e) header shows phase, block, round info', async () => {
    const pages = pm.getPages();
    const page = pages[0];

    // The header is in the status/players card area
    const headerText = await page.locator('.players.card h3').textContent();
    expect(headerText).not.toBeNull();

    // Should contain phase info
    expect(headerText).toContain('Phase');

    // Should contain block info
    expect(headerText).toContain('Block');

    // Profile area should have player name attribute
    const profileEl = page.locator(PLAYER_NAME_ATTR);
    await expect(profileEl).toBeVisible();
    const playerName = await profileEl.getAttribute('data-player-name');
    expect(playerName).not.toBeNull();
    expect(playerName!.length).toBeGreaterThan(0);

    // Profile area should have group attribute
    const groupEl = page.locator(PLAYER_GROUP_ATTR);
    await expect(groupEl.first()).toBeVisible();
    const group = await groupEl.first().getAttribute('data-player-group');
    expect(group).not.toBeNull();
    expect(['A', 'B', 'C']).toContain(group);

    // Score should be displayed in profile
    const scoreText = await page.textContent('body');
    expect(scoreText).toContain('Score');
  });

  // ─────────────────────────────────────────────────────────────────────────
  // 5.3: Waiting screens (mutates the Selection stage in place)
  // ─────────────────────────────────────────────────────────────────────────

  test('(5.3) waiting message appears after speaker sends but before listeners respond', async () => {
    const pages = pm.getPages();

    // Ensure we are in Selection stage
    for (const page of pages) {
      await expectPlayerInGame(page);
    }

    // Find all speakers and send messages
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        await speakerSendMessage(page, 'test message for waiting');
      }
    }
    await pages[0].waitForTimeout(1000);

    // After speaker sends, speaker should see waiting text (waiting for listeners)
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        const bodyText = await page.textContent('body');
        // Speaker has responded (sent message), so they see a waiting message
        const hasWaiting = bodyText?.includes('Waiting for') ||
          bodyText?.includes('All players');
        expect(hasWaiting).toBe(true);
        break;
      }
    }
  });

  test('(5.3) waiting message updates after all group members respond', async () => {
    const pages = pm.getPages();

    // Build group-target mapping from speakers
    const groupTargets: Record<string, number> = {};
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        groupTargets[info.currentGroup!] = info.targetIndex;
      }
    }

    // Have all listeners in ONE group click their tangrams
    // Pick the first group we find
    let targetGroup: string | null = null;
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.currentGroup) {
        targetGroup = info.currentGroup;
        break;
      }
    }
    expect(targetGroup).not.toBeNull();

    // Click tangrams for all listeners in the target group
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.currentGroup === targetGroup) {
        const targetIdx = groupTargets[targetGroup!] ?? 0;
        await listenerClickTangram(page, targetIdx);
      }
    }
    await pages[0].waitForTimeout(1000);

    // After all members in one group respond, they should see
    // "All players in group responded!" or "Waiting for members of other groups"
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup === targetGroup) {
        const bodyText = await page.textContent('body');
        const hasAllResponded = bodyText?.includes('All players') ||
          bodyText?.includes('Waiting for');
        expect(hasAllResponded).toBe(true);
        break;
      }
    }
  });

  test('(5.3) within-group waiting message shows for listeners who responded', async () => {
    const pages = pm.getPages();

    // Find a group where NOT all listeners have responded yet
    // (the groups other than the one we already completed above)
    const groupTargets: Record<string, number> = {};
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        groupTargets[info.currentGroup!] = info.targetIndex;
      }
    }

    // Find a group with listeners who haven't clicked yet
    let incompleteGroup: string | null = null;
    const listenerPages: { page: any; info: any }[] = [];
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && !info.stageName?.includes('Feedback')) {
        // Check if tangram was clicked
        const clicked = await page.evaluate(() => {
          // If there is no selection highlight, the listener hasn't clicked
          return !!document.querySelector('.tangrams.grid .selected, .tangrams.grid [data-clicked]');
        });
        if (!clicked && info.currentGroup) {
          incompleteGroup = info.currentGroup;
          listenerPages.push({ page, info });
        }
      }
    }

    if (incompleteGroup && listenerPages.length > 0) {
      // Have just ONE listener in this group click
      const firstListener = listenerPages[0];
      const targetIdx = groupTargets[incompleteGroup] ?? 0;
      await listenerClickTangram(firstListener.page, targetIdx);
      await firstListener.page.waitForTimeout(1000);

      // This listener should see a waiting message for the remaining group members
      const bodyText = await firstListener.page.textContent('body');
      const hasWaiting = bodyText?.includes('Waiting for') ||
        bodyText?.includes('All players');
      expect(hasWaiting).toBe(true);
    }
  });
});
