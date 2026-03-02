import { Browser, BrowserContext, Page } from '@playwright/test';
import { PLAYER_COUNT } from './constants';
import { completeIntro } from './game-actions';
import { GAME_CONTAINER } from './selectors';

export class PlayerManager {
  private contexts: BrowserContext[] = [];
  private pages: Page[] = [];
  private browser: Browser;
  private count: number;

  constructor(browser: Browser, count = PLAYER_COUNT) {
    this.browser = browser;
    this.count = count;
  }

  async initialize(): Promise<void> {
    for (let i = 0; i < this.count; i++) {
      const context = await this.browser.newContext();
      const page = await context.newPage();
      this.contexts.push(context);
      this.pages.push(page);
    }
  }

  /**
   * Navigate all players to the base URL (shows identifier page).
   * Includes retry logic for server connectivity issues.
   * Waits for the Empirica UI to render before continuing.
   */
  async registerAllPlayers(): Promise<void> {
    for (let i = 0; i < this.pages.length; i++) {
      const page = this.pages[i];

      // Retry goto up to 3 times for server connectivity
      let success = false;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          await page.goto('/', { timeout: 30_000 });
          success = true;
          break;
        } catch {
          if (attempt === 2) throw new Error(`Player ${i}: page.goto failed after 3 attempts`);
          await new Promise(r => setTimeout(r, 3000));
        }
      }

      // Wait for Empirica UI to render (consent dialog or identifier textbox)
      if (success) {
        const start = Date.now();
        while (Date.now() - start < 15_000) {
          const agree = page.getByRole('button', { name: /agree/i });
          const textbox = page.getByRole('textbox');
          if ((await agree.count()) > 0 || (await textbox.count()) > 0) break;
          await page.waitForTimeout(500);
        }
      }

      await page.waitForTimeout(300);
    }
  }

  /**
   * Complete intro (consent + instructions + quiz) for all players.
   * Runs sequentially to avoid race conditions with the Empirica backend.
   * Pass condition for exp2 treatments that have an extra quiz question.
   */
  async completeAllIntros(condition?: string): Promise<void> {
    // Run intros sequentially to reduce server load and avoid race conditions.
    // Parallel execution can overwhelm the Empirica websocket backend.
    for (const page of this.pages) {
      await completeIntro(page, condition ? { condition } : undefined);
    }
  }

  /**
   * Wait for all players to enter the game (game container visible)
   */
  async waitForGameStart(timeout = 120_000): Promise<boolean> {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      let allInGame = true;
      for (const page of this.pages) {
        const container = page.locator(GAME_CONTAINER);
        if (await container.count() === 0) {
          allInGame = false;
          break;
        }
      }
      if (allInGame) return true;
      await new Promise(r => setTimeout(r, 1000));
    }
    return false;
  }

  getPages(): Page[] {
    return this.pages;
  }

  getPage(index: number): Page {
    return this.pages[index];
  }

  /**
   * Get pages that are still in the game (have game-container)
   */
  async getActivePages(): Promise<Page[]> {
    const active: Page[] = [];
    for (const page of this.pages) {
      const container = page.locator(GAME_CONTAINER);
      if (await container.count() > 0) {
        active.push(page);
      }
    }
    return active;
  }

  /**
   * Get pages grouped by their current group attribute
   */
  async getPagesByGroup(): Promise<Record<string, Page[]>> {
    const groups: Record<string, Page[]> = {};
    for (const page of this.pages) {
      const container = page.locator(GAME_CONTAINER);
      if (await container.count() > 0) {
        const group = await container.getAttribute('data-player-group');
        if (group) {
          if (!groups[group]) groups[group] = [];
          groups[group].push(page);
        }
      }
    }
    return groups;
  }

  async cleanup(): Promise<void> {
    for (const context of this.contexts) {
      await context.close().catch(() => {});
    }
    this.contexts = [];
    this.pages = [];
  }
}
