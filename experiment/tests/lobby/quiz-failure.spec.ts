import { test, expect } from '@playwright/test';
import { createBatch } from '../helpers/admin';
import { PROLIFIC_CODES } from '../helpers/constants';
import { QUIZ_FAILED_SCREEN } from '../helpers/selectors';

// TEST_PLAN 4.2: Player fails comprehension quiz 3 times and is shown failure screen
test.describe.serial('Lobby: quiz failure after 3 attempts', () => {
  test('player sees quiz-failed screen after 3 wrong attempts', async ({ browser }) => {
    // Create a batch so the experiment is active
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
    await adminContext.close();

    // Create a single player context
    const playerContext = await browser.newContext();
    const page = await playerContext.newPage();
    await page.goto('/');
    await page.waitForTimeout(500);

    // Handle Empirica built-in consent ("I AGREE") if present
    try {
      await page.getByRole('button', { name: /agree/i }).click({ timeout: 10_000 });
      await page.waitForTimeout(500);
    } catch {
      // Consent may have already been accepted
    }

    // Enter identifier
    await page.getByRole('textbox').fill('quiz_fail_player');
    await page.getByRole('button', { name: /enter/i }).click();
    await page.waitForTimeout(200);

    // Custom consent
    await page.getByRole('button', { name: /consent/i }).click();
    await page.waitForTimeout(200);

    // Go through 5 intro/instruction pages
    for (let j = 0; j < 5; j++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(100);
    }

    // Now on the quiz page. Answer wrong 3 times.
    for (let attempt = 0; attempt < 3; attempt++) {
      // Wrong answers: first choice for each question
      await page.getByRole('radio', { name: /click on the target picture as fast/i }).click();
      await page.getByRole('radio', { name: /nothing, you can rejoin/i }).click();
      await page.getByRole('radio', { name: /anything related to the game/i }).click();
      await page.getByRole('radio', { name: /listeners can click on pictures at any time/i }).click();
      await page.getByRole('radio', { name: /same pictures in the same places/i }).click();
      await page.getByRole('radio', { name: /left and right are too vague/i }).click();

      if (attempt < 2) {
        // For attempts 1 and 2, an alert dialog appears saying answers are incorrect
        page.once('dialog', async (dialog) => {
          await dialog.accept();
        });
      }

      // Click submit
      await page.getByRole('button', { name: /submit/i }).click();
      await page.waitForTimeout(500);
    }

    // After 3 failed attempts, the quiz-failed screen should be visible
    const quizFailedScreen = page.locator(QUIZ_FAILED_SCREEN);
    await expect(quizFailedScreen).toBeVisible({ timeout: 10_000 });

    // Verify the data attributes on the quiz-failed screen
    await expect(quizFailedScreen).toHaveAttribute('data-testid', 'quiz-failed-screen');
    await expect(quizFailedScreen).toHaveAttribute('data-exit-reason', 'quiz_failed');
    await expect(quizFailedScreen).toHaveAttribute('data-prolific-code', PROLIFIC_CODES.quizFail);

    // Verify the failure message content
    const screenText = await quizFailedScreen.textContent();
    expect(screenText).toContain('Quiz Failed');
    expect(screenText).toContain(PROLIFIC_CODES.quizFail);

    // Cleanup
    await playerContext.close();
  });
});
