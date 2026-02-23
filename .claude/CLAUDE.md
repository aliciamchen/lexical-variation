# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multiplayer reference game experiment built with Empirica studying lexical variation and social signaling. Players communicate about tangram images in groups, with different experimental conditions affecting group dynamics in Phase 2.

A writeup of the framing and goals of the experiments (for submission as a registered report) is in `writing/Social_and_referential_goals_in_language_variation-12.pdf`. Note that in the introduction of that document there is an Experiment 2 planned; that is not written out yet, all of the methods in there are for Experiment 1, which should correspond to the code in this repository. 

**Experimental Design:**
- 9 players in 3 groups of 3
- Phase 1: Within-group reference game (6 blocks)
- Phase 2: Continued reference game with condition-dependent behavior (6 blocks)
- Conditions: `refer_separated` (same groups), `refer_mixed` (shuffled groups, masked identities), `social_mixed` (shuffled + social guessing task)

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

- **treatments.yaml**: Experimental factors and 3 treatment combinations
- **lobbies.yaml**: Participant grouping strategies
- **empirica.toml**: Auth and project metadata

## Key Patterns

### Quiz Answers (for Playwright automation)

1. Speaker's job → "Describe the target picture"
2. Inactive penalty → "Removed from the game"
3. Chat restrictions → "Only descriptions of the current target"
4. Listener waiting → "Listeners must wait for speaker"
5. Phase 2 groups → "Mixed up"
6. Tangram positions → "Different positions for each player"

### Identity Masking (Phase 2 Mixed Conditions)

In `refer_mixed` and `social_mixed`:
- `player.round.set("display_avatar/name")` for UI display
- `player.set("avatar/name")` overwritten for chat masking
- `player.get("original_avatar/name")` preserved for restoration

### Group Tracking

- `original_group`: Persists throughout game (A, B, C)
- `current_group`: Changes each block in mixed conditions

## Custom Chat Component

The project uses a custom Chat component at `experiment/client/src/components/Chat.jsx` instead of the Empirica Chat component. This avoids needing to patch `node_modules` (which gets overwritten on `npm install` and has Vite caching issues).

The custom Chat component includes:
- **Role labels**: Shows "(Speaker)" or "(Listener)" after player names
- **Identity masking**: Uses `display_name` in Phase 2 mixed conditions (shows "Player" instead of real name)
- **Timestamp display**: Shows 5-second increments for recent messages instead of all "now"
- **Square avatars**: Uses `rounded-md` instead of `rounded-full` to match the rest of the UI
- **DiceBear fallback**: Generates identicon avatars for players without custom avatars

Usage in `Game.jsx`:
```jsx
import { Chat } from "./components/Chat";

// In the component:
<Chat
  scope={stage}
  attribute={`${playerGroup}_chat`}
  customPlayerName={(p) => {
    const displayName = isMixed ? p.round?.get("display_name") : p.get("name");
    const role = p.round?.get("role");
    const roleLabel = role === "speaker" ? "(Speaker)" : "(Listener)";
    return `${displayName || "Player"} ${roleLabel}`;
  }}
/>
```

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

`analysis/run_pipeline.py` is the single entry point that processes a raw Empirica export zip into analysis-ready data, figures, and rendered notebooks.

**Running the pipeline:**

```bash
# Process the most recent zip under experiment/data/
uv run python analysis/run_pipeline.py

# Process a specific zip
uv run python analysis/run_pipeline.py experiment/data/20260222_125327/empirica-export-20260222_132407.zip

# Skip slow steps
uv run python analysis/run_pipeline.py --skip-embeddings   # skip SBERT (~minutes)
uv run python analysis/run_pipeline.py --skip-visualize    # skip plots/animations
uv run python analysis/run_pipeline.py --skip-render       # skip Quarto notebooks
```

**Pipeline steps:**

1. **Unzip** — extracts the Empirica export to a temp directory
2. **Extract bonuses** — writes `bonuses.csv` with Prolific IDs + bonus amounts (before anonymizing)
3. **Anonymize** — copies raw CSVs to `raw/`, stripping `participantIdentifier` and related columns from `player.csv`
4. **Preprocess** — runs `preprocessing.py` to produce analysis-ready CSVs (`games.csv`, `trials.csv`, `messages.csv`, etc.)
5. **Embeddings** — runs `compute_embeddings.py` for SBERT embeddings, similarity metrics, and UMAP projections
6. **Visualize** — runs `pilot_analysis.py` and `animate_umap.py` for all auto-discovered conditions
7. **Render** — renders Quarto notebooks (`00_preprocess.qmd` through `05_exit_survey.qmd`)

**Output structure** (datetime extracted from zip filename):

```
analysis/20260222_132407/
├── bonuses.csv              # Prolific IDs + bonus amounts (sensitive)
├── raw/                     # Anonymized raw Empirica export CSVs
│   ├── game.csv
│   ├── player.csv           # participantIdentifier REMOVED
│   ├── playerRound.csv
│   └── ...
├── data/                    # Preprocessed analysis-ready CSVs
│   ├── games.csv
│   ├── trials.csv
│   ├── messages.csv
│   ├── speaker_utterances.csv
│   ├── embeddings.npy
│   ├── umap_projections.csv
│   └── ...
└── figures/                 # Plots and animations
    ├── pilot_social_mixed_listener_accuracy.png
    └── ...
```

**Symlink:** The pipeline creates/updates `analysis/processed -> analysis/{datetime}/data/` so that Quarto notebooks (which read from `analysis/processed/`) always point to the most recently processed dataset.

**Individual scripts** can also be run standalone with `--data-dir` and `--output-dir`:

```bash
uv run python analysis/pilot_analysis.py --data-dir analysis/20260222_132407/data/ --output-dir analysis/20260222_132407/figures/
uv run python analysis/animate_umap.py --data-dir analysis/20260222_132407/data/ --output-dir analysis/20260222_132407/figures/
```
