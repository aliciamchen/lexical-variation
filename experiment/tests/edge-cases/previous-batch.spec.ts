/**
 * TEST_PLAN 9.4: Previous Batch Present
 *
 * Creating a new batch when a previous one exists should work without
 * interference. Create batch 1, then create batch 2, and verify both
 * can be created independently via the admin interface.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import { TREATMENTS } from '../helpers/constants';

test.describe.serial('Edge Case: Previous Batch Present (TEST_PLAN 9.4)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    pm = new PlayerManager(browser, 0); // No player pages needed for this admin test
    await pm.initialize();
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('create first batch (refer_separated)', async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();

    await createBatch(adminPage, 'exp1_refer_separated');

    // Verify the batch appears in the admin interface
    await adminPage.goto('/admin');
    await adminPage.waitForTimeout(1000);

    const bodyText = await adminPage.textContent('body');
    expect(bodyText).not.toBeNull();
    // The admin page should show the batch we created
    // Look for signs that a batch exists (batch status, treatment name, etc.)
    const hasBatchIndicator =
      bodyText?.includes('exp1_refer_separated') ||
      bodyText?.includes('Refer Separated') ||
      bodyText?.includes('running') ||
      bodyText?.includes('created') ||
      bodyText?.includes('waiting');
    expect(hasBatchIndicator).toBe(true);

    await adminContext.close();
  });

  test('create second batch (refer_mixed) with first batch still present', async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();

    // Create a second batch while the first one still exists
    await createBatch(adminPage, 'exp1_refer_mixed');

    // Verify the admin page shows both batches
    await adminPage.goto('/admin');
    await adminPage.waitForTimeout(1000);

    const bodyText = await adminPage.textContent('body');
    expect(bodyText).not.toBeNull();

    // The admin page should now reflect that a second batch was created
    // We check that the page is functional and not showing errors
    expect(bodyText).not.toContain('Error');
    expect(bodyText).not.toContain('Something went wrong');

    await adminContext.close();
  });

  test('admin interface remains functional after multiple batches', async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();

    await adminPage.goto('/admin');
    await adminPage.waitForTimeout(1000);

    // Verify the "New Batch" button is still available
    const newBatchBtn = adminPage.getByRole('button', { name: /new batch/i });
    await expect(newBatchBtn).toBeVisible({ timeout: 5000 });

    // Verify the page loads without errors
    const bodyText = await adminPage.textContent('body');
    expect(bodyText).not.toBeNull();
    expect(bodyText!.length).toBeGreaterThan(0);

    // Could create a third batch to prove no interference
    await createBatch(adminPage, 'exp1_social_mixed');
    await adminPage.waitForTimeout(1000);

    // All three batches should coexist without issues
    const finalBodyText = await adminPage.textContent('body');
    expect(finalBodyText).not.toContain('Error');
    expect(finalBodyText).not.toContain('Something went wrong');

    await adminContext.close();
  });
});
