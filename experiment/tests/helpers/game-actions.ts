import { Page } from '@playwright/test';
import { GAME_CONTAINER, TASK, SORRY_SCREEN, QUIZ_FAILED_SCREEN, EXIT_SURVEY, TANGRAM_ITEMS, SIMULTANEOUS_SUBMIT, CHAT_MESSAGES } from './selectors';
import { SELECTION_DURATION, PHASE2_SELECTION_DURATION, FEEDBACK_DURATION, ROUNDS_PER_BLOCK } from './constants';

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
  type: 'sorry' | 'quiz-failed' | 'exit-survey';
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
  /** Listener indices that make selections but do NOT click Submit — tests auto-commit on timer expiry */
  autocommitIndices?: number[];
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
      const exitSurvey = document.querySelector('[data-testid="exit-survey"]');
      const el = sorry || quizFailed;
      if (el) {
        return {
          type: sorry ? 'sorry' as const : 'quiz-failed' as const,
          exitReason: el.getAttribute('data-exit-reason'),
          prolificCode: el.getAttribute('data-prolific-code'),
          partialPay: el.getAttribute('data-partial-pay'),
          playerId: el.getAttribute('data-player-id'),
        };
      }
      if (exitSurvey) {
        return {
          type: 'exit-survey' as const,
          exitReason: exitSurvey.getAttribute('data-ended-reason'),
          // Only the confirmation page (after both survey pages) carries the code
          prolificCode: exitSurvey.getAttribute('data-prolific-code'),
          partialPay: null,
          playerId: null,
        };
      }
      return null;
    });
  } catch {
    return null;
  }
}

export async function isInGame(page: Page): Promise<boolean> {
  const container = page.locator(GAME_CONTAINER);
  if ((await container.count()) === 0) return false;
  // A kicked player is routed to the Sorry screen by Empirica's exit steps;
  // check for it in case the game container is still being torn down.
  const sorry = page.locator(SORRY_SCREEN);
  if ((await sorry.count()) > 0) return false;
  // Exit survey means the player has left the game (disbanded flow)
  const exitSurvey = page.locator(EXIT_SURVEY);
  if ((await exitSurvey.count()) > 0) return false;
  return true;
}

export async function isOnExitScreen(page: Page): Promise<boolean> {
  const sorry = page.locator(SORRY_SCREEN);
  const quizFailed = page.locator(QUIZ_FAILED_SCREEN);
  const exitSurvey = page.locator(EXIT_SURVEY);
  return (await sorry.count()) > 0 || (await quizFailed.count()) > 0 || (await exitSurvey.count()) > 0;
}

// ============ INTRO FLOW ============

export async function completeIntro(page: Page, options?: string | { playerName?: string; condition?: string }): Promise<void> {
  // Support both old string signature and new options object
  const opts = typeof options === 'string' ? { playerName: options } : (options ?? {});
  const identifier = opts.playerName || `player_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

  // Step 1: Custom consent page (now shown before identifier entry)
  await page.getByRole('button', { name: /consent/i }).waitFor({ state: 'visible', timeout: 15_000 });
  await page.getByRole('button', { name: /consent/i }).click();
  await page.waitForTimeout(500);

  // Step 2: Wait for textbox to appear, then enter player identifier
  await page.getByRole('textbox').waitFor({ state: 'visible', timeout: 15_000 });
  await page.getByRole('textbox').fill(identifier);
  await page.getByRole('button', { name: /enter/i }).click();
  await page.waitForTimeout(500);

  // Step 3: 6 intro/instruction pages
  for (let j = 0; j < 6; j++) {
    await page.getByRole('button', { name: /next/i }).click({ timeout: 10_000 });
    await page.waitForTimeout(200);
  }

  // Step 4: Quiz answers - wait for first radio to be visible (quiz page loaded)
  await page.getByRole('radio', { name: /describe the target picture/i }).waitFor({ state: 'visible', timeout: 10_000 });
  await page.getByRole('radio', { name: /describe the target picture/i }).click();
  await page.getByRole('radio', { name: /removed from the game/i }).click();
  await page.getByRole('radio', { name: /only topics related to picking out/i }).click();
  await page.getByRole('radio', { name: /listeners must wait/i }).click();
  await page.getByRole('radio', { name: /mixed up/i }).click();
  await page.getByRole('radio', { name: /different positions for each player/i }).click();

  // Step 5: Condition-specific 7th question (exp2 conditions only)
  if (opts.condition === 'social_first') {
    await page.getByRole('radio', { name: /mixed together.*figure out whether they were in the same Phase 1 group/i }).click();
  }

  // Handle quiz success dialog
  page.once('dialog', async dialog => await dialog.accept());
  await page.getByRole('button', { name: /submit/i }).click();
  await page.waitForTimeout(500);
}

// ============ GAME ACTIONS ============

export async function speakerSendMessage(page: Page, message: string, timeout = 10_000): Promise<boolean> {
  // The chat renders once the page is in Selection and the group has not all
  // responded; wait for it rather than checking once, so a stage-propagation
  // lag between browser contexts is not mistaken for a missing chat.
  try {
    const input = page.getByRole('textbox', { name: 'Say something' });
    await input.waitFor({ state: 'visible', timeout });
    await input.fill(message);
    await input.press('Enter');
    return true;
  } catch {
    return false;
  }
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

/**
 * Read the score shown in the player's Profile card.
 */
export async function readScore(page: Page): Promise<number> {
  return page.evaluate(() => {
    const label = Array.from(document.querySelectorAll('div')).find((el) => el.textContent?.trim() === 'Score');
    const numEl = label?.parentElement?.querySelector('.tabular-nums') ?? document.querySelector('.tabular-nums');
    return numEl ? parseInt(numEl.textContent || '0', 10) : 0;
  });
}

// ============ ROUND HELPERS ============

/**
 * Complete one full round for all players.
 * Handles: Continue clicks → speakers send → listeners click → social guess
 */
export async function playRound(pages: Page[], options: CompleteRoundOptions = {}): Promise<void> {
  const { skipIndices = [], wrongGroups = [], doSocialGuess = false, message = 'round message', autocommitIndices = [] } = options;

  // Find a non-skipped active page for monitoring (skip sorry-screen pages)
  let monitorPage = pages[0];
  for (let i = 0; i < pages.length; i++) {
    if (!skipIndices.includes(i) && await isInGame(pages[i])) {
      monitorPage = pages[i];
      break;
    }
  }

  // Click Continue only if we're NOT already in Selection (avoids 3s*N timeout waste)
  const currentInfo = await getPlayerInfo(monitorPage);
  if (currentInfo && currentInfo.stageName !== 'Selection') {
    for (let i = 0; i < pages.length; i++) {
      if (skipIndices.includes(i)) continue;
      if (!(await isInGame(pages[i]))) continue;
      await clickContinue(pages[i], 3000);
    }
  }

  // Wait for the Selection stage. If none arrives (transition, Bonus info, or
  // the game is over) there is no round to play: return without touching the
  // pages, so callers that loop "until the game moves on" do not burn stage time.
  const inSelection = await waitForStage(monitorPage, 'Selection', 15_000);
  if (!inSelection) return;

  // Build group → target mapping from speakers, and remember which groups'
  // speakers actually spoke (a skipped speaker leaves its listeners unable to act)
  const groupTargets: Record<string, number> = {};
  const speakerSpoke: Record<string, boolean> = {};

  // Speakers send messages (each page must itself have reached Selection first)
  for (let i = 0; i < pages.length; i++) {
    if (skipIndices.includes(i)) continue;
    if (!(await isInGame(pages[i]))) continue;
    // Other pages may lag the monitor page by a moment when the stage changes
    await waitForStage(pages[i], 'Selection', 5_000);
    const info = await getPlayerInfo(pages[i]);
    if (info?.role === 'speaker' && info.targetIndex >= 0) {
      groupTargets[info.currentGroup!] = info.targetIndex;
      const sent = await speakerSendMessage(pages[i], message);
      if (!sent) {
        throw new Error(
          `playRound: speaker on page ${i} (group ${info.currentGroup}) could not send a chat message`,
        );
      }
      speakerSpoke[info.currentGroup!] = true;
    }
  }

  // Listeners: wait for their speaker's message, then click.
  for (let i = 0; i < pages.length; i++) {
    if (skipIndices.includes(i)) continue;
    const info = await getPlayerInfo(pages[i]);
    if (info?.role === 'listener') {
      // The client ignores tangram clicks until the speaker's message has arrived,
      // so a listener whose speaker was skipped (idle tests) cannot act this round.
      if (!speakerSpoke[info.currentGroup!]) continue;
      await pages[i]
        .locator(CHAT_MESSAGES)
        .getByText(message, { exact: false })
        .first()
        .waitFor({ state: 'visible', timeout: 15_000 });

      // Listener sends a chat message before clicking
      await speakerSendMessage(pages[i], 'ok');

      // Each listener's targetIndex is the correct grid position in THEIR shuffled view
      let clickIdx = info.targetIndex >= 0 ? info.targetIndex : 0;

      // Wrong groups click wrong tangram
      if (wrongGroups.includes(info.originalGroup!)) {
        clickIdx = (clickIdx + 6) % 12;
      }

      const clicked = await listenerClickTangram(pages[i], clickIdx);
      if (!clicked) {
        throw new Error(
          `playRound: listener on page ${i} (group ${info.currentGroup}) could not click tangram ${clickIdx}`,
        );
      }

      // Social guess if needed (simultaneous mode: click Submit after both selections)
      if (doSocialGuess) {
        await pages[i].waitForTimeout(500);
        await makeSocialGuess(pages[i], i % 2 === 0 ? 'same' : 'different');
        // Autocommit indices: skip the Submit click so the timer expiry triggers auto-commit
        if (autocommitIndices.includes(i)) continue;
        // Click the simultaneous Submit button to commit both selections
        try {
          await pages[i].locator(SIMULTANEOUS_SUBMIT).click({ timeout: 2000 });
        } catch {
          // Fallback: button may not exist if not in simultaneous mode
        }
      }
    }
  }
  await pages[0]?.waitForTimeout(500);

  // When players are skipped or autocommitting, the round won't advance until
  // the stage timer expires. Wait for the full round cycle.
  const needsTimerExpiry = skipIndices.length > 0 || autocommitIndices.length > 0;
  if (needsTimerExpiry) {
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
      // Determine which timer applies (Phase 2 uses shorter duration)
      const monitorInfo = await getPlayerInfo(monitorPage);
      const selectionTimeout = monitorInfo?.phase === 2
        ? PHASE2_SELECTION_DURATION
        : SELECTION_DURATION;

      // Wait for Feedback stage (selection timer must expire first)
      const reachedFeedback = await waitForStage(
        monitorPage,
        'Feedback',
        (selectionTimeout + 15) * 1000,
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
  numRounds = ROUNDS_PER_BLOCK,
  options: CompleteRoundOptions = {},
): Promise<void> {
  for (let r = 0; r < numRounds; r++) {
    await playRound(pages, options);
  }
}

/**
 * Handle transition screen (click Continue for all).
 *
 * After the last round of a phase, the flow is:
 *   Feedback → (all submit or timer) → Phase 2 transition/Bonus info → (all submit or timer) → next stage
 *
 * This function handles BOTH clicks:
 * 1. Submit any pending Feedback stage
 * 2. Wait for the transition stage to appear
 * 3. Submit the transition stage
 */
export async function handleTransition(pages: Page[], timeout = 120_000): Promise<void> {
  // Find a monitor page that's still in the game (skip sorry-screen pages)
  let monitorPage = pages[0];
  for (const page of pages) {
    if (await isInGame(page)) {
      monitorPage = page;
      break;
    }
  }

  // Step 1: Submit any pending Feedback stage (skip sorry-screen pages)
  for (const page of pages) {
    if (await isInGame(page)) {
      await clickContinue(page, 5000);
    }
  }
  await monitorPage.waitForTimeout(1000);

  // Step 2: Wait for the transition stage to appear
  const transitionStages = ['Phase 2 transition', 'Bonus info'];
  const start = Date.now();
  let foundTransition = false;
  while (Date.now() - start < timeout) {
    const info = await getPlayerInfo(monitorPage);
    if (!info) break; // Player left game
    if (info.stageName && transitionStages.includes(info.stageName)) {
      foundTransition = true;
      break;
    }
    // If already past transition (in Phase 2 Selection or Feedback), return early
    if (info.phase === 2 && (info.stageName === 'Selection' || info.stageName === 'Feedback')) return;
    await monitorPage.waitForTimeout(1000);
  }

  if (foundTransition) {
    // Wait for all pages to reach the transition stage
    await monitorPage.waitForTimeout(2000);

    // Step 3: Click Continue on the transition stage for all active pages
    for (const page of pages) {
      if (!(await isInGame(page))) continue;
      try {
        await page.getByRole('button', { name: /continue/i }).waitFor({ state: 'visible', timeout: 10_000 });
        await page.getByRole('button', { name: /continue/i }).click();
      } catch {
        await clickContinue(page, 2000);
      }
    }
  }
  await monitorPage.waitForTimeout(1000);
}

// ============ EXIT SURVEY ============

export async function completeExitSurvey(page: Page): Promise<void> {
  // The ExitSurvey component (client/src/intro-exit/ExitSurvey.jsx) is a
  // three-page flow: page 1 required questions ("Next"), page 2 demographics
  // ("Submit"), page 3 confirmation with the Prolific code. Page 3 has no
  // button: the code stays on screen (data-prolific-code) until the tab is
  // closed. Removed players (disbanded, too few groups, low accuracy, batch
  // stopped) answer both pages too, but page 2's submit sends them to the
  // Sorry screen instead of page 3.

  // ── Page 1: required questions (gates the "Next" button) ──
  await page.locator('input[name="understood"][value="yes"]').click();
  await page.locator('input[name="groupIdentification"][value="5"]').click();
  await page.locator('input[name="groupCloseness"][value="5"]').click();
  await page.locator('input[name="groupLanguage"][value="yes"]').click();
  // fill() alone does not always fire React's onChange (which gates the
  // "Next" button on strategy), so dispatch an input event after filling.
  const strategy = page.locator('textarea[name="strategy"]');
  await strategy.fill('Test strategy');
  await strategy.dispatchEvent('input');

  // Page 1's submit button is labelled "Next" and stays disabled until every
  // required field is set; Playwright's actionability wait covers the React
  // state update that enables it.
  await page.getByRole('button', { name: /^next$/i }).click();

  // ── Page 2: demographics (age, gender, feltHuman gate the "Submit" button) ──
  const ageInput = page.locator('input[name="age"]');
  await ageInput.waitFor({ state: 'visible', timeout: 10_000 });
  await ageInput.fill('25');
  await ageInput.dispatchEvent('input'); // ensure React onChange fires (gates Submit)
  await page.locator('select[name="gender"]').selectOption('prefer-not-to-say');
  await page.locator('input[name="feltHuman"][value="yes"]').click();
  // Optional page-2 fields
  await page.locator('input[name="education"][value="bachelors"]').click();
  await page.locator('textarea[name="fair"]').fill('Yes');
  await page.locator('textarea[name="feedback"]').fill('Test feedback');

  await page.getByRole('button', { name: /^submit$/i }).click();

  // ── Page 3: confirmation with the Prolific code (nothing to click) ──
  // Removed players are routed to the Sorry screen here instead; wait for
  // whichever appears. The confirmation is the exit-survey container once it
  // carries the completion code.
  const confirmation = page.locator(`${EXIT_SURVEY}[data-prolific-code]`);
  const sorry = page.locator(SORRY_SCREEN);
  await confirmation.or(sorry).first().waitFor({ state: 'visible', timeout: 10_000 });
}

/**
 * Complete the exit survey for all disbanded players in the given page list.
 * Disbanded players see ExitSurvey before Sorry. This helper finds them,
 * submits the survey, and waits for them to reach the Sorry page.
 */
export async function completeDisbandedExitSurveys(pages: Page[]): Promise<void> {
  for (const page of pages) {
    const exitSurvey = page.locator(EXIT_SURVEY);
    if ((await exitSurvey.count()) > 0) {
      await completeExitSurvey(page);
      // Wait for Sorry screen to appear after survey submission
      await page.locator(SORRY_SCREEN).waitFor({ state: 'visible', timeout: 10_000 });
    }
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
  try {
    // Use Playwright's native waitFor (MutationObserver-based) instead of manual polling.
    // This catches DOM changes in real-time, even if the sorry screen briefly disappears
    // during Empirica's transition from game view to exit steps.
    // Also detect exit-survey (disbanded players see ExitSurvey before Sorry).
    await page.locator('[data-testid="sorry-screen"], [data-testid="quiz-failed-screen"], [data-testid="exit-survey"]')
      .first()
      .waitFor({ state: 'attached', timeout });
    // Small delay for React to finish rendering data attributes
    await page.waitForTimeout(200);
    return await getExitInfo(page);
  } catch {
    // Fallback: try polling once more (locator may have missed it due to frame changes)
    return await getExitInfo(page);
  }
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
    // Check via locator (more reliable than page.evaluate for detecting DOM presence)
    const sorryLocator = page.locator('[data-testid="sorry-screen"]');
    const quizFailLocator = page.locator('[data-testid="quiz-failed-screen"]');
    const exitSurveyLocator = page.locator('[data-testid="exit-survey"]');
    const hasSorry = (await sorryLocator.count()) > 0;
    const hasQuizFail = (await quizFailLocator.count()) > 0;
    const hasExitSurvey = (await exitSurveyLocator.count()) > 0;
    if (hasSorry || hasQuizFail || hasExitSurvey) {
      const info = await getExitInfo(page);
      if (info) {
        removed.push({ page, info });
      }
    }
  }
  return removed;
}
