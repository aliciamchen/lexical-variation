import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  playBlock,
  handleTransition,
  clickContinue,
  getActivePlayers,
  waitForStage,
  completeExitSurvey,
} from '../helpers/game-actions';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
  PROLIFIC_CODES,
} from '../helpers/constants';

/**
 * TEST_PLAN 5.6: Exit survey has all required fields.
 *
 * Completes the full game to reach the exit survey, then verifies
 * the survey contains: age input, gender input, education radios,
 * understanding radios, group identification Likert scale, group language
 * textarea, fair textarea, feedback textarea, and submit button.
 */
test.describe.serial('UI Verification: Exit Survey (5.6)', () => {
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

  test('complete full game to reach exit survey', async () => {
    test.slow(); // Full game: Phase 1 (18 rounds) + transition + Phase 2 (12 rounds)
    const pages = pm.getPages();

    // Phase 1
    for (let block = 0; block < PHASE_1_BLOCKS; block++) {
      const active = await getActivePlayers(pages);
      await playBlock(active, ROUNDS_PER_BLOCK);
    }

    // Transition
    await pages[0].waitForTimeout(2000);
    await handleTransition(pages);

    // Wait for Phase 2 Selection to ensure transition completed
    await waitForStage(pages[0], 'Selection', 120_000);

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

    // Wait for exit survey to appear
    await pages[0].waitForTimeout(5000);
  });

  test('exit survey page shows "Exit Survey" heading', async () => {
    const page = pm.getPage(0);
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('Exit Survey');
  });

  test('exit survey shows bonus info but not completion code before submission', async () => {
    const page = pm.getPage(0);
    const bodyText = await page.textContent('body');

    // Should NOT show the Prolific completion code before submission
    expect(bodyText).not.toContain(PROLIFIC_CODES.completion);

    // Should show score and bonus
    expect(bodyText).toContain('points');
    expect(bodyText).toContain('bonus');
  });

  test('exit survey has age input field', async () => {
    const page = pm.getPage(0);
    const ageInput = page.locator('input[name="age"]');
    await expect(ageInput).toBeVisible({ timeout: 10_000 });
    expect(await ageInput.getAttribute('type')).toBe('number');
  });

  test('exit survey has gender dropdown', async () => {
    const page = pm.getPage(0);
    const genderSelect = page.locator('select[name="gender"]');
    await expect(genderSelect).toBeVisible({ timeout: 5_000 });
  });

  test('exit survey has education radio buttons', async () => {
    const page = pm.getPage(0);

    // Education radios
    const highSchool = page.getByRole('radio', { name: /high school/i });
    const bachelor = page.getByRole('radio', { name: /bachelor/i });
    const master = page.getByRole('radio', { name: /master/i });
    const other = page.getByRole('radio', { name: /other/i });

    await expect(highSchool).toBeVisible();
    await expect(bachelor).toBeVisible();
    await expect(master).toBeVisible();
    await expect(other).toBeVisible();
  });

  test('exit survey has understanding radio buttons', async () => {
    const page = pm.getPage(0);

    // "Did you understand the instructions?" radios
    const yesRadio = page.getByRole('radio', { name: /^yes$/i });
    const noRadio = page.getByRole('radio', { name: /^no$/i });

    await expect(yesRadio).toBeVisible();
    await expect(noRadio).toBeVisible();
  });

  test('exit survey has group identification Likert scale', async () => {
    const page = pm.getPage(0);
    // Should have 7 radio buttons for the Likert scale
    const radios = page.locator('input[name="groupIdentification"]');
    await expect(radios).toHaveCount(7);
  });

  test('exit survey has group language yes/no radios', async () => {
    const page = pm.getPage(0);
    const radios = page.locator('input[name="groupLanguage"]');
    await expect(radios).toHaveCount(2);
  });

  test('exit survey has strategy textarea', async () => {
    const page = pm.getPage(0);
    const strategyTextarea = page.locator('textarea[name="strategy"]');
    await expect(strategyTextarea).toBeVisible({ timeout: 5_000 });
  });

  test('exit survey has fair textarea', async () => {
    const page = pm.getPage(0);
    const fairTextarea = page.locator('textarea[name="fair"]');
    await expect(fairTextarea).toBeVisible({ timeout: 5_000 });
  });

  test('exit survey has feedback textarea', async () => {
    const page = pm.getPage(0);
    const feedbackTextarea = page.locator('textarea[name="feedback"]');
    await expect(feedbackTextarea).toBeVisible({ timeout: 5_000 });
  });

  test('exit survey has submit button', async () => {
    const page = pm.getPage(0);
    const submitBtn = page.getByRole('button', { name: /submit/i });
    await expect(submitBtn).toBeVisible({ timeout: 5_000 });
  });

  test('completion code shown after survey submission', async () => {
    const page = pm.getPage(0);

    // Submit the survey
    await page.getByRole('button', { name: /submit/i }).click();
    await page.waitForTimeout(1000);

    // Should now show the Prolific completion code
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain(PROLIFIC_CODES.completion);

    // Should show the Finish button
    const finishBtn = page.getByRole('button', { name: /finish/i });
    await expect(finishBtn).toBeVisible({ timeout: 5_000 });

    // Click Finish to complete
    await finishBtn.click();
    await page.waitForTimeout(500);

    // Complete exit survey for remaining players
    const pages = pm.getPages();
    for (let i = 1; i < pages.length; i++) {
      await completeExitSurvey(pages[i]);
    }
  });
});
