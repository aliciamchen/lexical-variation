/**
 * Bookkeeping for the engagement log, kept separate from the React hook that
 * installs the browser listeners (see instrumentation.js).
 *
 * The split follows the same rule as the server modules (`scoring.js`,
 * `idle.js`, `reshuffling.js`): the logic that can be got wrong lives in a
 * plain function with tests beside it, and the part that only wires it to a
 * runtime stays thin. The cap in particular cannot be tested end to end --
 * that would take two hundred real tab switches -- so it has to be testable
 * here.
 */

// A participant who switches tabs constantly should not be able to grow the
// export without bound. Past the cap the log stops and says that it did, so a
// truncated log is never mistaken for a quiet one.
export const MAX_ENGAGEMENT_EVENTS = 200;

// Resize fires continuously while a window is dragged; only the settled size
// is worth a record.
export const RESIZE_DEBOUNCE_MS = 500;

/**
 * Create a recorder that writes engagement events until it hits the cap.
 *
 * @param {object} opts
 * @param {(event: object) => void} opts.write       appends one event
 * @param {() => void} opts.onTruncated              called once, when the cap is first hit
 * @param {number} [opts.max]                        cap, for tests
 * @param {() => number} [opts.now]                  clock, for tests
 */
export function createEngagementRecorder({
  write,
  onTruncated,
  max = MAX_ENGAGEMENT_EVENTS,
  now = Date.now,
}) {
  let count = 0;
  let truncated = false;
  let lastSize = null;
  // When the connection dropped, if it is currently down. Held rather than
  // written, because a write cannot leave the machine while it is offline.
  let offlineSince = null;

  /**
   * Record one event. Returns whether it was written.
   *
   * `at` overrides the timestamp, for an event that is written later than it
   * happened (see recordOnline).
   *
   * A write that throws still counts against the cap: the failure is almost
   * certainly persistent, and retrying it on every subsequent event would turn
   * one broken scope into an unbounded stream of warnings.
   */
  function record(type, extra = {}, at = null) {
    if (count >= max) {
      if (!truncated) {
        truncated = true;
        onTruncated();
      }
      return false;
    }
    count += 1;
    write({ t: at ?? now(), type, ...extra });
    return true;
  }

  /**
   * Record a resize, ignoring one that did not actually change the viewport.
   * The first resize always counts, since there is nothing to compare against.
   */
  function recordResize(size) {
    if (
      lastSize &&
      lastSize.viewportWidth === size.viewportWidth &&
      lastSize.viewportHeight === size.viewportHeight
    ) {
      return false;
    }
    lastSize = size;
    return record("resize", size);
  }

  /**
   * Note that the connection dropped, without writing anything.
   *
   * Writing here would be pointless: the socket is down, so the append cannot
   * reach the server and is lost when the connection is re-established. The
   * timestamp is held instead and written on reconnect, which is the only way
   * the *start* of an outage survives it -- and the start is what makes the
   * difference between a momentary blip and a participant who was gone for
   * minutes.
   */
  function recordOffline(at = now()) {
    if (offlineSince === null) offlineSince = at;
    return false;
  }

  /**
   * Record the reconnection, preceded by the outage it ended. Both writes
   * happen while connected, so both survive.
   *
   * An `online` with no preceding `offline` means the tab was offline before
   * the log started listening; it is still recorded, since knowing the
   * connection was re-established is worth more than nothing.
   */
  function recordOnline() {
    let wrote = false;
    if (offlineSince !== null) {
      wrote = record("offline", {}, offlineSince);
      offlineSince = null;
    }
    return record("online") || wrote;
  }

  return {
    record,
    recordResize,
    recordOffline,
    recordOnline,
    get count() {
      return count;
    },
    get truncated() {
      return truncated;
    },
  };
}
