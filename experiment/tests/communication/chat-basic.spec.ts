import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  speakerSendMessage,
  getActivePlayers,
  waitForStage,
} from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';
import { CHAT_TEXTBOX } from '../helpers/selectors';

// TEST_PLAN 2.1-2.3: Basic chat communication tests in refer_separated
test.describe.serial('Communication: basic chat in refer_separated', { tag: '@smoke' }, () => {
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

  test('2.1: speaker sends message and it appears for all group members', async () => {
    const pages = pm.getPages();
    const groups = await pm.getPagesByGroup();

    // Pick the first group
    const groupName = Object.keys(groups)[0];
    const groupPages = groups[groupName];
    expect(groupPages.length).toBe(3);

    // Find the speaker in this group
    let speakerPage = null;
    const listenerPages = [];
    for (const page of groupPages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        speakerPage = page;
      } else if (info?.role === 'listener') {
        listenerPages.push(page);
      }
    }
    expect(speakerPage).not.toBeNull();
    expect(listenerPages.length).toBe(2);

    // Verify speaker is on Selection stage (chat should be visible)
    const speakerInfo = await getPlayerInfo(speakerPage!);
    expect(speakerInfo?.stageName).toBe('Selection');

    // Speaker sends a test message
    const testMessage = 'the one that looks like a person dancing';
    const sent = await speakerSendMessage(speakerPage!, testMessage);
    expect(sent).toBe(true);

    // Wait for message to propagate
    await speakerPage!.waitForTimeout(1000);

    // Verify message appears in speaker's own chat
    await expect(speakerPage!.getByText(testMessage)).toBeVisible({ timeout: 5_000 });

    // Verify message appears for each listener in the group
    for (const listenerPage of listenerPages) {
      await expect(listenerPage.getByText(testMessage)).toBeVisible({ timeout: 5_000 });
    }
  });

  test('2.2: messages show role labels (Speaker) and (Listener)', async () => {
    const pages = pm.getPages();
    const groups = await pm.getPagesByGroup();

    // Use the same first group
    const groupName = Object.keys(groups)[0];
    const groupPages = groups[groupName];

    // Find speaker and a listener
    let speakerPage = null;
    let listenerPage = null;
    for (const page of groupPages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') speakerPage = page;
      else if (info?.role === 'listener' && !listenerPage) listenerPage = page;
    }
    expect(speakerPage).not.toBeNull();
    expect(listenerPage).not.toBeNull();

    // Wait briefly for chat rendering to settle
    await listenerPage!.waitForTimeout(500);

    // The speaker's message from the previous test should show "(Speaker)" label.
    // The Chat component renders sender names as "Name (Speaker)" or "Name (Listener)".
    // Use .first() since multiple messages from the speaker may exist.
    await expect(listenerPage!.getByText('(Speaker)').first()).toBeVisible({ timeout: 10_000 });

    // Now have the listener send a message so we can verify "(Listener)" label
    const listenerChatbox = listenerPage!.getByRole(CHAT_TEXTBOX.role, { name: CHAT_TEXTBOX.name });
    await expect(listenerChatbox, 'listeners can chat during Selection').toBeVisible({ timeout: 10_000 });
    await listenerChatbox.fill('which one do you mean?');
    await listenerChatbox.press('Enter');

    // Verify the listener message shows "(Listener)" label in the speaker's chat
    await expect(speakerPage!.getByText('(Listener)').first()).toBeVisible({ timeout: 10_000 });
    await expect(speakerPage!.getByText('which one do you mean?')).toBeVisible({ timeout: 10_000 });
  });

  test('2.3: chat input is available during Selection stage', async () => {
    const pages = pm.getPages();
    const active = await getActivePlayers(pages);

    // No group has fully responded yet (listeners have not clicked), so the chat
    // must be available to every player who is in Selection.
    let checked = 0;
    for (const page of active) {
      const info = await getPlayerInfo(page);
      if (info?.stageName !== 'Selection') continue;
      const chatbox = page.getByRole(CHAT_TEXTBOX.role, { name: CHAT_TEXTBOX.name });
      await expect(chatbox).toBeEnabled({ timeout: 10_000 });
      await chatbox.fill('test message');
      expect(await chatbox.inputValue()).toBe('test message');
      await chatbox.fill('');
      checked++;
      if (checked >= 3) break;
    }
    expect(checked, 'expected players in the Selection stage').toBeGreaterThan(0);
  });
});
