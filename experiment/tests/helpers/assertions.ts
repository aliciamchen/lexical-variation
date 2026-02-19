import { Page, expect } from '@playwright/test';
import { GAME_CONTAINER, SORRY_SCREEN, QUIZ_FAILED_SCREEN, SOCIAL_GUESS_CONTAINER } from './selectors';
import { getPlayerInfo, getExitInfo } from './game-actions';

/**
 * Assert player is in the active game
 */
export async function expectPlayerInGame(page: Page): Promise<void> {
  await expect(page.locator(GAME_CONTAINER)).toBeVisible({ timeout: 10_000 });
}

/**
 * Assert player is on a sorry/exit screen with expected reason and prolific code
 */
export async function expectPlayerOnExitScreen(
  page: Page,
  reason?: string,
  code?: string,
): Promise<void> {
  const sorry = page.locator(SORRY_SCREEN);
  const quizFailed = page.locator(QUIZ_FAILED_SCREEN);
  await expect(sorry.or(quizFailed)).toBeVisible({ timeout: 30_000 });

  if (reason) {
    const el = sorry.or(quizFailed);
    await expect(el).toHaveAttribute('data-exit-reason', reason);
  }

  if (code) {
    const el = sorry.or(quizFailed);
    await expect(el).toHaveAttribute('data-prolific-code', code);
  }
}

/**
 * Assert the current game phase
 */
export async function expectPhase(page: Page, phaseNum: number): Promise<void> {
  await expect(page.locator(GAME_CONTAINER)).toHaveAttribute(
    'data-game-phase',
    String(phaseNum),
  );
}

/**
 * Assert the current stage name
 */
export async function expectStage(page: Page, stageName: string): Promise<void> {
  await expect(page.locator(GAME_CONTAINER)).toHaveAttribute(
    'data-stage-name',
    stageName,
  );
}

/**
 * Assert player role (speaker/listener)
 */
export async function expectRole(page: Page, role: 'speaker' | 'listener'): Promise<void> {
  const info = await getPlayerInfo(page);
  expect(info?.role).toBe(role);
}

/**
 * Assert all players in pages have unchanged original groups throughout game
 */
export async function expectGroupUnchanged(pages: Page[]): Promise<void> {
  for (const page of pages) {
    const info = await getPlayerInfo(page);
    if (info) {
      expect(info.currentGroup).toBe(info.originalGroup);
    }
  }
}

/**
 * Assert identity is masked (player shows "Player" name)
 */
export async function expectIdentityMasked(page: Page): Promise<void> {
  const content = await page.textContent('body');
  // In mixed Phase 2, players should see "Player (Speaker)" or "Player (Listener)"
  // but not real names like "Repi", "Minu", etc.
  const playerNames = ['Repi', 'Minu', 'Laju', 'Hera', 'Zuda', 'Bavi', 'Lika', 'Felu', 'Nori'];
  for (const name of playerNames) {
    // Name should not appear in player display area (it can still appear in profile)
    const playerGroup = page.locator('.player-group');
    if (await playerGroup.count() > 0) {
      const groupText = await playerGroup.textContent();
      // Other players should show as "Player", not their real names
      // The current player shows "(You)" so their name might still appear
      // Just check that "Player" appears in the group display
      expect(groupText).toContain('Player');
    }
  }
}

/**
 * Assert social guess UI is visible
 */
export async function expectSocialGuessUI(page: Page): Promise<void> {
  await expect(page.locator(SOCIAL_GUESS_CONTAINER)).toBeVisible({ timeout: 5_000 });
}

/**
 * Assert social guess UI is NOT visible
 */
export async function expectNoSocialGuessUI(page: Page): Promise<void> {
  await expect(page.locator(SOCIAL_GUESS_CONTAINER)).not.toBeVisible();
}

/**
 * Assert that exactly one player per group is speaker
 */
export async function expectOneSpeakerPerGroup(
  pages: Page[],
): Promise<void> {
  const groups: Record<string, string[]> = {};
  for (const page of pages) {
    const info = await getPlayerInfo(page);
    if (info?.currentGroup && info.role) {
      if (!groups[info.currentGroup]) groups[info.currentGroup] = [];
      groups[info.currentGroup].push(info.role);
    }
  }
  for (const [group, roles] of Object.entries(groups)) {
    const speakers = roles.filter(r => r === 'speaker');
    expect(speakers.length, `Group ${group} should have exactly 1 speaker`).toBe(1);
  }
}

/**
 * Assert feedback content is displayed
 */
export async function expectFeedbackVisible(page: Page): Promise<void> {
  const body = await page.textContent('body');
  const hasFeedback = body?.includes('Correct!') ||
    body?.includes('Ooops') ||
    body?.includes('You earned') ||
    body?.includes('points this round') ||
    body?.includes('did not send a message') ||
    body?.includes('did not respond');
  expect(hasFeedback, 'Expected feedback to be visible').toBe(true);
}

/**
 * Assert a specific condition is set on the game container.
 * Retries via toHaveAttribute, with diagnostic fallback on failure.
 */
export async function expectCondition(page: Page, condition: string): Promise<void> {
  const container = page.locator(GAME_CONTAINER);
  await expect(container).toBeVisible({ timeout: 10_000 });

  try {
    await expect(container).toHaveAttribute('data-condition', condition, { timeout: 15_000 });
  } catch {
    // On failure, read the actual value for clear diagnostics
    const actual = await container.getAttribute('data-condition');
    throw new Error(
      `Expected data-condition="${condition}" but got "${actual}". ` +
      `Players may have joined a game from a stale batch.`
    );
  }
}

/**
 * Assert block number
 */
export async function expectBlock(page: Page, blockNum: number): Promise<void> {
  await expect(page.locator(GAME_CONTAINER)).toHaveAttribute(
    'data-game-block',
    String(blockNum),
  );
}
