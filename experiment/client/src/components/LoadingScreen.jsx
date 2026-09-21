import React, { useEffect, useState } from "react";

// Empirica renders this in two slots, and they differ enormously in how often
// they fire. The `connecting` slot is the websocket coming up or coming back,
// which is rare. The `loading` slot is every moment `useAllReady()` is false,
// and that includes the gap at each stage boundary while the other eight
// players' per-stage scopes reach this client: roughly 150 times in a
// production game, for a fraction of a second each.
//
// So nothing is shown at all until a wait outlasts an ordinary transition,
// and the explanation waits longer still. A participant playing normally sees
// this component do nothing; one whose connection has actually dropped gets a
// spinner and then something to act on. Showing the full message every time
// would train people to ignore it and make a healthy game look broken.
const SPINNER_AFTER_MS = 400;
const GUIDANCE_AFTER_MS = 3000;

export function LoadingScreen() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const spinner = setTimeout(() => setElapsed(SPINNER_AFTER_MS), SPINNER_AFTER_MS);
    const guidance = setTimeout(() => setElapsed(GUIDANCE_AFTER_MS), GUIDANCE_AFTER_MS);
    return () => {
      clearTimeout(spinner);
      clearTimeout(guidance);
    };
  }, []);

  return (
    <div
      className="h-full flex items-center justify-center px-4"
      data-testid="loading-screen"
      data-loading-elapsed={elapsed}
      data-sentry-unmask
    >
      <div className="max-w-md text-center">
        {elapsed >= SPINNER_AFTER_MS ? (
          <div className="mx-auto h-8 w-8 rounded-full border-2 border-empirica-500 border-t-transparent animate-spin" />
        ) : null}

        {elapsed >= GUIDANCE_AFTER_MS ? (
          <>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              Still waiting
            </h3>
            <p className="mt-2 text-sm text-gray-500">
              The study has not responded for a few seconds. This is usually a
              brief problem with the connection.
            </p>
            <p className="mt-2 text-sm text-gray-500">
              If it does not clear, reload the page. Your progress is saved, so
              you will return to where you were.
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}
