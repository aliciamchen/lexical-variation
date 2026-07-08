// Selection-stage scoring: listener/speaker reference-game points and the
// Phase 2 social-guessing points. Extracted from callbacks.js so the logic
// can be unit tested directly (see scoring.test.js) — tests import this
// function, not a copy.
//
// Must be called BEFORE idle detection / group-viability handling in
// onStageEnded: it scores against is_active / current_group / active_groups
// as the trial was actually played.
import {
  GROUP_NAMES,
  LISTENER_CORRECT_POINTS,
  SPEAKER_MAX_POINTS_PER_ROUND,
  SOCIAL_GUESS_CORRECT_POINTS,
  SOCIAL_SPEAKER_POINTS_PER_CORRECT,
  hasSocialGuessing,
} from "./constants";

export function scoreSelectionStage(game, stage) {
  const players = game.players;
  const condition = game.get("condition");
  const round = stage.round;
  const target = round.get("target");
  const phase_num = round.get("phase_num");
  const activeGroups = game.get("active_groups") || GROUP_NAMES;

  activeGroups.forEach((groupName) => {
    const groupPlayers = players.filter(
      (p) => p.get("is_active") && p.get("current_group") === groupName,
    );

    const listeners = groupPlayers.filter(
      (p) => p.round.get("role") === "listener",
    );
    const speaker = groupPlayers.find(
      (p) => p.round.get("role") === "speaker",
    );

    if (!speaker) return;

    // Check if speaker sent a message this round (listeners can only act if speaker did)
    const groupChat = stage.get(`${groupName}_chat`) || [];
    const speakerSentMessage = groupChat.some(
      (msg) => msg.sender?.id === speaker.id,
    );

    // Save correctness for each listener and count correct ones
    listeners.forEach((listener) => {
      const clicked = listener.round.get("clicked");
      const isCorrect = clicked === target;
      listener.round.set("clicked_correct", isCorrect);

      // Track per-block listener accuracy for Phase 1 accuracy threshold check
      // ONLY count trials where listener could actually respond (speaker sent message)
      // Otherwise listeners are unfairly penalized for speaker idleness
      if (phase_num === 1 && speakerSentMessage) {
        const blockNum = round.get("block_num");
        const blockAccuracy = listener.get("block_accuracy") || {};
        if (!blockAccuracy[blockNum]) {
          blockAccuracy[blockNum] = { correct: 0, total: 0 };
        }
        blockAccuracy[blockNum].total += 1;
        if (isCorrect) {
          blockAccuracy[blockNum].correct += 1;
        }
        listener.set("block_accuracy", blockAccuracy);
      }
    });

    const correctListeners = listeners.filter((p) =>
      p.round.get("clicked_correct"),
    );

    // Award points to correct listeners and save round_score
    listeners.forEach((listener) => {
      const isCorrect = listener.round.get("clicked_correct");
      const listenerPoints = isCorrect ? LISTENER_CORRECT_POINTS : 0;
      if (isCorrect) {
        listener.set("score", listener.get("score") + LISTENER_CORRECT_POINTS);
      }
      listener.round.set("round_score", listenerPoints);
    });

    // Award points to speaker (max points * proportion of correct listeners)
    // This accommodates groups with fewer listeners after dropout
    const speakerPoints =
      listeners.length > 0
        ? SPEAKER_MAX_POINTS_PER_ROUND *
          (correctListeners.length / listeners.length)
        : 0;
    speaker.set("score", speaker.get("score") + speakerPoints);
    speaker.round.set("round_score", speakerPoints);

    // ============ SOCIAL GUESSING (for conditions with social guessing in Phase 2) ============
    if (hasSocialGuessing(condition) && phase_num === 2) {
      const speakerOriginalGroup = speaker.get("original_group");
      let correctGuessesFromOriginalGroup = 0;

      // Find listeners who are from the speaker's original group
      const listenersFromOriginalGroup = listeners.filter(
        (l) => l.get("original_group") === speakerOriginalGroup,
      );

      listeners.forEach((listener) => {
        const listenerOriginalGroup = listener.get("original_group");
        const guess = listener.round.get("social_guess"); // "same_group" or "different_group"

        if (guess) {
          const wasInSameGroup =
            speakerOriginalGroup === listenerOriginalGroup;
          const guessedSame = guess === "same_group";
          const correct = wasInSameGroup === guessedSame;

          listener.round.set("social_guess_correct", correct);
          listener.round.set("speaker_was_same_group", wasInSameGroup);
          listener.round.set(
            "social_round_score",
            correct ? SOCIAL_GUESS_CORRECT_POINTS : 0,
          );
          listener.set(
            "score",
            listener.get("score") +
              (correct ? SOCIAL_GUESS_CORRECT_POINTS : 0),
          );

          // Track cumulative social guess stats for end-of-game summary
          const totalGuesses = (listener.get("social_guess_total") || 0) + 1;
          const correctTotal =
            (listener.get("social_guess_correct_total") || 0) +
            (correct ? 1 : 0);
          listener.set("social_guess_total", totalGuesses);
          listener.set("social_guess_correct_total", correctTotal);

          // Speaker earns bonus only when a listener from their original group
          // correctly identifies the speaker as being from the same group
          if (wasInSameGroup && correct) {
            correctGuessesFromOriginalGroup++;
          }
        }
      });

      // Track speaker's social round score (proportional, up to
      // SOCIAL_SPEAKER_POINTS_PER_CORRECT points), like tangram scoring:
      // max points * (proportion of original-group listeners who correctly identify)
      const socialSpeakerPoints =
        listenersFromOriginalGroup.length > 0
          ? SOCIAL_SPEAKER_POINTS_PER_CORRECT *
            (correctGuessesFromOriginalGroup /
              listenersFromOriginalGroup.length)
          : 0;
      speaker.round.set("social_round_score", socialSpeakerPoints);
      speaker.round.set(
        "social_recognized_count",
        correctGuessesFromOriginalGroup,
      );
      speaker.round.set(
        "social_original_group_listeners",
        listenersFromOriginalGroup.length,
      );
      speaker.set("score", speaker.get("score") + socialSpeakerPoints);

      // Track speaker's cumulative social stats (how many original-group listeners guessed correctly)
      const speakerGuessedAbout =
        (speaker.get("social_guessed_about_total") || 0) +
        listenersFromOriginalGroup.length;
      const speakerGuessedCorrect =
        (speaker.get("social_guessed_about_correct") || 0) +
        correctGuessesFromOriginalGroup;
      speaker.set("social_guessed_about_total", speakerGuessedAbout);
      speaker.set("social_guessed_about_correct", speakerGuessedCorrect);

      // Track cumulative proportional social speaker points
      const cumulativeSocialSpeakerPoints =
        (speaker.get("social_speaker_points_total") || 0) +
        socialSpeakerPoints;
      speaker.set(
        "social_speaker_points_total",
        cumulativeSocialSpeakerPoints,
      );
    }

    // Save chat
    const chat = stage.get(`${groupName}_chat`) || [];
    groupPlayers.forEach((player) => {
      player.round.set("chat", chat);
    });
  });
}
