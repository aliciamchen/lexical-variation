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
   * Navigate all players to the base URL (shows identifier page)
   */
  async registerAllPlayers(): Promise<void> {
    for (let i = 0; i < this.pages.length; i++) {
      const page = this.pages[i];
      await page.goto('/');
      await page.waitForTimeout(500);
    }
  }

  /**
   * Complete intro (consent + instructions + quiz) for all players
   */
  async completeAllIntros(): Promise<void> {
    // Run intros in parallel for speed
    await Promise.all(
      this.pages.map((page) => completeIntro(page))
    );
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
