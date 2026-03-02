/**
 * TEST_PLAN 7.3: Chat Messages Are Properly Recorded
 *
 * Goal: Verify that when a speaker sends a known message, it appears in
 * the chat area for all group members. Check message text content is
 * present on the page.
 *
 * Strategy:
 * - Set up a full game with 9 players.
 * - Identify a speaker in a specific group.
 * - Have the speaker send a distinctive message.
 * - Verify the message text appears on the page for all players in that group.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  speakerSendMessage,
} from '../helpers/game-actions';
import {
  expectPlayerInGame,
} from '../helpers/assertions';

test.describe.serial('Data Integrity: Chat Data (TEST_PLAN 7.3)', () => {
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

  test('speaker sends message and all group members see it', async () => {
    const pages = pm.getPages();
    const distinctiveMessage = 'UNIQUE_TEST_MESSAGE_12345';

    // Find a speaker and their group
    let speakerPage = null;
    let speakerGroup: string | null = null;

    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        speakerPage = page;
        speakerGroup = info.currentGroup;
        break;
      }
    }
    expect(speakerPage).not.toBeNull();
    expect(speakerGroup).not.toBeNull();

    // Send the distinctive message
    const sent = await speakerSendMessage(speakerPage!, distinctiveMessage);
    expect(sent).toBe(true);

    // Wait for the message to propagate
    await speakerPage!.waitForTimeout(2000);

    // Find all players in the same group
    const groupPages = [];
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup === speakerGroup) {
        groupPages.push(page);
      }
    }

    // Should have 3 players in the group
    expect(groupPages.length).toBe(3);

    // Verify the message appears on the page for all group members
    for (const page of groupPages) {
      const bodyText = await page.textContent('body');
      expect(
        bodyText,
        `Message should be visible for group member in group ${speakerGroup}`,
      ).toContain(distinctiveMessage);
    }
  });

  test('message does NOT appear for players in other groups', async () => {
    const pages = pm.getPages();
    const distinctiveMessage = 'UNIQUE_TEST_MESSAGE_12345';

    // Find the speaker's group
    let speakerGroup: string | null = null;
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        speakerGroup = info.currentGroup;
        break;
      }
    }
    expect(speakerGroup).not.toBeNull();

    // Check players in OTHER groups
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup !== speakerGroup) {
        const bodyText = await page.textContent('body');
        expect(
          bodyText,
          `Message should NOT appear for player in group ${info?.currentGroup}`,
        ).not.toContain(distinctiveMessage);
      }
    }
  });

  test('chat message includes role indicator for sender', async () => {
    const pages = pm.getPages();

    // Find a listener in the speaker's group who can see the chat
    let speakerGroup: string | null = null;
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        speakerGroup = info.currentGroup;
        break;
      }
    }

    // Check that a listener in the same group sees the role indicator
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup === speakerGroup && info?.role === 'listener') {
        const bodyText = await page.textContent('body');
        // The chat should show "(Speaker)" role label for the sender
        expect(bodyText).toContain('(Speaker)');
        break;
      }
    }
  });
});
