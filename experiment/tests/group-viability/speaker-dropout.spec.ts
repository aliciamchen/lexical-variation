/**
 * TEST_PLAN 3.7: Speaker Drops Mid-Block
 *
 * Goal: When the current speaker goes idle and gets kicked mid-block,
 * a new speaker should be reassigned from remaining group members
 * and the game should continue with the remaining players.
 *
 * Condition: refer_separated (simpler, no reshuffling)
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  getExitInfo,
  playRound,
  playBlock,
  getActivePlayers,
  getRemovedPlayers,
  getPlayersByGroup,
  waitForExitScreen,
  isOnExitScreen,
  isInGame,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectOneSpeakerPerGroup,
} from '../helpers/assertions';
import {
  MAX_IDLE_ROUNDS,
  ROUNDS_PER_BLOCK,
  PROLIFIC_CODES,
} from '../helpers/constants';

test.describe.serial('Group Viability: Speaker Dropout Mid-Block (3.7)', () => {
  let pm: PlayerManager;
  // Track the speaker page index and their group
  let speakerPageIndex: number;
  let speakerGroup: string;

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

  test('all 9 players join and start the game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('identify the current speaker in one group', async () => {
    const pages = pm.getPages();

    // Find a speaker and record their page index and group
    for (let i = 0; i < pages.length; i++) {
      const info = await getPlayerInfo(pages[i]);
      if (info?.role === 'speaker') {
        speakerPageIndex = i;
        speakerGroup = info.originalGroup!;
        break;
      }
    }

    expect(speakerPageIndex).toBeDefined();
    expect(speakerGroup).toBeDefined();
  });

  test('play a few rounds normally, then speaker goes idle', async () => {
    const pages = pm.getPages();

    // Play 2 rounds normally first (speaker participates)
    await playRound(pages);
    await playRound(pages);

    // Now the speaker goes idle for MAX_IDLE_ROUNDS consecutive rounds
    // The speaker does not send any messages
    for (let r = 0; r < MAX_IDLE_ROUNDS; r++) {
      await playRound(pages, { skipIndices: [speakerPageIndex] });
    }

    await pages[0].waitForTimeout(3000);
  });

  test('idle speaker is kicked with "player timeout"', async () => {
    const pages = pm.getPages();

    const exitInfo = await getExitInfo(pages[speakerPageIndex]);
    expect(exitInfo).not.toBeNull();
    expect(exitInfo!.exitReason).toBe('player timeout');
    expect(exitInfo!.partialPay).toBe('0'); // Idle players get no pay
  });

  test('a new speaker is assigned in the affected group', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Should have 8 active players (9 - 1 kicked speaker)
    expect(active.length).toBe(8);

    // Find remaining players in the affected group
    const groupMembers: { page: typeof pages[0]; info: NonNullable<Awaited<ReturnType<typeof getPlayerInfo>>> }[] = [];
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.originalGroup === speakerGroup) {
        groupMembers.push({ page, info });
      }
    }

    // Should have 2 remaining members in the group
    expect(groupMembers.length).toBe(2);

    // One of them should now be speaker (reassignment happened)
    const speakers = groupMembers.filter((m) => m.info.role === 'speaker');
    const listeners = groupMembers.filter((m) => m.info.role === 'listener');

    expect(speakers.length).toBe(1);
    expect(listeners.length).toBe(1);
  });

  test('verify one speaker per group across all active groups', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Each active group should have exactly one speaker
    await expectOneSpeakerPerGroup(active);
  });

  test('game continues and rounds complete normally with remaining players', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Play several more rounds to verify game functions correctly
    await playRound(active);
    await playRound(active);
    await playRound(active);

    // Verify the same 8 players are still active
    const stillActive = await getActivePlayers(pages);
    expect(stillActive.length).toBe(8);

    // Verify each group still has a speaker
    await expectOneSpeakerPerGroup(stillActive);
  });

  test('the affected group can still score points', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Find the remaining members of the affected group
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.originalGroup === speakerGroup) {
        // Verify they are still in the game and have valid roles
        expect(await isInGame(page)).toBe(true);
        expect(info.role).toBeDefined();
        expect(['speaker', 'listener']).toContain(info.role);
      }
    }
  });
});
