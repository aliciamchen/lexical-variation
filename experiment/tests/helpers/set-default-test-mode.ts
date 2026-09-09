// Imported first by constants.ts so the test runner shares the server's
// default: TEST_MODE=true unless the environment says otherwise (the server
// child gets the same default in server-manager.ts). shared/constants.js
// reads process.env.TEST_MODE === "true" at import time, so this must run
// before it is imported.
if (process.env.TEST_MODE === undefined) {
  process.env.TEST_MODE = 'true';
}
