/**
 * Engagement log reaches the player scope.
 *
 * The counting rules (the 200-event cap, resize de-duplication) are unit
 * tested in `shared/engagement.test.js`; two hundred real tab switches is not
 * something an end-to-end test can do. What only a real browser can establish
 * is the part those tests cannot reach: that the listeners are bound to
 * genuine browser events, and that `player.append` works against a live
 * Empirica player scope.
 *
 * `data-engagement-count` on the game container is the observable. It is
 * updated only when a write returns without throwing, so a count that rises
 * is evidence the append itself succeeded, not merely that the handler ran.
 *
 * Counts are asserted as increases from a baseline rather than as absolute
 * values, because a browser may emit a visibility or resize event of its own
 * and an exact count would make the spec flaky.
 */
import { test, expect, Page } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';

/** Current value of the engagement counter on the game container. */
async function engagementCount(page: Page): Promise<number> {
  const raw = await page
    .getByTestId('game-container')
    .getAttribute('data-engagement-count');
  return Number(raw ?? 0);
}

/** Fake a tab switch: browsers do not let a test set document.hidden directly. */
async function setTabHidden(page: Page, hidden: boolean): Promise<void> {
  await page.evaluate((isHidden) => {
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      get: () => isHidden,
    });
    document.dispatchEvent(new Event('visibilitychange'));
  }, hidden);
}

test.describe.serial('Data Integrity: Engagement Log', () => {
  let pm: PlayerManager;
  let page: Page;

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

    page = pm.getPages()[0];
    await expect(page.getByTestId('game-container')).toBeVisible();
  });

  test('the counter starts from nothing', async () => {
    // Nothing has happened yet, so any count here would mean the log is
    // recording something it should not.
    expect(await engagementCount(page)).toBe(0);
  });

  test('switching away from the tab and back is recorded', async () => {
    const before = await engagementCount(page);

    await setTabHidden(page, true);
    await setTabHidden(page, false);

    // Two events: the hidden and the return. A rise proves player.append
    // accepted the write, since the counter only advances when it does.
    await expect
      .poll(() => engagementCount(page))
      .toBeGreaterThanOrEqual(before + 2);
  });

  test('resizing the window is recorded once the size settles', async () => {
    const before = await engagementCount(page);

    await page.setViewportSize({ width: 1024, height: 700 });

    // The handler is debounced, so the poll has to outlast RESIZE_DEBOUNCE_MS.
    await expect
      .poll(() => engagementCount(page), { timeout: 10_000 })
      .toBeGreaterThanOrEqual(before + 1);
  });

  test('an outage is written on reconnect, not while it is happening', async () => {
    const before = await engagementCount(page);

    // Last, because dropping the socket is the only step here that disturbs
    // the player's connection to the server.
    await page.context().setOffline(true);

    // Nothing is written yet, and that is deliberate: an append made while the
    // socket is down never reaches the server. An earlier version of this code
    // wrote immediately and the offline event was simply missing from the
    // export, leaving the start of the outage unknown.
    await page.waitForTimeout(1_000);
    expect(await engagementCount(page)).toBe(before);

    await page.context().setOffline(false);

    // Both the outage and the reconnection arrive together, once there is a
    // connection to carry them.
    await expect
      .poll(() => engagementCount(page), { timeout: 30_000 })
      .toBeGreaterThanOrEqual(before + 2);
  });

  test('the log belongs to the player it was recorded for', async () => {
    // A second player who did nothing must still be at zero: the events above
    // were written to one player's scope, not broadcast to the game.
    const other = pm.getPages()[1];
    expect(await engagementCount(other)).toBe(0);
  });
});
