# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multiplayer reference game experiment built with Empirica studying lexical variation and social signaling. Players communicate about tangram images in groups, with different experimental conditions affecting group dynamics in Phase 2.

The registered report manuscript is in `paper/main.tex` (compiled with `cd paper && latexmk -pdf main.tex`). The paper describes the framing, design, and analysis plan for both Experiment 1 and Experiment 2.

We plan to submit the registered report to Nature Human Behavior. The submission guidelines are at https://www.nature.com/nathumbehav/submission-guidelines/registeredreports

**Experimental Design:**
- 9 players in 3 groups of 3
- Phase 1: Within-group reference game (6 blocks)
- Phase 2: Continued reference game with condition-dependent behavior (6 blocks)
- Experiment 1 conditions: `refer_separated` (same groups), `refer_mixed` (groups reshuffled every trial, masked identities), `social_mixed` (reshuffled every trial + social guessing task)
- Experiment 2 conditions: `refer_goal` (told groups will mix, no social task info), `social_goal` (told about social identification reward before Phase 1). Both use mixed + social guessing in Phase 2.

The TODOS.md file contains a list of things that need to be done to complete the experiment.

## Commands

### Testing the Experiment Manually

How to test the experiment locally by hand:

```bash
cd experiment
rm .empirica/local/tajriba.json
empirica
```

This starts both server and client. Admin interface at `localhost:3000/admin`, players at `localhost:3000/`. Press "new player" on the player interface to start a new player.

To test:
- click "new batch" on the admin console. "complete" refers to the assignment method, we want to do complete assignment. we can select treatment on the dropdown, lobby config is default shared fail. then click "create"
- open player interface at `localhost:3000/`
  - press "new player" to start a new player, we need to click this 9 times to get 9 players

### Testing with Playwright MCP (interactive)

You can use the Playwright MCP browser tools to manually test the experiment with multiple simulated players. This is useful for verifying UI changes without running the full test suite.

**Setup:**
1. Start the server in background: `cd experiment && rm .empirica/local/tajriba.json && empirica`
2. Navigate to `http://localhost:3000/admin` and create+start a batch
3. Use `browser_run_code` to create 9 player contexts and walk them through the intro

**Key lessons:**
- **Dialog handler first**: The quiz uses `window.alert()` which blocks Playwright. Register `page.on('dialog', async d => await d.accept())` on each player page *before* submitting the quiz, not after.
- **Player intro flow**: I AGREE → Enter identifier → I consent → 5x Next → Quiz (6 radio answers) → Submit. See exact quiz answer text in `experiment/client/src/intro-exit/Quiz.jsx`.
- **Globals don't persist**: `globalThis.__var` set in one `browser_run_code` call is NOT available in the next. Instead, access player pages via `browser.contexts()` (admin is `contexts[0]`, players are `contexts[1..9]`, each has `.pages()[0]`).
- **Inactivity kicks**: The selection timer runs during testing. If you spend too long inspecting state between actions, players get kicked for inactivity. Work quickly or use TEST_MODE (longer timeouts).
- **`fill()` vs real typing**: Playwright's `fill()` sets the value but doesn't fire React `onChange`. Follow `fill()` with `dispatchEvent('input')` to trigger typing indicators and other onChange-dependent state.
- **Killing the server**: Use `lsof -ti :3000 -ti :8844 | xargs kill -9` to free both the Empirica server port (3000) and Vite dev server port (8844) before restarting.
- **Finding players by role**: Use `.task` element's data attributes: `data-role` (speaker/listener), `data-current-group` (A/B/C) to identify which browser context belongs to which role/group.

### Playwright Tests

Tests live in `experiment/tests/` and use `@playwright/test`. The server is managed automatically by the test framework (no need to start it manually).

**Running tests:**

```bash
cd experiment

# Run the full test suite (test mode: 3+2 blocks, 120s selection)
npx playwright test

# Run with production timing (6+6 blocks, 45s selection, 2 idle rounds)
TEST_MODE=false npx playwright test

# Run a specific test file
npx playwright test tests/ui-verification/intro-instructions.spec.ts

# Run tests matching a category (matches directory names)
npx playwright test tests/happy-path/
npx playwright test tests/idle-detection/

# Run a specific test group (project) only
npx playwright test --project=group-1

# Run with visible browser
npx playwright test --headed

# View the HTML report after a run
npx playwright show-report
```

**Test architecture:**

Tests are split into 4 project groups in `playwright.config.ts`. Between each group, the Empirica server is restarted (tajriba.json deleted) to prevent state accumulation. Execution order: `setup-1 → group-1 → setup-2 → group-2 → setup-3 → group-3 → setup-4 → group-4`.

| Group | Categories | Description |
|-------|-----------|-------------|
| group-1 | happy-path, communication, lobby, edge-cases | Core game flow |
| group-2 | ui-verification, timing | UI and timing checks |
| group-3 | data-integrity, condition-specific, score-display | Data and conditions |
| group-4 | idle-detection, group-viability, compensation | Dropout handling |

**Writing a new test:**

1. Create a `.spec.ts` file in the appropriate category directory under `experiment/tests/` (e.g., `tests/ui-verification/my-test.spec.ts`). The file must be in a directory matching one of the group patterns above so the config picks it up.

2. Use the shared helpers:
   - `tests/helpers/admin.ts` — `createBatch(page, condition)` to set up a game via the admin UI
   - `tests/helpers/player-manager.ts` — `PlayerManager` class to create and manage multiple browser contexts (one per player)
   - `tests/helpers/game-actions.ts` — `completeIntro(page)` to walk a player through consent, instructions, and quiz
   - `tests/helpers/constants.ts` — all game constants (player count, timing, quiz answers, etc.)
   - `tests/helpers/selectors.ts` — shared CSS selectors

3. Typical test setup pattern:
   ```typescript
   import { test, expect } from '@playwright/test';
   import { createBatch } from '../helpers/admin';
   import { PlayerManager } from '../helpers/player-manager';

   test.describe.serial('My Test Suite', () => {
     let pm: PlayerManager;

     test.beforeAll(async ({ browser }) => {
       // Create batch via admin
       const adminPage = await browser.newPage();
       await createBatch(adminPage, 'refer_separated');
       await adminPage.close();

       // Set up 9 players
       pm = new PlayerManager(browser);
       await pm.initialize();
       await pm.registerAllPlayers();
       await pm.completeAllIntros();
       await pm.waitForGameStart();
     });

     test.afterAll(async () => {
       await pm.cleanup();
     });

     test('my test case', async () => {
       const pages = pm.getPages();
       // ... assertions
     });
   });
   ```

4. Tests run sequentially (`workers: 1`, `fullyParallel: false`) because they share a single Empirica server. Use `test.describe.serial` for tests that depend on ordering within a file.

**Key config values** (from `experiment/shared/constants.js`, mirrored in `tests/helpers/constants.ts`):
- `TEST_MODE` — controlled by `TEST_MODE` env var (defaults to `false` for production, `server-manager.ts` sets `true` for tests)
- Test mode: 3+2 blocks, 120s selection, 5 idle rounds, 600s timeout
- Production mode (`TEST_MODE=false`): 6+6 blocks, 45s selection, 2 idle rounds, 5400s timeout


### Python environment

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management. Dependencies are defined in `pyproject.toml`.

```bash
# Install dependencies
uv sync

# Run a Python script
uv run python script.py

# Run Jupyter
uv run jupyter notebook

# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# In R: renv::restore()
```

Note: `rpy2` requires R to be installed. Cairo-based packages (`cairosvg`) may require: `brew install cairo pango`

## Architecture

### Server (`experiment/server/src/`)

- **constants.js**: Central configuration - player counts, phase blocks, scoring, avatar generation (DiceBear API)
- **callbacks.js**: Game logic via Empirica callbacks:
  - `onGameStart`: Player/group assignment, round/stage creation
  - `onRoundStart`: Role assignment, group reshuffling (mixed conditions), identity masking
  - `onStageEnded`: Scoring, idle player detection, group viability checks

### Client (`experiment/client/src/`)

- **App.jsx**: Root with intro/exit step routing
- **Game.jsx**: Layout (Profile + Task + Chat), chat visibility logic
- **Task.jsx**: Phase dispatcher → Refgame, Transition, or Inactive
- **stages/Refgame.jsx**: Main game UI with tangram grid, social guessing UI
- **components/Tangram.jsx**: Click handling with auto-submit logic

### Configuration (`experiment/.empirica/`)

- **treatments.yaml**: Experimental factors and 5 treatment combinations (3 for Experiment 1, 2 for Experiment 2)
- **lobbies.yaml**: Participant grouping strategies
- **empirica.toml**: Auth and project metadata

## Key Patterns

### Quiz Answers (for Playwright automation)

1. Speaker's job → "Describe the target picture"
2. Inactive penalty → "Removed from the game"
3. Chat restrictions → "Only topics related to picking out the correct target picture"
4. Listener waiting → "Listeners must wait for speaker"
5. Phase 2 groups → "Mixed up"
6. Tangram positions → "Different positions for each player"

### Identity Masking (Phase 2 Mixed Conditions)

In `refer_mixed` and `social_mixed`, groups are reshuffled every trial (not per-block). Anonymous avatars are seeded per trial (`anon_block${blockNum}_trial${targetNum}_player${anonIndex}`) so the same player gets different avatars each round:
- `player.round.set("display_avatar/name")` for UI display
- `player.set("avatar/name")` overwritten for chat masking
- `player.get("original_avatar/name")` preserved for restoration

### Group Tracking

- `original_group`: Persists throughout game (A, B, C)
- `current_group`: Changes each block in mixed conditions

## Sentry (Error Monitoring)

The client app reports errors to Sentry via `@sentry/react`. A Sentry MCP server is connected, so you can query production issues directly.

**Project details:**
- Organization: `lexical-variation-project`
- Project: `javascript-react`
- Region URL: `https://us.sentry.io`
- Production URL: `https://tangramcommunication.empirica.app/`

**Available MCP tools:**
- `search_issues` — list grouped issues (e.g. unresolved bugs)
- `get_issue_details` — stacktrace and event details for a specific issue ID
- `search_events` — count/aggregate errors or find individual events
- `analyze_issue_with_seer` — AI root cause analysis with code fix suggestions

**Workflow:** When investigating production bugs, check Sentry for recent issues, then cross-reference the stacktrace with the client source in `experiment/client/src/`. Reference issue IDs in commit messages (e.g. `Fixes JAVASCRIPT-REACT-1`) to auto-resolve issues on merge.

## Data

- Live data: `experiment/.empirica/local/tajriba.json`
  - This changes to csvs by running `empirica export`
- Backup from production server:
  ```bash
  cd experiment
  bash copy_tajriba.sh            # loop every 5 minutes (default)
  bash copy_tajriba.sh --once     # single backup and exit
  bash copy_tajriba.sh --help     # show usage
  ```
  The script SSHs into `root@tangramcommunication.empirica.app`, runs `empirica export` in `~/empirica` to produce a CSV zip, then copies it locally into `experiment/data/<timestamp>/`. Safe to run while the experiment is live. Exits automatically after 3 consecutive failures.

### Analysis Pipeline

`analysis/run_pipeline.py` is the single entry point for all data processing. It has subcommands for different workflows.

**Scripts:**

| Script | Purpose |
|--------|---------|
| `run_pipeline.py` | Entry point — process zips, combine runs, browse metadata |
| `preprocessing.py` | Raw Empirica CSVs → analysis-ready CSVs (called by run_pipeline) |
| `compute_embeddings.py` | Speaker utterances → SBERT embeddings, similarity metrics, UMAP |
| `pilot_analysis.py` | Preprocessed data → static comparison plots across conditions |
| `animate_umap.py` | UMAP projections → animated videos of embedding trajectories |
| `plot_style.py` | Shared plotting constants and helpers (imported, not run directly) |
| `test_data_integrity.py` | Pytest validation of preprocessed CSV structure and content |
| `exploratory/` | Ad-hoc analysis scripts (contact networks, label dynamics) — not part of the pipeline |

**Quarto notebooks** (`00_preprocess.qmd` through `05_exit_survey.qmd`) read from `analysis/processed_data/` (a symlink updated by `run_pipeline.py`).

#### Processing a single run

```bash
# Process the most recent zip under experiment/data/
uv run python analysis/run_pipeline.py

# Process a specific zip
uv run python analysis/run_pipeline.py experiment/data/20260222_125327/empirica-export-20260222_132407.zip

# Skip slow steps
uv run python analysis/run_pipeline.py --skip-embeddings --skip-visualize --skip-render
```

Steps: unzip → extract bonuses → anonymize → preprocess → embeddings → visualize → render notebooks.

Output goes to `analysis/{datetime}/` with `raw/`, `data/`, and `figures/` subdirectories.

#### Combining multiple runs

When data spans multiple Empirica server runs, use the `combine` subcommand:

```bash
# Combine and preprocess only
uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147

# Full pipeline (embeddings + plots)
uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147

# Skip slow steps
uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147 --skip-embeddings --skip-visualize
```

Stacks raw CSVs, filters failed games (lobby timeouts), runs preprocessing, writes `manifest.json`. Output defaults to `analysis/pilots/` (configurable with `--output`). Each run must already be processed (i.e. `analysis/{timestamp}/raw/` must exist).

#### Browsing runs and metadata

```bash
uv run python analysis/run_pipeline.py list                               # list all runs
uv run python analysis/run_pipeline.py status                             # show processed_data symlink
uv run python analysis/run_pipeline.py bonuses                            # print latest bonuses
uv run python analysis/run_pipeline.py bonuses --run 20260225_210047      # specific run
```

#### Running individual scripts standalone

```bash
uv run python analysis/pilot_analysis.py --data-dir analysis/pilots/data/ --output-dir analysis/pilots/figures/
uv run python analysis/animate_umap.py --data-dir analysis/pilots/data/ --output-dir analysis/pilots/figures/
uv run python analysis/compute_embeddings.py analysis/pilots/data/
uv run pytest analysis/test_data_integrity.py -v
```
