/**
 * TEST_PLAN 11.1: Refer Condition Score Display
 *
 * In refer conditions, scores update in real-time. Set up a refer_separated
 * game, complete a round where listeners click correctly (playRound clicks
 * the correct tangram by default). After the round, check that the score
 * display shows a non-zero value in the Profile section of the page.
 */
import { test, expect } from '@playwright/test';
import { LISTENER_CORRECT_POINTS, SPEAKER_MAX_POINTS_PER_ROUND } from '../helpers/constants';
import { PlayerManager } from '../helpers/player-manager';
import { createBatch } from '../helpers/admin';
import { getPlayerInfo, playRound, getActivePlayers, waitForFeedback, readScore } from '../helpers/game-actions';
import { expectPlayerInGame } from '../helpers/assertions';

test.describe.serial('Score Display: Refer Scores (TEST_PLAN 11.1)', () => {
  let pm: PlayerManager;

  test.beforeAll(async ({ browser }) => {
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await createBatch(adminPage, 'refer_separated');
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
    for (const page of pages) {
      await expect(page.locator('[data-player-name]')).toBeVisible();
      expect(await readScore(page)).toBe(0);
    }
  });

  test('scores update after a correct round: listeners and speakers earn exactly their points', async () => {
    const pages = pm.getPages();

    // Roles for the round about to be played
    const roles: Record<number, string | null> = {};
    for (let i = 0; i < pages.length; i++) {
      roles[i] = (await getPlayerInfo(pages[i]))?.role ?? null;
    }
    expect(Object.values(roles).filter((r) => r === 'speaker').length).toBe(3);

    // All listeners click the correct tangram
    await playRound(pages);
    const feedbackReached = await waitForFeedback(pages[0], 30_000);
    expect(feedbackReached).toBe(true);

    // Every listener earns LISTENER_CORRECT_POINTS; every speaker earns the full
    // speaker share because both listeners were correct.
    for (let i = 0; i < pages.length; i++) {
      const expected = roles[i] === 'speaker' ? SPEAKER_MAX_POINTS_PER_ROUND : LISTENER_CORRECT_POINTS;
      await expect
        .poll(() => readScore(pages[i]), { timeout: 15_000, message: `score of page ${i} (${roles[i]})` })
        .toBe(expected);
    }
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
