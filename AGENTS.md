# Agent guide

Durable context for coding agents working in this repository. `CLAUDE.md` is a symlink to this file; keep it agent-neutral, because Codex and other tools read it too. `README.md` is the public overview and run instructions for reviewers, `make help` lists the pipeline commands, `.claude/rules/` holds area facts that load when you work in that area, and `.claude/skills/` holds procedures. `full-sample-todos.md` is the author's dated log of decisions, deviations and open tasks, and `reviews/` holds audit notes; both are gitignored and must not be referenced from public docs.

## Status

A nine-player Empirica reference game for studying lexical variation and social signaling: three groups of three describe tangrams, and four between-subjects conditions (`refer_separated`, `refer_mixed`, `social_mixed`, `social_first`) vary whether the groups are mixed in Phase 2 and whether players are rewarded for identifying each other's group. `writing/preregistration/main.tex` is the frozen preregistration. The full sample, dataset `full`, is collected and frozen: 120 started games in 31 sessions between 2026-09-22 and 2026-10-08, 63 of them intact, reproducing byte for byte from the raw exports. No production server exists; the droplet was destroyed on 2026-10-10 after the exports were copied off-site. What remains is the author's exclusion review and classifier check, the confirmatory render (the `run-analysis` skill), the article in `writing/manuscript/`, and the public release in the RefBank format.

## Commands

```bash
uv sync && uv run python <script>     # Python; never bare python or pip
Rscript -e 'renv::restore()'          # R
cd experiment && npm install          # Empirica app and Playwright
make help                             # extract, combine, process, frames, test, notebooks, descriptives, smoke, payments, final-exports
make test DATASET=full                # integrity suite plus the Python and R unit tests
cd experiment && npm run test:unit    # server unit tests; Playwright only through the npm scripts
```

## Hard rules

- Never read or print `.env` or `experiment/.empirica/empirica.toml`, never print a participant (Prolific) id, and never put a hostname, organization name or token in a committed file. `.env.example` documents the variables.
- `experiment/data/<timestamp>/` holds the raw exports and is read-only input: never edit, move or delete anything there. `data/full/`, `analysis/derived/full/`, `figures/meetings/`, `backups/`, `data/runs/` and `data/payments/` stay local until the RefBank release. The pilot dataset, its SI notebook and the LLM Phase 1 benchmark were retired from the working tree and remain at the git tag `pilot-archive`.
- `writing/` is gitignored, one Overleaf project per directory, synced through Dropbox. The preregistration is frozen: do not change its text, models or figures. Statistics reach a manuscript only through generated `\newcommand` macros, never typed in.
- In an interactive session, commit only when asked, on `main`, and do not push: the repository is public and the author publishes. Work the author will not watch (a cloud or background session, a worktree, or a self-contained piece such as the RefBank converter) goes on a branch named `agent/<topic>`: commit freely there, push it, and open a draft pull request for the author to review and merge. Never push to `main`, force-push or merge a pull request; a hook blocks these. Before committing, say what is uncommitted and leave out hunks you did not make: the author edits by hand and runs parallel sessions, so re-read a file before editing it and never revert an edit that is not yours.
- A worktree or a cloud clone has none of the gitignored inputs (`.env` and `empirica.toml` are copied in through `.worktreeinclude`; the raw exports, `data/full/` and `analysis/derived/full/` are not), so data processing, renders and manuscript work stay in the main checkout.
- The message filter spends Vertex AI credit: state the number of calls and get a yes first.
- The experiment code is the record of what ran. Change it for tests, documentation or a future deployment only, and never edit a test to make it pass or without saying so.
- Hooks enforce the sharp edges (`.claude/settings.json`, mirrored in `.codex/hooks.json`): recursive deletes are blocked, the pre-commit check scans for identifiers and runs the test suites, and pushes to main, force pushes and pull-request merges are denied 

## Working with the author

- Present decisions as a numbered list, each with the recommended option and the reason, and mark what is optional; the author answers by number.
- Verify at the source before stating how something behaves or how many of something there are: Empirica from the installed `@empirica/core` (treat Empirica as unmaintained), Prolific from its records, counts from the exports. Findings relayed from another session are leads, not facts, and the current data beat anything remembered from an earlier session. Say which statements are inferences.
- When you find one error, search the session's work for others of the same kind before reporting.
- Explain mechanisms in plain language when asked why. The maintainers are researchers, not software engineers, and "I don't understand" means simplify, not elaborate.
- Report every change beyond the one asked for. When the author defers something, record it in `full-sample-todos.md` and move on. After a task, say what comes next.
- The preregistered models are frozen: do not re-audit random effects, priors or inference policies, and do not propose refinements. The author wants simple, interpretable models that are not wrong, and the accepted and declined suggestions are in `reviews/prereg-revision-decisions.md`.
- Estimate money (participant pay, API calls) from actual spend with fees included, and default to the minimal scope.
- For long runs (Playwright, renders, Bayes factors) give a time estimate, pipe output through `tee` to a stable file, launch anything over ten minutes detached with `nohup`, and propose work to do meanwhile.

## Style

- Sentence case for headings and titles; US spelling in prose (library API names keep theirs); the native R pipe `|>`; no digits in LaTeX macro names.
- Comments, docstrings and docs describe current behavior only, never history or before-and-after comparisons, which belong in `full-sample-todos.md`. Public docs are natural prose written for reviewers and the author's future self.
- Commit messages follow conventional commits, `type(scope): subject`, lower case, imperative, no period, with a body only when the why is not in the diff.
- Manuscript text is short and conceptual, with no statistical minutiae and no new SI sections unless asked; apply agreed edits in the `.tex`.

## Sources of truth

- Game configuration is `experiment/shared/constants.js` (`tests/helpers/constants.ts` re-exports it and `operations/game_constants.py` parses it); treatments are in `experiment/.empirica/treatments.yaml`; game logic is `experiment/server/src/callbacks.js` with pure modules beside it, every callback wrapped in `guard()`.
- The data pipeline is `pipeline/`: `dataset_paths.py` defines the dataset layout (mirrored in `analysis/config.R`) and `process_data.py` runs the steps, each a module run with `python -m pipeline.<name>`. Analysis code is `analysis/config.R` and `analysis/R/`, which every notebook sources (tests in `analysis/tests/`). The notebooks `analysis/checks.qmd`, `primary.qmd` and `secondary.qmd` write the inferential macros in `writing/manuscript/stats/`, `primary.qmd` its per-game estimates in `analysis/results/<dataset>/`, and `analysis/descriptives.py` the descriptive macros; `writing/preregistration/stats/` is frozen with the preregistration. `analysis/plot_style.py` is the one description of how the article's figures look, and `analysis/stats_tex.py` is the Python twin of `R/stats_tex.R`.
- The per-dataset inputs (`runs.txt`, `exclude_games.txt`, `participant_exclusions.csv`, `integrity_exceptions.csv`, `payment_adjustments.csv`) are defined in `.claude/rules/data-pipeline.md`.
- Fetch current library documentation with Context7 for R packages, Python libraries, Empirica and Playwright instead of working from memory.

## Rules and skills

| Rule | Covers |
|------|--------|
| `.claude/rules/architecture.md` | the experiment: server callbacks, client, identity masking, exit routing |
| `.claude/rules/testing.md` | the Playwright suite and server unit tests |
| `.claude/rules/sentry.md` | error monitoring in the client |
| `.claude/rules/data-pipeline.md` | datasets, pipeline steps, notebooks, the definitions that are easy to get wrong |
| `.claude/rules/message-filter.md` | the LLM message filter |
| `.claude/rules/operations.md` | payments, blocklist and the other Prolific tooling |
| `.claude/rules/python-env.md` | uv and the Python environment |

Skills are in `.claude/skills/<name>/SKILL.md`, with a symlink per skill in `.agents/skills/` for Codex: `run-playwright-tests`, `rebuild-dataset`, `run-analysis` and `build-paper`. An agent whose harness does not load rules by path should read the rule before changing files in its area.
