/**
 * The "has responded" rule for a Selection stage, in one place.
 *
 * `Game.jsx` hides the chat once everyone in the group has responded and
 * `Refgame.jsx` shows the waiting message and auto-submits the stage on the
 * same condition. The rule has a condition-dependent twist -- in Phase 2 of
 * the social conditions a listener has responded only once both the tangram
 * and the social guess are in -- so keeping two copies invited drift.
 */

/** Whether one player has done everything the round asks of them. */
export function playerHasResponded(p, { needsSocialGuess }) {
  if (p.round.get("role") === "speaker") return true;
  if (!p.round.get("clicked")) return false;
  return !needsSocialGuess || Boolean(p.round.get("social_guess"));
}

/** Whether every active member of the group has responded. */
export function allGroupResponded(playersInGroup, { needsSocialGuess }) {
  return playersInGroup.every((p) =>
    playerHasResponded(p, { needsSocialGuess }),
  );
}
