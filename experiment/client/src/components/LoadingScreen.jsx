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
//
// The thresholds are generous because on a busy server a stage change can
// take several seconds (up to 12 s in a six-game session), so advice given
// after a few seconds would fire on ordinary slow transitions. Reloading is
// the worst response to one: it discards the update already on its way,
// reloads the app, and re-fetches the whole game from the same busy server
// while the stage timer keeps running, which costs participants rounds and
// can get them removed for inactivity. So the first message asks them to
// wait, and a reload is suggested only once a wait is long enough to mean a
// real disconnection.
const SPINNER_AFTER_MS = 400;
const WAIT_MESSAGE_AFTER_MS = 15000;
const RELOAD_ADVICE_AFTER_MS = 30000;

export function LoadingScreen() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timers = [SPINNER_AFTER_MS, WAIT_MESSAGE_AFTER_MS, RELOAD_ADVICE_AFTER_MS].map(
      (ms) => setTimeout(() => setElapsed(ms), ms),
    );
    return () => timers.forEach(clearTimeout);
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

        {elapsed >= WAIT_MESSAGE_AFTER_MS ? (
          <>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              The game is catching up
            </h3>
            <p className="mt-2 text-sm text-gray-500">
              Please wait here. The next screen will show up shortly.
            </p>
          </>
        ) : null}

        {elapsed >= RELOAD_ADVICE_AFTER_MS ? (
          <p className="mt-2 text-sm text-gray-500" data-testid="loading-reload-advice">
            If nothing has changed after another minute, please reload the
            page. Your progress will be saved.
          </p>
        ) : null}
      </div>
    </div>
  );
}
