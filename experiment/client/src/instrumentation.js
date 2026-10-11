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
 * - `ConnectionLog` records when the websocket to the game server drops and
 *   comes back, and each page load (so a reload is visible). The browser's
 *   `offline` event only fires when the whole network goes, so the engagement
 *   log never saw the drops participants actually reported.
 *
 * All of them write to the player scope, so the records survive whatever round
 * the participant happens to be in. None changes anything the participant sees.
 *
 * Every write is wrapped so that a failure here can never interrupt the game:
 * this is measurement, and losing a record costs one covariate, whereas an
 * exception raised during a round would cost the session.
 *
 * The counting rules live in `shared/engagement.js` so they can be unit tested
 * by the server's vitest; this module is only the wiring to the browser and
 * the player scope.
 */
import { useEffect, useRef, useState } from "react";
import { useTajribaConnected } from "@empirica/core/player/react";
import { usePlayer } from "@empirica/core/player/classic/react";
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
 * is a fingerprinting vector: `pipeline/extract_run.py` strips it during
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
 * Returns how many events have been recorded for this player. `Game` puts it
 * on a data attribute, which is how the end-to-end spec checks that real
 * browser events reach the player scope.
 */
export function useEngagementLog(player) {
  const [count, setCount] = useState(
    () => (player?.get("engagement_events") || []).length,
  );

  useEffect(() => {
    if (!player) return;

    // Seeded from the player scope so the cap is per player: a reload mounts
    // a new recorder, which must continue the count rather than restart it,
    // and must stay silent if the log was already marked truncated.
    const recorder = createEngagementRecorder({
      write: (event) => player.append("engagement_events", event),
      onTruncated: () => player.set("engagement_log_truncated", true),
      initialCount: (player.get("engagement_events") || []).length,
      truncated: Boolean(player.get("engagement_log_truncated")),
    });
    setCount(recorder.count);

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

function navigationType() {
  try {
    const entry = performance.getEntriesByType?.("navigation")?.[0];
    if (entry?.type) return entry.type;
    return performance.navigation?.type === 1 ? "reload" : "navigate";
  } catch {
    return "unknown";
  }
}

/**
 * Record drops of the connection to the game server, and page loads, in the
 * player's `connection_events` (separate from `engagement_events`, with its own
 * cap, so neither log can use up the other's).
 *
 * Mounted in App, beside EmpiricaContext rather than inside it: while the
 * connection is down, EmpiricaContext unmounts the game and shows the
 * connecting screen, so a component inside it could never see the drop. The
 * moment the connection went down is held here and written once it is back,
 * since nothing written while it is down can reach the server. A drop that
 * outlasts the page (a reload while disconnected) is not recorded, but the
 * reload itself is, as a page load with navigation "reload".
 *
 * Renders nothing and never throws into the tree.
 */
export function ConnectionLog() {
  const connected = useTajribaConnected();
  const player = usePlayer();
  const downSince = useRef(null);
  const pending = useRef([]);
  const recorder = useRef(null);
  const pageLoadRecorded = useRef(false);
  const everConnected = useRef(false);

  // Only a loss of a connection this page already had counts as a drop.
  // While a page first connects, `connected` reads false for a moment, and
  // counting that logged a 1-2 ms "disconnect" on every page load (seen in a
  // local test on 2026-09-25).
  useEffect(() => {
    if (connected === true) everConnected.current = true;
    if (connected === false && everConnected.current && downSince.current === null) {
      downSince.current = Date.now();
    } else if (connected === true && downSince.current !== null) {
      pending.current.push({ since: downSince.current, until: Date.now() });
      downSince.current = null;
    }
  }, [connected]);

  useEffect(() => {
    if (connected !== true || !player) return;
    try {
      if (recorder.current?.playerId !== player.id) {
        recorder.current = {
          playerId: player.id,
          rec: createEngagementRecorder({
            write: (event) => player.append("connection_events", event),
            onTruncated: () => player.set("connection_log_truncated", true),
            initialCount: (player.get("connection_events") || []).length,
            truncated: Boolean(player.get("connection_log_truncated")),
          }),
        };
      }
      const { rec } = recorder.current;
      if (!pageLoadRecorded.current) {
        pageLoadRecorded.current = true;
        rec.recordPageLoad(navigationType());
      }
      while (pending.current.length > 0) {
        const drop = pending.current.shift();
        rec.recordDisconnect(drop.since, drop.until);
      }
    } catch (e) {
      console.warn("Could not record connection event:", e);
    }
  }, [connected, player?.id]);

  return null;
}
