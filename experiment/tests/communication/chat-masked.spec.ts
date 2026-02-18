import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playBlock,
  handleTransition,
  speakerSendMessage,
  getActivePlayers,
  waitForStage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
  expectCondition,
  expectIdentityMasked,
} from '../helpers/assertions';
import {
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  PLAYER_NAMES,
} from '../helpers/constants';
import { CHAT_TEXTBOX, PLAYER_GROUP_DISPLAY } from '../helpers/selectors';

// TEST_PLAN 2.4: Chat in Phase 2 mixed conditions shows masked identities
test.describe.serial('Communication: chat with masked identities in refer_mixed', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_mixed');
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

    await expectCondition(pm.getPage(0), 'refer_mixed');
  });

  test('complete Phase 1', async () => {
    test.slow(); // Phase 1 is 18 rounds, takes several minutes
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      await playBlock(pages, ROUNDS_PER_BLOCK);
    }

    // Verify all players are still active
    const active = await getActivePlayers(pages);
    expect(active.length).toBe(9);
  });

  test('transition to Phase 2', async () => {
    const pages = pm.getPages();
    await pages[0].waitForTimeout(2000);
    await handleTransition(pages);
  });

  test('2.4: chat messages show masked identities in Phase 2', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // Wait for Phase 2 Selection stage so .task element is rendered
    await waitForStage(active[0], 'Selection', 120_000);

    // Verify we are in Phase 2
    const firstInfo = await getPlayerInfo(active[0]);
    expect(firstInfo?.phase).toBe(2);

    // Verify identity masking is active via the assertion helper
    for (const page of active) {
      await expectIdentityMasked(page);
    }

    // Find a speaker in any group and send a message
    let speakerPage = null;
    const listenerPages: typeof active = [];

    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && !speakerPage) {
        speakerPage = page;
      }
    }
    expect(speakerPage).not.toBeNull();

    const speakerInfo = await getPlayerInfo(speakerPage!);
    const speakerGroup = speakerInfo!.currentGroup;

    // Find listeners in the same group as the speaker
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.currentGroup === speakerGroup) {
        listenerPages.push(page);
      }
    }
    expect(listenerPages.length).toBeGreaterThan(0);

    // Speaker sends a message
    const testMessage = 'the figure with arms stretched out';
    const sent = await speakerSendMessage(speakerPage!, testMessage);
    expect(sent).toBe(true);
    await speakerPage!.waitForTimeout(1000);

    // Check that the chat message appears with masked name "Player (Speaker)"
    // instead of a real name like "Repi (Speaker)"
    for (const listenerPage of listenerPages) {
      const chatArea = listenerPage.locator('.h-full.overflow-auto');
      await expect(chatArea.getByText(testMessage)).toBeVisible({ timeout: 5_000 });

      // The sender name in chat should be "Player (Speaker)", not a real name
      // Use .first() since there may be multiple messages from the speaker
      await expect(chatArea.getByText('Player (Speaker)').first()).toBeVisible({ timeout: 5_000 });

      // Verify that no real player names appear in the chat message sender area
      const chatText = await chatArea.textContent();
      for (const name of PLAYER_NAMES) {
        // Real names should not appear as chat sender labels
        // (They might appear as the current player's own profile name, but not in chat)
        expect(chatText).not.toContain(`${name} (Speaker)`);
        expect(chatText).not.toContain(`${name} (Listener)`);
      }
    }

    // Also have a listener send a message and verify it shows "Player (Listener)"
    const listenerChatbox = listenerPages[0].getByRole(CHAT_TEXTBOX.role, { name: CHAT_TEXTBOX.name });
    if (await listenerChatbox.count() > 0) {
      await listenerChatbox.fill('the tall one?');
      await listenerChatbox.press('Enter');
      await listenerPages[0].waitForTimeout(1000);

      // Verify on the speaker's chat that it shows "Player (Listener)"
      const speakerChatArea = speakerPage!.locator('.h-full.overflow-auto');
      await expect(speakerChatArea.getByText('the tall one?')).toBeVisible({ timeout: 5_000 });
      await expect(speakerChatArea.getByText('Player (Listener)').first()).toBeVisible({ timeout: 5_000 });
    }

    // Check the player-group display area for masked identities
    for (const page of active) {
      const playerGroupDisplay = page.locator(PLAYER_GROUP_DISPLAY);
      if (await playerGroupDisplay.count() > 0) {
        const groupText = await playerGroupDisplay.textContent();
        // In Phase 2 mixed conditions, other players should show as "Player"
        expect(groupText).toContain('Player');
      }
    }
  });
});
