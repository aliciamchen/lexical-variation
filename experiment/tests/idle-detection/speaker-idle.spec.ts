import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  playBlock,
  waitForGameStart,
  getActivePlayers,
  getRemovedPlayers,
  waitForExitScreen,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectPlayerOnExitScreen,
} from '../helpers/assertions';
import {
  MAX_IDLE_ROUNDS,
  ROUNDS_PER_BLOCK,
} from '../helpers/constants';

/**
 * TEST_PLAN 3.1: Speaker Idle Detection
 *
 * A speaker who does not send any chat messages for MAX_IDLE_ROUNDS consecutive
 * rounds should be kicked from the game. The kicked player sees the sorry screen
 * with exit_reason="player timeout" and prolific_code="none". The remaining
 * players in the group continue playing.
 *
 * Strategy:
 * - Identify which player page index is the speaker in a given group.
 * - Use `skipIndices` in playRound to prevent that speaker from acting.
 * - After MAX_IDLE_ROUNDS rounds of idleness, verify the speaker is removed.
 * - Verify remaining players are still in the game.
 */
test.describe.serial('Idle Detection: Speaker Idle (TEST_PLAN 3.1)', () => {
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

  test(`speaker is kicked after ${MAX_IDLE_ROUNDS} idle rounds`, async () => {
    const pages = pm.getPages();

    // Identify a speaker to make idle. Find the first player who is a speaker.
    let idleSpeakerIndex = -1;
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'speaker') {
        idleSpeakerIndex = i;
        break;
      }
    }
    expect(idleSpeakerIndex).toBeGreaterThanOrEqual(0);

    const idleSpeakerPage = pages[idleSpeakerIndex];
    const speakerInfo = await getPlayerInfo(idleSpeakerPage);
    const speakerGroup = speakerInfo!.originalGroup;

    // Play MAX_IDLE_ROUNDS rounds with the speaker skipped (idle).
    // The speaker will not send any message each round.
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [idleSpeakerIndex] });
    }

    // Wait for the idle speaker to be removed and see the sorry screen
    const exitInfo = await waitForExitScreen(idleSpeakerPage, 60_000);
    expect(exitInfo).not.toBeNull();
    expect(exitInfo!.type).toBe('sorry');
    expect(exitInfo!.exitReason).toBe('player timeout');
    expect(exitInfo!.prolificCode).toBe('none');
  });

  test('remaining players are still in the game', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // One player was kicked, so 8 should remain
    expect(active.length).toBe(8);

    for (const page of active) {
      await expectPlayerInGame(page);
    }
  });

  test('exactly one player was removed with correct exit info', async () => {
    const pages = pm.getPages();
    const removed = await getRemovedPlayers(pages);

    expect(removed.length).toBe(1);
    expect(removed[0].info.exitReason).toBe('player timeout');
    expect(removed[0].info.prolificCode).toBe('none');
  });
});
