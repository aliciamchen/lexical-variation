/**
 * Idle-round classification (pure functions; see callbacks.js for the
 * Empirica wiring, which runs at the end of each Feedback stage).
 *
 * A speaker is idle when they sent no chat message. A listener is idle when
 * the speaker did send a message but the listener never selected a tangram;
 * if the speaker was silent the listener could not act and is not penalized.
 */
import { MAX_IDLE_ROUNDS } from "./constants";

export function classifyIdle({ role, sentMessage, clicked, speakerSentMessage }) {
  if (role === "speaker") return !sentMessage;
  if (!speakerSentMessage) return false;
  return !clicked;
}

/**
 * A late click is a listener selection that was absent when the Selection
 * deadline passed (`clickedAtDeadline === false`) but has arrived since. It is
 * unscored but is not idleness.
 */
export function isLateClick({ role, clicked, clickedAtDeadline }) {
  return role === "listener" && Boolean(clicked) && clickedAtDeadline === false;
}

/** Consecutive idle-round counter: resets on any active round. */
export function updateIdleRounds(previous, wasIdle, maxIdleRounds = MAX_IDLE_ROUNDS) {
  const idleRounds = wasIdle ? (Number(previous) || 0) + 1 : 0;
  return { idleRounds, remove: idleRounds >= maxIdleRounds };
}
