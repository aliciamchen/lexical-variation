/**
 * The server's vitest also runs the tests in `shared/`, which is where logic
 * used by the client but worth unit testing lives (see shared/engagement.js).
 * The client has no test runner of its own: it is pinned to Vite 5, and every
 * vitest new enough to install alongside it requires Vite 6 or later.
 */
export default {
  test: {
    include: ["src/**/*.test.js", "../shared/**/*.test.js"],
  },
};
