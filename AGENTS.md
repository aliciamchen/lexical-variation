# Agent guide

This file holds durable, agent-facing context for this repository and is read by every coding agent (`CLAUDE.md` is a symlink to it). The public project overview and run instructions are in `README.md`; the `Makefile` is the command source of truth for the data pipeline (`make help`). Area-specific facts are in `.claude/rules/`, procedures in the skills under `.claude/skills/`.

## Project status

This is a multiplayer reference game built with Empirica for studying lexical variation and social signaling: nine players in three groups of three describe tangram images, and four between-subjects conditions vary whether groups stay separate or are mixed in Phase 2 and whether players are rewarded for identifying each other's group. The pilot is complete, and the manuscript in `paper/main.tex` was written as a Stage 1 registered report. That manuscript now serves as the preregistration. The next phase is to collect the full sample, run the preregistered analyses (`analysis/00`–`05_*.qmd`), and submit the result as a regular article. `full-sample-todos.md` is the checklist for getting there; do not treat pilot-only assumptions (dataset paths, `PILOT_RUNS`, cached RDS fits) as permanent.

## Experimental design

- 9 players in 3 groups of 3; Phase 1 is a within-group reference game (6 blocks); Phase 2 continues for 6 blocks with condition-dependent behavior.
- Conditions: `refer_separated` (same groups throughout), `refer_mixed` (groups reshuffled every trial, identities masked), `social_mixed` (reshuffled plus a social guessing task), `social_first` (told about the social identification reward before Phase 1, then reshuffled plus social guessing).
- `original_group` (A, B, C) persists for the whole game; `current_group` changes per trial in mixed conditions. In mixed Phase 2, anonymous avatars are re-seeded per trial and chat names are masked, so `senderName` is uninformative there while `senderId` remains valid.
- `TEST_MODE` (default false) shortens games to 3+2 blocks with long timers; the Playwright framework sets it. Production timing is 6+6 blocks with 45 s / 25 s selection.

## Sources of truth

- Game configuration (player counts, blocks, timing, scoring) is `experiment/shared/constants.js`; `experiment/tests/helpers/constants.ts` must mirror it.
- Game logic is `experiment/server/src/callbacks.js`; scoring and reshuffling are importable modules (`scoring.js`, `reshuffling.js`) with vitest unit tests beside them. Treatments are in `experiment/.empirica/treatments.yaml`.
- `analysis/config.R` defines dataset paths, palettes, and the ggplot theme; every notebook sources it, and all ggplots use its scales and theme. `analysis/plot_style.py` is the Python counterpart.
- `paper/main.tex` describes the design and analysis plan. Statistics reach it only through `\newcommand` macros written by the notebooks to `paper/stats/*.tex`; never hardcode a computed value in the manuscript.
- The July 2026 audit notes (`review-full-audit.md`, local only) record verified-correct behavior and open findings; check them before re-investigating game logic or the analysis joins.

## Repository boundaries

- `paper/` is gitignored and synced with Overleaf through Dropbox. Read and edit it locally when asked to work on the manuscript, and run `bash figures/sync_figures.sh` to copy SI figures into `paper/figures/`.
- `experiment/data/` holds raw Empirica export zips with identifiable participant data and is gitignored. `data/pilot_runs/` (per-run extracts) is gitignored too. Only the anonymized outputs in `data/pilots/` are committed; `analysis/extract_run.py` strips the sensitive columns and a pre-commit hook blocks anything that looks like a participant identifier.
- `review*.md` at the root are local design notes and match a gitignore pattern; do not reference them from public docs.
- `.env` holds the production hostname, Sentry DSN, and organization. Never read or print it; `.env.example` documents the variables.

## Workflow and commands

```text
experiment (Empirica) -> copy_tajriba.sh -> experiment/data/<ts>/*.zip
  -> extract_run.py -> combine_runs.py -> process_data.py -> data/pilots/, analysis/pilot_derived/
  -> Quarto notebooks -> figures/*_plots/ + paper/stats/*.tex -> paper/main.tex
```

```bash
uv sync                       # Python; run scripts with `uv run python ...`
# R: renv::restore()           # analysis notebooks (Quarto + R)
cd experiment && npm install  # Empirica app and Playwright tests
make help                     # pipeline targets (extract, combine, process, test, notebooks)
```

Run the experiment locally with `cd experiment && rm .empirica/local/tajriba.json && empirica` (admin at `localhost:3000/admin`). Run tests through the npm scripts in `experiment/package.json` (`npm run test:unit`, `npm run test:group1`…`group4`, `npm test`), never through a bare `npx playwright test <file>`, which replays every earlier group.

## Area rules and skills

Before changing files in an area, read its rule unless the harness loaded it automatically:

| Rule | Covers |
|------|--------|
| `.claude/rules/architecture.md` | Server callbacks, client components, identity masking, quiz answers |
| `.claude/rules/testing.md` | Manual testing, Playwright MCP tips, test suite layout and helpers |
| `.claude/rules/data-pipeline.md` | Data export and backup, pipeline scripts, notebooks, stats-to-LaTeX flow |
| `.claude/rules/llm-simulation.md` | LLM Phase 1 benchmark and the non-referential message filter |
| `.claude/rules/sentry.md` | Sentry project details and the Sentry MCP server |
| `.claude/rules/python-env.md` | uv usage |

Skills live in `.claude/skills/<name>/SKILL.md`, and `.agents/skills/` holds one symlink per skill so Codex finds the same files; when adding a skill, add its symlink there too. Current skills: `run-playwright-tests` for running and reading the end-to-end suite, `process-new-run` for taking a new Empirica export through the pipeline, and `build-paper` for compiling the manuscript and recovering from Dropbox-corrupted builds.

## Project instructions

- Fetch current library documentation with Context7 (`resolve-library-id`, then `query-docs`) for R packages, Python libraries, Empirica, and Playwright instead of working from memory.
- `README.md` is public-facing documentation for reviewers. When you add or change a workflow, script, or tool that a user would need, update the README as well as this guide or the relevant rule.
- Do not commit or push unless asked. When you do commit, the pre-commit hook runs the server unit tests for changes under `experiment/server/src/` and the data integrity suite for changes under `analysis/` or `data/pilots/`.
- Playwright and holistic test runs take many minutes. Pipe their output through `tee` to a stable file and launch runs longer than ten minutes detached (`nohup ... &`) so the harness cannot kill them.
- LLM steps (the message filter, the Phase 1 simulation) spend Vertex AI credit; estimate the number of calls and say so before running them.
