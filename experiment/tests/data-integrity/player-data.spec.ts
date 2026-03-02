/**
 * TEST_PLAN 7.1: Player Data Attributes Are Consistent
 *
 * Goal: Verify that player data attributes rendered in the DOM are correct
 * and consistent. Each player should have a name from PLAYER_NAMES,
 * an original_group of A/B/C, and in Phase 1 the current_group should
 * match the original_group.
 *
 * Strategy:
 * - Set up a full game with 9 players.
 * - Once the game starts, read data attributes from each player's page.
 * - Verify name, original_group, current_group values.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  PLAYER_NAMES,
  GROUP_NAMES,
  PLAYER_COUNT,
} from '../helpers/constants';

test.describe.serial('Data Integrity: Player Data (TEST_PLAN 7.1)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'exp1_refer_separated');
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

  test('each player has a valid name from PLAYER_NAMES', async () => {
    const pages = pm.getPages();
    const assignedNames: string[] = [];

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      expect(info!.name).not.toBeNull();
      expect(PLAYER_NAMES).toContain(info!.name);
      assignedNames.push(info!.name!);
    }

    // All 9 names should be unique (each player gets a different name)
    const uniqueNames = new Set(assignedNames);
    expect(uniqueNames.size).toBe(PLAYER_COUNT);
  });

  test('each player has original_group A, B, or C', async () => {
    const pages = pm.getPages();
    const groupCounts: Record<string, number> = {};

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      expect(info!.originalGroup).not.toBeNull();
      expect(GROUP_NAMES).toContain(info!.originalGroup);

      const group = info!.originalGroup!;
      groupCounts[group] = (groupCounts[group] || 0) + 1;
    }

    // Should have exactly 3 groups of 3
    expect(Object.keys(groupCounts).length).toBe(3);
    for (const [group, count] of Object.entries(groupCounts)) {
      expect(count, `Group ${group} should have 3 players`).toBe(3);
    }
  });

  test('current_group matches original_group in Phase 1', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      expect(info!.phase).toBe(1);
      expect(info!.currentGroup).toBe(info!.originalGroup);
    }
  });

  test('data attributes are present on the game container', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const container = page.locator('[data-testid="game-container"]');
      await expect(container).toBeVisible();

      // Verify game-level data attributes exist and are valid
      const phase = await container.getAttribute('data-game-phase');
      expect(phase).not.toBeNull();
      expect(parseInt(phase!, 10)).toBeGreaterThanOrEqual(1);

      const block = await container.getAttribute('data-game-block');
      expect(block).not.toBeNull();

      const round = await container.getAttribute('data-game-round');
      expect(round).not.toBeNull();

      const stageName = await container.getAttribute('data-stage-name');
      expect(stageName).not.toBeNull();
      expect(stageName).not.toBe('unknown');

      const condition = await container.getAttribute('data-condition');
      expect(condition).toBe('exp1_refer_separated');

      const playerGroup = await container.getAttribute('data-player-group');
      expect(playerGroup).not.toBeNull();
      expect(GROUP_NAMES).toContain(playerGroup);
    }
  });
});
