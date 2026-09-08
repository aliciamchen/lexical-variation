/**
 * Phase 1 accuracy screen (pure functions; wired in callbacks.js at the
 * Phase 1 to Phase 2 transition).
 *
 * Over the last ACCURACY_CHECK_BLOCKS blocks of Phase 1, each player's
 * listener accuracy is the proportion of correct selections on trials where
 * the speaker sent a message (block_accuracy is only recorded for those). A
 * player with no counted trials scores 0. A group passes when at least
 * PLAYER_ACCURACY_THRESHOLD of its active members reach ACCURACY_THRESHOLD.
 */
import {
  ACCURACY_CHECK_BLOCKS,
  ACCURACY_THRESHOLD,
  PHASE_1_BLOCKS,
  PLAYER_ACCURACY_THRESHOLD,
} from "./constants";

/** Block indices (0-based) checked at the end of Phase 1. */
export function accuracyCheckBlocks(phase1Blocks = PHASE_1_BLOCKS, checkBlocks = ACCURACY_CHECK_BLOCKS) {
  const start = Math.max(0, phase1Blocks - checkBlocks);
  const blocks = [];
  for (let i = start; i < phase1Blocks; i++) blocks.push(i);
  return blocks;
}

/** Aggregate a player's per-block {correct, total} records over the checked blocks. */
export function playerAccuracyOverBlocks(blockAccuracy, blocks, threshold = ACCURACY_THRESHOLD) {
  let totalCorrect = 0;
  let totalTrials = 0;
  for (const blockNum of blocks) {
    const data = blockAccuracy?.[blockNum];
    if (data) {
      totalCorrect += Number(data.correct) || 0;
      totalTrials += Number(data.total) || 0;
    }
  }
  const accuracy = totalTrials > 0 ? totalCorrect / totalTrials : 0;
  return { accuracy, meetsThreshold: accuracy >= threshold, totalCorrect, totalTrials };
}

/** Does a group of players (given their accuracies) pass the screen? */
export function evaluateGroupAccuracy(
  accuracies,
  { accuracyThreshold = ACCURACY_THRESHOLD, playerThreshold = PLAYER_ACCURACY_THRESHOLD } = {},
) {
  const playersMeetingThreshold = accuracies.filter((a) => a >= accuracyThreshold).length;
  const proportionMeeting = accuracies.length > 0 ? playersMeetingThreshold / accuracies.length : 0;
  return {
    playersMeetingThreshold,
    proportionMeeting,
    groupMeetsThreshold: accuracies.length > 0 && proportionMeeting >= playerThreshold,
  };
}
