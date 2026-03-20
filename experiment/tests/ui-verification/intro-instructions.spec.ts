import { test, expect, Page, BrowserContext } from '@playwright/test';
import { createBatch } from '../helpers/admin';

/**
 * TEST_PLAN 5.1: Verify intro pages display correctly.
 *
 * Creates a single player context and walks through the consent page,
 * 6 instruction pages, and the comprehension quiz page, checking that
 * all expected elements are present at each step.
 */
test.describe.serial('UI Verification: Intro & Instructions (5.1)', () => {
  let page: Page;
  let context: BrowserContext;

  test.beforeAll(async ({ browser }) => {
    // Must create a batch first — Empirica shows "No experiments available"
    // if no batch exists, blocking the intro flow entirely.
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    context = await browser.newContext();
    page = await context.newPage();

    // Navigate to the app and enter as a new player
    await page.goto('/');

    // Wait for and click Empirica built-in consent ("I AGREE")
    try {
      await page.getByRole('button', { name: /agree/i }).click({ timeout: 15_000 });
      await page.waitForTimeout(500);
    } catch {
      // Consent dialog may already have been accepted
    }

    // Wait for the textbox to be visible before filling
    const textbox = page.getByRole('textbox');
    await textbox.waitFor({ state: 'visible', timeout: 15_000 });
    await textbox.fill('intro_test_player');
    await page.getByRole('button', { name: /enter/i }).click();
    await page.waitForTimeout(500);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('(a) consent page has "I consent" button', async () => {
    // We should be on the consent page after entering player ID
    const consentButton = page.getByRole('button', { name: /consent/i });
    await expect(consentButton).toBeVisible({ timeout: 10_000 });

    // Verify consent page has key elements
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('Consent');
  });

  test('(b) instruction page 1 has Next button and correct content', async () => {
    // Click consent to move to instruction page 1
    await page.getByRole('button', { name: /consent/i }).click();
    await page.waitForTimeout(500);

    // Verify Next button is visible
    const nextButton = page.getByRole('button', { name: /next/i });
    await expect(nextButton).toBeVisible({ timeout: 5_000 });

    // Instruction page 1: "How to play"
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('How to play');
    expect(bodyText).toContain('quiz');
  });

  test('(b) instruction page 2 has Next button and phase/pay info', async () => {
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    const nextButton = page.getByRole('button', { name: /next/i });
    await expect(nextButton).toBeVisible({ timeout: 5_000 });

    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('two phases');
    expect(bodyText).toContain('base pay');
  });

  test('(c) instruction page 3 references Speaker, Listener, and tangrams', async () => {
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    const nextButton = page.getByRole('button', { name: /next/i });
    await expect(nextButton).toBeVisible({ timeout: 5_000 });

    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('Speaker');
    expect(bodyText).toContain('Listener');
    // Tangram grid should be present in the instructions
    const tangramGrid = page.locator('.tangrams.grid');
    const gridCount = await tangramGrid.count();
    expect(gridCount).toBeGreaterThanOrEqual(1);
  });

  test('(c) instruction page 4 has player group example and references Speaker/Listener', async () => {
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    const nextButton = page.getByRole('button', { name: /next/i });
    await expect(nextButton).toBeVisible({ timeout: 5_000 });

    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('Speaker');
    expect(bodyText).toContain('Listener');
    expect(bodyText).toContain('Your Group');

    // Should show player-group display area
    const playerGroup = page.locator('.player-group');
    await expect(playerGroup).toBeVisible();
  });

  test('(b) instruction page 5 has Next button and Phase 2 info', async () => {
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    const nextButton = page.getByRole('button', { name: /next/i });
    await expect(nextButton).toBeVisible({ timeout: 5_000 });

    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('Phase 2');
  });

  test('(b) instruction page 6 has Next button and scoring info', async () => {
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(300);

    const nextButton = page.getByRole('button', { name: /next/i });
    await expect(nextButton).toBeVisible({ timeout: 5_000 });

    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('Scoring');
    expect(bodyText).toContain('points');
  });

  test('(d)(e) quiz page has 6 questions with radio buttons and title "Comprehension Quiz"', async () => {
    // Navigate to quiz page (the 7th instruction component)
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(500);

    // (e) Verify quiz title
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('Comprehension Quiz');

    // (d) Verify 6 questions exist -- each question uses radio inputs
    // Count the number of question groups (each <h2> is a question heading)
    const questionHeadings = page.locator('form h2');
    const headingCount = await questionHeadings.count();
    expect(headingCount).toBe(6);

    // Verify radio buttons exist
    const radioButtons = page.getByRole('radio');
    const radioCount = await radioButtons.count();
    // 6 questions with 2-3 choices each, so at least 12 radios
    expect(radioCount).toBeGreaterThanOrEqual(12);

    // Verify Submit button exists on quiz page
    const submitButton = page.getByRole('button', { name: /submit/i });
    await expect(submitButton).toBeVisible();

    // Verify the Next button is NOT visible on the quiz page
    // (quiz handles its own flow, no Next/Prev buttons)
    const nextButton = page.getByRole('button', { name: /^next$/i });
    await expect(nextButton).not.toBeVisible();
  });
});
