/**
 * When a keystroke in the chat box means "send".
 *
 * This lives in shared/ rather than in the Chat component because the client
 * has no test runner of its own (see server/vitest.config.js), and the rule
 * below is worth pinning: getting it wrong costs the study data, not just
 * convenience.
 */

/**
 * Enter sends, Shift+Enter makes a newline -- except while an input method
 * editor is composing.
 *
 * An IME is how Chinese, Japanese and Korean are typed: the participant types
 * Latin letters, the editor offers candidate characters, and Enter commits the
 * chosen one into the field. That Enter belongs to the candidate picker, and
 * the browser says so by setting `isComposing` on the event. Treating it as a
 * send broadcasts a half-written description to the group and empties the box,
 * which in a reference game corrupts the utterance itself -- the study's
 * primary measure -- and resets the composition timer with it, under a running
 * selection clock.
 *
 * `keyCode === 229` is the same signal from browsers that predate
 * `isComposing`: they report every key pressed during composition as 229.
 *
 * Takes the native event (React's synthetic event exposes it as
 * `event.nativeEvent`).
 */
export function isSendKey(event) {
  if (!event) return false;
  if (event.isComposing || event.keyCode === 229) return false;
  return event.key === "Enter" && !event.shiftKey;
}
