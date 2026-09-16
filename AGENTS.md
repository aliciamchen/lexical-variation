# Agent guide

This file holds durable, agent-facing context for this repository and is read by every coding agent (`CLAUDE.md` is a symlink to it). The public project overview and run instructions are in `README.md`; the `Makefile` is the command source of truth for the data pipeline (`make help`). Area-specific facts are in `.claude/rules/`, procedures in the skills under `.claude/skills/`.

## Project status

This is a multiplayer reference game built with Empirica for studying lexical variation and social signaling: nine players in three groups of three describe tangram images, and four between-subjects conditions vary whether groups stay separate or are mixed in Phase 2 and whether players are rewarded for identifying each other's group. The pilot is complete, and the manuscript in `writing/preregistration/main.tex` was written as a Stage 1 registered report. That manuscript now serves as the preregistration. The next phase is to collect the full sample, run the preregistered analyses (`analysis/00`–`05_*.qmd`), and submit the result as a regular article. `full-sample-todos.md` is the checklist for getting there; do not treat pilot-only assumptions (dataset paths, `PILOT_RUNS`, cached RDS fits) as permanent.

## Experimental design

- 9 players in 3 groups of 3; Phase 1 is a within-group reference game (6 blocks); Phase 2 continues for 6 blocks with condition-dependent behavior.
- Conditions: `refer_separated` (same groups throughout), `refer_mixed` (groups reshuffled every trial, identities masked), `social_mixed` (reshuffled plus a social guessing task), `social_first` (told about the social identification reward before Phase 1, then reshuffled plus social guessing).
- `original_group` (A, B, C) persists for the whole game; `current_group` changes per trial in mixed conditions. In mixed Phase 2, anonymous avatars are re-seeded per trial and chat names are masked, so `senderName` is uninformative there while `senderId` remains valid.
- `TEST_MODE` (default false) shortens games to 3+2 blocks; timers and the idle threshold are always the production values (45 s / 25 s selection, 3 idle rounds). The Playwright framework sets it; `IDLE_TEST_TIMING` shortens timers further for idle suites.

## Sources of truth

- Game configuration (player counts, blocks, timing, scoring) is `experiment/shared/constants.js`; `experiment/tests/helpers/constants.ts` must mirror it.
- Game logic is `experiment/server/src/callbacks.js`; scoring, reshuffling, compensation, idle classification, the Phase 1 accuracy screen, and tangram-set assignment are importable modules (`scoring.js`, `reshuffling.js`, `compensation.js`, `idle.js`, `accuracy.js`, `tangrams.js`) with vitest unit tests beside them. Treatments are in `experiment/.empirica/treatments.yaml`: two per condition, one per tangram set, so sets are counterbalanced by alternating treatments across sessions.
- `analysis/config.R` defines dataset paths, palettes, and the ggplot theme and sources every helper in `analysis/R/` (data preparation, group specificity, mixed-model simplification, contrasts, Bayes factors, stats-to-LaTeX, plots); every notebook sources it and loads its tables with `load_tables()`, and all ggplots use its scales and theme. The R helpers are tested by `analysis/tests/` (`Rscript analysis/tests/run_all.R`). `analysis/plot_style.py` is the Python counterpart.
- `writing/preregistration/main.tex` describes the design and analysis plan. Statistics reach it only through `\newcommand` macros written by the notebooks to `writing/preregistration/stats/*.tex`; never hardcode a computed value in the manuscript.
- Local, gitignored audit notes are in `reviews/` (dated files; the July 2026 full audit and the September 2026 manuscript-alignment check are the current ones). They record verified-correct behavior and open findings; check them before re-investigating game logic or the analysis joins.

## Repository boundaries

- `writing/` holds one directory per Overleaf project, each gitignored and mirrored to Overleaf through Dropbox: `writing/preregistration/` is the Stage 1 manuscript that serves as the preregistration, and the full-sample manuscript will be `writing/manuscript/`, a separate Overleaf project cloned from it. Read and edit them locally when asked to work on a manuscript, and run `bash figures/sync_figures.sh [writing/<project>]` to copy SI figures into a project's `figures/`.
- `experiment/data/` holds raw Empirica export zips with identifiable participant data and is gitignored. `data/runs/` (per-run extracts) is gitignored too. Only the anonymized outputs in `data/<dataset>/` (`data/pilots/` for the pilot) are committed; `analysis/extract_run.py` strips the sensitive columns and a pre-commit hook blocks anything that looks like a participant identifier.
- `reviews/` holds local audit and design notes and is gitignored; do not reference it from public docs.
- `operations/` holds the tooling for running a data-collection session, separate from the Empirica app: `session.py` (the Prolific API client for recruitment, messaging, and payment), `game_constants.py` (completion codes, pay figures and condition names parsed out of `experiment/shared/constants.js`, so the tooling cannot drift from the running experiment), `copy_tajriba.sh` (export backups), `messages/` (participant message templates), `procedures.md` (the session runbook), and `test_session.py` (`make test-ops`, no API or data needed). Every `session.py` command that changes anything prints its plan and asks before acting (`--yes` skips the prompt); ids are shared between steps through `--session <name>`. Three facts worth knowing before changing any of it: Empirica exports are cumulative, so `extract_run.py` scopes the payment files to one batch and `pay` refuses anyone another run's ledger records as paid; lobby-timeout participants exist only as Prolific submissions and are paid from there, not from any export; and `publish --at` is read in the timezone the session's announced time names, not the machine's.
- `.env` holds the production hostname, Sentry DSN, organization, and Prolific API token. Never read or print it; `.env.example` documents the variables.

## Workflow and commands

```text
experiment (Empirica) -> operations/copy_tajriba.sh -> experiment/data/<ts>/*.zip
  -> extract_run.py -> combine_runs.py -> process_data.py -> data/<dataset>/, analysis/derived/<dataset>/
  -> Quarto notebooks -> figures/<dataset>/ + writing/preregistration/stats/*.tex -> writing/preregistration/main.tex
```

The pipeline is keyed by a dataset name (`DATASET`, default `pilots`; `analysis/dataset_paths.py` and `analysis/config.R` define the layout). The full sample will be a second dataset beside the pilot, not an edit of the pilot paths.

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
