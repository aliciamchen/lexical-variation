import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playBlock,
  handleTransition,
  getActivePlayers,
} from '../helpers/game-actions';
import {
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  PHASE_2_BLOCKS,
  NUM_TANGRAMS,
} from '../helpers/constants';

/**
 * TEST_PLAN 5.5: Phase transition screen content.
 *
 * After Phase 1 completes, the transition screen should appear with
 * condition-specific text. We test refer_separated (primary) and verify
 * the transition includes key content like "End of Phase 1", "Phase 2",
 * and condition-specific instructions about same group.
 */
test.describe.serial('UI Verification: Transition Screens (5.5)', () => {
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

  test('complete Phase 1 to reach transition', async () => {
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      const active = await getActivePlayers(pages);
      await playBlock(active, ROUNDS_PER_BLOCK);
    }

    // Wait for transition stage to appear
    await pages[0].waitForTimeout(2000);
  });

  test('transition screen shows "End of Phase 1" text', async () => {
    const pages = pm.getPages();

    // At least one page should show the transition content
    let foundTransition = false;
    for (const page of pages) {
      const bodyText = await page.textContent('body');
      if (bodyText?.includes('End of Phase 1')) {
        foundTransition = true;
        break;
      }
    }
    expect(foundTransition).toBe(true);
  });

  test('transition screen mentions Phase 2', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const bodyText = await page.textContent('body');
      if (bodyText?.includes('End of Phase 1')) {
        expect(bodyText).toContain('Phase 2');
        break;
      }
    }
  });

  test('refer_separated transition mentions "same group members"', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const bodyText = await page.textContent('body');
      if (bodyText?.includes('End of Phase 1')) {
        // refer_separated should mention staying with the same group
        expect(bodyText).toContain('same group members');
        break;
      }
    }
  });

  test('transition screen shows scoring reminder', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const bodyText = await page.textContent('body');
      if (bodyText?.includes('End of Phase 1')) {
        // Scoring section should be present
        expect(bodyText).toContain('Scoring');
        expect(bodyText).toContain('points');
        break;
      }
    }
  });

  test('transition screen shows block count for Phase 2', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const bodyText = await page.textContent('body');
      if (bodyText?.includes('End of Phase 1')) {
        // Should mention the number of Phase 2 blocks
        expect(bodyText).toContain(`${PHASE_2_BLOCKS} blocks`);
        expect(bodyText).toContain(`${NUM_TANGRAMS} rounds`);
        break;
      }
    }
  });

  test('transition screen has Continue button', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const bodyText = await page.textContent('body');
      if (bodyText?.includes('End of Phase 1')) {
        const continueBtn = page.getByRole('button', { name: /continue/i });
        await expect(continueBtn).toBeVisible({ timeout: 5_000 });
        break;
      }
    }
  });

  test('clicking Continue advances past transition', async () => {
    const pages = pm.getPages();

    // Click Continue for all players
    await handleTransition(pages);

    // After transition, should be in Phase 2 Selection stage
    await pages[0].waitForTimeout(2000);

    let foundPhase2 = false;
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.phase === 2) {
        foundPhase2 = true;
        break;
      }
    }
    expect(foundPhase2).toBe(true);
  });
});
