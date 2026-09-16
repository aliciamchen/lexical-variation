/**
 * Client-side session instrumentation.
 *
 * Two things the server cannot see on its own:
 *
 * - `recordClientContext` captures the device and viewport the participant is
 *   playing on. The task is a 4x4 grid of 16 tangrams, so viewport size changes
 *   how much visual search a selection takes and is a plausible covariate for
 *   accuracy and response time.
 * - `useEngagementLog` records when the tab is hidden or shown and when the
 *   browser goes offline or comes back. Without it, idle classification cannot
 *   tell a participant who tabbed away or briefly lost their connection from
 *   one who was present and chose not to act, and the three have different
 *   implications for exclusion.
 *
 * Both write to the player scope, so the records survive whatever round the
 * participant happens to be in. Neither changes anything the participant sees.
 *
 * Every write is wrapped so that a failure here can never interrupt the game:
 * this is measurement, and losing a record costs one covariate, whereas an
 * exception raised during a round would cost the session.
 *
 * The counting rules live in `shared/engagement.js` so they can be unit tested
 * by the server's vitest; this module is only the wiring to the browser and
 * the player scope.
 */
import { useEffect, useState } from "react";
import {
  createEngagementRecorder,
  RESIZE_DEBOUNCE_MS,
} from "../../shared/engagement.js";

function viewport() {
  return {
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
  };
}

/**
 * Record the device and viewport once per player. Safe to call repeatedly:
 * it writes only if nothing has been recorded yet.
 *
 * The raw user agent is recorded separately from the coarse fields because it
 * is a fingerprinting vector: `analysis/extract_run.py` strips it during
 * anonymization, so it exists only in the gitignored export and is available
 * for debugging a live session, never in committed data.
 */
export function recordClientContext(player) {
  if (!player || player.get("client_context")) return;

  try {
    player.set("client_context", {
      ...viewport(),
      screenWidth: window.screen?.width ?? null,
      screenHeight: window.screen?.height ?? null,
      devicePixelRatio: window.devicePixelRatio ?? null,
      // Coarse enough not to identify anyone, but enough to read a session's
      // local time of day, which bears on fatigue.
      timezoneOffsetMin: new Date().getTimezoneOffset(),
      language: navigator.language ?? null,
      touch: (navigator.maxTouchPoints ?? 0) > 0,
      recordedAt: Date.now(),
    });
    player.set("userAgent", navigator.userAgent ?? "");
  } catch (e) {
    console.warn("Could not record client context:", e);
  }
}

/**
 * Log tab-visibility, connectivity, and viewport-resize events for as long as
 * the calling component is mounted. Mounted from `Game`, so the log covers
 * gameplay, which is the window idle classification draws on.
 *
 * Returns how many events have been recorded. `Game` puts it on a data
 * attribute, which is how the end-to-end spec checks that real browser events
 * reach the player scope.
 */
export function useEngagementLog(player) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!player) return;

    const recorder = createEngagementRecorder({
      write: (event) => player.append("engagement_events", event),
      onTruncated: () => player.set("engagement_log_truncated", true),
    });

    // Each branch returns whether anything was written, so the counter only
    // advances when the append actually succeeded.
    const log = (record) => {
      try {
        if (record()) setCount(recorder.count);
      } catch (e) {
        console.warn("Could not record engagement event:", e);
      }
    };

    const onVisibility = () =>
      log(() => recorder.record(document.hidden ? "hidden" : "visible"));
    // Going offline writes nothing: the append could not leave the machine.
    // The outage is written on reconnect, start time and all.
    const onOffline = () => log(() => recorder.recordOffline());
    const onOnline = () => log(() => recorder.recordOnline());

    let resizeTimer = null;
    const onResize = () => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(
        () => log(() => recorder.recordResize(viewport())),
        RESIZE_DEBOUNCE_MS,
      );
    };

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    window.addEventListener("resize", onResize);

    return () => {
      if (resizeTimer) clearTimeout(resizeTimer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("resize", onResize);
    };
  }, [player?.id]);

  return count;
}
