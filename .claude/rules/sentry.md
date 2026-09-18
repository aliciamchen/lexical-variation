---
paths:
  - "experiment/client/src/**"
---

# Sentry (error monitoring)

The client app reports errors to Sentry via `@sentry/react`, initialized in `experiment/client/src/index.jsx` with error tracking, browser tracing, structured logs, and session replays for sessions that hit an error only (`replaysSessionSampleRate: 0`, `replaysOnErrorSampleRate: 1.0`).

Replays mask all text and inputs by default and unmask an allowlist: the elements carrying `data-sentry-unmask`, which are the stage header (`Profile.jsx`), the task panel (`Refgame.jsx`'s `.task`), alerts, button labels, and the transition screens. The allowlist direction is deliberate, so anything added to the UI later stays masked until someone decides otherwise. Chat message text stays masked, being both the participants' own language and the study's data, and so does every form input, which covers the typed identifier and the survey's free-text answers. Media is deliberately not blocked, so the tangram grid is recorded: seeing which images a participant was looking at is most of the diagnostic value in a reference game.

`beforeSend`, `beforeSendTransaction`, and `beforeBreadcrumb` in `index.jsx` cut every reported URL at the `?`, so the Prolific ids in the study link's query string (and Empirica's `ns` parameter) never reach Sentry; the location itself is not rewritten because a reload needs `ns`. Those hooks do not cover the replay upload pipeline, so an error session's replay metadata can still carry the query string; only erroring sessions are affected and the decision was to leave it rather than add an unverified hook. `Introduction.jsx` sets the Sentry user to the Empirica player id only.

**Project details:**
- Organization: set via `SENTRY_ORG` in `.env`
- Project: `javascript-react`
- Region URL: `https://us.sentry.io`
- Production URL: set via `EMPIRICA_SERVER` in `.env`
- DSN: set via `VITE_SENTRY_DSN` in the repository-root `.env`, which the client build reads through Vite's `envDir` and compiles into the bundle; a production build without it fails (`shared/sentry-env.js`) unless `ALLOW_NO_SENTRY=1`. Never read `.env` directly; the values are secrets, and hostnames and organization names must not appear in committed files

**MCP server:** the Sentry MCP server (`https://mcp.sentry.dev/mcp`, declared in `.mcp.json` and `.codex/config.toml`) exposes `search_issues`, `get_issue_details`, `search_events`, and `analyze_issue_with_seer`. Use it to query production issues directly.

**Workflow:** when investigating a production bug, check Sentry for recent issues, then cross-reference the stacktrace with the client source in `experiment/client/src/`. Reference issue IDs in commit messages (e.g. `Fixes JAVASCRIPT-REACT-1`) to auto-resolve issues on merge. During live sessions, keep the Sentry dashboard open to watch for client errors, slow page loads, and websocket disconnections.

**SDK usage:** for `Sentry.captureException`, `Sentry.startSpan`, or the `logger` API, fetch the current `@sentry/react` documentation with Context7 rather than working from memory.
