import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  waitForGameStart,
  getActivePlayers,
  getRemovedPlayers,
  waitForExitScreen,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';
import {
  MAX_IDLE_ROUNDS,
  ROUNDS_PER_BLOCK,
} from '../helpers/constants';

/**
 * TEST_PLAN 3.3: Listeners NOT Kicked When Speaker Idles
 *
 * When a speaker does not send any message, listeners cannot act (tangrams are
 * disabled until the speaker sends). In this case, listeners' idle_rounds should
 * NOT increment -- it is not their fault the speaker was idle.
 *
 * Strategy:
 * - Identify a speaker and the listeners in the same group.
 * - Skip the speaker AND the listeners in that group each round (simulating
 *   the speaker not sending, which means listeners can't click).
 * - After MAX_IDLE_ROUNDS rounds, the speaker should be kicked but the
 *   listeners should remain in the game.
 * - Continue for additional rounds to confirm listeners are never kicked
 *   as long as the idle rounds don't accumulate.
 */
test.describe.serial('Idle Detection: Listener Not Kicked When Speaker Idles (TEST_PLAN 3.3)', () => {
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

  test('speaker is kicked but listeners in same group are NOT kicked', async () => {
    const pages = pm.getPages();

    // Find a speaker and identify all group members (speaker + listeners)
    let speakerIndex = -1;
    let speakerGroup: string | null = null;

    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'speaker') {
        speakerIndex = i;
        speakerGroup = info.originalGroup;
        break;
      }
    }
    expect(speakerIndex).toBeGreaterThanOrEqual(0);
    expect(speakerGroup).not.toBeNull();

    // Find the listener indices in the same group as the speaker
    const groupListenerIndices: number[] = [];
    for (let i = 0; i < pages.length; i++) {
      if (i === speakerIndex) continue;
      const info = await getPlayerInfo(pages[i]);
      if (info?.originalGroup === speakerGroup && info?.role === 'listener') {
        groupListenerIndices.push(i);
      }
    }
    expect(groupListenerIndices.length).toBeGreaterThanOrEqual(1);

    // Skip the entire group: speaker doesn't send, listeners can't click.
    // This simulates the speaker being idle, meaning listeners are blocked.
    const groupSkipIndices = [speakerIndex, ...groupListenerIndices];

    // Play MAX_IDLE_ROUNDS rounds with the whole group skipped.
    // The speaker accumulates idle rounds, but listeners should NOT.
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: groupSkipIndices });
    }

    // Wait for the speaker to be removed
    const speakerPage = pages[speakerIndex];
    const speakerExit = await waitForExitScreen(speakerPage, 60_000);
    expect(speakerExit).not.toBeNull();
    expect(speakerExit!.exitReason).toBe('player timeout');

    // Verify listeners in the same group are still active and in the game
    for (const listenerIdx of groupListenerIndices) {
      const listenerPage = pages[listenerIdx];
      // The listener should still be in the game, NOT on an exit screen
      const listenerInfo = await getPlayerInfo(listenerPage);
      // listenerInfo could be null if game ended, but the listener should not
      // have been kicked for idleness. Check they are not on sorry screen
      // with "player timeout".
      const exitInfo = await waitForExitScreen(listenerPage, 5_000);
      if (exitInfo) {
        // If listener ended up on exit screen, it should NOT be "player timeout"
        expect(exitInfo.exitReason).not.toBe('player timeout');
      } else {
        // Listener is still in the game -- this is the expected outcome
        await expectPlayerInGame(listenerPage);
      }
    }
  });

  test('only the speaker was removed for player timeout', async () => {
    const pages = pm.getPages();
    const removed = await getRemovedPlayers(pages);

    // Filter for those removed specifically for "player timeout"
    const timedOut = removed.filter(r => r.info.exitReason === 'player timeout');
    expect(timedOut.length).toBe(1);
  });

  test('listeners from speaker group remain active after additional rounds', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Game should still have active players. If the group was disbanded
    // (only 1 listener left after speaker kicked from group of 3 -> 2 remain,
    // which is >= MIN_GROUP_SIZE=2), game continues. Play a few more rounds
    // to confirm listeners are not at risk of being kicked.
    if (active.length >= 2) {
      // Play 2 more rounds normally with all active players participating
      for (let r = 0; r < 2; r++) {
        await playRound(active);
      }

      // Verify no additional players were kicked for timeout
      const removed = await getRemovedPlayers(pages);
      const timedOut = removed.filter(r => r.info.exitReason === 'player timeout');
      expect(timedOut.length).toBe(1); // Still only the original speaker
    }
  });
});
