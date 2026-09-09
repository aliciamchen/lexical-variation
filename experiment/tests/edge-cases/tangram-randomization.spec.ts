/**
 * TEST_PLAN 9.2-9.3: Tangram Randomization
 *
 * Verifies that:
 * - Tangram order is different per player (grid is shuffled individually)
 * - Not all players see the same target index for the same tangram
 *
 * Strategy:
 * - Set up a game and reach the first Selection round
 * - Read each player's tangram grid order by examining the DOM
 * - Read each player's target index
 * - Verify that not all players have identical grid orderings
 */
import { test, expect, Page } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  getActivePlayers,
  playRound,
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  PLAYER_COUNT,
  NUM_DISPLAY_TANGRAMS,
} from '../helpers/constants';
import { TANGRAM_ITEMS } from '../helpers/selectors';

test.describe.serial('Edge Case: Tangram Randomization (TEST_PLAN 9.2-9.3)', () => {
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

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('tangram grid order differs across players', async () => {
    const pages = pm.getPages();

    // Collect the tangram grid order for each player by reading the tangram
    // background-image CSS from the DOM. Tangrams are rendered as divs with
    // background: "url(tangram_X.svg)" style, NOT as <img> elements.
    const gridOrders: string[][] = [];

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (!info) continue;

      const order = await page.evaluate(() => {
        const tangrams = document.querySelectorAll('.tangrams.grid > div');
        const sources: string[] = [];
        tangrams.forEach(t => {
          const bg = (t as HTMLElement).style.background || (t as HTMLElement).style.backgroundImage;
          if (bg) {
            // Extract the tangram identifier from the URL, e.g., "url(tangram_3.svg)"
            const match = bg.match(/tangram_([\w-]+)/);
            sources.push(match ? match[1] : bg);
          }
        });
        return sources;
      });

      if (order.length > 0) {
        gridOrders.push(order);
      }
    }

    // We should have grid orders for all 9 players
    expect(gridOrders.length).toBe(PLAYER_COUNT);

    // Each player should see NUM_DISPLAY_TANGRAMS tangrams
    for (const order of gridOrders) {
      expect(order.length).toBe(NUM_DISPLAY_TANGRAMS);
    }

    // Verify that NOT all players have the exact same order
    const orderStrings = gridOrders.map(order => order.join('|'));
    const uniqueOrders = new Set(orderStrings);

    // With 9 players, it's extremely unlikely (essentially impossible)
    // that all have the same random order
    expect(
      uniqueOrders.size,
      'Expected different tangram grid orders across players',
    ).toBeGreaterThan(1);
  });

  // Grid order as the sequence of tangram ids the player sees
  async function gridOrder(page: Page): Promise<string[]> {
    return page.evaluate(() =>
      Array.from(document.querySelectorAll('.tangrams.grid > div')).map(
        (t) => (t as HTMLElement).dataset.tangramId ?? '',
      ),
    );
  }

  test('all group members share the round target, and each target index points at it in that player\'s own grid', async () => {
    const pages = pm.getPages();

    const perGroupTargets: Record<string, Set<string>> = {};
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      const target = await page.locator('.task').getAttribute('data-target');
      expect(target, 'the task exposes the round target').toMatch(/^page/);
      (perGroupTargets[info!.currentGroup!] ??= new Set()).add(target!);

      // data-target-index is the position of the target in THIS player's grid
      const order = await gridOrder(page);
      expect(order.length).toBe(NUM_DISPLAY_TANGRAMS);
      expect(info!.targetIndex).toBeGreaterThanOrEqual(0);
      expect(order[info!.targetIndex], `page's target index should point at ${target}`).toBe(target);
    }
    // Everyone in a group describes and selects the same tangram
    for (const [group, targets] of Object.entries(perGroupTargets)) {
      expect(targets.size, `group ${group} should share one target`).toBe(1);
    }
  });

  test('each player\'s grid order stays fixed from one round to the next', async () => {
    const pages = pm.getPages();
    const before = await Promise.all(pages.map((p) => gridOrder(p)));

    await playRound(pages);
    expect(await waitForStage(pages[0], 'Selection', 60_000), 'expected the next Selection stage').toBe(true);

    const after = await Promise.all(pages.map((p) => gridOrder(p)));
    for (let i = 0; i < pages.length; i++) {
      expect(after[i], `grid order of page ${i} changed between rounds`).toEqual(before[i]);
    }
  });

  test('tangram positions differ between players for same tangram image', async () => {
    const pages = pm.getPages();

    // For a more direct test of tangram randomization:
    // Get the position (index in grid) of each tangram by reading background-image CSS.
    // Tangrams use background: "url(tangram_X.svg)" style, NOT <img> elements.
    const tangramPositions: Record<string, number[]> = {};

    for (let playerIdx = 0; playerIdx < pages.length; playerIdx++) {
      const positions = await pages[playerIdx].evaluate(() => {
        const tangrams = document.querySelectorAll('.tangrams.grid > div');
        const posMap: Record<string, number> = {};
        tangrams.forEach((t, idx) => {
          const bg = (t as HTMLElement).style.background || (t as HTMLElement).style.backgroundImage;
          if (bg) {
            const match = bg.match(/tangram_([\w-]+)/);
            const tangramId = match ? `tangram_${match[1]}` : `unknown_${idx}`;
            posMap[tangramId] = idx;
          }
        });
        return posMap;
      });

      for (const [tangramId, position] of Object.entries(positions)) {
        if (!tangramPositions[tangramId]) tangramPositions[tangramId] = [];
        tangramPositions[tangramId].push(position);
      }
    }

    // For at least some tangram images, the positions should differ across players
    let anyDifferent = false;
    for (const [tangramId, positions] of Object.entries(tangramPositions)) {
      if (positions.length > 1) {
        const uniquePositions = new Set(positions);
        if (uniquePositions.size > 1) {
          anyDifferent = true;
          break;
        }
      }
    }

    expect(
      anyDifferent,
      'Expected at least some tangram images to appear at different positions for different players',
    ).toBe(true);
  });
});
