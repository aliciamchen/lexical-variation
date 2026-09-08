import { test, expect } from '@playwright/test';
import { createBatch } from '../helpers/admin';
import { QUIZ_FAILED_SCREEN, SORRY_SCREEN } from '../helpers/selectors';

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

    // Custom consent page comes first (Empirica's built-in "I AGREE" is disabled)
    await page.getByRole('button', { name: /consent/i }).click({ timeout: 15_000 });

    // Enter identifier
    await page.getByRole('textbox').waitFor({ state: 'visible', timeout: 15_000 });
    await page.getByRole('textbox').fill('quiz_fail_player');
    await page.getByRole('button', { name: /enter/i }).click();
    await page.waitForTimeout(200);

    // Go through 6 intro/instruction pages
    for (let j = 0; j < 6; j++) {
      await page.getByRole('button', { name: /next/i }).click();
      await page.waitForTimeout(100);
    }

    // Now on the quiz page. Answer wrong 3 times. Between the second and third
    // attempt the page is reloaded: the attempt count is stored on the player
    // record, so the reload must not grant fresh attempts.
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt === 2) {
        await page.reload();
        // Same participant token: after reconnecting, the intro restarts at its
        // first instruction page (consent and identifier are already done).
        const consent = page.getByRole('button', { name: /consent/i });
        const textbox = page.getByRole('textbox');
        const next = page.getByRole('button', { name: /next/i });
        await consent.or(textbox).or(next).first().waitFor({ state: 'visible', timeout: 20_000 });
        if (await consent.count()) await consent.click();
        if (await textbox.count()) {
          await textbox.fill('quiz_fail_player');
          await page.getByRole('button', { name: /enter/i }).click();
        }
        for (let j = 0; j < 8; j++) {
          if (!(await next.isVisible().catch(() => false))) break;
          await next.click();
          await page.waitForTimeout(200);
        }
        await page.getByRole('radio', { name: /click on the target picture as fast/i }).waitFor({ state: 'visible', timeout: 15_000 });
      }
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

    // After 3 failed attempts the player is marked ended ("quiz failed") and
    // routed to the Sorry page; the Quiz component's own failure screen may show
    // briefly first. Either must carry the quiz-failed reason and no code.
    const sorry = page.locator(SORRY_SCREEN);
    const failedScreen = page.locator(QUIZ_FAILED_SCREEN).or(sorry);
    await expect(failedScreen.first()).toBeVisible({ timeout: 10_000 });
    await expect(sorry).toBeVisible({ timeout: 15_000 });
    await expect(sorry).toHaveAttribute('data-exit-reason', 'quiz failed');
    await expect(sorry).toHaveAttribute('data-prolific-code', 'none');

    // Verify the failure message content — no code, player is asked to return the study
    const screenText = await sorry.textContent();
    expect(screenText).toContain('Quiz Failed');
    expect(screenText).toContain('return this study on Prolific');

    // Cleanup
    await playerContext.close();
  });
});
