# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multiplayer reference game experiment built with Empirica studying lexical variation and social signaling. Players communicate about tangram images in groups, with different experimental conditions affecting group dynamics in Phase 2.

The registered report manuscript is in `paper/main.tex` (compiled with `cd paper && latexmk -pdf main.tex`). The paper describes the framing, design, and analysis plan. Statistics flow from analysis notebooks into the paper via `\newcommand` definitions in `paper/stats/*.tex` (see data-pipeline.md for details).

We plan to submit the registered report to Nature Human Behavior. The submission guidelines are at https://www.nature.com/nathumbehav/submission-guidelines/registeredreports

**Experimental Design:**
- 9 players in 3 groups of 3
- Phase 1: Within-group reference game (6 blocks)
- Phase 2: Continued reference game with condition-dependent behavior (6 blocks)
- 4 between-subjects conditions:
  - `refer_separated`: same groups throughout Phase 2
  - `refer_mixed`: groups reshuffled every trial in Phase 2, masked identities
  - `social_mixed`: reshuffled every trial + social guessing task in Phase 2
  - `social_first`: told about social identification reward before Phase 1, reshuffled + social guessing in Phase 2

## README.md

`README.md` in the project root is the public-facing documentation — reviewers and the public read it to understand the repo and how to run the code. When you add or change a workflow, script, or tool that a user would need to know about, update the README too (not just CLAUDE.md or rules files).

## Rules reference

Path-scoped rules are in `.claude/rules/`. Read the relevant file when the topic comes up but the rule isn't auto-loaded:

- **testing.md** — manual testing, Playwright MCP tips, Playwright test suite
- **sentry.md** — Sentry project details and SDK usage
- **data-pipeline.md** — data export/backup, analysis pipeline, combining runs
- **llm-simulation.md** — LLM simulation and non-referential message filter
