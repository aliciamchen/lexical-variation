---
name: test-experiment
description: Run automated tests for the Empirica experiment using Playwright MCP (project)
permissions:
  allow:
    - "mcp__playwright__browser_navigate"
    - "mcp__playwright__browser_snapshot"
    - "mcp__playwright__browser_click"
    - "mcp__playwright__browser_type"
    - "mcp__playwright__browser_run_code"
    - "mcp__playwright__browser_tabs"
    - "mcp__playwright__browser_take_screenshot"
    - "mcp__playwright__browser_handle_dialog"
    - "mcp__playwright__browser_select_option"
    - "mcp__playwright__browser_wait_for"
    - "mcp__playwright__browser_close"
    - "mcp__playwright__browser_evaluate"
    - "mcp__playwright__browser_fill_form"
    - "mcp__playwright__browser_press_key"
    - "mcp__playwright__browser_resize"
    - "Bash(empirica:*)"
    - "Bash(pkill:*)"
    - "Bash(lsof:*)"
    - "Bash(curl:*)"
    - "Bash(mkdir:*)"
    - "Bash(unzip:*)"
    - "Bash(ls:*)"
    - "Bash(sleep:*)"
    - "Bash(tail:*)"
    - "Bash(grep:*)"
    - "Bash(kill:*)"
    - "Read"
    - "KillShell"
---

# Test Experiment Skill

This skill automates testing of the Empirica reference game experiment using Playwright MCP.

## Test Plan

**See `experiment/TEST_PLAN.md` for the comprehensive test plan.** The test plan covers:
- Happy path tests for all 3 conditions (refer_separated, refer_mixed, social_mixed)
- Chat and communication tests
- Dropout and attrition scenarios
- Lobby and pre-game tests
- UI/UX verification
- Timing and timeout tests
- Data integrity verification
- Compensation verification

## Prerequisites

Before running tests:
1. Start the Empirica server: `cd experiment && rm .empirica/local/tajriba.json && empirica`
2. Ensure Playwright MCP is connected

## Test Mode Configuration

Set `TEST_MODE = true` in `experiment/shared/constants.js` for faster testing:

| Setting | TEST_MODE=true | TEST_MODE=false (Production) |
|---------|----------------|------------------------------|
| SELECTION_DURATION | 120s | 45s |
| MAX_IDLE_ROUNDS | 5 | 2 |
| PHASE_1_BLOCKS | 3 | 6 |
| PHASE_2_BLOCKS | 2 | 6 |

**Note:** `PHASE_1_BLOCKS` is set to 3 in test mode to match `ACCURACY_CHECK_BLOCKS` (the number of blocks checked for the Phase 1 accuracy threshold).

This makes tests faster and gives more time for manual inspection. **Remember to set back to `false` for production!**

## Screenshot Path Notes

**Important:** Playwright MCP saves screenshots relative to `.playwright-mcp/` directory. Use relative paths:
```javascript
// Correct - relative path within .playwright-mcp
await page.screenshot({ path: 'test-screenshots/01-player-page.png' });

// Incorrect - absolute path may fail
await page.screenshot({ path: '/Users/.../experiment/test-screenshots/01-player-page.png' });
```

---

## Test Data Attributes

The following data attributes are exposed on the client UI to help with automated testing:

### Profile Component (`Profile.jsx`)
The profile header exposes player identity:
```javascript
// Selector: [data-player-name] or [data-player-group]
const el = document.querySelector('[data-player-name]');
el.getAttribute('data-player-name');  // e.g., "Repi"
el.getAttribute('data-player-group'); // e.g., "A", "B", or "C"
```

### Refgame Component (`Refgame.jsx`)
The task container exposes game state:
```javascript
// Selector: .task
const el = document.querySelector('.task');
el.getAttribute('data-target-index');   // e.g., "2" (0-5, position in tangram grid)
el.getAttribute('data-role');           // "speaker" or "listener"
el.getAttribute('data-current-group');  // e.g., "A", "B", or "C"
```

### Game Component (`Game.jsx`)
The game container exposes overall game state:
```javascript
// Selector: [data-testid="game-container"]
const el = document.querySelector('[data-testid="game-container"]');
el.getAttribute('data-game-phase');     // e.g., "1" or "2"
el.getAttribute('data-game-block');     // e.g., "0", "1", "2", etc.
el.getAttribute('data-game-round');     // e.g., "0"-"5" (target number within block)
el.getAttribute('data-stage-name');     // e.g., "Selection", "Feedback"
el.getAttribute('data-condition');      // e.g., "refer_separated", "refer_mixed", "social_mixed"
el.getAttribute('data-player-group');   // e.g., "A", "B", or "C" (current group)
```

### Exit/Sorry Screens (`Sorry.jsx`, `Quiz.jsx`)
Exit screens expose removal reason and compensation info:
```javascript
// Selector: [data-testid="sorry-screen"] or [data-testid="quiz-failed-screen"]
const el = document.querySelector('[data-testid="sorry-screen"]');
el.getAttribute('data-exit-reason');    // e.g., "player timeout", "group disbanded", "low accuracy", "lobby_timeout"
el.getAttribute('data-prolific-code');  // e.g., "DISBANDED2026", "TIMEOUT2026", "QUIZFAIL2026", "none"
el.getAttribute('data-partial-pay');    // e.g., "0.82" (dollars)
el.getAttribute('data-player-id');      // Empirica player ID
```

### Helper Function to Get Player Info
```javascript
async function getPlayerInfo(page) {
  return await page.evaluate(() => {
    const profile = document.querySelector('[data-player-name]');
    const task = document.querySelector('.task');
    const game = document.querySelector('[data-testid="game-container"]');
    return {
      name: profile?.getAttribute('data-player-name'),
      originalGroup: profile?.getAttribute('data-player-group'),
      currentGroup: task?.getAttribute('data-current-group'),
      role: task?.getAttribute('data-role'),
      targetIndex: parseInt(task?.getAttribute('data-target-index') ?? '-1', 10),
      phase: parseInt(game?.getAttribute('data-game-phase') ?? '0', 10),
      block: parseInt(game?.getAttribute('data-game-block') ?? '-1', 10),
      round: parseInt(game?.getAttribute('data-game-round') ?? '-1', 10),
      stageName: game?.getAttribute('data-stage-name'),
      condition: game?.getAttribute('data-condition')
    };
  });
}
```

### Helper Function to Detect Exit Screens
```javascript
async function getExitInfo(page) {
  return await page.evaluate(() => {
    const sorry = document.querySelector('[data-testid="sorry-screen"]');
    const quizFailed = document.querySelector('[data-testid="quiz-failed-screen"]');
    const el = sorry || quizFailed;
    if (!el) return null;
    return {
      exitReason: el.getAttribute('data-exit-reason'),
      prolificCode: el.getAttribute('data-prolific-code'),
      partialPay: el.getAttribute('data-partial-pay'),
      playerId: el.getAttribute('data-player-id')
    };
  });
}
```

---

## Test Utilities File

For complex tests, copy helper functions from `test-utils.js` in this skill directory. The file contains:

- **Player Info Helpers**: `getPlayerInfo()`, `getExitInfo()`, `getPlayerState()`
- **Game Action Helpers**: `completeIntro()`, `speakerSendMessage()`, `listenerClickTangram()`, `makeSocialGuess()`
- **Round Completion**: `completeRound()` with options for skip indices, wrong groups, social guessing
- **Player Management**: `getPlayerPages()`, `getActivePlayers()`, `getPlayersByGroup()`, `getRemovedPlayers()`
- **Wait Helpers**: `waitForStage()`, `waitForFeedback()`, `waitForAnyExit()`, `waitForGameStart()`
- **Verification**: `verifyGroupConsistency()`, `verifyNoSoloPlayers()`

Example usage:
```javascript
// Controlled accuracy test - Group B clicks wrong
await completeRound(playerPages, { wrongGroups: ['B'] });

// Idle test - skip player at index 0
await completeRound(playerPages, { skipIndices: [0] });

// Check for removed players
const removed = await getRemovedPlayers(playerPages);
console.log(`${removed.length} players removed`);
```

---

## Quick Start

### 1. Preflight Check

```bash
# Kill stale processes and verify server
lsof -ti:3000,8844 | xargs kill -9 2>/dev/null || true
cd experiment && rm -f .empirica/local/tajriba.json && empirica
```

### 2. Create Batch (Admin Console)

```javascript
browser_navigate({ url: "http://localhost:3000/admin" })
// Click "New Batch" → Select treatment → Create → Start
```

**Available Treatments:**
| Treatment | Players | Condition |
|-----------|---------|-----------|
| Refer Separated (9 players) | 9 | refer_separated |
| Refer Mixed (9 players) | 9 | refer_mixed |
| Social Mixed (9 players) | 9 | social_mixed |

### 3. Create Players and Complete Intro

```javascript
// Create 9 player tabs and complete intro (parallel)
browser_run_code:
async (page) => {
  const context = page.context();

  // Create 9 player tabs
  for (let i = 0; i < 9; i++) {
    const newPage = await context.newPage();
    await newPage.goto('http://localhost:3000');
    await newPage.waitForTimeout(300);
    await newPage.getByRole('button', { name: /new participant/i }).click();
    await newPage.waitForTimeout(300);
  }

  // Complete intro for all players in parallel
  const playerPages = context.pages().filter(p => p.url().includes('participantKey'));

  await Promise.all(playerPages.map(async (p, i) => {
    // Identifier
    await p.getByRole('textbox').fill(`player${i + 1}`);
    await p.waitForTimeout(100);
    await p.getByRole('button', { name: /enter/i }).click();
    await p.waitForTimeout(200);

    // Consent
    await p.getByRole('button', { name: /consent/i }).click();
    await p.waitForTimeout(200);

    // 5 intro pages
    for (let j = 0; j < 5; j++) {
      await p.getByRole('button', { name: /next/i }).click();
      await p.waitForTimeout(100);
    }

    // Quiz answers
    await p.getByRole('radio', { name: /describe the target picture/i }).click();
    await p.getByRole('radio', { name: /removed from the game/i }).click();
    await p.getByRole('radio', { name: /only descriptions of the current/i }).click();
    await p.getByRole('radio', { name: /listeners must wait/i }).click();
    await p.getByRole('radio', { name: /mixed up/i }).click();
    await p.getByRole('radio', { name: /different positions for each player/i }).click();

    p.once('dialog', async dialog => await dialog.accept());
    await p.getByRole('button', { name: /submit/i }).click();
    await p.waitForTimeout(400);
  }));

  return `All ${playerPages.length} players completed intro`;
}
```

### 4. Play Game Rounds

```javascript
// Play through all rounds using data attributes for reliability
browser_run_code:
async (page) => {
  const context = page.context();
  const playerPages = context.pages().filter(p => p.url().includes('participantKey'));

  // Helper to get player info from data attributes
  async function getPlayerInfo(p) {
    try {
      return await p.evaluate(() => {
        const profile = document.querySelector('[data-player-name]');
        const task = document.querySelector('.task');
        return {
          name: profile?.getAttribute('data-player-name'),
          group: profile?.getAttribute('data-player-group'),
          role: task?.getAttribute('data-role'),
          targetIndex: parseInt(task?.getAttribute('data-target-index') ?? '-1', 10)
        };
      });
    } catch { return null; }
  }

  async function completeRound(roundNum) {
    // Click Continue buttons
    for (const p of playerPages) {
      try { await p.getByRole('button', { name: /continue/i }).click({ timeout: 500 }); } catch {}
    }
    await page.waitForTimeout(300);

    // Speakers send messages (use data-role attribute)
    for (const p of playerPages) {
      const info = await getPlayerInfo(p);
      if (info?.role === 'speaker') {
        const input = p.getByRole('textbox', { name: 'Say something' });
        if (await input.count() > 0) {
          await input.fill(`r${roundNum}`);
          await input.press('Enter');
        }
      }
    }
    await page.waitForTimeout(300);

    // Listeners click correct tangram (use data-target-index from their group's speaker)
    // For simple happy path, just click first tangram
    for (const p of playerPages) {
      const info = await getPlayerInfo(p);
      if (info?.role === 'listener') {
        const tangrams = p.locator('.tangrams.grid > div');
        if (await tangrams.count() > 0) await tangrams.first().click();
      }
    }
    await page.waitForTimeout(400);
  }

  // Phase 1: 6 blocks × 6 rounds = 36 rounds (or fewer in TEST_MODE)
  for (let r = 1; r <= 36; r++) {
    await completeRound(r);
    if (r % 6 === 0) console.log(`Block ${r/6} complete`);
  }

  // Phase transition
  await page.waitForTimeout(2000);
  for (const p of playerPages) {
    try { await p.getByRole('button', { name: /continue/i }).click({ timeout: 5000 }); } catch {}
  }
  await page.waitForTimeout(1000);

  // Phase 2: 6 blocks × 6 rounds = 36 rounds (or fewer in TEST_MODE)
  for (let r = 37; r <= 72; r++) {
    await completeRound(r);
    if ((r - 36) % 6 === 0) console.log(`Phase 2 Block ${(r-36)/6} complete`);
  }

  return "Game complete";
}
```

---

## Critical Element Selectors

### Quiz Answers
```javascript
await page.getByRole('radio', { name: /describe the target picture/i }).click();
await page.getByRole('radio', { name: /removed from the game/i }).click();
await page.getByRole('radio', { name: /only descriptions of the current/i }).click();
await page.getByRole('radio', { name: /listeners must wait/i }).click();
await page.getByRole('radio', { name: /mixed up/i }).click();
await page.getByRole('radio', { name: /different positions for each player/i }).click();
```

### Tangram Click
```javascript
const tangrams = page.locator('.tangrams.grid > div');
await tangrams.first().click();
```

### Chat Input
```javascript
const textbox = page.getByRole('textbox', { name: 'Say something' });
await textbox.fill("message");
await textbox.press('Enter');
```

### Identifier Entry
```javascript
await page.getByRole('textbox').fill('player1');
await page.getByRole('button', { name: /enter/i }).click();
```

### Social Guess Buttons (social_mixed Phase 2)
```javascript
// After tangram click, social guess UI appears
await page.getByRole('button', { name: /same group/i }).click();
// OR
await page.getByRole('button', { name: /different group/i }).click();
```

---

## Helper Functions

### Wait for Feedback Stage
The feedback stage only lasts 10 seconds. Use polling to catch it:
```javascript
async function waitForFeedback(page, timeout = 30000) {
  for (let i = 0; i < timeout/500; i++) {
    const content = await page.content();
    if (content.includes('Correct!') || content.includes('Ooops') ||
        content.includes('You earned') || content.includes('points this round')) {
      return true;
    }
    await page.waitForTimeout(500);
  }
  return false;
}
```

### Scroll Inner Containers
Some pages (like intro pages) have scrollable inner containers:
```javascript
async function scrollToBottom(page) {
  await page.evaluate(() => {
    const container = document.querySelector('.overflow-auto, .overflow-y-auto');
    if (container) {
      container.scrollTo(0, container.scrollHeight);
      return { scrolled: 'container', height: container.scrollHeight };
    }
    window.scrollTo(0, document.body.scrollHeight);
    return { scrolled: 'window', height: document.body.scrollHeight };
  });
}
```

### Robust Dialog Handling
Set up dialog handler that won't error if already handled:
```javascript
// Global dialog handler - set once at start
page.on('dialog', async dialog => {
  try { await dialog.accept(); } catch {}
});

// Or for specific dialogs
page.once('dialog', async dialog => await dialog.accept());
```

### Wait for Exit Screen
Poll for various exit screens:
```javascript
async function waitForExitScreen(pages, timeout = 120000) {
  for (let i = 0; i < timeout/2000; i++) {
    for (const p of pages) {
      try {
        const content = await p.content();
        if (content.includes('Sorry!') || content.includes('Removed for Inactivity') ||
            content.includes('Group Disbanded') || content.includes('TIMEOUT2026') ||
            content.includes('DISBANDED2026') || content.includes('QUIZFAIL2026')) {
          return { found: true, page: p, content };
        }
      } catch {}
    }
    await new Promise(r => setTimeout(r, 2000));
  }
  return { found: false };
}
```

---

## Test Scenarios

When invoked, ask the user which test to run from `experiment/TEST_PLAN.md`:

### Happy Path Tests
1. `refer_separated` - 9 players, same groups throughout
2. `refer_mixed` - 9 players, shuffled groups with masked identities in Phase 2
3. `social_mixed` - 9 players, shuffled groups + social guessing in Phase 2

### Dropout/Edge Case Tests
4. `idle-speaker` - Speaker idles for 2 rounds, gets kicked
5. `idle-listener` - Listener idles for 2 rounds, gets kicked
6. `group-disbanded` - 2 players drop, remaining player sees disbanded message
7. `speaker-dropout-mid-block` - Speaker drops mid-block, role reassigned
8. `quiz-failure` - Player fails quiz 3 times

### Accuracy Threshold Tests
9. `accuracy-threshold` - Test Phase 1 accuracy check that removes underperforming groups (see below)

### Comprehensive Tests
10. `social-mixed-comprehensive` - Full test with dropouts, reshuffling, social guessing (see below)

### Data Verification
11. `data-export` - Export and verify all data fields

---

## PHASE 1 ACCURACY THRESHOLD TEST

This test verifies that groups with low listener accuracy in Phase 1 are removed at the Phase 1 → Phase 2 transition.

### Accuracy Threshold Rules

At the end of Phase 1, the system checks each group:
- **Blocks checked:** Last 3 blocks of Phase 1 (configured via `ACCURACY_CHECK_BLOCKS`)
- **Player threshold:** Players must achieve ≥ 66.7% accuracy as listeners (`ACCURACY_THRESHOLD = 2/3`)
- **Group threshold:** At least 2/3 of group members must meet the accuracy threshold (`PLAYER_ACCURACY_THRESHOLD = 2/3`)
- **Outcome:** Groups that don't meet the threshold are removed, players receive proportional compensation

### Test Configuration

**Important:** Set `TEST_MODE = true` and `PHASE_1_BLOCKS = 3` in `experiment/shared/constants.js`:

```javascript
export const TEST_MODE = true;
export const PHASE_1_BLOCKS = TEST_MODE ? 3 : 6; // Must be >= ACCURACY_CHECK_BLOCKS (3)
```

This gives us exactly 3 blocks to test (matching `ACCURACY_CHECK_BLOCKS = 3`).

### Test Plan

| Group | Player Accuracy Strategy | Expected Outcome |
|-------|-------------------------|------------------|
| A | All 3 players click correctly | PASSES (3/3 ≥ 66.7%) |
| B | 2 players click wrong, 1 clicks correct | FAILS (1/3 < 66.7%) → Removed |
| C | All 3 players click correctly | PASSES (3/3 ≥ 66.7%) |

### Test Steps

#### Step 1: Start Server and Create Batch

```bash
# Kill any existing processes
lsof -ti:3000,8844 | xargs kill -9 2>/dev/null || true

# Start fresh server
cd experiment && rm -f .empirica/local/tajriba.json && empirica
```

Then in Playwright:
```javascript
browser_navigate({ url: "http://localhost:3000/admin" })
// Click "New Batch" → Select "Refer Separated (9 players)" → Create → Start
```

#### Step 2: Create 9 Players and Complete Intro

```javascript
browser_run_code:
async (page) => {
  const context = page.context();

  // Create 9 player tabs
  const playerPages = [page];
  for (let i = 1; i < 9; i++) {
    const newPage = await context.newPage();
    await newPage.goto('http://localhost:3000');
    await newPage.waitForTimeout(1000);
    playerPages.push(newPage);
  }

  // Complete intro for all players
  for (let i = 0; i < playerPages.length; i++) {
    const p = playerPages[i];

    // Enter identifier
    await p.locator('input').first().fill(`player${i + 1}`);
    await p.getByRole('button', { name: /enter/i }).click();
    await p.waitForTimeout(500);

    // Consent
    await p.getByRole('button', { name: /consent/i }).click();
    await p.waitForTimeout(300);

    // 5 intro pages
    for (let j = 0; j < 5; j++) {
      await p.getByRole('button', { name: /next/i }).click();
      await p.waitForTimeout(200);
    }

    // Quiz answers
    await p.getByRole('radio', { name: /describe the target picture/i }).click();
    await p.getByRole('radio', { name: /removed from the game/i }).click();
    await p.getByRole('radio', { name: /only descriptions of the current/i }).click();
    await p.getByRole('radio', { name: /listeners must wait/i }).click();
    await p.getByRole('radio', { name: /mixed up/i }).click();
    await p.getByRole('radio', { name: /different positions for each player/i }).click();

    p.once('dialog', async dialog => await dialog.accept());
    await p.getByRole('button', { name: /submit/i }).click();
    await p.waitForTimeout(500);
  }

  return `Created ${playerPages.length} players`;
}
```

#### Step 3: Play Phase 1 with Controlled Accuracy

The key is to use the data attributes to identify player groups and target indices accurately.

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const playerPages = context.pages().filter(p => p.url().includes('participantKey'));

  // Wait for game to start
  await page.waitForTimeout(2000);

  // Helper to get player info from data attributes
  async function getPlayerInfo(p) {
    try {
      return await p.evaluate(() => {
        const profile = document.querySelector('[data-player-name]');
        const task = document.querySelector('.task');
        return {
          name: profile?.getAttribute('data-player-name'),
          group: profile?.getAttribute('data-player-group'),
          role: task?.getAttribute('data-role'),
          targetIndex: parseInt(task?.getAttribute('data-target-index') ?? '-1', 10)
        };
      });
    } catch {
      return null;
    }
  }

  // Helper function to complete a round with controlled accuracy
  async function completeRoundWithAccuracy(roundNum) {
    // Click Continue buttons (feedback → selection transition)
    for (const p of playerPages) {
      try { await p.getByRole('button', { name: /continue/i }).click({ timeout: 500 }); } catch {}
    }
    await page.waitForTimeout(500);

    // Build group → target mapping from speakers
    const groupTargets = {};

    // First, all speakers send messages
    for (const p of playerPages) {
      const info = await getPlayerInfo(p);
      if (info?.role === 'speaker' && info.targetIndex >= 0) {
        groupTargets[info.group] = info.targetIndex;

        // Speaker sends message
        const input = p.getByRole('textbox', { name: 'Say something' });
        if (await input.count() > 0) {
          await input.fill(`round ${roundNum}`);
          await input.press('Enter');
        }
        console.log(`Round ${roundNum}: Group ${info.group} speaker target=${info.targetIndex}`);
      }
    }
    await page.waitForTimeout(500);

    // Listeners click tangrams based on group
    for (const p of playerPages) {
      const info = await getPlayerInfo(p);
      if (info?.role !== 'listener') continue;

      const targetIdx = groupTargets[info.group];
      if (targetIdx === undefined || targetIdx < 0) continue;

      // Groups A and C click correct, Group B clicks wrong
      let clickIdx;
      if (info.group === 'B') {
        clickIdx = (targetIdx + 3) % 6; // Wrong tangram (offset by 3)
      } else {
        clickIdx = targetIdx; // Correct tangram
      }

      const tangrams = p.locator('.tangrams.grid > div');
      const count = await tangrams.count();
      if (count > clickIdx) {
        await tangrams.nth(clickIdx).click();
        const correct = clickIdx === targetIdx;
        console.log(`Round ${roundNum}: ${info.name} (${info.group}) clicked ${clickIdx} (target=${targetIdx}) ${correct ? '✓' : '✗'}`);
      }
    }
    await page.waitForTimeout(500);
  }

  // Phase 1: 3 blocks × 6 rounds = 18 rounds
  for (let r = 1; r <= 18; r++) {
    await completeRoundWithAccuracy(r);
    if (r % 6 === 0) console.log(`=== Block ${r/6} complete ===`);
  }

  return "Phase 1 complete - Groups A,C should pass, Group B should fail";
}
```

#### Step 4: Verify Accuracy Check at Transition

After Phase 1 completes, the transition round triggers the accuracy check.

**Check server logs for:**
```
============ PHASE 1 ACCURACY CHECK ============
Checking blocks: 0, 1, 2 (last 3 blocks of Phase 1)
Accuracy threshold: 66.7%
Player threshold: 66.7% of group must meet accuracy

Group A:
  Repi: 83.3% (10/12) - PASS
  Minu: 75.0% (9/12) - PASS
  Laju: 91.7% (11/12) - PASS
  -> 3/3 players meet threshold (100.0%) - Group PASSES

Group B:
  Hera: 16.7% (2/12) - FAIL
  Zuda: 8.3% (1/12) - FAIL
  Bavi: 75.0% (9/12) - PASS
  -> 1/3 players meet threshold (33.3%) - Group FAILS
  -> Removing group B due to low accuracy
    Removing player ... (Hera)
    -> Proportional pay: $X.XX
    Removing player ... (Zuda)
    -> Proportional pay: $X.XX
    Removing player ... (Bavi)
    -> Proportional pay: $X.XX

Group C:
  Lika: 83.3% (10/12) - PASS
  Felu: 91.7% (11/12) - PASS
  Nori: 75.0% (9/12) - PASS
  -> 3/3 players meet threshold (100.0%) - Group PASSES

Active groups after accuracy check: A, C
============ END ACCURACY CHECK ============
```

#### Step 5: Verify Exit Screens for Removed Players

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const allPages = context.pages().filter(p => p.url().includes('localhost:3000') && !p.url().includes('admin'));

  // Wait for transition to process
  await page.waitForTimeout(2000);

  // Check for "Sorry" screens with "low accuracy" reason
  const results = { removed: [], active: [] };

  for (let i = 0; i < allPages.length; i++) {
    const p = allPages[i];
    const content = await p.content();

    if (content.includes('Sorry') || content.includes('Low Accuracy') || content.includes('ended')) {
      results.removed.push({
        index: i,
        hasPartialPay: content.includes('$') || content.includes('compensation'),
        reason: content.includes('accuracy') ? 'low accuracy' : 'unknown'
      });

      // Screenshot the exit screen
      await p.screenshot({ path: `accuracy-test-removed-player-${i}.png` });
    } else if (content.includes('Phase 2') || content.includes('speaker') || content.includes('listener')) {
      results.active.push(i);
    }
  }

  return `Removed: ${results.removed.length}, Active: ${results.active.length}`;
}
```

#### Step 6: Verify Remaining Groups Continue

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const allPages = context.pages().filter(p => p.url().includes('localhost:3000') && !p.url().includes('admin'));

  // Get active players (those in Phase 2)
  const activePlayers = [];
  for (const p of allPages) {
    const content = await p.content();
    if (content.includes('Phase 2') || content.includes('speaker') || content.includes('listener')) {
      activePlayers.push(p);
    }
  }

  console.log(`${activePlayers.length} players continuing to Phase 2`);

  // Should be 6 players (Groups A and C)
  if (activePlayers.length !== 6) {
    console.log(`WARNING: Expected 6 players, got ${activePlayers.length}`);
  }

  // Play a few Phase 2 rounds to verify game continues normally
  for (let r = 1; r <= 6; r++) {
    // Click Continue
    for (const p of activePlayers) {
      try { await p.getByRole('button', { name: /continue/i }).click({ timeout: 500 }); } catch {}
    }
    await page.waitForTimeout(300);

    // Speakers send messages
    for (const p of activePlayers) {
      const content = await p.content();
      if (content.includes('You are the speaker')) {
        const input = p.getByRole('textbox', { name: 'Say something' });
        if (await input.count() > 0) {
          await input.fill(`phase 2 round ${r}`);
          await input.press('Enter');
        }
      }
    }
    await page.waitForTimeout(200);

    // Listeners click
    for (const p of activePlayers) {
      const content = await p.content();
      if (content.includes('You are a listener')) {
        const tangrams = p.locator('.tangrams.grid > div');
        if (await tangrams.count() > 0) await tangrams.first().click();
      }
    }
    await page.waitForTimeout(300);
  }

  return `Phase 2 continues with ${activePlayers.length} players`;
}
```

### Data Verification

After test, export and verify:

```bash
cd experiment && empirica export
unzip -o $(ls -t export-*.zip | head -1) -d export-accuracy-test
```

**Check in `player.csv`:**
- `ended` field should be `"low accuracy"` for Group B players
- `partialPay` should be non-zero (proportional compensation)
- `is_active` should be `false` for removed players

**Check in `game.csv`:**
- `phase1_accuracy_results` should contain the accuracy data for all groups

### Edge Cases to Test

1. **All groups pass:** Set all listeners to click correctly → all 9 players continue
2. **All groups fail:** Set all listeners to click wrong → game terminates (not enough groups)
3. **Exactly 2/3 threshold:** Test with exactly 2 out of 3 players meeting accuracy → group passes
4. **Just below threshold:** Test with 1 out of 3 players meeting accuracy → group fails

### Prolific Code for Low Accuracy

Players removed for low accuracy see the "Sorry" screen with:
- Reason: "Low Accuracy" or similar message
- Compensation: Proportional pay displayed
- Code: Should use existing `DISBANDED2026` or add new `LOWACCURACY2026`

---

## COMPREHENSIVE SOCIAL_MIXED TEST

This is the most comprehensive test scenario, covering:
- 12 players starting intro
- Quiz failure (1 player)
- Lobby timeout (2 players)
- Phase 1 dropouts (2 players from different groups)
- Phase 2 dropouts and group disbanding
- **Mid-block reshuffling** when solo player detected
- Social guessing verification
- Data tracking verification
- Screenshots of every screen type

### Test Setup

```bash
# Create screenshot folder with date
mkdir -p experiment/test-screenshots/$(date +%Y-%m-%d)
```

### Timeline Overview

| Phase | Event | Active Players | Original Groups | Current Groups |
|-------|-------|----------------|-----------------|----------------|
| Intro | 12 players start | 12 | - | - |
| Quiz | 1 fails quiz 3x | 11 | - | - |
| Lobby | 9 matched, 2 timeout | 9 | A(3), B(3), C(3) | Same |
| Phase 1 | Round 1-6: Normal play | 9 | A(3), B(3), C(3) | Same |
| Phase 1 | Round 7-8: A-speaker & B-listener idle | 7 | A(2), B(2), C(3) | Same |
| Transition | Phase 2 transition | 7 | A(2), B(2), C(3) | - |
| Phase 2 | Block 1 start: Reshuffle | 7 | A(2), B(2), C(3) | X(3), Y(2), Z(2) |
| Phase 2 | Block 2 start: Reshuffle | 7 | A(2), B(2), C(3) | Reshuffled |
| Phase 2 | Block 3 Round 2: A-player idles, kicked | 6 | A(1), B(2), C(3) | One group has solo |
| Phase 2 | Block 3 Round 2: A disbands, **MID-BLOCK RESHUFFLE** | 5 | A(0), B(2), C(3) | Immediate reshuffle! |
| Phase 2 | Block 3-6: Continue with 5 players | 5 | A(0), B(2), C(3) | Reshuffled each block |
| End | Exit survey | 5 | - | - |

**Key test: Mid-block reshuffling** - When the last Group A player is kicked for "group disbanded", their partner in the current shuffled group would be left alone. The system should trigger an immediate reshuffle so no one plays solo.

### Screenshot Checklist

Take screenshots at each of these screens. **For scrollable pages, use `fullPage: true` or scroll the inner container.**

Screenshots are saved to `.playwright-mcp/<folder-name>/` directory.

#### Pre-Game (01-12)
- [ ] `01-identifier-entry.png` - Prolific ID entry
- [ ] `02-consent.png` - Consent page
- [ ] `03-intro-page1.png` - Introduction page 1 ("How to play")
- [ ] `04-intro-page2.png` - Introduction page 2 (time/pay info)
- [ ] `05-intro-page3.png` - Introduction page 3 ("Phase 1: Reference Game") - **scroll for bottom**
- [ ] `06-intro-page4.png` - Introduction page 4 (scoring info)
- [ ] `07-intro-page5.png` - Introduction page 5 ("Phase 2" info)
- [ ] `08-quiz.png` - Comprehension quiz
- [ ] `09-quiz-failed.png` - Quiz failed screen (QUIZFAIL2026 code)

#### Game - Phase 1 (10-12)
- [ ] `10-game-phase1-speaker.png` - Speaker view during selection (target highlighted)
- [ ] `11-feedback-stage.png` - Feedback stage showing correct/incorrect
- [ ] `12-game-phase1-listener.png` - Listener view during selection

#### Phase Transition (13)
- [ ] `13-phase2-transition.png` - Phase 2 transition screen (condition-specific)

#### Game - Phase 2 (14-16)
- [ ] `14-phase2-masked-identities.png` - Players shown as "Player" with anonymous avatars
- [ ] `15-social-guess-ui.png` - Social guess UI after tangram click (social_mixed only)
- [ ] `16-bonus-info.png` - End of game bonus/score summary

#### Exit Screens (17-22)
- [ ] `17-exit-survey.png` - Exit survey form
- [ ] `18-finished.png` - Completion screen with Prolific code (C3OIIB3N)
- [ ] `19-phase1-feedback-speaker.png` - Speaker feedback ("You earned X points")
- [ ] `20-phase1-feedback-listener.png` - Listener feedback ("Correct!" or "Ooops")
- [ ] `21-idle-exit-screen.png` - "Removed for Inactivity" (no pay, TIMEOUT2026)
- [ ] `22-disbanded-exit-screen.png` - "Group Disbanded" (proportional pay, DISBANDED2026)

#### Mid-Block Reshuffle Verification
- [ ] Verify server logs show: `MID-BLOCK RESHUFFLE: Solo player detected in Phase 2 mixed`
- [ ] Screenshot before/after reshuffle showing group reassignment
- [ ] Verify no player is left alone after reshuffle

---

### Mid-Block Reshuffle Test

This tests the scenario where a player dropout in Phase 2 would leave someone alone in their shuffled group.

**Scenario:**
1. Start with 9 players in 3 groups (A, B, C)
2. In Phase 1, let 2 players idle out (one from A, one from B) → 7 players remain
3. In Phase 2 Block 3, let another Group A player idle out
4. When Group A disbands, their partner in the current shuffled group would be alone
5. **Mid-block reshuffle triggers** to redistribute remaining players

**Server Log Indicators:**
```
[server] MID-BLOCK RESHUFFLE: Solo player detected in Phase 2 mixed, triggering immediate reshuffling
[server]   -> X active players will be redistributed
[server] Reshuffling groups for mixed condition (balanced)
```

**Data Verification:**
Check `playerRound.csv` - the `current_group` should change mid-block after the reshuffle:
- Round N: Player X in group "A"
- Round N (after reshuffle): Player X in group "B" (different assignment)

**Test Code:**
```javascript
// In Phase 2, make one player idle for 2 rounds
async function triggerMidBlockReshuffle(playerPages, idlePlayerIndex) {
  // Round 1: Player idles
  await completePhase2Round(playerPages, [idlePlayerIndex]);
  console.log('Player idle round 1/2');

  // Round 2: Player kicked, may trigger reshuffle
  await completePhase2Round(playerPages, [idlePlayerIndex]);
  console.log('Player kicked - check server logs for MID-BLOCK RESHUFFLE');

  // Verify remaining players have valid groups
  const activePlayers = await getActivePlayers(playerPages);
  for (const p of activePlayers) {
    const content = await p.content();
    // No player should see "You are alone" or similar
    if (content.includes('alone') || content.includes('no other players')) {
      throw new Error('Player left alone after reshuffle!');
    }
  }
}
```

### Detailed Test Steps

#### Step 1: Create 12 Players and Start Intro

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const screenshotDir = 'experiment/test-screenshots/' + new Date().toISOString().split('T')[0];

  // Resize for consistent screenshots
  await page.setViewportSize({ width: 1280, height: 900 });

  // Take screenshot of initial player page
  await page.goto('http://localhost:3000');
  await page.screenshot({ path: `${screenshotDir}/01-player-page.png` });

  // Create 12 player tabs
  const playerPages = [];
  for (let i = 0; i < 12; i++) {
    const newPage = await context.newPage();
    await newPage.setViewportSize({ width: 1280, height: 900 });
    await newPage.goto('http://localhost:3000');
    await newPage.waitForTimeout(300);
    await newPage.getByRole('button', { name: /new participant/i }).click();
    await newPage.waitForTimeout(500);
    playerPages.push(newPage);
  }

  return `Created ${playerPages.length} player tabs`;
}
```

#### Step 2: Complete Intro for 11 Players, 1 Fails Quiz

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const screenshotDir = 'experiment/test-screenshots/' + new Date().toISOString().split('T')[0];
  const playerPages = context.pages().filter(p => p.url().includes('participantKey'));

  // Take intro screenshots from first player
  const p1 = playerPages[0];

  // Identifier entry
  await p1.getByRole('textbox').fill('player1');
  await p1.screenshot({ path: `${screenshotDir}/02-identifier-entry.png` });
  await p1.getByRole('button', { name: /enter/i }).click();
  await p1.waitForTimeout(500);

  // Consent page
  await p1.screenshot({ path: `${screenshotDir}/03-consent.png`, fullPage: true });
  await p1.getByRole('button', { name: /consent/i }).click();
  await p1.waitForTimeout(500);

  // Intro pages with screenshots
  for (let j = 0; j < 5; j++) {
    await p1.screenshot({ path: `${screenshotDir}/04-intro-page-${j+1}.png`, fullPage: true });
    await p1.getByRole('button', { name: /next/i }).click();
    await p1.waitForTimeout(300);
  }

  // Quiz page
  await p1.screenshot({ path: `${screenshotDir}/09-quiz.png`, fullPage: true });

  // Complete intro for players 1-11 (pass quiz)
  for (let i = 0; i < 11; i++) {
    const p = playerPages[i];
    if (i > 0) {
      await p.getByRole('textbox').fill(`player${i + 1}`);
      await p.getByRole('button', { name: /enter/i }).click();
      await p.waitForTimeout(200);
      await p.getByRole('button', { name: /consent/i }).click();
      await p.waitForTimeout(200);
      for (let j = 0; j < 5; j++) {
        await p.getByRole('button', { name: /next/i }).click();
        await p.waitForTimeout(100);
      }
    }

    // Correct quiz answers
    await p.getByRole('radio', { name: /describe the target picture/i }).click();
    await p.getByRole('radio', { name: /removed from the game/i }).click();
    await p.getByRole('radio', { name: /only descriptions of the current/i }).click();
    await p.getByRole('radio', { name: /listeners must wait/i }).click();
    await p.getByRole('radio', { name: /mixed up/i }).click();
    await p.getByRole('radio', { name: /different positions for each player/i }).click();

    p.once('dialog', async dialog => await dialog.accept());
    await p.getByRole('button', { name: /submit/i }).click();
    await p.waitForTimeout(400);
  }

  // Player 12: Fail quiz 3 times
  const p12 = playerPages[11];
  await p12.getByRole('textbox').fill('player12');
  await p12.getByRole('button', { name: /enter/i }).click();
  await p12.waitForTimeout(200);
  await p12.getByRole('button', { name: /consent/i }).click();
  await p12.waitForTimeout(200);
  for (let j = 0; j < 5; j++) {
    await p12.getByRole('button', { name: /next/i }).click();
    await p12.waitForTimeout(100);
  }

  // Wrong answers 3 times
  for (let attempt = 0; attempt < 3; attempt++) {
    // Select wrong answers
    const radios = await p12.locator('input[type="radio"]').all();
    for (const radio of radios) {
      const name = await radio.getAttribute('name');
      if (name && !await radio.isChecked()) {
        await radio.click();
        break; // Just click first unselected for each question
      }
    }
    // Select first option for each question (some will be wrong)
    await p12.locator('input[type="radio"][value*="click"]').first().click().catch(() => {});
    await p12.locator('input[type="radio"][value*="Nothing"]').first().click().catch(() => {});
    await p12.locator('input[type="radio"][value*="Anything"]').first().click().catch(() => {});
    await p12.locator('input[type="radio"][value*="any time"]').first().click().catch(() => {});
    await p12.locator('input[type="radio"][value*="same places"]').first().click().catch(() => {});
    await p12.locator('input[type="radio"][value*="vague"]').first().click().catch(() => {});

    p12.once('dialog', async dialog => await dialog.accept());
    await p12.getByRole('button', { name: /submit/i }).click();
    await p12.waitForTimeout(500);
  }

  // Screenshot quiz failed
  await p12.screenshot({ path: `${screenshotDir}/10-quiz-failed.png` });

  return "11 players passed quiz, 1 failed";
}
```

#### Step 3: Wait for Game Start (9 players match, 2 timeout)

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const screenshotDir = 'experiment/test-screenshots/' + new Date().toISOString().split('T')[0];
  const playerPages = context.pages().filter(p =>
    p.url().includes('participantKey') &&
    !p.url().includes('player12') // Skip failed player
  );

  // Take lobby screenshot
  const lobbyPlayer = playerPages.find(async p => {
    const content = await p.content();
    return content.includes('Waiting') || content.includes('lobby');
  });
  if (lobbyPlayer) {
    await lobbyPlayer.screenshot({ path: `${screenshotDir}/11-lobby-waiting.png` });
  }

  // Wait for 9 players to be in game (game starts)
  // The other 2 will eventually timeout
  await page.waitForTimeout(5000);

  // Check which players are in game vs still waiting
  let inGame = 0;
  let waiting = 0;
  for (const p of playerPages.slice(0, 11)) {
    const content = await p.content();
    if (content.includes('You are the speaker') || content.includes('You are a listener')) {
      inGame++;
    } else if (content.includes('Waiting')) {
      waiting++;
    }
  }

  return `In game: ${inGame}, Still waiting: ${waiting}`;
}
```

#### Step 4: Phase 1 - Play Rounds with Screenshots

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const screenshotDir = 'experiment/test-screenshots/' + new Date().toISOString().split('T')[0];

  // Get active player pages (in game)
  const allPages = context.pages().filter(p => p.url().includes('participantKey'));
  const activePlayers = [];
  for (const p of allPages) {
    const content = await p.content();
    if (content.includes('You are the speaker') || content.includes('You are a listener') || content.includes('Phase')) {
      activePlayers.push(p);
    }
  }

  // Identify speakers and listeners for screenshots
  let speakerPage = null;
  let listenerPage = null;
  for (const p of activePlayers) {
    const content = await p.content();
    if (content.includes('You are the speaker') && !speakerPage) {
      speakerPage = p;
    } else if (content.includes('You are a listener') && !listenerPage) {
      listenerPage = p;
    }
  }

  // Screenshot speaker selection
  if (speakerPage) {
    await speakerPage.screenshot({ path: `${screenshotDir}/13-speaker-selection.png` });
  }

  // Screenshot listener before speaker message
  if (listenerPage) {
    await listenerPage.screenshot({ path: `${screenshotDir}/14-listener-selection-disabled.png` });
  }

  // Speaker sends message
  if (speakerPage) {
    const input = speakerPage.getByRole('textbox', { name: 'Say something' });
    await input.fill('the one that looks like a person');
    await input.press('Enter');
    await page.waitForTimeout(500);
  }

  // Screenshot listener after speaker message
  if (listenerPage) {
    await listenerPage.screenshot({ path: `${screenshotDir}/15-listener-selection-enabled.png` });

    // Click tangram
    const tangrams = listenerPage.locator('.tangrams.grid > div');
    await tangrams.first().click();
    await listenerPage.waitForTimeout(300);

    await listenerPage.screenshot({ path: `${screenshotDir}/16-listener-after-click.png` });
  }

  return "Phase 1 round 1 screenshots captured";
}
```

#### Step 5: Continue Phase 1, Make 2 Players Idle

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const screenshotDir = 'experiment/test-screenshots/' + new Date().toISOString().split('T')[0];

  const allPages = context.pages().filter(p => p.url().includes('participantKey'));

  // Helper to get active players
  async function getActivePlayers() {
    const active = [];
    for (const p of allPages) {
      const content = await p.content();
      if (content.includes('You are the speaker') || content.includes('You are a listener') ||
          content.includes('Phase') || content.includes('Feedback')) {
        active.push(p);
      }
    }
    return active;
  }

  // Helper to complete a round
  async function completeRound(skipPlayerIndices = []) {
    const players = await getActivePlayers();

    // Click Continue buttons
    for (const p of players) {
      try {
        await p.getByRole('button', { name: /continue/i }).click({ timeout: 500 });
      } catch {}
    }
    await page.waitForTimeout(300);

    // Speakers send messages (unless skipped)
    for (let i = 0; i < players.length; i++) {
      if (skipPlayerIndices.includes(i)) continue;
      const p = players[i];
      const content = await p.content();
      if (content.includes('You are the speaker')) {
        const input = p.getByRole('textbox', { name: 'Say something' });
        if (await input.count() > 0) {
          await input.fill('test message');
          await input.press('Enter');
        }
      }
    }
    await page.waitForTimeout(300);

    // Listeners click tangrams (unless skipped)
    for (let i = 0; i < players.length; i++) {
      if (skipPlayerIndices.includes(i)) continue;
      const p = players[i];
      const content = await p.content();
      if (content.includes('You are a listener')) {
        const tangrams = p.locator('.tangrams.grid > div');
        if (await tangrams.count() > 0) await tangrams.first().click();
      }
    }
    await page.waitForTimeout(500);
  }

  // Complete rounds 1-6 normally (Block 1)
  for (let r = 1; r <= 6; r++) {
    await completeRound();
  }
  console.log('Block 1 complete');

  // Block 2: Identify player indices for Group A speaker and Group B listener
  // These will be the ones to idle
  let players = await getActivePlayers();
  let groupASpeakerIdx = -1;
  let groupBListenerIdx = -1;

  for (let i = 0; i < players.length; i++) {
    const p = players[i];
    const content = await p.content();
    // We'll make player at index 0 and 3 idle (assuming they're in different groups)
    if (i === 0) groupASpeakerIdx = i;
    if (i === 3) groupBListenerIdx = i;
  }

  // Round 7: First idle round for players 0 and 3
  await completeRound([0, 3]);
  console.log('Round 7: 2 players idle (round 1/2)');

  // Take idle warning screenshot after feedback
  await page.waitForTimeout(1000);
  players = await getActivePlayers();
  for (const p of players) {
    const content = await p.content();
    if (content.includes('Warning: You were inactive')) {
      await p.screenshot({ path: `${screenshotDir}/22-idle-warning.png` });
      break;
    }
  }

  // Round 8: Second idle round - players get kicked
  await completeRound([0, 3]);
  console.log('Round 8: 2 players kicked');

  // Take sorry page screenshot for idle player
  await page.waitForTimeout(1000);
  for (const p of allPages) {
    const content = await p.content();
    if (content.includes('Removed for Inactivity')) {
      await p.screenshot({ path: `${screenshotDir}/24-sorry-player-timeout.png` });
      break;
    }
  }

  // Complete remaining rounds in Phase 1 (rounds 9-36)
  for (let r = 9; r <= 36; r++) {
    await completeRound();
    if (r % 6 === 0) console.log(`Block ${r/6} complete`);
  }

  return "Phase 1 complete, 2 players kicked for idleness";
}
```

#### Step 6: Phase 2 Transition and Screenshots

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const screenshotDir = 'experiment/test-screenshots/' + new Date().toISOString().split('T')[0];

  const allPages = context.pages().filter(p => p.url().includes('participantKey'));

  // Wait for transition
  await page.waitForTimeout(2000);

  // Find transition screen and screenshot
  for (const p of allPages) {
    const content = await p.content();
    if (content.includes('End of Phase 1') || content.includes('Phase 2')) {
      await p.screenshot({ path: `${screenshotDir}/25-phase-transition-social.png`, fullPage: true });
      break;
    }
  }

  // Click Continue for all active players
  for (const p of allPages) {
    try {
      await p.getByRole('button', { name: /continue/i }).click({ timeout: 2000 });
    } catch {}
  }
  await page.waitForTimeout(1000);

  return "Phase 2 transition complete";
}
```

#### Step 7: Phase 2 with Social Guessing and More Dropouts

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const screenshotDir = 'experiment/test-screenshots/' + new Date().toISOString().split('T')[0];

  const allPages = context.pages().filter(p => p.url().includes('participantKey'));

  // Get active players (7 remaining)
  async function getActivePlayers() {
    const active = [];
    for (const p of allPages) {
      const content = await p.content();
      if (content.includes('You are the speaker') || content.includes('You are a listener') ||
          content.includes('Phase 2') || content.includes('Feedback')) {
        active.push(p);
      }
    }
    return active;
  }

  // Helper for Phase 2 rounds with social guessing
  async function completePhase2Round(skipPlayerIndex = -1, screenshotSocialGuess = false) {
    const players = await getActivePlayers();

    // Click Continue buttons
    for (const p of players) {
      try {
        await p.getByRole('button', { name: /continue/i }).click({ timeout: 500 });
      } catch {}
    }
    await page.waitForTimeout(300);

    // Speakers send messages
    for (let i = 0; i < players.length; i++) {
      if (i === skipPlayerIndex) continue;
      const p = players[i];
      const content = await p.content();
      if (content.includes('You are the speaker')) {
        // Screenshot anonymous speaker
        if (screenshotSocialGuess) {
          await p.screenshot({ path: `${screenshotDir}/26-phase2-speaker-anonymous.png` });
        }
        const input = p.getByRole('textbox', { name: 'Say something' });
        if (await input.count() > 0) {
          await input.fill('phase 2 message');
          await input.press('Enter');
        }
      }
    }
    await page.waitForTimeout(300);

    // Listeners click tangrams and make social guess
    for (let i = 0; i < players.length; i++) {
      if (i === skipPlayerIndex) continue;
      const p = players[i];
      const content = await p.content();
      if (content.includes('You are a listener')) {
        // Screenshot anonymous listener
        if (screenshotSocialGuess) {
          await p.screenshot({ path: `${screenshotDir}/27-phase2-listener-anonymous.png` });
        }

        const tangrams = p.locator('.tangrams.grid > div');
        if (await tangrams.count() > 0) {
          await tangrams.first().click();
          await p.waitForTimeout(500);

          // Screenshot social guess UI
          if (screenshotSocialGuess) {
            await p.screenshot({ path: `${screenshotDir}/28-social-guess-ui.png` });
          }

          // Make social guess
          try {
            await p.getByRole('button', { name: /yes, same group/i }).click({ timeout: 1000 });
          } catch {
            try {
              await p.getByRole('button', { name: /no, different group/i }).click({ timeout: 1000 });
            } catch {}
          }

          // Screenshot after guess
          if (screenshotSocialGuess) {
            await p.waitForTimeout(300);
            await p.screenshot({ path: `${screenshotDir}/29-social-guess-made.png` });
          }
        }
      }
    }
    await page.waitForTimeout(500);
  }

  // Block 1 of Phase 2 (rounds 1-6) - take screenshots on first round
  await completePhase2Round(-1, true);
  for (let r = 2; r <= 6; r++) {
    await completePhase2Round();
  }
  console.log('Phase 2 Block 1 complete');

  // Screenshot shuffling message (appears at end of block)
  let players = await getActivePlayers();
  for (const p of players) {
    const content = await p.content();
    if (content.includes('Shuffling players')) {
      await p.screenshot({ path: `${screenshotDir}/31-shuffling-players.png` });
      break;
    }
  }

  // Block 2 (rounds 7-12)
  for (let r = 7; r <= 12; r++) {
    await completePhase2Round();
  }
  console.log('Phase 2 Block 2 complete');

  // Block 3: Make another Group A player idle (they get kicked, group disbands)
  // This will trigger MID-BLOCK RESHUFFLE because the Group A player's partner
  // in their current shuffled group would be left alone otherwise.

  // Round 13: First idle
  await completePhase2Round(0);
  console.log('Phase 2 Round 13: Player 0 idle (1/2)');

  // Before the kick happens, record current group assignments for comparison
  players = await getActivePlayers();
  const groupsBefore = {};
  for (const p of players) {
    const content = await p.content();
    // Try to extract group info from the page
    groupsBefore[await p.url()] = content.includes('Group') ? 'recorded' : 'unknown';
  }
  console.log(`Players before kick: ${players.length}`);

  // Round 14: Second idle - player kicked, group disbands, MID-BLOCK RESHUFFLE triggered
  await completePhase2Round(0);
  console.log('Phase 2 Round 14: Player 0 kicked, group disbanded');
  console.log('*** MID-BLOCK RESHUFFLE should have been triggered! ***');
  console.log('Check server logs for: "MID-BLOCK RESHUFFLE: Solo player detected in Phase 2 mixed"');

  // Screenshot group disbanded (for the kicked player)
  await page.waitForTimeout(1000);
  for (const p of allPages) {
    const content = await p.content();
    if (content.includes('Group Disbanded')) {
      await p.screenshot({ path: `${screenshotDir}/32-sorry-group-disbanded.png` });
      break;
    }
  }

  // After mid-block reshuffle, take screenshot showing new group assignments
  players = await getActivePlayers();
  console.log(`Players after kick and mid-block reshuffle: ${players.length}`);

  // Screenshot the new group state after mid-block reshuffle
  if (players.length > 0) {
    await players[0].screenshot({ path: `${screenshotDir}/34-mid-block-after.png` });
  }

  // Verify no player is alone - each player should have at least 1 group member
  for (const p of players) {
    const content = await p.content();
    // If someone is alone, they'd see "Your group is smaller" but still have >0 other players shown
    if (content.includes('group is smaller')) {
      await p.screenshot({ path: `${screenshotDir}/30-phase2-group-smaller.png` });
      console.log('Found "group is smaller" message - verifying player is not alone');
    }
  }

  // Complete remaining rounds in Block 3 (rounds 15-18)
  for (let r = 15; r <= 18; r++) {
    await completePhase2Round();
  }
  console.log('Phase 2 Block 3 complete (with mid-block reshuffle)');

  // Complete remaining blocks (4-6) - normal reshuffling at block boundaries
  for (let r = 19; r <= 36; r++) {
    await completePhase2Round();
    if (r % 6 === 0) console.log(`Phase 2 Block ${Math.floor(r/6)} complete`);
  }

  return "Phase 2 complete (mid-block reshuffle verified)";
}
```

#### Step 8: Bonus Info and Exit Survey

```javascript
browser_run_code:
async (page) => {
  const context = page.context();
  const screenshotDir = 'experiment/test-screenshots/' + new Date().toISOString().split('T')[0];

  const allPages = context.pages().filter(p => p.url().includes('participantKey'));

  // Wait for bonus info stage
  await page.waitForTimeout(2000);

  // Find and screenshot bonus info
  for (const p of allPages) {
    const content = await p.content();
    if (content.includes('End of Game') || content.includes('Social Guessing Summary')) {
      await p.screenshot({ path: `${screenshotDir}/35-bonus-info.png`, fullPage: true });
      await p.getByRole('button', { name: /continue/i }).click();
      break;
    }
  }

  await page.waitForTimeout(1000);

  // Click Continue for all remaining players
  for (const p of allPages) {
    try {
      await p.getByRole('button', { name: /continue/i }).click({ timeout: 1000 });
    } catch {}
  }

  await page.waitForTimeout(1000);

  // Find and screenshot exit survey
  for (const p of allPages) {
    const content = await p.content();
    if (content.includes('Exit Survey') || content.includes('Game Complete')) {
      await p.screenshot({ path: `${screenshotDir}/36-exit-survey.png`, fullPage: true });

      // Fill exit survey
      await p.locator('input[name="age"]').fill('25');
      await p.locator('input[name="gender"]').fill('prefer not to say');
      await p.getByRole('radio', { name: /bachelor/i }).click();
      await p.getByRole('radio', { name: /^yes$/i }).click();
      await p.locator('textarea[name="strength"]').fill('Test strategy');
      await p.locator('textarea[name="fair"]').fill('Yes');
      await p.locator('textarea[name="feedback"]').fill('Test feedback');

      await p.getByRole('button', { name: /submit/i }).click();
      await p.waitForTimeout(1000);

      await p.screenshot({ path: `${screenshotDir}/37-completion.png` });
      break;
    }
  }

  // Submit exit survey for remaining players
  for (const p of allPages) {
    try {
      const content = await p.content();
      if (content.includes('Exit Survey')) {
        await p.locator('input[name="age"]').fill('30');
        await p.locator('input[name="gender"]').fill('test');
        await p.getByRole('radio', { name: /bachelor/i }).click();
        await p.getByRole('radio', { name: /^yes$/i }).click();
        await p.locator('textarea[name="strength"]').fill('Test');
        await p.locator('textarea[name="fair"]').fill('Yes');
        await p.locator('textarea[name="feedback"]').fill('None');
        await p.getByRole('button', { name: /submit/i }).click();
      }
    } catch {}
  }

  return "Test complete!";
}
```

### Data Verification

After test completion, verify the data:

```bash
cd experiment && empirica export
unzip -o $(ls -t export-*.zip | head -1) -d export-test

# Verify key fields in playerRound.csv:
# - role: speaker/listener
# - target: tangram ID
# - clicked: tangram ID (listeners)
# - clicked_correct: boolean
# - block_num, phase_num
# - original_group: A, B, C (preserved)
# - current_group: changes in Phase 2
# - social_guess: same_group/different_group (Phase 2)
# - social_guess_correct: boolean

# Verify reshuffling:
# - Each block should show different current_group assignments
# - original_group should remain constant per player
```

### Mid-Block Reshuffle Verification

**Server Logs:** Look for these log messages:
```
MID-BLOCK RESHUFFLE: Solo player detected in Phase 2 mixed, triggering immediate reshuffling
  -> 5 active players will be redistributed
Reshuffling groups for mixed condition (balanced)
```

**Data Fields:** Check `game.csv` for:
```
midBlockReshuffle_block2_target1: true  # (block and target numbers will vary)
```

**Verification Steps:**
1. Before mid-block reshuffle: 6 active players after A-player kicked (A:1, B:2, C:3)
2. Group A disbands: remaining A player kicked with "group disbanded"
3. 5 players remain, but one B or C player would be alone in their shuffled group
4. Mid-block reshuffle triggers: 5 players redistributed into groups of (3,2) or (2,2,1→reshuffled)
5. No player should be alone after the reshuffle

**What to verify in playerRound.csv:**
- Look at `current_group` values before and after the mid-block reshuffle
- All active players should have valid group assignments
- No player should be the only one in their `current_group` after reshuffle

---

## Timeout Configuration

For idle/dropout tests, you can adjust timeouts in `experiment/shared/constants.js`:

```javascript
export const SELECTION_DURATION = 45;  // Seconds for selection stage
export const FEEDBACK_DURATION = 10;   // Seconds for feedback stage
export const MAX_IDLE_ROUNDS = 2;      // Rounds before idle kick
```

With default settings, players are kicked after ~2 minutes of inactivity (2 rounds × ~55s each).

---

## Prolific Codes

| Scenario | Code |
|----------|------|
| Completed successfully | C3OIIB3N |
| Failed quiz 3 times | QUIZFAIL2026 |
| Removed for inactivity | TIMEOUT2026 |
| Group disbanded | DISBANDED2026 |
| Removed for low accuracy | DISBANDED2026 (uses same code) |
| Lobby timeout | LOBBYTIMEOUT |

---

## Troubleshooting

**Port conflict (tangrams not rendering):**
```bash
lsof -ti:3000,8844 | xargs kill -9 2>/dev/null
```

**Tangram clicks not registering:**
- Use `.tangrams.grid > div` selector (DIVs with background-image, not IMGs)

**Dialog blocking automation:**
- Set up `page.once('dialog', ...)` BEFORE triggering the dialog

**Players kicked too fast:**
- Increase timeouts in `experiment/shared/constants.js`

**Screenshots cut off:**
- Use `fullPage: true` option for scrollable pages
- Or resize viewport with `page.setViewportSize({ width: 1280, height: 1600 })`

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `utils.js` | Core utilities: retry logic, state detection, tangram helpers |
| `test-reporter.js` | Test reporting with checkpoints |
| `00-preflight-check.js` | Port cleanup, server health check |
| `17-data-verification.js` | Verify exported data fields |
| `18-advanced-automation.js` | Parallel player processing, social guessing |
| `19-edge-case-tests.js` | Quiz failure, idle detection, dropout tests |
