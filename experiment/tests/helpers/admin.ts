import { Page } from '@playwright/test';
import { Condition, TREATMENTS } from './constants';

/**
 * Stop all running batches in the admin interface to prevent
 * new players from joining stale batches.
 */
async function stopRunningBatches(page: Page): Promise<void> {
  // Look for stop buttons (square icon) on running batches
  const stopButtons = page.locator('button[title="Stop"]');
  let count = await stopButtons.count();
  while (count > 0) {
    await stopButtons.first().click();
    await page.waitForTimeout(500);
    count = await stopButtons.count();
  }
}

/**
 * Create a new batch in the admin interface.
 * Navigates to /admin, stops any running batches, creates batch with specified treatment.
 */
export async function createBatch(page: Page, condition: Condition): Promise<void> {
  await page.goto('/admin');
  await page.waitForTimeout(1000);

  // Stop any running batches to prevent new players from joining them
  await stopRunningBatches(page);

  // Click the button to open the new batch dialog
  // When no batches exist: "Create a Batch" (dashed placeholder)
  // When batches exist: "New Batch" (top-right button)
  const createBatchBtn = page.getByRole('button', { name: /create a batch/i });
  const newBatchBtn = page.getByRole('button', { name: /new batch/i });
  if (await createBatchBtn.count() > 0) {
    await createBatchBtn.click();
  } else {
    await newBatchBtn.click();
  }
  await page.waitForTimeout(500);

  // Select treatment from dropdown
  const treatmentName = TREATMENTS[condition];
  const treatmentSelect = page.locator('select').first();
  await treatmentSelect.selectOption({ label: treatmentName });
  await page.waitForTimeout(300);

  // Click Create (use data-test attribute to avoid matching "Create a Batch" button)
  const createBtn = page.locator('[data-test="createBatchButton"]');
  await createBtn.click();
  await page.waitForTimeout(1000);

  // Start the batch if needed (click the play/start button)
  try {
    const startBtn = page.locator('button[title="Start"]').or(
      page.getByRole('button', { name: /start/i })
    );
    if (await startBtn.count() > 0) {
      await startBtn.first().click();
      await page.waitForTimeout(500);
    }
  } catch {
    // Batch may auto-start
  }
}
