import React from "react";
import { createRoot } from "react-dom/client";
import "@unocss/reset/tailwind-compat.css";
import "virtual:uno.css";
import "../node_modules/@empirica/core/dist/player.css";
import App from "./App";
import "./index.css";
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  // Do not attach IP addresses or other default PII to events.
  sendDefaultPii: false,
  integrations: [
    Sentry.browserTracingIntegration(),
    // Replays are kept for diagnosing disconnections and layout problems, but
    // all text and typed input are masked so chat content and survey answers
    // never leave the experiment server.
    Sentry.replayIntegration({
      maskAllText: true,
      maskAllInputs: true,
      blockAllMedia: false,
    }),
  ],
  // Tracing
  tracesSampleRate: 1.0, //  Capture 100% of the transactions
  // Set 'tracePropagationTargets' to control for which URLs distributed tracing should be enabled
  tracePropagationTargets: ["localhost", /^https:\/\/.*\.empirica\.app/],
  // Session Replay
  replaysSessionSampleRate: 1.0, // record every session (masked; see above)
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
