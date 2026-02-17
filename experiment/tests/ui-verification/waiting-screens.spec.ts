import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  speakerSendMessage,
  listenerClickTangram,
} from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';

/**
 * TEST_PLAN 5.3: Waiting screens display correctly.
 *
 * After all group members respond, a waiting message should appear.
 * Sets up a 9-player game, has speaker send and listeners click,
 * then verifies that waiting text ("Waiting for" or "All players")
 * appears on screen.
 */
test.describe.serial('UI Verification: Waiting Screens (5.3)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('waiting message appears after speaker sends but before listeners respond', async () => {
    const pages = pm.getPages();

    // Ensure we are in Selection stage
    for (const page of pages) {
      await expectPlayerInGame(page);
    }

    // Find all speakers and send messages
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        await speakerSendMessage(page, 'test message for waiting');
      }
    }
    await pages[0].waitForTimeout(1000);

    // After speaker sends, speaker should see waiting text (waiting for listeners)
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker') {
        const bodyText = await page.textContent('body');
        // Speaker has responded (sent message), so they see a waiting message
        const hasWaiting = bodyText?.includes('Waiting for') ||
          bodyText?.includes('All players');
        expect(hasWaiting).toBe(true);
        break;
      }
    }
  });

  test('waiting message updates after all group members respond', async () => {
    const pages = pm.getPages();

    // Build group-target mapping from speakers
    const groupTargets: Record<string, number> = {};
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        groupTargets[info.currentGroup!] = info.targetIndex;
      }
    }

    // Have all listeners in ONE group click their tangrams
    // Pick the first group we find
    let targetGroup: string | null = null;
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.currentGroup) {
        targetGroup = info.currentGroup;
        break;
      }
    }
    expect(targetGroup).not.toBeNull();

    // Click tangrams for all listeners in the target group
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && info.currentGroup === targetGroup) {
        const targetIdx = groupTargets[targetGroup!] ?? 0;
        await listenerClickTangram(page, targetIdx);
      }
    }
    await pages[0].waitForTimeout(1000);

    // After all members in one group respond, they should see
    // "All players in group responded!" or "Waiting for members of other groups"
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.currentGroup === targetGroup) {
        const bodyText = await page.textContent('body');
        const hasAllResponded = bodyText?.includes('All players') ||
          bodyText?.includes('Waiting for');
        expect(hasAllResponded).toBe(true);
        break;
      }
    }
  });

  test('within-group waiting message shows for listeners who responded', async () => {
    const pages = pm.getPages();

    // Find a group where NOT all listeners have responded yet
    // (the groups other than the one we already completed above)
    const groupTargets: Record<string, number> = {};
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        groupTargets[info.currentGroup!] = info.targetIndex;
      }
    }

    // Find a group with listeners who haven't clicked yet
    let incompleteGroup: string | null = null;
    const listenerPages: { page: any; info: any }[] = [];
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.role === 'listener' && !info.stageName?.includes('Feedback')) {
        // Check if tangram was clicked
        const clicked = await page.evaluate(() => {
          const task = document.querySelector('.task');
          // If there is no selection highlight, the listener hasn't clicked
          return !!document.querySelector('.tangrams.grid .selected, .tangrams.grid [data-clicked]');
        });
        if (!clicked && info.currentGroup) {
          incompleteGroup = info.currentGroup;
          listenerPages.push({ page, info });
        }
      }
    }

    if (incompleteGroup && listenerPages.length > 0) {
      // Have just ONE listener in this group click
      const firstListener = listenerPages[0];
      const targetIdx = groupTargets[incompleteGroup] ?? 0;
      await listenerClickTangram(firstListener.page, targetIdx);
      await firstListener.page.waitForTimeout(1000);

      // This listener should see a waiting message for the remaining group members
      const bodyText = await firstListener.page.textContent('body');
      const hasWaiting = bodyText?.includes('Waiting for') ||
        bodyText?.includes('All players');
      expect(hasWaiting).toBe(true);
    }
  });
});
