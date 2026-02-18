import { Page } from '@playwright/test';
import { GAME_CONTAINER, TASK, SORRY_SCREEN, QUIZ_FAILED_SCREEN, TANGRAM_ITEMS } from './selectors';
import { SELECTION_DURATION, FEEDBACK_DURATION } from './constants';

// ============ TYPES ============

export interface PlayerInfo {
  name: string | null;
  originalGroup: string | null;
  currentGroup: string | null;
  role: string | null;
  targetIndex: number;
  phase: number;
  block: number;
  round: number;
  stageName: string | null;
  condition: string | null;
}

export interface ExitInfo {
  type: 'sorry' | 'quiz-failed';
  exitReason: string | null;
  prolificCode: string | null;
  partialPay: string | null;
  playerId: string | null;
}

export interface CompleteRoundOptions {
  skipIndices?: number[];
  wrongGroups?: string[];
  doSocialGuess?: boolean;
  message?: string;
}

// ============ PLAYER INFO ============

export async function getPlayerInfo(page: Page): Promise<PlayerInfo | null> {
  try {
    return await page.evaluate(() => {
      const profile = document.querySelector('[data-player-name]');
      const task = document.querySelector('.task');
      const game = document.querySelector('[data-testid="game-container"]');
      if (!game) return null;
      return {
        name: profile?.getAttribute('data-player-name') ?? null,
        originalGroup: profile?.getAttribute('data-player-group') ?? null,
        currentGroup: task?.getAttribute('data-current-group') ?? null,
        role: task?.getAttribute('data-role') ?? null,
        targetIndex: parseInt(task?.getAttribute('data-target-index') ?? '-1', 10),
        phase: parseInt(game.getAttribute('data-game-phase') ?? '0', 10),
        block: parseInt(game.getAttribute('data-game-block') ?? '-1', 10),
        round: parseInt(game.getAttribute('data-game-round') ?? '-1', 10),
        stageName: game.getAttribute('data-stage-name'),
        condition: game.getAttribute('data-condition'),
      };
    });
  } catch {
    return null;
  }
}

export async function getExitInfo(page: Page): Promise<ExitInfo | null> {
  try {
    return await page.evaluate(() => {
      const sorry = document.querySelector('[data-testid="sorry-screen"]');
      const quizFailed = document.querySelector('[data-testid="quiz-failed-screen"]');
      const el = sorry || quizFailed;
      if (!el) return null;
      return {
        type: sorry ? 'sorry' as const : 'quiz-failed' as const,
        exitReason: el.getAttribute('data-exit-reason'),
        prolificCode: el.getAttribute('data-prolific-code'),
        partialPay: el.getAttribute('data-partial-pay'),
        playerId: el.getAttribute('data-player-id'),
      };
    });
  } catch {
    return null;
  }
}

export async function isInGame(page: Page): Promise<boolean> {
  const container = page.locator(GAME_CONTAINER);
  return (await container.count()) > 0;
}

export async function isOnExitScreen(page: Page): Promise<boolean> {
  const sorry = page.locator(SORRY_SCREEN);
  const quizFailed = page.locator(QUIZ_FAILED_SCREEN);
  return (await sorry.count()) > 0 || (await quizFailed.count()) > 0;
}

// ============ INTRO FLOW ============

export async function completeIntro(page: Page, playerName?: string): Promise<void> {
  const identifier = playerName || `player_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

  // Step 1: Handle Empirica built-in consent ("I AGREE") if present
  const agreeBtn = page.getByRole('button', { name: /agree/i });
  if (await agreeBtn.count() > 0) {
    await agreeBtn.click();
    await page.waitForTimeout(500);
  }

  // Step 2: Enter player identifier
  await page.getByRole('textbox').fill(identifier);
  await page.getByRole('button', { name: /enter/i }).click();
  await page.waitForTimeout(200);

  // Step 3: Custom consent page - click "I consent"
  await page.getByRole('button', { name: /consent/i }).click();
  await page.waitForTimeout(200);

  // Step 4: 5 intro/instruction pages
  for (let j = 0; j < 5; j++) {
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForTimeout(100);
  }

  // Step 5: Quiz answers
  await page.getByRole('radio', { name: /describe the target picture/i }).click();
  await page.getByRole('radio', { name: /removed from the game/i }).click();
  await page.getByRole('radio', { name: /only descriptions of the current/i }).click();
  await page.getByRole('radio', { name: /listeners must wait/i }).click();
  await page.getByRole('radio', { name: /mixed up/i }).click();
  await page.getByRole('radio', { name: /different positions for each player/i }).click();

  // Handle quiz success dialog
  page.once('dialog', async dialog => await dialog.accept());
  await page.getByRole('button', { name: /submit/i }).click();
  await page.waitForTimeout(400);
}

// ============ GAME ACTIONS ============

export async function speakerSendMessage(page: Page, message: string): Promise<boolean> {
  try {
    const input = page.getByRole('textbox', { name: 'Say something' });
    if (await input.count() > 0) {
      await input.fill(message);
      await input.press('Enter');
      return true;
    }
  } catch {
    // Chat not available
  }
  return false;
}

export async function listenerClickTangram(page: Page, index: number): Promise<boolean> {
  try {
    const tangrams = page.locator(TANGRAM_ITEMS);
    const count = await tangrams.count();
    if (count === 0) return false;
    const clickIndex = index >= 0 && index < count ? index : 0;
    await tangrams.nth(clickIndex).click();
    return true;
  } catch {
    return false;
  }
}

export async function makeSocialGuess(page: Page, guess: 'same' | 'different'): Promise<boolean> {
  try {
    if (guess === 'same') {
      await page.getByRole('button', { name: /yes, same group/i }).click({ timeout: 2000 });
    } else {
      await page.getByRole('button', { name: /no, different group/i }).click({ timeout: 2000 });
    }
    return true;
  } catch {
    return false;
  }
}

export async function clickContinue(page: Page, timeout = 1000): Promise<boolean> {
  try {
    await page.getByRole('button', { name: /continue/i }).click({ timeout });
    return true;
  } catch {
    return false;
  }
}

// ============ ROUND HELPERS ============

/**
 * Complete one full round for all players.
 * Handles: Continue clicks → speakers send → listeners click → social guess
 */
export async function playRound(pages: Page[], options: CompleteRoundOptions = {}): Promise<void> {
  const { skipIndices = [], wrongGroups = [], doSocialGuess = false, message = 'round message' } = options;

  // Click Continue buttons (feedback → selection transition)
  for (const page of pages) {
    await clickContinue(page, 500);
  }
  await pages[0]?.waitForTimeout(500);

  // Build group → target mapping from speakers
  const groupTargets: Record<string, number> = {};

  // Speakers send messages
  for (let i = 0; i < pages.length; i++) {
    if (skipIndices.includes(i)) continue;
    const info = await getPlayerInfo(pages[i]);
    if (info?.role === 'speaker' && info.targetIndex >= 0) {
      groupTargets[info.currentGroup!] = info.targetIndex;
      await speakerSendMessage(pages[i], message);
    }
  }
  await pages[0]?.waitForTimeout(500);

  // Listeners click tangrams
  for (let i = 0; i < pages.length; i++) {
    if (skipIndices.includes(i)) continue;
    const info = await getPlayerInfo(pages[i]);
    if (info?.role === 'listener') {
      // Each listener's targetIndex is the correct grid position in THEIR shuffled view
      let clickIdx = info.targetIndex >= 0 ? info.targetIndex : 0;

      // Wrong groups click wrong tangram
      if (wrongGroups.includes(info.originalGroup!)) {
        clickIdx = (clickIdx + 3) % 6;
      }

      await listenerClickTangram(pages[i], clickIdx);

      // Social guess if needed
      if (doSocialGuess) {
        await pages[i].waitForTimeout(500);
        await makeSocialGuess(pages[i], 'same');
      }
    }
  }
  await pages[0]?.waitForTimeout(500);

  // When players are skipped, the round won't advance until SELECTION_DURATION
  // timer expires (skipped players never submit). Wait for the full round cycle.
  if (skipIndices.length > 0) {
    let monitorPage: Page | null = null;
    for (let i = 0; i < pages.length; i++) {
      if (skipIndices.includes(i)) continue;
      const info = await getPlayerInfo(pages[i]);
      if (info) {
        monitorPage = pages[i];
        break;
      }
    }

    if (monitorPage) {
      // Wait for Feedback stage (SELECTION_DURATION timer must expire first)
      const reachedFeedback = await waitForStage(
        monitorPage,
        'Feedback',
        (SELECTION_DURATION + 15) * 1000,
      );

      if (reachedFeedback) {
        // Wait for Feedback stage to end (FEEDBACK_DURATION + buffer)
        const startWait = Date.now();
        const maxWait = (FEEDBACK_DURATION + 10) * 1000;
        while (Date.now() - startWait < maxWait) {
          const info = await getPlayerInfo(monitorPage);
          if (!info) break; // Player left game (kicked/disbanded)
          if (info.stageName !== 'Feedback') break; // Stage advanced
          await monitorPage.waitForTimeout(1000);
        }
      }
    }
  }
}

/**
 * Play a full block of rounds
 */
export async function playBlock(
  pages: Page[],
  numRounds = 6,
  options: CompleteRoundOptions = {},
): Promise<void> {
  for (let r = 0; r < numRounds; r++) {
    await playRound(pages, options);
  }
}

/**
 * Handle transition screen (click Continue for all)
 * Waits for each page to show the transition, then clicks Continue.
 */
export async function handleTransition(pages: Page[], timeout = 10000): Promise<void> {
  // Wait for transition content to appear on first page
  await pages[0]?.waitForTimeout(2000);

  // Click Continue on each page, retrying to handle rendering delays
  for (const page of pages) {
    // Wait for the Continue button to appear (transition may render at different times)
    try {
      await page.getByRole('button', { name: /continue/i }).waitFor({ state: 'visible', timeout });
      await page.getByRole('button', { name: /continue/i }).click();
    } catch {
      // Fallback: player may have already submitted or screen may differ
      await clickContinue(page, 2000);
    }
  }
  await pages[0]?.waitForTimeout(1000);
}

// ============ EXIT SURVEY ============

export async function completeExitSurvey(page: Page): Promise<void> {
  try {
    // Fill survey fields
    const ageInput = page.locator('input[name="age"]');
    if (await ageInput.count() > 0) await ageInput.fill('25');

    const genderInput = page.locator('input[name="gender"]');
    if (await genderInput.count() > 0) await genderInput.fill('prefer not to say');

    // Education radio
    const educationRadio = page.getByRole('radio', { name: /bachelor/i });
    if (await educationRadio.count() > 0) await educationRadio.click();

    // Understanding radio
    const understandingRadio = page.getByRole('radio', { name: /^yes$/i });
    if (await understandingRadio.count() > 0) await understandingRadio.click();

    // Textareas
    const strengthTextarea = page.locator('textarea[name="strength"]');
    if (await strengthTextarea.count() > 0) await strengthTextarea.fill('Test strategy');

    const fairTextarea = page.locator('textarea[name="fair"]');
    if (await fairTextarea.count() > 0) await fairTextarea.fill('Yes');

    const feedbackTextarea = page.locator('textarea[name="feedback"]');
    if (await feedbackTextarea.count() > 0) await feedbackTextarea.fill('Test feedback');

    // Submit
    await page.getByRole('button', { name: /submit/i }).click();
    await page.waitForTimeout(500);
  } catch {
    // Survey fields may vary
  }
}

// ============ WAIT HELPERS ============

export async function waitForStage(page: Page, stageName: string, timeout = 30_000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const info = await getPlayerInfo(page);
    if (info?.stageName === stageName) return true;
    await page.waitForTimeout(500);
  }
  return false;
}

export async function waitForPhase(page: Page, phaseNum: number, timeout = 60_000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const info = await getPlayerInfo(page);
    if (info?.phase === phaseNum) return true;
    await page.waitForTimeout(500);
  }
  return false;
}

export async function waitForFeedback(page: Page, timeout = 30_000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const content = await page.textContent('body');
    if (content?.includes('Correct!') || content?.includes('Ooops') ||
        content?.includes('You earned') || content?.includes('points this round')) {
      return true;
    }
    await page.waitForTimeout(500);
  }
  return false;
}

export async function waitForExitScreen(page: Page, timeout = 120_000): Promise<ExitInfo | null> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const info = await getExitInfo(page);
    if (info) return info;
    await page.waitForTimeout(1000);
  }
  return null;
}

export async function waitForGameStart(pages: Page[], timeout = 120_000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    for (const page of pages) {
      const info = await getPlayerInfo(page);
      if (info?.stageName === 'Selection') return true;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  return false;
}

// ============ PLAYER GROUPING ============

export async function getActivePlayers(pages: Page[]): Promise<Page[]> {
  const active: Page[] = [];
  for (const page of pages) {
    if (await isInGame(page)) {
      active.push(page);
    }
  }
  return active;
}

export async function getPlayersByGroup(pages: Page[]): Promise<Record<string, { page: Page; info: PlayerInfo }[]>> {
  const groups: Record<string, { page: Page; info: PlayerInfo }[]> = {};
  for (const page of pages) {
    const info = await getPlayerInfo(page);
    if (info?.originalGroup) {
      if (!groups[info.originalGroup]) groups[info.originalGroup] = [];
      groups[info.originalGroup].push({ page, info });
    }
  }
  return groups;
}

export async function getRemovedPlayers(pages: Page[]): Promise<{ page: Page; info: ExitInfo }[]> {
  const removed: { page: Page; info: ExitInfo }[] = [];
  for (const page of pages) {
    const info = await getExitInfo(page);
    if (info) {
      removed.push({ page, info });
    }
  }
  return removed;
}
