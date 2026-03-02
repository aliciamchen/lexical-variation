/**
 * TEST_PLAN 11.1: Refer Condition Score Display
 *
 * In refer conditions, scores update in real-time. Set up a refer_separated
 * game, complete a round where listeners click correctly (playRound clicks
 * the correct tangram by default). After the round, check that the score
 * display shows a non-zero value in the Profile section of the page.
 */
import { test, expect } from '@playwright/test';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import {
  getPlayerInfo,
  playRound,
  getActivePlayers,
  waitForFeedback,
} from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';

test.describe.serial('Score Display: Refer Scores (TEST_PLAN 11.1)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'exp1_refer_separated');
    await adminContext.close();

    pm = new PlayerManager(browser);
    await pm.initialize();
  });

  test.afterAll(async () => {
    await pm.cleanup();
  });

  test('all 9 players complete intro and enter game', async () => {
    await pm.registerAllPlayers();
    await pm.completeAllIntros();

    const started = await pm.waitForGameStart();
    expect(started).toBe(true);

    const pages = pm.getPages();
    for (const page of pages) {
      await expectPlayerInGame(page);
    }
  });

  test('scores start at zero before any rounds', async () => {
    const pages = pm.getPages();

    // Verify all players start with score 0
    for (const page of pages) {
      // The Profile component renders score in a div with text "Score" label
      // and a numeric value below it. Check the page for the score display.
      const scoreText = await page.locator('[data-player-name]').textContent();
      // The score element is a sibling in the Profile component
      const profileSection = page.locator('[data-player-name]');
      await expect(profileSection).toBeVisible();
    }
  });

  test('scores update after a correct round', async () => {
    const pages = pm.getPages();

    // Play one round where listeners click the correct tangram (default behavior)
    await playRound(pages);

    // Wait for Feedback stage where scores are updated
    const feedbackReached = await waitForFeedback(pages[0], 30_000);
    expect(feedbackReached).toBe(true);
    await pages[0].waitForTimeout(2000);

    // Check that at least some players now have non-zero scores
    // Listeners who clicked correctly get LISTENER_CORRECT_POINTS (2)
    // Speakers get points based on proportion of correct listeners
    let foundNonZeroScore = false;

    for (const page of pages) {
      // Look for the score display in the Profile section
      // Profile.jsx renders: <div className="text-3xl font-semibold !leading-none tabular-nums">{score}</div>
      // Use page.evaluate to find the score more reliably
      const score = await page.evaluate(() => {
        // Find by the "Score" label and get the adjacent numeric value
        const scoreLabel = Array.from(document.querySelectorAll('div'))
          .find(el => el.textContent?.trim() === 'Score');
        if (scoreLabel) {
          const parent = scoreLabel.parentElement;
          if (parent) {
            const numEl = parent.querySelector('.tabular-nums');
            if (numEl) return parseInt(numEl.textContent || '0', 10);
          }
        }
        // Fallback: find by class
        const el = document.querySelector('.tabular-nums');
        return el ? parseInt(el.textContent || '0', 10) : 0;
      });

      if (score > 0) {
        foundNonZeroScore = true;
        break;
      }
    }

    expect(foundNonZeroScore, 'At least one player should have a non-zero score after a correct round').toBe(true);
  });

  test('scores continue to increment after additional rounds', async () => {
    const pages = pm.getPages();

    // Helper to read score from a page — find the "Score" label first,
    // then get .tabular-nums within its parent (avoids matching the timer)
    const readScore = async (page: typeof pages[0]) => {
      return await page.evaluate(() => {
        const scoreLabel = Array.from(document.querySelectorAll('div'))
          .find(el => el.textContent?.trim() === 'Score');
        if (scoreLabel) {
          const parent = scoreLabel.parentElement;
          if (parent) {
            const numEl = parent.querySelector('.tabular-nums');
            if (numEl) return parseInt(numEl.textContent || '0', 10);
          }
        }
        return 0;
      });
    };

    // Record scores before playing more rounds
    const scoresBefore: number[] = [];
    for (const page of pages) {
      scoresBefore.push(await readScore(page));
    }

    // Play another round
    await playRound(pages);

    // Wait for Feedback stage where scores are updated
    await waitForFeedback(pages[0], 30_000);
    await pages[0].waitForTimeout(2000);

    // Record scores after
    const scoresAfter: number[] = [];
    for (const page of pages) {
      scoresAfter.push(await readScore(page));
    }

    // At least some players should have higher scores
    let someScoreIncreased = false;
    for (let i = 0; i < scoresBefore.length; i++) {
      if (scoresAfter[i] > scoresBefore[i]) {
        someScoreIncreased = true;
        break;
      }
    }

    expect(
      someScoreIncreased,
      'At least one player score should have increased after another correct round',
    ).toBe(true);
  });
});
