import { ClassicListenersCollector } from "@empirica/core/admin/classic";
export const Empirica = new ClassicListenersCollector();
import _ from "lodash";
import {
  tangram_sets,
  names,
  name_colors,
  conditions,
  avatar_seeds,
  getAvatarUrl,
  getAnonymousAvatarUrl,
  bonus_per_point,
  BONUS_PER_POINT_SOCIAL,
  GROUP_SIZE,
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  LISTENER_CORRECT_POINTS,
  SPEAKER_MAX_POINTS_PER_ROUND,
  SOCIAL_GUESS_CORRECT_POINTS,
  MAX_IDLE_ROUNDS,
  MIN_GROUP_SIZE,
  TEST_MODE,
  SELECTION_DURATION,
  FEEDBACK_DURATION,
  TRANSITION_DURATION,
  BONUS_INFO_DURATION,
  BASE_PAY,
  EXPECTED_GAME_DURATION_MIN,
  ACCURACY_CHECK_BLOCKS,
  ACCURACY_THRESHOLD,
  PLAYER_ACCURACY_THRESHOLD,
} from "./constants";

// Group names (no color distinction)
const GROUP_NAMES = ["A", "B", "C"];

Empirica.onGameStart(({ game }) => {
  console.log(`Game ${game.id} started`);
  game.set("justStarted", true);

  // Get condition from game treatment
  const treatment = game.get("treatment");
  const condition = treatment?.condition || conditions[0];
  game.set("condition", condition);
  console.log(
    `Game condition: ${condition}, Treatment: ${JSON.stringify(treatment)}`,
  );

  // Randomly assign tangram set (two sets with Ji et al. 2022 high-SND tangrams)
  // TODO: Restore randomization for full data collection: Math.random() < 0.5 ? 0 : 1
  // Hardcoded to set 1 during pilot to reduce variability while debugging
  const tangram_set = 1;
  const context = tangram_sets[tangram_set];
  console.log(`Game assigned to tangram set: ${tangram_set}`);
  game.set("tangram_set", tangram_set);
  game.set("context", context);

  // Shuffle players for random group assignment
  const shuffledPlayers = _.shuffle(game.players);

  // Assign players to groups (3 groups of 3)
  shuffledPlayers.forEach((player, i) => {
    const groupIndex = Math.floor(i / GROUP_SIZE);
    const groupName = GROUP_NAMES[groupIndex];
    const playerIndexInGroup = i % GROUP_SIZE;

    player.set("name", names[i]);
    player.set("original_name", names[i]);
    player.set("tangram_set", tangram_set);
    player.set("context", context);
    player.set("score", 0);
    player.set("bonus", 0);
    player.set("idle_rounds", 0);
    player.set("is_active", true);

    // Group assignment
    player.set("original_group", groupName);
    player.set("current_group", groupName);
    player.set("player_index", playerIndexInGroup);

    // Avatar assignment using DiceBear API (no group color distinction)
    const avatarSeed = avatar_seeds[i];
    player.set("avatar_seed", avatarSeed);
    const avatarUrl = getAvatarUrl(avatarSeed);
    player.set("avatar", avatarUrl);
    player.set("original_avatar", avatarUrl);
    player.set("name_color", name_colors[i]);

    // Tangram shuffling
    const shuffled_tangrams = _.shuffle(context);
    player.set("shuffled_tangrams", shuffled_tangrams);
    player.set(
      "tangramURLs",
      shuffled_tangrams.map((tangram) => `/tangram_${tangram}.svg`),
    );

    // Time tracking for compensation calculation
    player.set("gameStartTime", Date.now());
  });

  // Derive actual group count from number of players (to support both test and production treatments)
  const actualGroupCount = Math.floor(game.players.length / GROUP_SIZE);
  console.log(
    `Game starting with ${game.players.length} players → ${actualGroupCount} groups`,
  );
  game.set("active_groups", GROUP_NAMES.slice(0, actualGroupCount));

  // Set min active groups dynamically (need at least 2 groups for 9-player, 1 group for 3-player)
  const minActiveGroups = actualGroupCount > 1 ? 2 : 1;
  game.set("min_active_groups", minActiveGroups);

  // Store constants for client display
  game.set("phase1Blocks", PHASE_1_BLOCKS);
  game.set("phase2Blocks", PHASE_2_BLOCKS);
  game.set("selectionDuration", SELECTION_DURATION);
  game.set("numTangrams", context.length);
  game.set("groupSize", GROUP_SIZE);
  // Use lower multiplier for social condition to keep max bonus equal across conditions
  game.set(
    "bonusPerPoint",
    condition === "social_mixed" ? BONUS_PER_POINT_SOCIAL : bonus_per_point,
  );
  game.set("listenerCorrectPoints", LISTENER_CORRECT_POINTS);
  game.set("speakerMaxPointsPerRound", SPEAKER_MAX_POINTS_PER_ROUND);

  // ============ PHASE 1: REFERENCE GAME ============
  // Players play within their original groups
  // Production: 6 blocks (each of 3 players speaks twice)
  // Test mode: 2 blocks

  let trialNum = 0;

  _.times(PHASE_1_BLOCKS, (blockNum) => {
    const speakerIndex = blockNum % GROUP_SIZE; // Rotate through speakers
    const shuffled_context = _.shuffle(context);
    _.times(shuffled_context.length, (target_num) => {
      const round = game.addRound({
        name: `Phase 1: Block ${blockNum + 1}`,
        phase: "refgame",
        phase_num: 1,
        block_num: blockNum,
        speaker_index: speakerIndex,
        target_order: shuffled_context,
        target: shuffled_context[target_num],
        target_num: target_num,
        trial_num: trialNum++,
      });
      round.addStage({
        name: "Selection",
        duration: SELECTION_DURATION,
      });
      round.addStage({
        name: "Feedback",
        duration: FEEDBACK_DURATION,
      });
    });
  });

  // ============ TRANSITION BETWEEN PHASES ============
  const transition = game.addRound({
    phase: "transition",
    transition_type: "phase_2",
  });

  transition.addStage({
    name: "phase_2_transition",
    duration: TRANSITION_DURATION,
  });

  // ============ PHASE 2: CONTINUED REFERENCE GAME ============
  // Behavior depends on condition:
  // - refer_separated: Same groups as Phase 1
  // - refer_mixed: Groups reshuffled at start of each block (after 6 trials), identities masked
  // - social_mixed: Same as refer_mixed + social guessing question
  // Production: 12 blocks, Test mode: 4 blocks

  _.times(PHASE_2_BLOCKS, (blockNum) => {
    const speakerIndex = blockNum % GROUP_SIZE; // Rotate through speakers
    const shuffled_context = _.shuffle(context);
    _.times(shuffled_context.length, (target_num) => {
      const round = game.addRound({
        name: `Phase 2: Block ${blockNum + 1}`,
        phase: "refgame",
        phase_num: 2,
        block_num: blockNum,
        speaker_index: speakerIndex,
        target_order: shuffled_context,
        target: shuffled_context[target_num],
        target_num: target_num,
        trial_num: trialNum++,
      });
      round.addStage({
        name: "Selection",
        duration: SELECTION_DURATION,
      });
      round.addStage({
        name: "Feedback",
        duration: FEEDBACK_DURATION,
      });
    });
  });

  // ============ FINAL TRANSITION (BONUS INFO) ============
  const finalTransition = game.addRound({
    phase: "transition",
    transition_type: "bonus_info",
  });

  finalTransition.addStage({
    name: "bonus_info",
    duration: BONUS_INFO_DURATION,
  });
});

Empirica.onRoundStart(({ round }) => {
  round.set("justStarted", true);
  const game = round.currentGame;
  const condition = game.get("condition");
  const phase_num = round.get("phase_num");

  // Skip processing if game has been terminated due to insufficient groups
  if (game.get("gameTerminated")) {
    return;
  }

  // Check if we still have enough active groups to continue
  const activeGroups = game.get("active_groups") || GROUP_NAMES;
  const minRequired = game.get("min_active_groups") || 1;
  if (activeGroups.length < minRequired) {
    return;
  }

  // ============ PHASE 1 → PHASE 2 TRANSITION: ACCURACY CHECK ============
  // At the start of the Phase 2 transition, check if groups meet accuracy threshold
  if (
    round.get("phase") === "transition" &&
    round.get("transition_type") === "phase_2"
  ) {
    console.log(
      "Phase 1 → Phase 2 transition: Running accuracy threshold check",
    );
    checkPhase1AccuracyThreshold(game);

    // After accuracy check, game might be terminated - check again
    if (game.get("gameTerminated")) {
      return;
    }
  }

  if (round.get("phase") === "refgame") {
    const players = game.players.filter((p) => p.get("is_active"));
    const blockNum = round.get("block_num");

    // In Phase 2 with mixed conditions, reshuffle groups at start of each BLOCK
    // (only when target_num === 0, i.e., first trial of the block)
    const targetNum = round.get("target_num");
    if (
      phase_num === 2 &&
      targetNum === 0 &&
      (condition === "refer_mixed" || condition === "social_mixed")
    ) {
      reshuffleGroups(game, players);
    }

    // Set roles for each group
    const activeGroups = game.get("active_groups") || GROUP_NAMES;

    activeGroups.forEach((groupName) => {
      const groupPlayers = players.filter(
        (p) => p.get("current_group") === groupName,
      );

      if (groupPlayers.length === 0) {
        console.log(
          `Group ${groupName} has no active players, skipping role assignment`,
        );
        return;
      }

      // Determine speaker based on player_index (consistent rotation across all conditions)
      // Speaker is the player whose original_player_index matches blockNum % GROUP_SIZE
      const speakerTargetIndex = blockNum % GROUP_SIZE;

      // Find the designated speaker (player with matching player_index)
      let speaker = groupPlayers.find(
        (p) => p.get("player_index") === speakerTargetIndex,
      );

      // SPEAKER REASSIGNMENT: If designated speaker is not available (kicked/inactive),
      // reassign speaker role to another player in the group
      if (!speaker && groupPlayers.length > 0) {
        // Sort by player_index to ensure consistent fallback selection
        const sortedPlayers = _.sortBy(groupPlayers, (p) =>
          p.get("player_index"),
        );

        // Pick the next available player in rotation order
        // Use the same block-based rotation but with available players only
        const fallbackIdx = blockNum % sortedPlayers.length;
        speaker = sortedPlayers[fallbackIdx];

        console.log(
          `SPEAKER REASSIGNMENT: Original speaker (index ${speakerTargetIndex}) not available in group ${groupName}`,
        );
        console.log(
          `  -> Reassigning to ${speaker.get("name")} (index ${speaker.get("player_index")}) for remaining trials in block ${blockNum}`,
        );

        // Track that speaker was reassigned (useful for debugging)
        game.set(
          `speaker_reassigned_block_${blockNum}_group_${groupName}`,
          true,
        );
      }

      const isMixedPhase2 =
        phase_num === 2 &&
        (condition === "refer_mixed" || condition === "social_mixed");

      groupPlayers.forEach((player, i) => {
        // In mixed conditions, use anonymous avatars for both display and chat
        if (isMixedPhase2) {
          const anonIndex = activeGroups.indexOf(groupName) * GROUP_SIZE + i;
          const anonSeed = `anon_block${blockNum}_player${anonIndex}`;
          const anonAvatar = getAnonymousAvatarUrl(anonSeed);
          const anonName = "Player";

          // Set on round for display in header
          player.round.set("display_avatar", anonAvatar);
          player.round.set("display_name", anonName);

          // Also set on player so Chat component uses masked identity
          player.set("avatar", anonAvatar);
          player.set("name", anonName);
        } else {
          // Use original avatar/name
          player.round.set("display_avatar", player.get("original_avatar"));
          player.round.set("display_name", player.get("original_name"));

          // Restore original for chat
          player.set("avatar", player.get("original_avatar"));
          player.set("name", player.get("original_name"));
        }

        // Assign speaker/listener roles based on player_index matching
        player.round.set("role", player === speaker ? "speaker" : "listener");
      });
    });

    // Save round info to players
    players.forEach((player) => {
      player.round.set("name", player.get("name"));
      player.round.set("phase", "refgame");
      player.round.set("phase_num", phase_num);
      player.round.set("current_group", player.get("current_group"));
      player.round.set("original_group", player.get("original_group"));
      player.round.set("block_num", blockNum);
      player.round.set("target", round.get("target"));
    });
  }
});

// Helper function to reshuffle groups for mixed conditions with BALANCED assignment
// Goal: Each group should have one player from each original_player_index (0, 1, 2)
// This ensures speaker rotation (blockNum % 3) works consistently across conditions
// Additionally: Ensures groups are MIXED (players from different original groups together)
function reshuffleGroups(game, players) {
  const activeGroups = game.get("active_groups") || GROUP_NAMES;
  const numPlayers = players.length;

  // Calculate how many groups we can support (each needs MIN_GROUP_SIZE players)
  const maxGroups = Math.floor(numPlayers / MIN_GROUP_SIZE);
  const numGroups = Math.min(maxGroups, activeGroups.length);

  if (numGroups === 0) {
    console.log("Not enough players for any viable group");
    return;
  }

  const usedGroups = activeGroups.slice(0, numGroups);

  // Calculate target group sizes for even distribution
  const baseSize = Math.floor(numPlayers / numGroups);
  const extraPlayers = numPlayers % numGroups;
  const targetSizes = [];
  for (let i = 0; i < numGroups; i++) {
    targetSizes.push(baseSize + (i < extraPlayers ? 1 : 0));
  }
  // Check how many unique original groups we have
  const uniqueOriginalGroups = new Set(
    players.map((p) => p.get("original_group")),
  );
  const canMix = uniqueOriginalGroups.size >= 2;

  // Helper function to perform one reshuffling attempt
  function doReshuffle() {
    // Group players by their original_player_index
    const playersByIndex = {
      0: players.filter((p) => p.get("player_index") === 0),
      1: players.filter((p) => p.get("player_index") === 1),
      2: players.filter((p) => p.get("player_index") === 2),
    };

    // Shuffle within each index group for randomization
    Object.keys(playersByIndex).forEach((idx) => {
      playersByIndex[idx] = _.shuffle(playersByIndex[idx]);
    });

    // Track which players have been assigned in THIS reshuffling
    const assignedInThisReshuffling = new Set();
    const indexPointers = { 0: 0, 1: 0, 2: 0 };

    // First pass: Fill each group with one player from each index
    usedGroups.forEach((groupName, groupIdx) => {
      const targetSize = targetSizes[groupIdx];
      let assigned = 0;

      // Try to assign one player from each index
      for (let idx = 0; idx < GROUP_SIZE && assigned < targetSize; idx++) {
        const pointer = indexPointers[idx];
        if (pointer < playersByIndex[idx].length) {
          const player = playersByIndex[idx][pointer];
          player.set("current_group", groupName);
          assignedInThisReshuffling.add(player.id);
          indexPointers[idx]++;
          assigned++;
        }
      }
    });

    // Second pass: Distribute any remaining unassigned players
    const unassignedPlayers = players.filter(
      (p) => !assignedInThisReshuffling.has(p.id),
    );

    if (unassignedPlayers.length > 0) {
      let unassignedIdx = 0;
      usedGroups.forEach((groupName, groupIdx) => {
        const targetSize = targetSizes[groupIdx];
        let currentSize = players.filter(
          (p) =>
            assignedInThisReshuffling.has(p.id) &&
            p.get("current_group") === groupName,
        ).length;

        while (
          currentSize < targetSize &&
          unassignedIdx < unassignedPlayers.length
        ) {
          const player = unassignedPlayers[unassignedIdx];
          player.set("current_group", groupName);
          assignedInThisReshuffling.add(player.id);
          currentSize++;
          unassignedIdx++;
        }
      });
    }
  }

  // Helper function to check if groups are properly mixed
  // Mixed = at least one group has players from 2+ different original groups
  function checkMixing() {
    for (const groupName of usedGroups) {
      const groupPlayers = players.filter(
        (p) => p.get("current_group") === groupName,
      );
      const originalGroups = new Set(
        groupPlayers.map((p) => p.get("original_group")),
      );
      if (originalGroups.size >= 2) {
        return true; // At least one group is mixed
      }
    }
    return false; // No group has players from different original groups
  }

  // Perform reshuffling with mixing guarantee (if possible)
  const MAX_RESHUFFLE_ATTEMPTS = 10;
  let attempts = 0;
  let isMixed = false;

  // Log distribution for debugging (only once)
  const playersByIndex = {
    0: players.filter((p) => p.get("player_index") === 0),
    1: players.filter((p) => p.get("player_index") === 1),
    2: players.filter((p) => p.get("player_index") === 2),
  };
  if (!canMix) {
    // Only one original group remaining, mixing is impossible
    console.log("Only one original group remaining - mixing not possible");
    doReshuffle();
  } else {
    // Try to get a mixed result
    while (attempts < MAX_RESHUFFLE_ATTEMPTS && !isMixed) {
      attempts++;
      doReshuffle();
      isMixed = checkMixing();
    }

    if (isMixed) {
      console.log(`Achieved mixed groups after ${attempts} attempt(s)`);
    } else {
      console.warn(
        `WARNING: Could not achieve mixing after ${MAX_RESHUFFLE_ATTEMPTS} attempts`,
      );
    }
  }

  // Verification: Log final group composition
  const groupComposition = {};
  usedGroups.forEach((groupName) => {
    const groupPlayers = players.filter(
      (p) => p.get("current_group") === groupName,
    );
    const indices = groupPlayers.map((p) => p.get("player_index"));
    const originalGroups = [
      ...new Set(groupPlayers.map((p) => p.get("original_group"))),
    ];
    groupComposition[groupName] = {
      size: groupPlayers.length,
      indices: indices.sort(),
      hasAllIndices: [0, 1, 2].every((idx) => indices.includes(idx)),
      originalGroups: originalGroups.sort(),
      isMixed: originalGroups.length >= 2,
    };
  });

  // Verify all groups meet MIN_GROUP_SIZE
  const undersizedGroups = Object.entries(groupComposition)
    .filter(([_, info]) => info.size < MIN_GROUP_SIZE)
    .map(([name, _]) => name);

  if (undersizedGroups.length > 0) {
    console.error(
      `ERROR: Groups ${undersizedGroups.join(", ")} are below MIN_GROUP_SIZE=${MIN_GROUP_SIZE}`,
    );
  }

  // Warn if any group is missing an index (will need fallback for speaker selection)
  const numComplete = Object.values(groupComposition).filter(
    (g) => g.hasAllIndices,
  ).length;
  const numMixed = Object.values(groupComposition).filter(
    (g) => g.isMixed,
  ).length;
  console.log(
    `Reshuffled ${numPlayers} players into ${numGroups} groups (${numComplete} complete, ${numMixed} mixed)`,
  );
}

Empirica.onStageStart(({ stage }) => {
  // Stage start - no special handling needed
  // Speaker reassignment is handled in onRoundStart via fallback logic
});

Empirica.onStageEnded(({ stage }) => {
  const game = stage.currentGame;
  const players = game.players;
  const condition = game.get("condition");
  const stageName = stage.get("name");

  // Skip processing if game has been terminated due to insufficient groups
  if (game.get("gameTerminated")) {
    return;
  }

  // ============ IDLE PLAYER DETECTION ============
  // Only check idleness during Selection stage (not Feedback or transitions)
  // Speakers are idle if they don't send any chat message
  // Listeners are idle if they don't send any chat message AND don't click a tangram
  if (stageName === "Selection") {
    const activeGroups = game.get("active_groups") || GROUP_NAMES;

    players.forEach((player) => {
      if (!player.get("is_active")) return;

      const playerGroup = player.get("current_group");
      const role = player.round.get("role");
      const chat = stage.get(`${playerGroup}_chat`) || [];

      // Check if player sent any message
      const sentMessage = chat.some((msg) => msg.sender?.id === player.id);

      // Check if player clicked a tangram (only relevant for listeners)
      const clickedTangram = player.round.get("clicked");

      // Check if the speaker in this group sent any message
      // (listeners shouldn't be marked idle if speaker didn't send anything - they couldn't act)
      const groupPlayers = game.players.filter(
        (p) => p.get("is_active") && p.get("current_group") === playerGroup,
      );
      const groupSpeaker = groupPlayers.find(
        (p) => p.round.get("role") === "speaker",
      );
      const speakerSentMessage =
        groupSpeaker && chat.some((msg) => msg.sender?.id === groupSpeaker.id);

      // Determine if player was idle this round
      let wasIdle = false;
      if (role === "speaker") {
        // Speakers are idle if they didn't send any message
        wasIdle = !sentMessage;
      } else {
        // Listeners are idle ONLY if speaker sent a message but listener didn't respond
        // If speaker didn't send a message, listener couldn't act - not their fault
        if (!speakerSentMessage) {
          // Speaker was idle, don't penalize listeners
          wasIdle = false;
        } else {
          // Speaker sent a message, listener should have clicked
          wasIdle = !clickedTangram;
        }
      }

      if (wasIdle) {
        const idleRounds = (player.get("idle_rounds") || 0) + 1;
        player.set("idle_rounds", idleRounds);
        console.log(
          `Player ${player.id} (${role}) idle round ${idleRounds}/${MAX_IDLE_ROUNDS}`,
        );

        if (idleRounds >= MAX_IDLE_ROUNDS) {
          const wasSpeak = role === "speaker";
          console.log(
            `Player ${player.id} (${role}) removed after ${MAX_IDLE_ROUNDS} idle rounds`,
          );
          player.set("is_active", false);
          player.set("ended", "player timeout");
          player.set("exitReason", "player timeout");
          player.set("gameEndTime", Date.now());
          // Idle players get NO compensation
          player.set("partialPay", 0);

          // If speaker was kicked, log that reassignment will occur
          if (wasSpeak) {
            const playerGroup = player.get("current_group");
            const remainingInGroup = game.players.filter(
              (p) =>
                p.get("is_active") && p.get("current_group") === playerGroup,
            );
            if (remainingInGroup.length >= MIN_GROUP_SIZE) {
              console.log(
                `SPEAKER KICKED: Group ${playerGroup} has ${remainingInGroup.length} remaining players, speaker will be reassigned in next round`,
              );
            }
          }

          // Check if group can continue
          checkGroupViability(game);
        }
      } else {
        // Reset idle counter when player is active
        player.set("idle_rounds", 0);
      }
    });
  }

  // ============ SCORING FOR SELECTION STAGE ============
  if (stage.get("name") === "Selection") {
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

      // Award points to speaker (2 * proportion of correct listeners)
      // This accommodates groups with fewer listeners after dropout
      const speakerPoints =
        listeners.length > 0
          ? 2 * (correctListeners.length / listeners.length)
          : 0;
      speaker.set("score", speaker.get("score") + speakerPoints);
      speaker.round.set("round_score", speakerPoints);

      // ============ SOCIAL GUESSING (for social_mixed condition in Phase 2) ============
      if (condition === "social_mixed" && phase_num === 2) {
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

        // Track speaker's social round score (proportional, up to 2 points)
        // Similar to tangram scoring: 2 * (proportion of original-group listeners who correctly identify)
        const socialSpeakerPoints =
          listenersFromOriginalGroup.length > 0
            ? 2 *
              (correctGuessesFromOriginalGroup /
                listenersFromOriginalGroup.length)
            : 0;
        speaker.round.set("social_round_score", socialSpeakerPoints);

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
});

// Helper function to check if groups are still viable
function checkGroupViability(game) {
  const players = game.players;
  const activeGroups = game.get("active_groups") || GROUP_NAMES;
  const condition = game.get("condition");

  // Get current phase from the current round
  const currentRound = game.rounds.find((r) => !r.get("ended"));
  const phase_num = currentRound?.get("phase_num") || 1;
  const isMixedPhase2 =
    phase_num === 2 &&
    (condition === "refer_mixed" || condition === "social_mixed");

  const viableGroups = activeGroups.filter((groupName) => {
    const groupPlayers = players.filter(
      (p) => p.get("is_active") && p.get("original_group") === groupName,
    );
    return groupPlayers.length >= MIN_GROUP_SIZE;
  });

  // If a group is no longer viable, remove remaining member with proportional pay
  activeGroups.forEach((groupName) => {
    if (!viableGroups.includes(groupName)) {
      const remainingPlayers = players.filter(
        (p) => p.get("is_active") && p.get("original_group") === groupName,
      );
      remainingPlayers.forEach((player) => {
        console.log(
          `Removing final member ${player.id} from disbanded group ${groupName}`,
        );
        player.set("is_active", false);
        player.set("ended", "group disbanded");
        player.set("exitReason", "group disbanded");
        player.set("gameEndTime", Date.now());

        // Calculate proportional pay based on time spent + earned bonus
        const startTime = player.get("gameStartTime");
        const endTime = Date.now();
        const minutesSpent = (endTime - startTime) / (1000 * 60);
        const proportionalBasePay = Math.min(
          BASE_PAY,
          (minutesSpent / EXPECTED_GAME_DURATION_MIN) * BASE_PAY,
        );
        // Include bonus earned so far
        const earnedBonus = player.get("bonus") || 0;
        const totalPartialPay = proportionalBasePay + earnedBonus;

        player.set("partialPay", Math.round(totalPartialPay * 100) / 100); // Round to 2 decimals
        player.set(
          "partialBasePay",
          Math.round(proportionalBasePay * 100) / 100,
        );
        player.set("partialBonus", Math.round(earnedBonus * 100) / 100);
        player.set("minutesSpent", Math.round(minutesSpent));
        console.log(
          `  -> Proportional pay: $${player.get("partialPay")} (base: $${player.get("partialBasePay")} + bonus: $${player.get("partialBonus")}) for ${Math.round(minutesSpent)} minutes`,
        );
      });
    }
  });

  game.set("active_groups", viableGroups);

  // Check if game can continue (use dynamic min_active_groups from game)
  const minRequired = game.get("min_active_groups") || 1;
  if (viableGroups.length < minRequired) {
    console.log(
      `Not enough active groups (${viableGroups.length} < ${minRequired}), ending game`,
    );

    // Give remaining active players partial compensation and end them
    const remainingActivePlayers = players.filter((p) => p.get("is_active"));
    remainingActivePlayers.forEach((player) => {
      console.log(
        `Ending remaining player ${player.id} due to insufficient groups`,
      );
      player.set("is_active", false);
      player.set("ended", "group disbanded");
      player.set("exitReason", "group disbanded");
      player.set("gameEndTime", Date.now());

      // Calculate proportional pay based on time spent + earned bonus
      const startTime = player.get("gameStartTime");
      const endTime = Date.now();
      const minutesSpent = (endTime - startTime) / (1000 * 60);
      const proportionalBasePay = Math.min(
        BASE_PAY,
        (minutesSpent / EXPECTED_GAME_DURATION_MIN) * BASE_PAY,
      );
      const earnedBonus = player.get("bonus") || 0;
      const totalPartialPay = proportionalBasePay + earnedBonus;

      player.set("partialPay", Math.round(totalPartialPay * 100) / 100);
      player.set("partialBasePay", Math.round(proportionalBasePay * 100) / 100);
      player.set("partialBonus", Math.round(earnedBonus * 100) / 100);
      player.set("minutesSpent", Math.round(minutesSpent));
      console.log(
        `  -> Proportional pay: $${player.get("partialPay")} for ${Math.round(minutesSpent)} minutes`,
      );
    });

    // Mark the game as terminated so subsequent rounds/stages are skipped
    game.set("gameTerminated", true);
    game.end("ended", "all players removed");
    console.log("Game marked as terminated - remaining rounds will be skipped");
    return; // Exit early, no need to check for solo players
  }

  // ============ PHASE 2 MIXED: CHECK FOR SOLO PLAYERS IN CURRENT GROUPS ============
  // After original group disbanding, some current (shuffled) groups might have only 1 player.
  // Trigger immediate reshuffling so no one plays alone for the rest of the block.
  if (isMixedPhase2) {
    const activePlayers = players.filter((p) => p.get("is_active"));

    // Get all unique current groups that have active players
    const currentGroupNames = [
      ...new Set(activePlayers.map((p) => p.get("current_group"))),
    ];

    // Check if any current group has fewer than MIN_GROUP_SIZE players
    const hasSoloPlayer = currentGroupNames.some((groupName) => {
      const groupSize = activePlayers.filter(
        (p) => p.get("current_group") === groupName,
      ).length;
      return groupSize < MIN_GROUP_SIZE;
    });

    if (hasSoloPlayer) {
      // Only reshuffle if we have enough players to form at least one viable group
      if (activePlayers.length >= MIN_GROUP_SIZE) {
        console.log(
          `MID-BLOCK RESHUFFLE: Solo player detected in Phase 2 mixed, triggering immediate reshuffling`,
        );
        console.log(
          `  -> ${activePlayers.length} active players will be redistributed`,
        );

        // Track that we did a mid-block reshuffle (for data analysis)
        const currentBlock = currentRound?.get("block_num") || 0;
        const currentTarget = currentRound?.get("target_num") || 0;
        game.set(
          `midBlockReshuffle_block${currentBlock}_target${currentTarget}`,
          true,
        );

        reshuffleGroups(game, activePlayers);
      } else {
        console.log(
          `Cannot reshuffle: only ${activePlayers.length} players remaining (need ${MIN_GROUP_SIZE})`,
        );
      }
    }
  }
}

// Helper function to check Phase 1 accuracy threshold and remove underperforming groups
// Called at the Phase 1 → Phase 2 transition
function checkPhase1AccuracyThreshold(game) {
  const players = game.players;
  const activeGroups = game.get("active_groups") || GROUP_NAMES;

  // Determine which blocks to check (last ACCURACY_CHECK_BLOCKS of Phase 1)
  const startBlock = Math.max(0, PHASE_1_BLOCKS - ACCURACY_CHECK_BLOCKS);
  const blocksToCheck = [];
  for (let i = startBlock; i < PHASE_1_BLOCKS; i++) {
    blocksToCheck.push(i);
  }

  const groupResults = {};
  const viableGroups = [];

  activeGroups.forEach((groupName) => {
    const groupPlayers = players.filter(
      (p) => p.get("is_active") && p.get("original_group") === groupName,
    );

    if (groupPlayers.length === 0) {
      console.log(`Group ${groupName}: No active players, skipping`);
      return;
    }

    // Calculate accuracy for each player in the checked blocks
    const playerAccuracies = groupPlayers.map((player) => {
      const blockAccuracy = player.get("block_accuracy") || {};
      let totalCorrect = 0;
      let totalTrials = 0;

      blocksToCheck.forEach((blockNum) => {
        const blockData = blockAccuracy[blockNum];
        if (blockData) {
          totalCorrect += blockData.correct;
          totalTrials += blockData.total;
        }
      });

      const accuracy = totalTrials > 0 ? totalCorrect / totalTrials : 0;
      return {
        playerId: player.id,
        playerName: player.get("original_name"),
        accuracy,
        meetsThreshold: accuracy >= ACCURACY_THRESHOLD,
        totalCorrect,
        totalTrials,
      };
    });

    // Count players meeting the threshold
    const playersMeetingThreshold = playerAccuracies.filter(
      (p) => p.meetsThreshold,
    ).length;
    const proportionMeeting = playersMeetingThreshold / groupPlayers.length;
    const groupMeetsThreshold = proportionMeeting >= PLAYER_ACCURACY_THRESHOLD;

    groupResults[groupName] = {
      players: playerAccuracies,
      playersMeetingThreshold,
      totalPlayers: groupPlayers.length,
      proportionMeeting,
      groupMeetsThreshold,
    };

    console.log(
      `  -> ${playersMeetingThreshold}/${groupPlayers.length} players meet threshold (${(proportionMeeting * 100).toFixed(1)}%) - Group ${groupMeetsThreshold ? "PASSES" : "FAILS"}`,
    );

    if (groupMeetsThreshold) {
      viableGroups.push(groupName);
    } else {
      // Remove all players in this group with proportional compensation
      console.log(`  -> Removing group ${groupName} due to low accuracy`);
      groupPlayers.forEach((player) => {
        console.log(
          `    Removing player ${player.id} (${player.get("original_name")})`,
        );
        player.set("is_active", false);
        player.set("ended", "low accuracy");
        player.set("exitReason", "low accuracy");
        player.set("gameEndTime", Date.now());

        // Calculate proportional pay based on time spent + earned bonus
        const startTime = player.get("gameStartTime");
        const endTime = Date.now();
        const minutesSpent = (endTime - startTime) / (1000 * 60);
        const proportionalBasePay = Math.min(
          BASE_PAY,
          (minutesSpent / EXPECTED_GAME_DURATION_MIN) * BASE_PAY,
        );
        const earnedBonus = player.get("bonus") || 0;
        const totalPartialPay = proportionalBasePay + earnedBonus;

        player.set("partialPay", Math.round(totalPartialPay * 100) / 100);
        player.set(
          "partialBasePay",
          Math.round(proportionalBasePay * 100) / 100,
        );
        player.set("partialBonus", Math.round(earnedBonus * 100) / 100);
        player.set("minutesSpent", Math.round(minutesSpent));
        console.log(
          `    -> Proportional pay: $${player.get("partialPay")} (base: $${player.get("partialBasePay")} + bonus: $${player.get("partialBonus")}) for ${Math.round(minutesSpent)} minutes`,
        );
      });
    }
  });

  // Update active groups
  game.set("active_groups", viableGroups);
  game.set("phase1_accuracy_results", groupResults);

  console.log(
    `\nActive groups after accuracy check: ${viableGroups.join(", ") || "NONE"}`,
  );

  // Check if game can continue
  const minRequired = game.get("min_active_groups") || 1;
  if (viableGroups.length < minRequired) {
    console.log(
      `Not enough active groups (${viableGroups.length} < ${minRequired}), ending game`,
    );

    // Give remaining active players partial compensation and end them
    const remainingActivePlayers = players.filter((p) => p.get("is_active"));
    remainingActivePlayers.forEach((player) => {
      console.log(
        `Ending remaining player ${player.id} due to insufficient groups after accuracy check`,
      );
      player.set("is_active", false);
      player.set("ended", "insufficient groups after accuracy check");
      player.set("exitReason", "insufficient groups after accuracy check");
      player.set("gameEndTime", Date.now());

      const startTime = player.get("gameStartTime");
      const endTime = Date.now();
      const minutesSpent = (endTime - startTime) / (1000 * 60);
      const proportionalBasePay = Math.min(
        BASE_PAY,
        (minutesSpent / EXPECTED_GAME_DURATION_MIN) * BASE_PAY,
      );
      const earnedBonus = player.get("bonus") || 0;
      const totalPartialPay = proportionalBasePay + earnedBonus;

      player.set("partialPay", Math.round(totalPartialPay * 100) / 100);
      player.set("partialBasePay", Math.round(proportionalBasePay * 100) / 100);
      player.set("partialBonus", Math.round(earnedBonus * 100) / 100);
      player.set("minutesSpent", Math.round(minutesSpent));
      console.log(
        `  -> Proportional pay: $${player.get("partialPay")} for ${Math.round(minutesSpent)} minutes`,
      );
    });

    game.set("gameTerminated", true);
    game.end("ended", "all players removed");
    console.log("Game marked as terminated after Phase 1 accuracy check");
  }
}

Empirica.onRoundEnded(({ round }) => {
  // Calculate and update bonuses at end of each round
  const game = round.currentGame;

  // Skip processing if game has been terminated
  if (game.get("gameTerminated")) {
    return;
  }

  const players = game.players;
  const condition = game.get("treatment")?.condition;
  // Use lower multiplier for social condition to keep max bonus equal across conditions
  const multiplier =
    condition === "social_mixed" ? BONUS_PER_POINT_SOCIAL : bonus_per_point;

  players.forEach((player) => {
    // Base score from picture guessing
    const baseScore = player.get("score") || 0;

    // Social points (tracked separately, added to bonus only)
    const listenerSocialPoints =
      (player.get("social_guess_correct_total") || 0) *
      SOCIAL_GUESS_CORRECT_POINTS;
    // Speaker social points are now proportional (accumulated each round)
    const speakerSocialPoints = player.get("social_speaker_points_total") || 0;
    const totalScore = baseScore + listenerSocialPoints + speakerSocialPoints;

    player.set("bonus", totalScore * multiplier);
  });
});

Empirica.onGameEnded(({ game }) => {
  console.log(`Game ${game.id} ended`);

  // Final bonus calculation
  const players = game.players;
  const condition = game.get("treatment")?.condition;
  // Use lower multiplier for social condition to keep max bonus equal across conditions
  const multiplier =
    condition === "social_mixed" ? BONUS_PER_POINT_SOCIAL : bonus_per_point;

  players.forEach((player) => {
    // Base score from picture guessing
    const baseScore = player.get("score") || 0;

    // Social points (tracked separately, added to bonus only)
    const listenerSocialPoints =
      (player.get("social_guess_correct_total") || 0) *
      SOCIAL_GUESS_CORRECT_POINTS;
    // Speaker social points are now proportional (accumulated each round)
    const speakerSocialPoints = player.get("social_speaker_points_total") || 0;
    const totalScore = baseScore + listenerSocialPoints + speakerSocialPoints;

    player.set("bonus", totalScore * multiplier);
    console.log(
      `Player ${player.id}: Score=${baseScore}, SocialPoints=${listenerSocialPoints + speakerSocialPoints}, TotalScore=${totalScore}, Bonus=$${player.get("bonus").toFixed(2)}`,
    );
  });
});
