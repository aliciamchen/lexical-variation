/**
 * TEST_PLAN 7.5: Overall Game Data Attributes
 *
 * Goal: Verify that the game container has all expected data attributes
 * (condition, phase, block, round, stage) and that they contain correct,
 * non-placeholder values when the game is active.
 *
 * Strategy:
 * - Set up a full game with 9 players.
 * - Once the game starts, inspect the game container on each player's page.
 * - Verify all expected data attributes are present.
 * - Verify values are not "unknown", "0" (for phase), or other invalid defaults.
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
  CONDITIONS,
  GROUP_NAMES,
  NUM_TANGRAMS,
} from '../helpers/constants';

test.describe.serial('Data Integrity: Game Data (TEST_PLAN 7.5)', () => {
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

  test('game container has all required data attributes', async () => {
    const pages = pm.getPages();

    for (let i = 0; i < pages.length; i++) {
      const page = pages[i];
      const container = page.locator('[data-testid="game-container"]');
      await expect(container).toBeVisible();

      // Verify each expected attribute exists
      const attrs = await page.evaluate(() => {
        const el = document.querySelector('[data-testid="game-container"]');
        if (!el) return null;
        return {
          phase: el.getAttribute('data-game-phase'),
          block: el.getAttribute('data-game-block'),
          round: el.getAttribute('data-game-round'),
          stageName: el.getAttribute('data-stage-name'),
          condition: el.getAttribute('data-condition'),
          playerGroup: el.getAttribute('data-player-group'),
        };
      });

      expect(attrs, `Player ${i} should have game container attributes`).not.toBeNull();

      // All attributes should be present (not null)
      expect(attrs!.phase, `Player ${i}: data-game-phase should exist`).not.toBeNull();
      expect(attrs!.block, `Player ${i}: data-game-block should exist`).not.toBeNull();
      expect(attrs!.round, `Player ${i}: data-game-round should exist`).not.toBeNull();
      expect(attrs!.stageName, `Player ${i}: data-stage-name should exist`).not.toBeNull();
      expect(attrs!.condition, `Player ${i}: data-condition should exist`).not.toBeNull();
      expect(attrs!.playerGroup, `Player ${i}: data-player-group should exist`).not.toBeNull();
    }
  });

  test('condition attribute is a valid condition string', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const condition = await page.locator('[data-testid="game-container"]')
        .getAttribute('data-condition');
      expect(condition).not.toBe('unknown');
      expect(CONDITIONS).toContain(condition);
      // For this test we specifically used refer_separated
      expect(condition).toBe('refer_separated');
    }
  });

  test('phase attribute is not "0" when game is active', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const phase = await page.locator('[data-testid="game-container"]')
        .getAttribute('data-game-phase');
      expect(phase).not.toBe('0');
      const phaseNum = parseInt(phase!, 10);
      expect(phaseNum).toBeGreaterThanOrEqual(1);
      expect(phaseNum).toBeLessThanOrEqual(2);
    }
  });

  test('block attribute is a valid non-negative number', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const block = await page.locator('[data-testid="game-container"]')
        .getAttribute('data-game-block');
      const blockNum = parseInt(block!, 10);
      expect(blockNum).toBeGreaterThanOrEqual(0);
    }
  });

  test('round attribute (target_num) is within valid range 0 to NUM_TANGRAMS-1', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const round = await page.locator('[data-testid="game-container"]')
        .getAttribute('data-game-round');
      const roundNum = parseInt(round!, 10);
      expect(roundNum).toBeGreaterThanOrEqual(0);
      expect(roundNum).toBeLessThan(NUM_TANGRAMS);
    }
  });

  test('stage-name attribute is a valid stage name, not "unknown"', async () => {
    const pages = pm.getPages();
    const validStageNames = ['Selection', 'Feedback', 'Phase 2 transition', 'Bonus info'];

    for (const page of pages) {
      const stageName = await page.locator('[data-testid="game-container"]')
        .getAttribute('data-stage-name');
      expect(stageName).not.toBe('unknown');
      expect(validStageNames).toContain(stageName);
    }
  });

  test('player-group attribute is a valid group name', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const group = await page.locator('[data-testid="game-container"]')
        .getAttribute('data-player-group');
      expect(group).not.toBe('unknown');
      expect(GROUP_NAMES).toContain(group);
    }
  });

  test('data attributes are consistent via getPlayerInfo helper', async () => {
    const pages = pm.getPages();

    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      expect(info, `Player ${i} should have player info`).not.toBeNull();

      // Verify consistency between getPlayerInfo and raw attributes
      const container = pages[i].locator('[data-testid="game-container"]');
      const rawPhase = await container.getAttribute('data-game-phase');
      const rawBlock = await container.getAttribute('data-game-block');
      const rawStage = await container.getAttribute('data-stage-name');
      const rawCondition = await container.getAttribute('data-condition');

      expect(info!.phase).toBe(parseInt(rawPhase!, 10));
      expect(info!.block).toBe(parseInt(rawBlock!, 10));
      expect(info!.stageName).toBe(rawStage);
      expect(info!.condition).toBe(rawCondition);
    }
  });
});
