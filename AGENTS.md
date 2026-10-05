# Agent guide

This file holds durable, agent-facing context for this repository and is read by every coding agent (`CLAUDE.md` is a symlink to it). The public project overview and run instructions are in `README.md`; the `Makefile` is the command source of truth for the data pipeline (`make help`). Area-specific facts are in `.claude/rules/`, procedures in the skills under `.claude/skills/`.

## Project status

This is a multiplayer reference game built with Empirica for studying lexical variation and social signaling: nine players in three groups of three describe tangram images, and four between-subjects conditions vary whether groups stay separate or are mixed in Phase 2 and whether players are rewarded for identifying each other's group. The pilot is complete, and the manuscript in `writing/preregistration/main.tex` was written as a Stage 1 registered report. That manuscript now serves as the preregistration. The full sample (dataset `full`) is being collected in manual Prolific sessions until the preregistered stopping rule is reached; after that come the preregistered analyses (`analysis/00`–`05_*.qmd`) and a regular article. `full-sample-todos.md` (local, gitignored) is the checklist for getting there; do not treat pilot-only assumptions (dataset paths, `PILOT_RUNS`, cached RDS fits) as permanent. "During data collection" below has the rules that hold until collection ends.

## Experimental design

- 9 players in 3 groups of 3; Phase 1 is a within-group reference game (6 blocks); Phase 2 continues for 6 blocks with condition-dependent behavior.
- Conditions: `refer_separated` (same groups throughout), `refer_mixed` (groups reshuffled every trial, identities masked), `social_mixed` (reshuffled plus a social guessing task), `social_first` (told about the social identification reward before Phase 1, then reshuffled plus social guessing).
- `original_group` (A, B, C) persists for the whole game; `current_group` changes per trial in mixed conditions. In mixed Phase 2, anonymous avatars are re-seeded per trial and chat names are masked, so `senderName` is uninformative there while `senderId` remains valid.
- `TEST_MODE` (default false) shortens games to 3+2 blocks; timers and the idle threshold are always the production values (45 s / 25 s selection, 3 idle rounds). The Playwright framework sets it; `IDLE_TEST_TIMING` shortens timers further for idle suites.

## Sources of truth

- Game configuration (player counts, blocks, timing, scoring, the `EXIT_REASONS` the server writes when it removes a player, the quiz attempt limit, the lobby wait) is `experiment/shared/constants.js`; `experiment/tests/helpers/constants.ts` re-exports it, and `operations/game_constants.py` parses it so the payment tooling cannot drift. `LOBBY_TIMEOUT_MINUTES` must match `duration` in `experiment/.empirica/lobbies.yaml`, which Empirica reads directly.
- Game logic is `experiment/server/src/callbacks.js`; scoring, reshuffling, compensation, idle classification, the Phase 1 accuracy screen, and tangram-set assignment are importable modules (`scoring.js`, `reshuffling.js`, `compensation.js`, `idle.js`, `accuracy.js`, `tangrams.js`) with vitest unit tests beside them. Every callback is wrapped in `guard()` (`guard.js`), because Empirica does not catch what a callback throws and an uncaught one leaves a group half-updated while the others play on; see `.claude/rules/architecture.md` before touching a callback's registration. Treatments are in `experiment/.empirica/treatments.yaml`: two per condition, one per tangram set, so sets are counterbalanced by alternating treatments across sessions.
- `analysis/config.R` defines dataset paths, palettes, and the ggplot theme and sources every helper in `analysis/R/` (data preparation, group specificity, mixed-model simplification, contrasts, Bayes factors, convergence, multiple membership, social identification, attrition, survey, reshuffle health, stats-to-LaTeX, plots); every notebook sources it and loads its tables with `load_tables()`, and all ggplots use its scales and theme. The R helpers are tested by `analysis/tests/` (`Rscript analysis/tests/run_all.R`). `analysis/plot_style.py` is the Python counterpart.
- `writing/preregistration/main.tex` describes the design and analysis plan. Statistics reach a manuscript only through `\newcommand` macros; never hardcode a computed value. `SI_pilot.qmd` writes the pilot's to `writing/preregistration/stats/`, and notebooks `00`-`05` write the full sample's to `writing/manuscript/stats/` (one file per notebook, macro names prefixed by notebook).
- Local, gitignored audit notes are in `reviews/` (dated files; the July 2026 full audit, the September 2026 manuscript-alignment check, the September 16 readiness audit `2026-09-16-readiness-audit.md`, the server crash and Empirica upgrade note `2026-09-23-server-crash-and-empirica-upgrade.md`, and the October 4 housekeeping audit `2026-10-04-housekeeping-audit.md`, which lists the open tasks and decisions from the first weeks of collection, are the current ones). They record verified-correct behavior and open findings; check them before re-investigating game logic or the analysis joins.

## Repository boundaries

- `writing/` holds one directory per Overleaf project, each gitignored and mirrored to Overleaf through Dropbox: `writing/preregistration/` is the Stage 1 manuscript that serves as the preregistration, and the full-sample manuscript will be `writing/manuscript/`, a separate Overleaf project cloned from it. Read and edit them locally when asked to work on a manuscript, and run `bash figures/sync_figures.sh [writing/<project>]` to copy SI figures into a project's `figures/`, but not into the frozen preregistration, whose group-specificity figure was edited by hand.
- `data/<dataset>/` also takes two optional inputs, absent for the pilot: `exclude_games.txt` drops rehearsal or deploy-check games that ran on the production server, and `participant_exclusions.csv` (`playerId,reason`) removes only the observations a post-hoc exclusion touches, recomputing every derived measure without them. It gains `dropouts.csv` (quiz failures and lobby timeouts, who appear in no game) and a `speaker_utterances_filtered.source.json` sidecar that makes a stale filtered file impossible to analyze silently.
- `experiment/data/` holds raw Empirica export zips with identifiable participant data and is gitignored. `data/runs/` (per-run extracts) is gitignored too. The pilot's anonymized outputs in `data/pilots/` are committed. The full sample's (`data/full/`, `analysis/derived/full/`, and the slide figures in `figures/meetings/`) are gitignored and stay local until collection ends: none of it is to be made public before then, and the public release will be converted to the RefBank format for reference-game corpora (mapping notes in `full-sample-todos.md`) rather than committed in the pipeline's own layout. `analysis/extract_run.py` strips the sensitive columns and redacts Prolific-id-shaped tokens typed into free text, and the git pre-commit hook in `.githooks/pre-commit` blocks anything that looks like a participant identifier. The hook is active only after `git config core.hooksPath .githooks` (once per clone); the Claude Code hook `.claude/hooks/pre-commit-check.sh` runs the same script before an agent's `git commit`.
- `reviews/` holds local audit and design notes and is gitignored; do not reference it from public docs.
- `operations/` holds the tooling around a data-collection session, separate from the Empirica app. Recruitment, approvals and payment are done by hand on the Prolific website; the tooling only reads. `payments.py` (`make payments`) works out what each Prolific study still owes: it reads every export zip in `runs.txt`, identifies each player by the Prolific id they entered on the identifier screen, places them in the study where that id has a submission (matched by completion code, then by time, so players who reached a game through a link sent by message are still paid in the right study), pays anyone with no game-study submission through their scheduling-survey submission (`unsubmitted.csv`), and checks each study's submissions on Prolific with read-only calls for status and bonuses already paid, writing two paste-ready bulk-bonus files per study (`1_main.csv`, then `2_overtime.csv`) to the gitignored `data/payments/<dataset>/<study>/`, and it flags anyone who took part in more than one session. `tally.py` (`make tally`) counts games per treatment, marks the one with the fewest started games for the next session, and reports progress against the cap of 120 started games. `prolific.py` is the read-only API client, `game_constants.py` parses completion codes, pay figures and condition names out of `experiment/shared/constants.js` so the tooling cannot drift from the running experiment, `copy_tajriba.sh` takes export backups, and `procedures.md` is the session runbook. `make test-ops` runs `test_payments.py`, `test_tally.py` and `test_prolific.py`, which need no API access or data. Two facts worth knowing before changing any of it: Empirica exports are cumulative snapshots of one server, so a later export of the same server replaces an earlier one in `runs.txt`; and lobby-timeout participants (including overflow players Empirica turns away with "no more games", who are shown the same screen) have player records but no started game, so `payments.py` finds them by the lobby-timeout code on their Prolific submission, or, when they returned without entering it, by the lobby record in the export. The earlier recruitment and payment CLI, `session.py`, was retired on 2026-09-23 and is in git history.
- `.env` holds the production hostname, Sentry DSN, organization, and Prolific API token. Never read or print it; `.env.example` documents the variables. `experiment/.empirica/empirica.toml` holds the admin panel password and the tajriba service token and is gitignored for the same reason (`empirica.toml.example` is the template; `empirica bundle` ships the real file to the server, so rotating the values means rebuilding and redeploying).

## Workflow and commands

```text
experiment (Empirica) -> operations/copy_tajriba.sh -> experiment/data/<ts>/*.zip
  -> extract_run.py -> combine_runs.py -> process_data.py -> data/<dataset>/, analysis/derived/<dataset>/
  -> Quarto notebooks -> figures/<dataset>/ + writing/preregistration/stats/*.tex -> writing/preregistration/main.tex
  (payments, alongside:) every zip in runs.txt + Prolific (read-only) -> operations/payments.py -> data/payments/<dataset>/<study>/
```

The pipeline is keyed by a dataset name (`DATASET`, default `pilots`; `analysis/dataset_paths.py` and `analysis/config.R` define the layout). The full sample will be a second dataset beside the pilot, not an edit of the pilot paths. Put a new export through `make smoke ZIP=<path>` first: it runs the whole pipeline and the integrity suite on a throwaway dataset, so a bad export is caught before it touches a real dataset.

```bash
uv sync                       # Python; run scripts with `uv run python ...`
# R: renv::restore()           # analysis notebooks (Quarto + R)
cd experiment && npm install  # Empirica app and Playwright tests
make help                     # pipeline targets (extract, combine, process, test, notebooks)
```

Run the experiment locally with `cd experiment && rm .empirica/local/tajriba.json && empirica` (admin at `localhost:3000/admin`). Run tests through the npm scripts in `experiment/package.json` (`npm run test:unit`, `npm run test:group1`…`group4`, `npm test`), never through a bare `npx playwright test <file>`, which replays every earlier group.

## During data collection

- **The production server runs live games.** Never run anything that can stop or restart a game while one may be running: `systemctl restart` or `stop` on the `empirica` service, deleting, moving or truncating `~/empirica/.empirica/local/tajriba.json`, uploading a bundle (the server restarts whenever `~/empirica/empirica.tar.zst` changes), rebooting, or killing processes. Before any such command, ask the author to confirm that no game is running at that moment, even if a similar command was approved earlier in the conversation; `.claude/hooks/confirm-server-commands.sh` makes Claude Code ask as well. Say whether a command touches the server before running it, and keep tests local. Read-only checks (`empirica export`, `journalctl`, `free`, `uptime`) are safe, but `systemctl status empirica` and `ps -eo args` print the tajriba service token on the process command line: use `systemctl is-active empirica` and never print process arguments.
- **Raw exports are read-only.** Each `experiment/data/<timestamp>/` folder (the export zip and the server log saved beside it) is the only copy of what the server recorded at that moment. Read it and derive from it, but never edit, rename, move or delete anything inside it; everything downstream (`data/runs/`, `data/<dataset>/`, `analysis/derived/<dataset>/`) is regenerated from it.
- **Stopping rule and allocation.** Collection runs to the preregistered cap of 120 started games, balanced by started games: 30 per condition, 15 per treatment (condition by tangram set). `make tally` marks the treatment with the fewest started games, which is the one the next session runs. Sessions run five games of a single treatment; a sixth game roughly doubles the server's pauses between stages and pushes most games past 60 minutes.
- **Interim looks are fine.** The author confirmed on 2026-10-04 that the full sample will be collected whatever the results show, so every notebook, including the hypothesis tests in `02` and `03`, and condition-level plots may be rerun as data arrive. The preregistered analyses were first run on 57 games on 2026-09-27, when stopping early for budget reasons was still being considered.
- **After a session**, follow the `process-new-run` skill: process the newest export in which every game has ended and the exit surveys are in, report the tally and the payments table, and refresh the published artifacts (memory has their URLs and builders).
- **Backups.** The raw export folders are also backed up on MIT's Engaging cluster. Agents do not access it.

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
- The author often works in parallel sessions and edits files by hand. Re-read a file before editing it, never revert an edit you did not make, and leave hunks that are not yours out of your commits.
- Do not commit or push unless asked, and commit directly on `main` when asked. When you do commit, the pre-commit hook (`.githooks/pre-commit`) runs the server unit tests for changes under `experiment/server/src/` or `experiment/shared/`, the R helper tests for changes under `analysis/R/` or `analysis/tests/`, and the Python suites for changes under `analysis/*.py`, `data/<dataset>/`, or `operations/`.
- Playwright and holistic test runs take many minutes. Pipe their output through `tee` to a stable file and launch runs longer than ten minutes detached (`nohup ... &`) so the harness cannot kill them.
- LLM steps (the message filter, the Phase 1 simulation) spend Vertex AI credit; estimate the number of calls and say so before running them.
