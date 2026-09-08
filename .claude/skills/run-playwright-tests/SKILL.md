---
name: run-playwright-tests
description: Use when running, debugging, or reading results from the Playwright end-to-end suite or the server unit tests in experiment/ -- "run the tests", "run group 4", "why did the idle test fail" -- and after changing server callbacks, client components, shared constants, or test helpers.
allowed-tools: Bash, Read, Grep, Glob
---

# Run the Playwright suite

Facts about the suite (groups, helpers, config values) are in `.claude/rules/testing.md`. This is the procedure.

1. **Pick the narrowest run.** `npm run test:unit` (vitest on `scoring.js` and `reshuffling.js`, under a second) for scoring or reshuffling changes; `npm run test:groupN` for one group; `npm run test:group4:fast` for idle and viability tests (shortened timers); `npm test` for everything in test mode; `npm run test:holistic` for a full game at production timing. All from `experiment/`. Never run a bare `npx playwright test <file>` or `--project=group-N`: the groups are chained and Playwright replays every earlier group first. One file:

   ```bash
   npx playwright test reset-server.setup tests/<category>/<file>.spec.ts \
     --project=setup-N --project=group-N --no-deps
   ```

2. **Capture output to a stable file.** Always `2>&1 | tee <scratch>/test-<group>.txt`. Anything longer than about ten minutes (full suite, group 4 without fast timing, holistic) must be launched detached, `nohup npm run ... > <file> 2>&1 &`, and polled, because background shell commands are killed at the harness cap and their output files disappear.

3. **Recover a dirty state before rerunning.** Free both ports with `lsof -ti :3000 -ti :8844 | xargs kill -9`, and delete `experiment/.empirica/local/tajriba.json` if a crashed run left the framework's reset undone.

4. **Read results from the file, not memory.** `npm run test:report` opens the HTML report; screenshots, traces, and video for failures are under `experiment/test-results/`.

5. **Triage a failure in this order.** (a) UI copy drifted from an assertion string (the most recent fixes were exactly this); (b) a timing or block constant changed in `shared/constants.js` without the mirror in `tests/helpers/constants.ts`; (c) the test clicked Continue before every player reached the stage; (d) a real logic regression. Confirm (d) with `npm run test:unit` or a targeted single-file run before editing server code.

6. **Report** which groups ran, pass and fail counts, and the output file path. Never claim a pass from a partial log or from a run that was still in progress.
