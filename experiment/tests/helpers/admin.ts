import { Page } from '@playwright/test';
import { Condition, TREATMENTS, TreatmentKey } from './constants';

/**
 * Wait for the admin page to fully load by checking for known UI elements.
 * Returns 'empty' if no batches exist, 'loaded' if batch list is rendered.
 *
 * IMPORTANT: Check for "New Batch" FIRST because both "New Batch" and
 * "Create a Batch" are visible when batches exist. "New Batch" only
 * appears after batches have been created.
 */
async function waitForAdminReady(page: Page, timeout = 15_000): Promise<'empty' | 'loaded'> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    // "New Batch" button appears when there ARE batches (top-right)
    const newBatchBtn = page.getByRole('button', { name: /new batch/i });
    if ((await newBatchBtn.count()) > 0) {
      // Extra wait for the batch list items to render below the button
      await page.waitForTimeout(1000);
      return 'loaded';
    }

    // "Create a Batch" = empty state (no batches at all, large dashed
    // placeholder). Confirmed with a second look, because the placeholder can
    // render a beat before the "New Batch" button on a page that does have
    // batches: reading that instant as "empty" made stopAllBatches return
    // without stopping anything and without reaching its own assertion, so a
    // spec that had asked for a batch to be stopped carried on against a
    // running one and failed a minute later somewhere else.
    const createBatchBtn = page.getByRole('button', { name: /create a batch/i });
    if ((await createBatchBtn.count()) > 0) {
      await page.waitForTimeout(750);
      if ((await newBatchBtn.count()) > 0) {
        await page.waitForTimeout(1000);
        return 'loaded';
      }
      return 'empty';
    }

    await page.waitForTimeout(500);
  }
  // Timeout - assume loaded to avoid blocking
  return 'loaded';
}

/**
 * Stop all running batches in the admin interface to prevent
 * new players from joining stale batches.
 *
 * Clicks all Stop buttons with a safety limit to prevent infinite loops
 * (Empirica may not immediately update the UI after clicking Stop).
 * Reloads the page between passes to ensure fresh UI state.
 */
async function stopRunningBatches(page: Page): Promise<void> {
  const MAX_CLICKS = 10; // Safety limit to prevent infinite loops

  // Stopping a batch asks for confirmation in a browser dialog; Playwright
  // dismisses dialogs by default, which silently cancelled every Stop.
  page.on('dialog', (dialog) => dialog.accept().catch(() => {}));

  // First pass: click all visible stop buttons
  for (let clicks = 0; clicks < MAX_CLICKS; clicks++) {
    const stopButtons = page.getByRole('button', { name: 'Stop' });
    const count = await stopButtons.count();
    if (count === 0) break;
    await stopButtons.first().click();
    await page.waitForTimeout(2000); // 2s for Empirica to process
  }

  // Reload and re-check: the batch list may not have fully rendered initially
  await page.reload({ waitUntil: 'load' });
  await waitForAdminReady(page);

  // Second pass after reload
  for (let clicks = 0; clicks < MAX_CLICKS; clicks++) {
    const stopButtons = page.getByRole('button', { name: 'Stop' });
    const count = await stopButtons.count();
    if (count === 0) break;
    await stopButtons.first().click();
    await page.waitForTimeout(2000);
  }
}

/**
 * Stop every running batch from the admin interface, as a researcher would to
 * end a live session early. Empirica then terminates the games in those
 * batches: each player's `ended` becomes "game terminated" and the server's
 * onGameEnded pays them like a disbanded group (see callbacks.js).
 *
 * Navigates to /admin itself, so any page from a fresh context will do.
 */
export async function stopAllBatches(page: Page): Promise<void> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await page.goto('/admin', { timeout: 30_000 });
      break;
    } catch {
      if (attempt === 2) throw new Error('Admin page unreachable after 3 attempts');
      await page.waitForTimeout(5000);
    }
  }
  // Deliberately not short-circuiting on an 'empty' reading: stopping nothing
  // has to be proven by the absence of Stop buttons below, not assumed from a
  // state read that can be wrong. stopRunningBatches is a no-op when there is
  // nothing to stop.
  await waitForAdminReady(page);
  await stopRunningBatches(page);

  const stillRunning = await page.getByRole('button', { name: 'Stop' }).count();
  if (stillRunning > 0) {
    throw new Error(`stopAllBatches: ${stillRunning} batch(es) still running after stopping`);
  }
}

/**
 * Create a new batch in the admin interface.
 * Navigates to /admin, stops any running batches, creates batch with specified treatment.
 *
 * Includes retry logic for server connectivity and proper admin UI wait.
 */
export async function createBatch(page: Page, condition: TreatmentKey): Promise<void> {
  // Navigate to admin with retry for server connectivity
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await page.goto('/admin', { timeout: 30_000 });
      break;
    } catch {
      if (attempt === 2) throw new Error('Admin page unreachable after 3 attempts');
      await page.waitForTimeout(5000);
    }
  }

  // Wait for admin UI to be ready
  const state = await waitForAdminReady(page);

  // Stop any running batches to prevent new players from joining them
  if (state === 'loaded') {
    await stopRunningBatches(page);
  }

  // Click "New Batch" to open the batch creation panel.
  // Both "New Batch" and "Create a Batch" can open the panel, but
  // "New Batch" is always in the header, while "Create a Batch" is
  // only a standalone placeholder when no batches exist.
  const newBatchBtn = page.getByRole('button', { name: /new batch/i });
  const createBatchBtn = page.getByRole('button', { name: /create a batch/i });
  if (await newBatchBtn.count() > 0) {
    await newBatchBtn.click();
  } else {
    await createBatchBtn.click();
  }
  await page.waitForTimeout(500);

  // Select treatment from dropdown (first <select> is the treatment selector)
  const treatmentName = TREATMENTS[condition];
  const treatmentSelect = page.locator('select').first();
  await treatmentSelect.selectOption({ label: treatmentName });
  await page.waitForTimeout(300);

  // Click the "Create" submit button in the form.
  // Use exact match to avoid matching "Create a Batch" placeholder.
  await page.getByRole('button', { name: 'Create', exact: true }).click();
  await page.waitForTimeout(1500);

  // Start the batch (click the Start button).
  // The newly created batch appears at the END of the list.
  try {
    const startBtn = page.getByRole('button', { name: 'Start' });
    const startCount = await startBtn.count();
    if (startCount > 0) {
      await startBtn.last().click();
      await page.waitForTimeout(1000);
    }
  } catch {
    // Batch may auto-start
  }

  // Verify at least one batch is running (has a Stop button)
  await page.waitForTimeout(500);
  const runningCount = await page.getByRole('button', { name: 'Stop' }).count();
  if (runningCount === 0) {
    // Batch may not have started - try starting the last one again
    const startBtn = page.getByRole('button', { name: 'Start' });
    if (await startBtn.count() > 0) {
      await startBtn.last().click();
      await page.waitForTimeout(1000);
    }
  } else if (runningCount > 1) {
    // Multiple batches running - stop all except the last (our new one)
    const stopBtns = page.getByRole('button', { name: 'Stop' });
    for (let i = 0; i < runningCount - 1; i++) {
      await stopBtns.first().click();
      await page.waitForTimeout(1000);
    }
  }

  // Fail here, with a clear message, rather than letting every player later
  // time out in the lobby because no batch is running. (Earlier batches from
  // previous specs may still be listed with a Stop button, so only require
  // that at least one batch is running.)
  await page.waitForTimeout(500);
  const running = await page.getByRole('button', { name: 'Stop' }).count();
  if (running === 0) {
    throw new Error('createBatch: no running batch after creation');
  }
}
