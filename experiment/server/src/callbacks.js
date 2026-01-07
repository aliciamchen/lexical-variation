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
  PLAYER_COUNT,
  GROUP_COUNT,
  GROUP_SIZE,
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  LISTENER_CORRECT_POINTS,
  SPEAKER_POINTS_PER_CORRECT_LISTENER,
  SOCIAL_GUESS_CORRECT_POINTS,
  SOCIAL_SPEAKER_POINTS_PER_CORRECT,
  MAX_IDLE_ROUNDS,
  MIN_GROUP_SIZE,
  MIN_ACTIVE_GROUPS,
  TEST_MODE,
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
  console.log(`Game condition: ${condition}, Treatment: ${JSON.stringify(treatment)}`);

  // Randomly assign tangram set (two sets with Ji et al. 2022 high-SND tangrams)
  const tangram_set = Math.random() < 0.5 ? 0 : 1;
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
      shuffled_tangrams.map((tangram) => `/tangram_${tangram}.svg`)
    );
  });

  // Store active groups (just the names, not player objects)
  game.set("active_groups", GROUP_NAMES.slice(0, GROUP_COUNT));

  // Store block counts for client display
  game.set("phase1Blocks", PHASE_1_BLOCKS);
  game.set("phase2Blocks", PHASE_2_BLOCKS);

  // ============ PHASE 1: REFERENCE GAME ============
  // Players play within their original groups
  // Production: 6 blocks (each of 3 players speaks twice)
  // Test mode: 2 blocks

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
      });
      round.addStage({
        name: "Selection",
        duration: 120, // Increased for MCP testing
      });
      round.addStage({
        name: "Feedback",
        duration: 10,
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
    duration: 30,
  });

  // ============ PHASE 2: CONTINUED REFERENCE GAME ============
  // Behavior depends on condition:
  // - refer_separated: Same groups as Phase 1
  // - refer_mixed: Groups reshuffled each block, identities masked
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
      });
      round.addStage({
        name: "Selection",
        duration: 120, // Increased for testing
      });
      round.addStage({
        name: "Feedback",
        duration: 10,
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
    duration: 30,
  });
});

Empirica.onRoundStart(({ round }) => {
  round.set("justStarted", true);
  const game = round.currentGame;
  const condition = game.get("condition");
  const phase_num = round.get("phase_num");

  if (round.get("phase") === "refgame") {
    const players = game.players.filter((p) => p.get("is_active"));
    const blockNum = round.get("block_num");

    // In Phase 2 with mixed conditions, reshuffle groups at start of each trial
    if (
      phase_num === 2 &&
      (condition === "refer_mixed" || condition === "social_mixed")
    ) {
      reshuffleGroups(game, players);
    }

    // Set roles for each group
    const activeGroups = game.get("active_groups") || GROUP_NAMES.slice(0, GROUP_COUNT);

    activeGroups.forEach((groupName) => {
      const groupPlayers = players.filter(
        (p) => p.get("current_group") === groupName
      );

      // Determine speaker based on player_index (consistent rotation across all conditions)
      // Speaker is the player whose original_player_index matches blockNum % GROUP_SIZE
      const speakerTargetIndex = blockNum % GROUP_SIZE;

      // Find the designated speaker (player with matching player_index)
      let speaker = groupPlayers.find(p => p.get("player_index") === speakerTargetIndex);

      // Fallback: if no player with matching index (due to dropouts), pick based on position
      if (!speaker && groupPlayers.length > 0) {
        const fallbackIdx = blockNum % groupPlayers.length;
        const sortedPlayers = _.sortBy(groupPlayers, p => p.get("player_index"));
        speaker = sortedPlayers[fallbackIdx];
        console.log(`Speaker fallback: No player with index ${speakerTargetIndex} in group ${groupName}, using ${speaker.get("name")} (index ${speaker.get("player_index")})`);
      }

      const isMixedPhase2 = phase_num === 2 &&
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
function reshuffleGroups(game, players) {
  console.log("Reshuffling groups for mixed condition (balanced)");

  const activeGroups = game.get("active_groups") || GROUP_NAMES.slice(0, GROUP_COUNT);
  const numPlayers = players.length;

  // Calculate how many groups we can support (each needs MIN_GROUP_SIZE players)
  const maxGroups = Math.floor(numPlayers / MIN_GROUP_SIZE);
  const numGroups = Math.min(maxGroups, activeGroups.length);

  if (numGroups === 0) {
    console.log("Not enough players for any viable group");
    return;
  }

  // Group players by their original_player_index
  const playersByIndex = {
    0: players.filter(p => p.get("player_index") === 0),
    1: players.filter(p => p.get("player_index") === 1),
    2: players.filter(p => p.get("player_index") === 2),
  };

  // Shuffle within each index group for randomization
  Object.keys(playersByIndex).forEach(idx => {
    playersByIndex[idx] = _.shuffle(playersByIndex[idx]);
  });

  // Log distribution for debugging
  console.log(`Player distribution by index: 0=${playersByIndex[0].length}, 1=${playersByIndex[1].length}, 2=${playersByIndex[2].length}`);

  // Calculate target group sizes for even distribution
  // E.g., 8 players / 3 groups = 2 groups of 3, 1 group of 2 → [3, 3, 2]
  const baseSize = Math.floor(numPlayers / numGroups);
  const extraPlayers = numPlayers % numGroups;
  const targetSizes = [];
  for (let i = 0; i < numGroups; i++) {
    targetSizes.push(baseSize + (i < extraPlayers ? 1 : 0));
  }
  console.log(`Target group sizes: ${targetSizes.join(", ")}`);

  const usedGroups = activeGroups.slice(0, numGroups);

  // Strategy: For each group, assign one player from each index (0, 1, 2)
  // This ensures each group gets balanced indices when possible
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
  // This handles cases where some index has more players than others
  const unassignedPlayers = players.filter(p => !assignedInThisReshuffling.has(p.id));

  if (unassignedPlayers.length > 0) {
    console.log(`Second pass: ${unassignedPlayers.length} unassigned players to distribute`);

    // Assign remaining players to groups that haven't reached target size
    let unassignedIdx = 0;
    usedGroups.forEach((groupName, groupIdx) => {
      const targetSize = targetSizes[groupIdx];
      let currentSize = players.filter(
        p => assignedInThisReshuffling.has(p.id) && p.get("current_group") === groupName
      ).length;

      while (currentSize < targetSize && unassignedIdx < unassignedPlayers.length) {
        const player = unassignedPlayers[unassignedIdx];
        player.set("current_group", groupName);
        assignedInThisReshuffling.add(player.id);
        currentSize++;
        unassignedIdx++;
      }
    });
  }

  // Verification: Log final group composition
  const groupComposition = {};
  usedGroups.forEach(groupName => {
    const groupPlayers = players.filter(p => p.get("current_group") === groupName);
    const indices = groupPlayers.map(p => p.get("player_index"));
    groupComposition[groupName] = {
      size: groupPlayers.length,
      indices: indices.sort(),
      hasAllIndices: [0, 1, 2].every(idx => indices.includes(idx))
    };
  });

  console.log("Group composition after reshuffling:", JSON.stringify(groupComposition));

  // Verify all groups meet MIN_GROUP_SIZE
  const undersizedGroups = Object.entries(groupComposition)
    .filter(([_, info]) => info.size < MIN_GROUP_SIZE)
    .map(([name, _]) => name);

  if (undersizedGroups.length > 0) {
    console.error(`ERROR: Groups ${undersizedGroups.join(", ")} are below MIN_GROUP_SIZE=${MIN_GROUP_SIZE}`);
  }

  // Warn if any group is missing an index (will need fallback for speaker selection)
  const incompleteGroups = Object.entries(groupComposition)
    .filter(([_, info]) => !info.hasAllIndices)
    .map(([name, _]) => name);

  if (incompleteGroups.length > 0) {
    console.warn(`WARNING: Groups ${incompleteGroups.join(", ")} don't have all indices - speaker fallback will be used`);
  }

  const numComplete = Object.values(groupComposition).filter(g => g.hasAllIndices).length;
  console.log(`Reshuffled ${numPlayers} players into ${numGroups} groups (${numComplete} complete)`);
}

Empirica.onStageStart(({ stage }) => {
  const game = stage.currentGame;
  const players = game.players.filter((p) => p.get("is_active"));

  // Handle players who have been kicked
  players.forEach((player) => {
    if (player.get("ended") === "player timeout") {
      player.stage.set("submit", "true");
      if (player.round.get("role") === "speaker") {
        // Auto-submit for listeners in same group if speaker is kicked
        const playerGroup = player.get("current_group");
        players.forEach((p) => {
          if (
            p.get("current_group") === playerGroup &&
            p.round.get("role") === "listener"
          ) {
            p.stage.set("submit", "true");
          }
        });
      }
    }
  });
});

Empirica.onStageEnded(({ stage }) => {
  const game = stage.currentGame;
  const players = game.players;
  const condition = game.get("condition");
  const stageName = stage.get("name");

  // ============ IDLE PLAYER DETECTION ============
  // Only check idleness during Selection stage (not Feedback or transitions)
  // Speakers are idle if they don't send any chat message
  // Listeners are idle if they don't send any chat message AND don't click a tangram
  if (stageName === "Selection") {
    const activeGroups = game.get("active_groups") || GROUP_NAMES.slice(0, GROUP_COUNT);

    players.forEach((player) => {
      if (!player.get("is_active")) return;

      const playerGroup = player.get("current_group");
      const role = player.round.get("role");
      const chat = stage.get(`${playerGroup}_chat`) || [];

      // Check if player sent any message
      const sentMessage = chat.some((msg) => msg.sender?.id === player.id);

      // Check if player clicked a tangram (only relevant for listeners)
      const clickedTangram = player.round.get("clicked");

      // Determine if player was idle this round
      let wasIdle = false;
      if (role === "speaker") {
        // Speakers are idle if they didn't send any message
        wasIdle = !sentMessage;
      } else {
        // Listeners are idle if they didn't send a message AND didn't click a tangram
        wasIdle = !sentMessage && !clickedTangram;
      }

      if (wasIdle) {
        const idleRounds = (player.get("idle_rounds") || 0) + 1;
        player.set("idle_rounds", idleRounds);
        console.log(
          `Player ${player.id} (${role}) idle round ${idleRounds}/${MAX_IDLE_ROUNDS}`
        );

        if (idleRounds >= MAX_IDLE_ROUNDS) {
          console.log(
            `Player ${player.id} removed after ${MAX_IDLE_ROUNDS} idle rounds`
          );
          player.set("is_active", false);
          player.set("ended", "player timeout");

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
    const activeGroups = game.get("active_groups") || GROUP_NAMES.slice(0, GROUP_COUNT);

    activeGroups.forEach((groupName) => {
      const groupPlayers = players.filter(
        (p) => p.get("is_active") && p.get("current_group") === groupName
      );

      const listeners = groupPlayers.filter(
        (p) => p.round.get("role") === "listener"
      );
      const speaker = groupPlayers.find(
        (p) => p.round.get("role") === "speaker"
      );

      if (!speaker) return;

      // Save correctness for each listener and count correct ones
      listeners.forEach((listener) => {
        const clicked = listener.round.get("clicked");
        const isCorrect = clicked === target;
        listener.round.set("clicked_correct", isCorrect);
      });

      const correctListeners = listeners.filter(
        (p) => p.round.get("clicked_correct")
      );

      // Award points to correct listeners
      correctListeners.forEach((listener) => {
        listener.set("score", listener.get("score") + LISTENER_CORRECT_POINTS);
      });

      // Award points to speaker (1 point per correct listener)
      const speakerPoints = correctListeners.length * SPEAKER_POINTS_PER_CORRECT_LISTENER;
      speaker.set("score", speaker.get("score") + speakerPoints);
      speaker.round.set("round_score", speakerPoints);

      // ============ SOCIAL GUESSING (for social_mixed condition in Phase 2) ============
      if (condition === "social_mixed" && phase_num === 2) {
        const speakerOriginalGroup = speaker.get("original_group");
        let correctGuesses = 0;
        let socialSpeakerPoints = 0;

        listeners.forEach((listener) => {
          const listenerOriginalGroup = listener.get("original_group");
          const guess = listener.round.get("social_guess"); // "same_group" or "different_group"

          if (guess) {
            const wasInSameGroup = speakerOriginalGroup === listenerOriginalGroup;
            const guessedSame = guess === "same_group";
            const correct = wasInSameGroup === guessedSame;

            listener.round.set("social_guess_correct", correct);

            // Track cumulative social guess stats for end-of-game summary
            const totalGuesses = (listener.get("social_guess_total") || 0) + 1;
            const correctTotal = (listener.get("social_guess_correct_total") || 0) + (correct ? 1 : 0);
            listener.set("social_guess_total", totalGuesses);
            listener.set("social_guess_correct_total", correctTotal);

            if (correct) {
              listener.set("score", listener.get("score") + SOCIAL_GUESS_CORRECT_POINTS);
              correctGuesses++;
            }
          }
        });

        // Speaker gets points for each correct guess about them
        socialSpeakerPoints = correctGuesses * SOCIAL_SPEAKER_POINTS_PER_CORRECT;
        speaker.set("score", speaker.get("score") + socialSpeakerPoints);
        speaker.round.set("social_round_score", socialSpeakerPoints);

        // Track speaker's cumulative social stats (how many guessed correctly about them)
        const speakerGuessedAbout = (speaker.get("social_guessed_about_total") || 0) + listeners.length;
        const speakerGuessedCorrect = (speaker.get("social_guessed_about_correct") || 0) + correctGuesses;
        speaker.set("social_guessed_about_total", speakerGuessedAbout);
        speaker.set("social_guessed_about_correct", speakerGuessedCorrect);
      }

      // Save chat
      const chat = stage.get(`${groupName}_chat`);
      groupPlayers.forEach((player) => {
        player.round.set("chat", chat);
      });
    });
  }
});

// Helper function to check if groups are still viable
function checkGroupViability(game) {
  const players = game.players;
  const activeGroups = game.get("active_groups") || GROUP_NAMES.slice(0, GROUP_COUNT);

  const viableGroups = activeGroups.filter((groupName) => {
    const groupPlayers = players.filter(
      (p) => p.get("is_active") && p.get("original_group") === groupName
    );
    return groupPlayers.length >= MIN_GROUP_SIZE;
  });

  // If a group is no longer viable, remove remaining member
  activeGroups.forEach((groupName) => {
    if (!viableGroups.includes(groupName)) {
      const remainingPlayers = players.filter(
        (p) => p.get("is_active") && p.get("original_group") === groupName
      );
      remainingPlayers.forEach((player) => {
        console.log(`Removing final member ${player.id} from disbanded group ${groupName}`);
        player.set("is_active", false);
        player.set("ended", "group disbanded");
      });
    }
  });

  game.set("active_groups", viableGroups);

  // Check if game can continue
  if (viableGroups.length < MIN_ACTIVE_GROUPS) {
    console.log("Not enough active groups, ending game");
    // Game will end naturally when rounds complete
  }
}

Empirica.onRoundEnded(({ round }) => {
  // Calculate and update bonuses at end of each round
  const game = round.currentGame;
  const players = game.players;

  players.forEach((player) => {
    player.set("bonus", player.get("score") * bonus_per_point);
  });
});

Empirica.onGameEnded(({ game }) => {
  console.log(`Game ${game.id} ended`);

  // Final bonus calculation
  const players = game.players;
  players.forEach((player) => {
    player.set("bonus", player.get("score") * bonus_per_point);
    console.log(
      `Player ${player.id}: Score=${player.get("score")}, Bonus=$${player.get("bonus").toFixed(2)}`
    );
  });
});
