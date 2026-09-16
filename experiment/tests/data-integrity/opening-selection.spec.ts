/**
 * TEST_PLAN 7.1 + 7.5 + 7.3: Player, game, and chat data in the opening round.
 *
 * All three suites observe the same opening Phase 1 / Block 0 / Round 0
 * Selection stage of a refer_separated game, so they share one 9-player game
 * instead of setting up three. Setting up a game is by far the slowest part
 * of the suite, so this is where group 3's runtime goes.
 *
 * Order matters. The 7.1 and 7.5 checks are read-only (they inspect the
 * pristine Selection stage) and run first; the 7.3 checks then have a speaker
 * send one message. That mutation stays inside the same Selection stage --
 * nobody clicks a tangram, so the round never completes -- and no later
 * assertion sees a different block, phase, or score.
 *
 * Adding a suite here is only safe if it observes this same stage and leaves
 * it in place. A suite that plays a round to completion (round-data,
 * refer-scores) or needs another condition (social-data) keeps its own game.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import { getPlayerInfo, speakerSendMessage } from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';
import {
  CONDITIONS,
  GROUP_NAMES,
  NUM_TANGRAMS,
  PLAYER_COUNT,
  PLAYER_NAMES,
} from '../helpers/constants';

const GAME_CONTAINER = '[data-testid="game-container"]';

test.describe.serial('Data Integrity: Opening Selection (7.1, 7.5, 7.3)', () => {
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

  // ── 7.1: Player data attributes are consistent ────────────────────────────

  test('each player has a valid name from PLAYER_NAMES', async () => {
    const assignedNames: string[] = [];

    for (const page of pm.getPages()) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      expect(info!.name).not.toBeNull();
      expect(PLAYER_NAMES).toContain(info!.name);
      assignedNames.push(info!.name!);
    }

    // All 9 names should be unique (each player gets a different name)
    expect(new Set(assignedNames).size).toBe(PLAYER_COUNT);
  });

  test('each player has original_group A, B, or C', async () => {
    const groupCounts: Record<string, number> = {};

    for (const page of pm.getPages()) {
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
    for (const page of pm.getPages()) {
      const info = await getPlayerInfo(page);
      expect(info).not.toBeNull();
      expect(info!.phase).toBe(1);
      expect(info!.currentGroup).toBe(info!.originalGroup);
    }
  });

  // ── 7.5: Overall game data attributes ─────────────────────────────────────

  test('game container has all required data attributes', async () => {
    const pages = pm.getPages();

    for (let i = 0; i < pages.length; i++) {
      const container = pages[i].locator(GAME_CONTAINER);
      await expect(container).toBeVisible();

      const attrs = await pages[i].evaluate((selector) => {
        const el = document.querySelector(selector);
        if (!el) return null;
        return {
          phase: el.getAttribute('data-game-phase'),
          block: el.getAttribute('data-game-block'),
          round: el.getAttribute('data-game-round'),
          stageName: el.getAttribute('data-stage-name'),
          condition: el.getAttribute('data-condition'),
          playerGroup: el.getAttribute('data-player-group'),
        };
      }, GAME_CONTAINER);

      expect(attrs, `Player ${i} should have game container attributes`).not.toBeNull();
      for (const [name, value] of Object.entries(attrs!)) {
        expect(value, `Player ${i}: ${name} should exist`).not.toBeNull();
      }
    }
  });

  test('condition attribute is a valid condition string', async () => {
    for (const page of pm.getPages()) {
      const condition = await page.locator(GAME_CONTAINER).getAttribute('data-condition');
      expect(condition).not.toBe('unknown');
      expect(CONDITIONS).toContain(condition);
      // This shared game is specifically refer_separated
      expect(condition).toBe('refer_separated');
    }
  });

  test('phase attribute is not "0" when game is active', async () => {
    for (const page of pm.getPages()) {
      const phase = await page.locator(GAME_CONTAINER).getAttribute('data-game-phase');
      expect(phase).not.toBe('0');
      const phaseNum = parseInt(phase!, 10);
      expect(phaseNum).toBeGreaterThanOrEqual(1);
      expect(phaseNum).toBeLessThanOrEqual(2);
    }
  });

  test('block attribute is a valid non-negative number', async () => {
    for (const page of pm.getPages()) {
      const block = await page.locator(GAME_CONTAINER).getAttribute('data-game-block');
      expect(parseInt(block!, 10)).toBeGreaterThanOrEqual(0);
    }
  });

  test('round attribute (target_num) is within valid range 0 to NUM_TANGRAMS-1', async () => {
    for (const page of pm.getPages()) {
      const round = await page.locator(GAME_CONTAINER).getAttribute('data-game-round');
      const roundNum = parseInt(round!, 10);
      expect(roundNum).toBeGreaterThanOrEqual(0);
      expect(roundNum).toBeLessThan(NUM_TANGRAMS);
    }
  });

  test('stage-name attribute is a valid stage name, not "unknown"', async () => {
    const validStageNames = ['Selection', 'Feedback', 'Phase 2 transition', 'Bonus info'];

    for (const page of pm.getPages()) {
      const stageName = await page.locator(GAME_CONTAINER).getAttribute('data-stage-name');
      expect(stageName).not.toBe('unknown');
      expect(validStageNames).toContain(stageName);
    }
  });

  test('player-group attribute is a valid group name', async () => {
    for (const page of pm.getPages()) {
      const group = await page.locator(GAME_CONTAINER).getAttribute('data-player-group');
      expect(group).not.toBe('unknown');
      expect(GROUP_NAMES).toContain(group);
    }
  });

  test('data attributes are consistent via getPlayerInfo helper', async () => {
    const pages = pm.getPages();

    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      expect(info, `Player ${i} should have player info`).not.toBeNull();

      const container = pages[i].locator(GAME_CONTAINER);
      expect(info!.phase).toBe(parseInt((await container.getAttribute('data-game-phase'))!, 10));
      expect(info!.block).toBe(parseInt((await container.getAttribute('data-game-block'))!, 10));
      expect(info!.stageName).toBe(await container.getAttribute('data-stage-name'));
      expect(info!.condition).toBe(await container.getAttribute('data-condition'));
    }
  });

  // ── 7.3: Chat messages are properly recorded ──────────────────────────────
  //
  // From here on a speaker has sent one message. The round is not completed:
  // no listener clicks, so the stage, block, and scores are untouched.

  const DISTINCTIVE_MESSAGE = 'UNIQUE_TEST_MESSAGE_12345';
  let speakerGroup: string;

  test('speaker sends message and all group members see it', async () => {
    const pages = pm.getPages();

    let speakerPage = null;
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        speakerPage = page;
        speakerGroup = info.currentGroup!;
        break;
      }
    }
    expect(speakerPage, 'a speaker should be assigned in the opening round').not.toBeNull();
    expect(speakerGroup).not.toBeUndefined();

    await speakerSendMessage(speakerPage!, DISTINCTIVE_MESSAGE);

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup !== speakerGroup) continue;
      await expect(
        page.getByText(DISTINCTIVE_MESSAGE),
        `Message should be visible for group member in group ${speakerGroup}`,
      ).toBeVisible();
    }
  });

  test('message does NOT appear for players in other groups', async () => {
    let checked = 0;

    for (const page of pm.getPages()) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup === speakerGroup) continue;
      const bodyText = await page.textContent('body');
      expect(
        bodyText,
        `Message should NOT appear for player in group ${info?.currentGroup}`,
      ).not.toContain(DISTINCTIVE_MESSAGE);
      checked++;
    }

    // Two other groups of three: the assertion above must actually have run
    expect(checked, 'players outside the speaker group should exist').toBe(6);
  });

  test('chat message includes role indicator for sender', async () => {
    let checked = 0;

    for (const page of pm.getPages()) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup !== speakerGroup || info?.role !== 'listener') continue;
      const bodyText = await page.textContent('body');
      // The chat should show "(Speaker)" role label for the sender
      expect(bodyText).toContain('(Speaker)');
      checked++;
    }

    expect(checked, 'the speaker group should have listeners').toBe(2);
  });
});
