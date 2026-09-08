import { test, expect } from '@playwright/test';
import { createBatch } from '../helpers/admin';
import { PlayerManager } from '../helpers/player-manager';

/**
 * Tangram-set counterbalancing: the target set is a treatment factor. A batch
 * created with a "tangram set 1" treatment must run every player's game on
 * set 1, and all nine players must see the same round target (the per-block
 * target order is shared by the three groups).
 */
test.describe.serial('Edge case: tangram set treatment factor', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated_set1');
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

  test('every player is in a game using tangram set 1', async () => {
    for (const page of pm.getPages()) {
      const task = page.locator('.task');
      await expect(task).toHaveAttribute('data-tangram-set', '1', { timeout: 30_000 });
    }
  });

  test('all players share the same round target and it is a real tangram id', async () => {
    const targets = new Set<string>();
    for (const page of pm.getPages()) {
      const target = await page.locator('.task').getAttribute('data-target');
      expect(target).toMatch(/^page/);
      targets.add(target!);
    }
    expect(targets.size).toBe(1);
  });
});
