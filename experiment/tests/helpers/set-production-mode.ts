// Side-effect module: forces production-mode constants for the holistic specs.
// Import it BEFORE any module that reads constants.ts, so that the
// TEST_MODE-dependent values (PHASE_1_BLOCKS, PHASE_2_BLOCKS, ...) take their
// production values in the worker that runs those specs.
//
// Only inside a worker. Playwright also loads every spec file in the runner
// process when it collects the test list for a multi-project run (`npm test`),
// and a flip there would be inherited by every worker it later forks: the
// test-mode groups would then start the Empirica server with TEST_MODE=false
// and play 6+6 blocks against specs written for 3+2 (a full `npm test` did
// exactly that on 2026-09-17). Workers carry TEST_WORKER_INDEX; the runner
// does not.
if (process.env.TEST_WORKER_INDEX !== undefined) {
  process.env.TEST_MODE = 'false';
}
