/**
 * Several players in one group send at the same instant.
 *
 * The group chat is a single shared stage attribute (`${group}_chat`). In
 * September it was deliberately changed from read-modify-write to Empirica's
 * atomic `append`, precisely so that two players sending simultaneously could
 * not lose a message. Nothing reproduced that condition: every other spec
 * awaits one send before starting the next, so nine players had never hit
 * Enter at once, and the fix's whole reason for existing was untested.
 *
 * A lost message here would be lost research data, and it would be invisible:
 * the game plays on, and nobody can tell from the transcript that a line is
 * missing. So this sends from every member of a group with Promise.all and
 * asserts that all of them survive, exactly once each, for every member.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import { getPlayerInfo, waitForStage } from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';
import { CHAT_TEXTBOX, CHAT_MESSAGES } from '../helpers/selectors';

test.describe.serial('Communication: simultaneous sends in one group', () => {
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
    expect(await pm.waitForGameStart()).toBe(true);
    for (const page of pm.getPages()) {
      await expectPlayerInGame(page);
    }
  });

  test('every message survives when a whole group sends at once', async () => {
    const pages = pm.getPages();
    await waitForStage(pages[0], 'Selection', 60_000);

    // One group, so every sender is writing to the same stage attribute.
    const group: { page: import('@playwright/test').Page; text: string }[] = [];
    for (const page of pages) {
      await waitForStage(page, 'Selection', 10_000);
      const info = await getPlayerInfo(page);
      if (info?.currentGroup === 'A') {
        // Distinct text per sender so a lost message is identifiable rather
        // than hidden by a duplicate that happens to look the same.
        group.push({ page, text: `simultaneous-${group.length}` });
      }
    }
    expect(group.length, 'expected a full group of three').toBe(3);

    // Fill every box first, so the only thing left to do is press Enter and
    // the presses land as close together as the browsers allow. Filling inside
    // Promise.all would serialize on typing rather than on the write.
    for (const { page, text } of group) {
      const box = page.getByRole(CHAT_TEXTBOX.role, { name: CHAT_TEXTBOX.name });
      await box.waitFor({ state: 'visible', timeout: 10_000 });
      await box.fill(text);
    }
    await Promise.all(
      group.map(({ page }) =>
        page.getByRole(CHAT_TEXTBOX.role, { name: CHAT_TEXTBOX.name }).press('Enter'),
      ),
    );

    // Every member must see every message, once each. Reading all three pages
    // also catches a message that reached the server but never came back to a
    // particular client.
    const expected = group.map((g) => g.text);
    for (const { page } of group) {
      await expect
        .poll(
          async () => {
            const text = (await page.locator(CHAT_MESSAGES).textContent()) ?? '';
            return expected.filter((t) => text.includes(t)).length;
          },
          {
            message: 'every simultaneous message should reach every group member',
            timeout: 20_000,
          },
        )
        .toBe(expected.length);

      const body = (await page.locator(CHAT_MESSAGES).textContent()) ?? '';
      for (const t of expected) {
        const occurrences = body.split(t).length - 1;
        expect(occurrences, `"${t}" should appear exactly once, not ${occurrences}`).toBe(1);
      }
    }
  });

  test('a rapid burst from one player keeps every message and its order', async () => {
    // The other way to contend for the same attribute: one player sending
    // faster than the round trip completes. Ordering is asserted because the
    // transcript is the unit of analysis, so a reordered conversation is a
    // corrupted one even when nothing is lost.
    const pages = pm.getPages();
    // Array.find cannot take an async predicate: the promise it returns is
    // always truthy, so the first page would always "match" and the group
    // filter would be a lie. Resolve the roles first.
    let page = pages[0];
    for (const candidate of pages) {
      const info = await getPlayerInfo(candidate);
      if (info?.currentGroup === 'A') {
        page = candidate;
        break;
      }
    }
    const box = page.getByRole(CHAT_TEXTBOX.role, { name: CHAT_TEXTBOX.name });
    if (!(await box.isVisible().catch(() => false))) {
      test.skip(true, 'chat closed for this player (group already responded)');
    }

    const burst = ['burst-one', 'burst-two', 'burst-three'];
    for (const text of burst) {
      await box.fill(text);
      await box.press('Enter');
    }

    await expect
      .poll(
        async () => {
          const body = (await page.locator(CHAT_MESSAGES).textContent()) ?? '';
          return burst.filter((t) => body.includes(t)).length;
        },
        { message: 'a burst should not drop messages', timeout: 20_000 },
      )
      .toBe(burst.length);

    const body = (await page.locator(CHAT_MESSAGES).textContent()) ?? '';
    const positions = burst.map((t) => body.indexOf(t));
    expect(positions, 'the burst should appear in the order it was sent').toEqual(
      [...positions].sort((a, b) => a - b),
    );
  });
});
