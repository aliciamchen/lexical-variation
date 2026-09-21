import React from "react";
import { createRoot } from "react-dom/client";
import "@unocss/reset/tailwind-compat.css";
import "virtual:uno.css";
import "../node_modules/@empirica/core/dist/player.css";
import App from "./App";
import { CrashFallback } from "./components/CrashFallback";
import "./index.css";
import * as Sentry from "@sentry/react";

// Prolific opens the study with PROLIFIC_PID, STUDY_ID and SESSION_ID in the
// query string, and Empirica keeps the participant namespace there too (the
// `ns` parameter, which a reload needs). The location itself is therefore
// left alone, and instead every URL field that Sentry would report is cut at
// the "?" before it leaves the browser: the page URL on error events, the
// transaction name and trace data on performance events, and the from/to/url
// fields of navigation and fetch breadcrumbs.
function stripQuery(url) {
  if (typeof url !== "string") return url;
  const cut = url.indexOf("?");
  return cut === -1 ? url : url.slice(0, cut);
}

function stripQueryFields(obj, keys) {
  if (!obj) return;
  for (const key of keys) {
    if (typeof obj[key] === "string") obj[key] = stripQuery(obj[key]);
  }
}

// Shared by beforeSend, beforeSendTransaction, and -- as a global event
// processor registered after init -- every other event type the SDK builds,
// which is how replays are covered: the SDK calls neither beforeSend nor
// beforeSendTransaction for a replay event, but it does run the global
// processors, so registering this there is what keeps the study URL out of a
// replay's `urls` list and request context.
function scrubEvent(event) {
  stripQueryFields(event.request, ["url"]);
  // httpContextIntegration adds the referrer to every event it touches,
  // replay events included, and on a single-page study the referrer is this
  // same URL with the Prolific ids still attached.
  stripQueryFields(event.request?.headers, ["Referer", "referer"]);
  stripQueryFields(event, ["transaction"]);
  stripQueryFields(event.contexts?.trace?.data, ["url", "http.url"]);
  for (const span of event.spans || []) {
    stripQueryFields(span.data, ["url", "http.url"]);
  }
  // Replay events carry the pages visited during the recording.
  if (Array.isArray(event.urls)) {
    event.urls = event.urls.map(stripQuery);
  }
  return event;
}

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  // Which deployment an event came from. The dev server and the Playwright
  // suite read the same DSN from the root .env, and the suite deliberately
  // provokes quiz failures, idle removals and terminated batches, so without
  // this every test run lands in the same feed as real participants and a
  // participant's fault is indistinguishable from our own noise. A Vite build
  // reports "production"; anything served by `empirica` in development reports
  // "development". Scope Sentry alert rules to production.
  environment: import.meta.env.MODE,
  // The commit the bundle was built from, substituted by Vite's `define` (see
  // vite.config.js). Guarded because an undefined free variable here would
  // throw while this module loads and leave the participant a blank page;
  // shipping without a release is the lesser failure.
  release: typeof __APP_RELEASE__ === "undefined" ? undefined : __APP_RELEASE__,
  // Do not attach IP addresses or other default PII to events.
  sendDefaultPii: false,
  integrations: [
    Sentry.browserTracingIntegration(),
    // Replays are recorded only for sessions in which an error occurs, for
    // diagnosing disconnections and layout problems.
    //
    // Everything is masked by default and the interface chrome is unmasked by
    // an allowlist: elements carrying `data-sentry-unmask` (the stage header,
    // the task panel, alerts and button labels). The allowlist direction is
    // deliberate -- anything added to the UI later is masked until someone
    // decides otherwise, whereas a blocklist would leak a new field silently.
    //
    // Still masked, and to stay that way: chat message text, which is both the
    // participants' own language and the study's data, and every form input,
    // which covers the typed identifier and the survey's free-text answers.
    // Media is deliberately NOT blocked, so the tangram grid is recorded --
    // seeing which images a participant was looking at is most of the
    // diagnostic value in a reference game.
    Sentry.replayIntegration({
      maskAllText: true,
      maskAllInputs: true,
      blockAllMedia: false,
      unmask: ["[data-sentry-unmask]", ".sentry-unmask"],
      // The recording itself carries the page address, separately from the
      // event envelope: rrweb writes a Meta frame (type 4) with the full
      // href at every full snapshot. Event processors never see inside the
      // recording, so it is cut here instead.
      beforeAddRecordingEvent: (event) => {
        if (event?.type === 4 && typeof event.data?.href === "string") {
          return {
            ...event,
            data: { ...event.data, href: stripQuery(event.data.href) },
          };
        }
        return event;
      },
    }),
  ],
  beforeSend: scrubEvent,
  beforeSendTransaction: scrubEvent,
  beforeBreadcrumb(breadcrumb) {
    stripQueryFields(breadcrumb.data, ["url", "from", "to"]);
    return breadcrumb;
  },
  // Tracing
  tracesSampleRate: 1.0, //  Capture 100% of the transactions
  // Set 'tracePropagationTargets' to control for which URLs distributed tracing should be enabled
  tracePropagationTargets: ["localhost", /^https:\/\/.*\.empirica\.app/],
  // Session Replay: none by default, every session that hits an error.
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 1.0,
  // Enable logs to be sent to Sentry
  enableLogs: true,
});

// Covers the event types beforeSend and beforeSendTransaction never see,
// which is what leaves replay events unscrubbed if this is omitted.
Sentry.addEventProcessor(scrubEvent);

const container = document.getElementById("root");
const root = createRoot(container); // createRoot(container!) if you use TypeScript
// Any render error anywhere unmounts the entire tree, so without a boundary
// one bad read leaves the participant on a blank page -- which is how a
// momentarily empty player subscription blanked the exit screen in production
// on 2026-09-19. The components that read a player now guard themselves; this
// catches whatever we have not thought of, reports it, and tells the
// participant to reload.
root.render(
  <React.StrictMode>
    <Sentry.ErrorBoundary fallback={<CrashFallback />}>
      <App />
    </Sentry.ErrorBoundary>
  </React.StrictMode>,
);
