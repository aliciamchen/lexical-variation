---
paths:
  - "experiment/client/src/**"
---

# Sentry (error monitoring)

The client app reports errors to Sentry via `@sentry/react`, initialized in `experiment/client/src/index.jsx` with error tracking, session replays (100%), browser tracing, and structured logs. `Introduction.jsx` sets the Sentry user from the Prolific URL parameters.

**Project details:**
- Organization: set via `SENTRY_ORG` in `.env`
- Project: `javascript-react`
- Region URL: `https://us.sentry.io`
- Production URL: set via `EMPIRICA_SERVER` in `.env`
- DSN: set via `VITE_SENTRY_DSN` in `.env` (never read `.env` directly; the values are secrets)

**MCP server:** the Sentry MCP server (`https://mcp.sentry.dev/mcp`, declared in `.mcp.json` and `.codex/config.toml`) exposes `search_issues`, `get_issue_details`, `search_events`, and `analyze_issue_with_seer`. Use it to query production issues directly.

**Workflow:** when investigating a production bug, check Sentry for recent issues, then cross-reference the stacktrace with the client source in `experiment/client/src/`. Reference issue IDs in commit messages (e.g. `Fixes JAVASCRIPT-REACT-1`) to auto-resolve issues on merge. During live sessions, keep the Sentry dashboard open to watch for client errors, slow page loads, and websocket disconnections.

**SDK usage:** for `Sentry.captureException`, `Sentry.startSpan`, or the `logger` API, fetch the current `@sentry/react` documentation with Context7 rather than working from memory.
