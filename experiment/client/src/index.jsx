import React from "react";
import { createRoot } from "react-dom/client";
import "@unocss/reset/tailwind-compat.css";
import "virtual:uno.css";
import "../node_modules/@empirica/core/dist/player.css";
import App from "./App";
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

// Shared by beforeSend (errors and messages) and beforeSendTransaction.
function scrubEvent(event) {
  stripQueryFields(event.request, ["url"]);
  stripQueryFields(event, ["transaction"]);
  stripQueryFields(event.contexts?.trace?.data, ["url", "http.url"]);
  for (const span of event.spans || []) {
    stripQueryFields(span.data, ["url", "http.url"]);
  }
  return event;
}

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  // Do not attach IP addresses or other default PII to events.
  sendDefaultPii: false,
  integrations: [
    Sentry.browserTracingIntegration(),
    // Replays are recorded only for sessions in which an error occurs, for
    // diagnosing disconnections and layout problems; all text and typed input
    // are masked so chat content and survey answers never leave the
    // experiment server.
    Sentry.replayIntegration({
      maskAllText: true,
      maskAllInputs: true,
      blockAllMedia: false,
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

const container = document.getElementById("root");
const root = createRoot(container); // createRoot(container!) if you use TypeScript
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
