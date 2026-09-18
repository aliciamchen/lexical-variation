/**
 * Error containment for the Empirica callbacks.
 *
 * Empirica does not catch what a callback throws: its dispatch wrapper awaits
 * the callback and only then sets the "already ran" sentinel, so a throw both
 * leaves whatever the callback had already written in place AND leaves the
 * callback eligible to run again on a later trigger. The throw itself becomes
 * an unhandled promise rejection, which `index.js` logs.
 *
 * For a nine-player synchronous game that is the worst shape of failure: not a
 * crash, but a group whose roles were half-assigned while everyone else plays
 * on, with nothing announcing it. Letting the exception propagate does not help
 * either, because the alternative to one broken group is nine lost
 * participants.
 *
 * So every callback is wrapped: the error is logged with enough context to
 * find it (the callback, the game, the round and stage, the active player
 * count) and swallowed, the game continues, and a counter on the game records
 * that it happened so the export and the researcher can both see it. The log
 * line is deliberately loud and single-line, because it is read by grep in a
 * server journal during a live session.
 */

/** Identify where we were, without assuming any of it is present. */
function describe(payload) {
  const parts = [];
  try {
    const game = payload?.game ?? payload?.round?.currentGame ?? payload?.stage?.currentGame;
    if (game) {
      parts.push(`game=${game.id}`);
      const condition = game.get("condition");
      if (condition) parts.push(`condition=${condition}`);
      const players = game.players?.filter((p) => p.get("is_active"));
      if (players) parts.push(`active=${players.length}`);
    }
    const round = payload?.round ?? payload?.stage?.round;
    if (round) {
      parts.push(`phase=${round.get("phase_num")}`);
      parts.push(`block=${round.get("block_num")}`);
      parts.push(`target=${round.get("target_num")}`);
    }
    const stage = payload?.stage;
    if (stage) parts.push(`stage=${stage.get("name")}`);
  } catch {
    // Reading the context must never be the thing that throws.
    parts.push("context-unavailable");
  }
  return parts.join(" ");
}

/**
 * Wrap one callback so a throw is reported and contained.
 *
 * @param {string} name   the callback's name, for the log line
 * @param {Function} fn   the callback itself
 */
export function guard(name, fn) {
  return (payload) => {
    try {
      return fn(payload);
    } catch (error) {
      console.error(
        `CALLBACK ERROR in ${name}: ${error?.message} | ${describe(payload)}`,
      );
      if (error?.stack) console.error(error.stack);
      // Count it on the game so it reaches the export and the admin panel
      // rather than living only in the server's log.
      try {
        const game =
          payload?.game ?? payload?.round?.currentGame ?? payload?.stage?.currentGame;
        if (game) {
          game.set("callbackErrors", (game.get("callbackErrors") || 0) + 1);
          game.set("lastCallbackError", `${name}: ${error?.message}`);
        }
      } catch {
        // Nothing more we can do; the log line above is the record.
      }
      return undefined;
    }
  };
}
