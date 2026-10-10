---
paths:
  - "experiment/client/src/**"
---

# Sentry (error monitoring)

The client app reports errors to Sentry via `@sentry/react`, initialized in `experiment/client/src/index.jsx` with error tracking, browser tracing, structured logs, and session replays for sessions that hit an error only (`replaysSessionSampleRate: 0`, `replaysOnErrorSampleRate: 1.0`).

Replays mask all text and inputs by default and unmask an allowlist: the elements carrying `data-sentry-unmask`, which are the stage header (`Profile.jsx`), the task panel (`Refgame.jsx`'s `.task`), alerts, button labels, and the transition screens. The allowlist direction is deliberate, so anything added to the UI later stays masked until someone decides otherwise. Chat message text stays masked, being both the participants' own language and the study's data, and so does every form input, which covers the typed identifier and the survey's free-text answers. Media is deliberately not blocked, so the tangram grid is recorded: seeing which images a participant was looking at is most of the diagnostic value in a reference game.

`beforeSend`, `beforeSendTransaction`, and `beforeBreadcrumb` in `index.jsx` cut every reported URL at the `?`, so the Prolific ids in the study link's query string (and Empirica's `ns` parameter) never reach Sentry; the location itself is not rewritten because a reload needs `ns`. `Introduction.jsx` sets the Sentry user to the Empirica player id only.

Replays need three more things, because the SDK calls neither `beforeSend` nor `beforeSendTransaction` for a `replay_event`. The same scrubbing function is registered with `Sentry.addEventProcessor`, which does run for every event type; it also strips `event.urls` (the pages a replay records visiting) and `request.headers.Referer` (added by `httpContextIntegration`, and on a single-page study the referrer is this URL with the ids still on it); and `beforeAddRecordingEvent` cuts `data.href` on rrweb Meta frames (`type === 4`), which live inside the recording payload where no event processor can see them. One gap remains: slow-click and rage-click breadcrumbs (`type === 5`) carry the full page URL in their payload, which is how issue JAVASCRIPT-REACT-D came to hold a Prolific id (open item in `full-sample-todos.md`). After any future deploy, confirm by forcing one error on the live site and opening the replay: its URL should carry no query string. Every event carries `release`, the git short sha of the build (`-dirty` if any tracked file had uncommitted changes), so the newest production events show which build is live.

**Project details:**
- Organization: set via `SENTRY_ORG` in `.env`
- Project: `javascript-react`
- Region URL: `https://us.sentry.io`
- DSN: set via `VITE_SENTRY_DSN` in the repository-root `.env`, which the client build reads through Vite's `envDir` and compiles into the bundle; a production build without it fails (`shared/sentry-env.js`) unless `ALLOW_NO_SENTRY=1`. Never read `.env` directly; the values are secrets, and hostnames and organization names must not appear in committed files

**MCP server:** the Sentry MCP server (`https://mcp.sentry.dev/mcp`, declared in `.mcp.json` and `.codex/config.toml`) exposes `search_issues`, `get_issue_details`, `search_events`, and `analyze_issue_with_seer`. Use it to query production issues directly.

**Workflow:** when investigating a production bug, check Sentry for recent issues, then cross-reference the stacktrace with the client source in `experiment/client/src/`. Reference issue IDs in commit messages (e.g. `Fixes JAVASCRIPT-REACT-1`) to auto-resolve issues on merge. An unhandled error from Empirica's `TajribaParticipant.emit` (also seen as `CombinedError: [Network]`) is a participant's websocket dropping, not a game bug; the connection log on each player is the record of disconnects. The MCP `search_events` tool rejects natural-language queries; `search_issues` with a structured query (`lastSeen:-6h`, `level:error`) works.

**SDK usage:** for `Sentry.captureException`, `Sentry.startSpan`, or the `logger` API, fetch the current `@sentry/react` documentation with Context7 rather than working from memory.
