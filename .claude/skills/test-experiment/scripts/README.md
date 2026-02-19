# Test Experiment Scripts

Modular test scripts for the Empirica reference game experiment using Playwright MCP.

**See `experiment/TEST_PLAN.md` for the comprehensive test plan.**

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `00-preflight-check.js` | Port cleanup, server health verification |
| `17-data-verification.js` | Verify exported data contains required fields |
| `18-advanced-automation.js` | Main automation: parallel intro, round completion, social guessing |
| `19-edge-case-tests.js` | Quiz failure, idle detection, dropout, group disbanded tests |
| `22-server-restart.sh` | Restart Empirica server with fresh database |
| `24-reshuffling-verification.js` | Verify reshuffling happens at block boundaries only |
| `test-reporter.js` | Test reporting with checkpoints and verification |
| `utils.js` | Core utilities: retry logic, state detection, tangram helpers |

---

## Quick Reference

### Element Selectors

**Quiz Answers:**
```javascript
await page.getByRole('radio', { name: /describe the target picture/i }).click();
await page.getByRole('radio', { name: /removed from the game/i }).click();
await page.getByRole('radio', { name: /only descriptions of the current/i }).click();
await page.getByRole('radio', { name: /listeners must wait/i }).click();
await page.getByRole('radio', { name: /mixed up/i }).click();
await page.getByRole('radio', { name: /different positions for each player/i }).click();
```

**Tangrams:**
```javascript
const tangrams = page.locator('.tangrams.grid > div');
await tangrams.first().click();
```

**Chat Input:**
```javascript
const textbox = page.getByRole('textbox', { name: 'Say something' });
await textbox.fill("message");
await textbox.press('Enter');
```

**Identifier Entry:**
```javascript
await page.getByRole('textbox').fill('player1');
await page.getByRole('button', { name: /enter/i }).click();
```

---

## Using the Scripts

### 1. Preflight Check

```javascript
const { runPreflightChecks, printPreflightResults } = require('./00-preflight-check.js');

const results = await runPreflightChecks({ cleanPorts: true });
printPreflightResults(results);
```

### 2. Advanced Automation

```javascript
const {
  CONFIG,
  completeIntroForAllPlayersParallel,
  completeRoundWithSocialGuessing,
  runFullTestWithReporting
} = require('./18-advanced-automation.js');

// Complete intro for all players in parallel
await completeIntroForAllPlayersParallel(page, CONFIG.FAST);

// Complete a single round with social guessing support
await completeRoundWithSocialGuessing(page, {
  config: CONFIG.NORMAL,
  isSocialMixed: true,
  isPhase2: true
});

// Run full test with reporting
const report = await runFullTestWithReporting(page, {
  testName: 'Social Mixed Test',
  numPlayers: 9,
  condition: 'social_mixed',
  mode: 'NORMAL'
});
```

### 3. Edge Case Tests

```javascript
const {
  testQuizFailure,
  testIdleDetection,
  testDropout,
  testGroupDisbanded
} = require('./19-edge-case-tests.js');

// Test quiz 3-attempt failure
const report = await testQuizFailure(page);

// Test idle player removal
const report = await testIdleDetection(page);
```

### 4. Data Verification

```bash
# Export data
cd experiment && empirica export
unzip -o $(ls -t export-*.zip | head -1) -d export-test

# Verify
node -e "
  const { runAllVerifications } = require('./17-data-verification.js');
  runAllVerifications('./export-test', {
    condition: 'social_mixed',
    expectedPlayers: 9
  });
"
```

### 5. Utilities

```javascript
const {
  withRetry,
  detectGameState,
  detectPlayerRole,
  getPlayerPages,
  verifyTangramsLoaded,
  clickTangram,
  withScreenshotOnError
} = require('./utils.js');

// Retry flaky operations
await withRetry(() => someFlakyOperation(), 3, 500);

// Detect current game state
const state = await detectGameState(page);
// Returns: 'identifier', 'consent', 'introduction', 'quiz', 'lobby',
//          'phase1_game', 'phase2_game', 'exit_survey', 'kicked_idle', etc.

// Get all player pages
const playerPages = await getPlayerPages(page);

// Verify tangrams loaded before clicking
const result = await verifyTangramsLoaded(page, 6, 5000);

// Screenshot on failure
await withScreenshotOnError(page, async () => {
  await page.locator('.tangram').first().click();
}, 'tangram-click');
```

---

## Server Restart

```bash
# Restart server with fresh database
bash 22-server-restart.sh

# Or manually:
lsof -ti:3000,8844 | xargs kill -9 2>/dev/null || true
cd experiment
rm -f .empirica/local/tajriba.json
empirica
```

---

## Prolific Codes

| Scenario | Code |
|----------|------|
| Completed successfully | C3OIIB3N |
| Failed quiz 3 times | QUIZFAIL2024 |
| Removed for inactivity | TIMEOUT2024 |
| Group disbanded | DISBANDED2024 |
| Lobby timeout | LOBBYTIMEOUT |
