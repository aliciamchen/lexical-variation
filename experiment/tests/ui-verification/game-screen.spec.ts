import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
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
 * TEST_PLAN 5.2: Verify game screen elements.
 *
 * Sets up a full 9-player game and verifies:
 * (a) game container data attributes
 * (b) tangram grid shows 6 tangrams
 * (c) chat input visible during Selection stage
 * (d) player group display shows player names/avatars
 * (e) header shows phase, block, round info
 */
test.describe.serial('UI Verification: Game Screen Elements (5.2)', () => {
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

  test('(a) game container has correct data attributes', async () => {
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

  test('(b) tangram grid shows 12 tangrams', async () => {
    const pages = pm.getPages();
    const page = pages[0];

    const grid = page.locator(TANGRAM_GRID);
    await expect(grid).toBeVisible({ timeout: 10_000 });

    const tangrams = page.locator(TANGRAM_ITEMS);
    const count = await tangrams.count();
    expect(count).toBe(NUM_DISPLAY_TANGRAMS);
  });

  test('(c) chat input visible during Selection stage', async () => {
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

  test('(d) player group display shows player names and avatars', async () => {
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

  test('(e) header shows phase, block, round info', async () => {
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
});
