---
name: run-playwright-tests
description: Use when running, debugging, or reading results from the Playwright end-to-end suite or the server unit tests in experiment/ -- "run the tests", "run group 4", "why did the idle test fail" -- and after changing server callbacks, client components, shared constants, or test helpers.
allowed-tools: Bash, Read, Grep, Glob
---

# Run the Playwright suite

Facts about the suite (groups, helpers, config values) are in `.claude/rules/testing.md`. This is the procedure.

1. **Pick the narrowest run.** `npm run test:unit` (vitest on every pure server module and the tests in `shared/`, 11 files in about a second; run it from `experiment/`, never `npx vitest` from there, which finds no config and globs the Playwright specs into an alarming pile of failures) for scoring or reshuffling changes; `npm run test:groupN` for one group; `npm run test:group4:fast` for idle and viability tests (shortened timers); `npm test` for everything in test mode; `npm run test:holistic` for a full game at production timing. All from `experiment/`. Never run a bare `npx playwright test <file>` or `--project=group-N`: the groups are chained and Playwright replays every earlier group first. One file:

   ```bash
   npx playwright test reset-server.setup tests/<category>/<file>.spec.ts \
     --project=setup-N --project=group-N --no-deps
   ```

2. **Capture output to a stable file.** Always `2>&1 | tee <scratch>/test-<group>.txt`. Anything longer than about ten minutes (full suite, group 4 without fast timing, holistic) must be launched detached, `nohup npm run ... > <file> 2>&1 &`, and polled, because background shell commands are killed at the harness cap and their output files disappear.

3. **Recover a dirty state before rerunning, and only when nothing else is running.** `pgrep -fl "playwright test"` must show no other run: runs share ports 3000 and 8844 and reset the same server, and the harness refuses to start while another run holds `experiment/.empirica/local/playwright-run.lock` (a lock left by a dead process is cleared automatically). Then free both ports with `npm run test:free-ports` (it refuses while a live run holds the lock; never use a raw `lsof ... | xargs kill -9`, which would kill that run's server), and delete `experiment/.empirica/local/tajriba.json` if a crashed run left the framework's reset undone. Do not edit files under `experiment/server/src` while a run is in progress: the dev server restarts on every change and the running stage never ends.

4. **Read results from the file, not memory.** `npm run test:report` opens the HTML report; screenshots, traces, and video for failures are under `experiment/test-results/`.

5. **Check the server log, and expect the teardown to.** The harness writes the Empirica server's output to `experiment/test-results/empirica-server.log`, and the global teardown fails the run if it contains a `CALLBACK ERROR` or an unhandled rejection. This is the only way a server-side failure is visible: `guard()` contains callback errors so the remaining players can finish, so the browser looks healthy and no assertion trips. A run that fails **only** in teardown means the game played fine and the server threw; read that log, not the specs.

6. **Triage a failure in this order.** Suspect the harness before the game: every one of the three failures found on 2026-09-17 was in the harness, and each looked like a broken experiment.

   (a) **Wrong mode.** Check the `[server-manager] Starting empirica with TEST_MODE=...` line first. Groups 1 to 4 need `true`; only the holistic group needs `false`. A flip leaking out of the holistic specs into the runner process once made every group play 6+6 blocks against specs written for 3+2.
   (b) **A filtered run with no server.** If tests fail in milliseconds against an unreachable admin page, no server started. Playwright's `--grep` filters every project including the setup that starts it, which is why both resets are tagged `@setup` and `test:smoke` greps `@smoke|@setup`.
   (c) **An assumed removal.** A spec that idles players for exactly `MAX_IDLE_ROUNDS` and then asserts they are gone is fragile: a round whose speaker stayed silent resets the counter by design. Wait for the removal instead of counting rounds.
   (d) UI copy drifted from an assertion string; (e) a constant changed in `shared/constants.js` without the mirror in `tests/helpers/constants.ts`; (f) the test clicked Continue before every player reached the stage; (g) a real logic regression. Confirm (g) with `npm run test:unit` or a targeted single-file run before editing server code.

   Also note a failure in group 4 makes Playwright skip the holistic group as a failed dependency, so `npm test` reporting "35 did not run" means the production-timing check never happened.

7. **Report** which groups ran, pass and fail counts, and the output file path. Never claim a pass from a partial log or from a run that was still in progress.
