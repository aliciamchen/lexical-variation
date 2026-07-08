import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playBlock,
  handleTransition,
  getActivePlayers,
  waitForStage,
  clickContinue,
  completeExitSurvey,
} from '../helpers/game-actions';
import {
  PHASE_1_BLOCKS,
  ROUNDS_PER_BLOCK,
  PHASE_2_BLOCKS,
  NUM_TANGRAMS,
  PROLIFIC_CODES,
} from '../helpers/constants';
import { EXIT_SURVEY } from '../helpers/selectors';

/**
 * TEST_PLAN 5.5 + 5.6: Phase transition screen and exit survey.
 *
 * These share one refer_separated game played to completion. The transition
 * screen (5.5) is a natural checkpoint midway through the playthrough the exit
 * survey (5.6) already requires, so both are verified in a single game instead
 * of two. Tests are ordered by game progression: Phase 1 → transition screen
 * checks → Phase 2 → exit survey checks.
 *
 * The exit survey is the revamped three-page flow in
 * client/src/intro-exit/ExitSurvey.jsx: page 1 required questions (understood,
 * groupIdentification, groupCloseness, groupLanguage, strategy) behind a "Next"
 * button, page 2 demographics (age, gender, feltHuman required; education,
 * fair, feedback optional) behind a "Submit" button, then a confirmation page
 * with the Prolific code and a "Finish" button. The Empirica player object is
 * not exposed to page context, so we verify that player.set("exitSurvey", ...)
 * captured every required field via the component's own gating: it only stores
 * the required fields and advances to page 2 once they are all set, and only
 * merges the demographics and shows the completion code once page 2's required
 * fields are set.
 */
test.describe.serial('UI Verification: Endgame — Transition & Exit Survey (5.5, 5.6)', () => {
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

  // ─────────────────────────────────────────────────────────────────────────
  // 5.5: Phase transition screen
  // ─────────────────────────────────────────────────────────────────────────

  test('(5.5) complete Phase 1 to reach transition', async () => {
    test.slow(); // Phase 1 is many rounds, takes several minutes
    const pages = pm.getPages();

    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      const active = await getActivePlayers(pages);
      await playBlock(active, ROUNDS_PER_BLOCK);
    }

    // Wait for transition stage to appear
    const reachedTransition = await waitForStage(pages[0], 'Phase 2 transition', 60_000);
    expect(reachedTransition).toBe(true);
  });

  test('(5.5) transition screen shows "End of Phase 1" text', async () => {
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

  test('(5.5) transition screen mentions Phase 2', async () => {
    const pages = pm.getPages();

    for (const page of pages) {
      const bodyText = await page.textContent('body');
      if (bodyText?.includes('End of Phase 1')) {
        expect(bodyText).toContain('Phase 2');
        break;
      }
    }
  });

  test('(5.5) refer_separated transition mentions "same group members"', async () => {
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

  test('(5.5) transition screen shows scoring reminder', async () => {
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

  test('(5.5) transition screen shows block count for Phase 2', async () => {
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

  test('(5.5) transition screen has Continue button', async () => {
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

  test('(5.5) clicking Continue advances past transition', async () => {
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

  // ─────────────────────────────────────────────────────────────────────────
  // 5.6: Exit survey (three-page flow)
  // ─────────────────────────────────────────────────────────────────────────

  test('(5.6) complete Phase 2 and reach the exit survey', async () => {
    test.slow(); // Phase 2 rounds + bonus info
    const pages = pm.getPages();

    // Phase 2
    for (let block = 0; block < PHASE_2_BLOCKS; block++) {
      const active = await getActivePlayers(pages);
      await playBlock(active, ROUNDS_PER_BLOCK);
    }

    // Click Continue to exit last Feedback stage
    for (const page of pages) {
      await clickContinue(page, 5000);
    }

    // Wait for Bonus info stage
    await waitForStage(pages[0], 'Bonus info', 120_000);

    // Click Continue on Bonus info for all players
    for (const page of pages) {
      await waitForStage(page, 'Bonus info', 30_000);
      await clickContinue(page, 5000);
    }

    // Wait for the exit survey to appear for player 0
    await expect(pm.getPage(0).locator(EXIT_SURVEY)).toBeVisible({ timeout: 30_000 });
  });

  test('(5.6) exit survey page 1 shows "Exit survey" heading', async () => {
    const page = pm.getPage(0);
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('Exit survey');
  });

  test('(5.6) exit survey shows bonus info but not completion code before submission', async () => {
    const page = pm.getPage(0);
    const bodyText = await page.textContent('body');

    // Should NOT show the Prolific completion code before submission
    expect(bodyText).not.toContain(PROLIFIC_CODES.completion);

    // Should show score and bonus in the header
    expect(bodyText).toContain('points');
    expect(bodyText).toContain('bonus');
  });

  test('(5.6) page 1 has all required fields', async () => {
    const page = pm.getPage(0);

    // Understanding yes/no radios
    await expect(page.locator('input[name="understood"]')).toHaveCount(2);
    // Group identification 7-point Likert
    await expect(page.locator('input[name="groupIdentification"]')).toHaveCount(7);
    // Group closeness 7-point Likert
    await expect(page.locator('input[name="groupCloseness"]')).toHaveCount(7);
    // Group language yes/no radios
    await expect(page.locator('input[name="groupLanguage"]')).toHaveCount(2);
    // Strategy free-text
    await expect(page.locator('textarea[name="strategy"]')).toBeVisible();
  });

  test('(5.6) page 1 "Next" gates on required fields and stores them on submit', async () => {
    const page = pm.getPage(0);
    const nextBtn = page.getByRole('button', { name: /^next$/i });

    // Disabled until every required field is set
    await expect(nextBtn).toBeDisabled();

    await page.locator('input[name="understood"][value="yes"]').click();
    await page.locator('input[name="groupIdentification"][value="5"]').click();
    await page.locator('input[name="groupCloseness"][value="5"]').click();
    await page.locator('input[name="groupLanguage"][value="yes"]').click();
    const strategy = page.locator('textarea[name="strategy"]');
    await strategy.fill('Describe distinctive features of each tangram');
    await strategy.dispatchEvent('input'); // ensure React onChange fires

    // With all required fields set, the Next button enables
    await expect(nextBtn).toBeEnabled();

    // Submitting page 1 is the only path that both stores the required fields
    // into player.get("exitSurvey") and advances to page 2. Reaching page 2
    // (age field visible) is the observable proof they were all captured.
    await nextBtn.click();
    await expect(page.locator('input[name="age"]')).toBeVisible({ timeout: 10_000 });
  });

  test('(5.6) page 2 has demographic fields', async () => {
    const page = pm.getPage(0);

    const ageInput = page.locator('input[name="age"]');
    await expect(ageInput).toBeVisible();
    expect(await ageInput.getAttribute('type')).toBe('number');

    await expect(page.locator('select[name="gender"]')).toBeVisible();
    // "Did you feel like you were playing with other humans?" yes/no (required)
    await expect(page.locator('input[name="feltHuman"]')).toHaveCount(2);
    // Education radios (optional)
    await expect(page.locator('input[name="education"]')).toHaveCount(4);
    // Optional free-text fields
    await expect(page.locator('textarea[name="fair"]')).toBeVisible();
    await expect(page.locator('textarea[name="feedback"]')).toBeVisible();
  });

  test('(5.6) page 2 "Submit" gates on required demographics and reaches confirmation', async () => {
    const page = pm.getPage(0);
    const submitBtn = page.getByRole('button', { name: /^submit$/i });

    // Disabled until age, gender, and feltHuman are set
    await expect(submitBtn).toBeDisabled();

    const ageInput = page.locator('input[name="age"]');
    await ageInput.fill('25');
    await ageInput.dispatchEvent('input'); // ensure React onChange fires
    await page.locator('select[name="gender"]').selectOption('prefer-not-to-say');
    await page.locator('input[name="feltHuman"][value="yes"]').click();
    // Optional fields
    await page.locator('input[name="education"][value="bachelor"]').click();
    await page.locator('textarea[name="fair"]').fill('Yes');
    await page.locator('textarea[name="feedback"]').fill('No issues');

    // With the required demographics set, Submit enables
    await expect(submitBtn).toBeEnabled();

    // Submitting merges the demographics into player.get("exitSurvey") and
    // advances to the confirmation page.
    await submitBtn.click();
  });

  test('(5.6) confirmation page shows completion code and Finish button after submission', async () => {
    const page = pm.getPage(0);

    // The Finish button marks the confirmation page (page 3)
    const finishBtn = page.getByRole('button', { name: /finish/i });
    await expect(finishBtn).toBeVisible({ timeout: 10_000 });

    // The Prolific completion code is now shown
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain(PROLIFIC_CODES.completion);

    // Click Finish to complete
    await finishBtn.click();

    // Complete the exit survey for the remaining players so the game finishes
    const pages = pm.getPages();
    for (let i = 1; i < pages.length; i++) {
      await completeExitSurvey(pages[i]);
    }
  });
});
