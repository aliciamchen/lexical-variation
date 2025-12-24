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

  // Assign tangram set (single set with Ji et al. 2022 tangrams)
  const tangram_set = 0;
  const context = tangram_sets[tangram_set];
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
        duration: 45,
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
        duration: 45,
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

      // In Phase 1 (or Phase 2 separated): Use consistent player order so speaker stays same within block
      // In Phase 2 mixed conditions: Shuffle for fair distribution since groups change each trial
      const isMixedPhase2 = phase_num === 2 &&
        (condition === "refer_mixed" || condition === "social_mixed");

      const orderedGroupPlayers = isMixedPhase2
        ? _.shuffle(groupPlayers)
        : _.sortBy(groupPlayers, (p) => p.get("player_index"));

      // Calculate speaker index based on block number and CURRENT group size
      // This ensures even rotation even after dropouts (e.g., with 2 players: 0,1,0,1...)
      const adjustedSpeakerIndex = orderedGroupPlayers.length > 0
        ? blockNum % orderedGroupPlayers.length
        : 0;

      orderedGroupPlayers.forEach((player, i) => {
        // In mixed conditions, use anonymous avatars for both display and chat
        if (
          phase_num === 2 &&
          (condition === "refer_mixed" || condition === "social_mixed")
        ) {
          const anonIndex = activeGroups.indexOf(groupName) * GROUP_SIZE + i;
          const anonSeed = `anon_block${blockNum}_player${anonIndex}`;
          const anonAvatar = getAnonymousAvatarUrl(anonSeed);
          const anonName = `Player ${anonIndex + 1}`;

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

        // Assign speaker/listener roles (using adjusted index for reduced groups)
        player.round.set("role", i === adjustedSpeakerIndex ? "speaker" : "listener");
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

// Helper function to reshuffle groups for mixed conditions
function reshuffleGroups(game, players) {
  console.log("Reshuffling groups for mixed condition");

  const activeGroups = game.get("active_groups") || GROUP_NAMES.slice(0, GROUP_COUNT);
  const shuffledPlayers = _.shuffle(players);
  const numPlayers = shuffledPlayers.length;

  // Calculate how many groups we can support with MIN_GROUP_SIZE each
  const maxGroups = Math.floor(numPlayers / MIN_GROUP_SIZE);
  const numGroups = Math.min(maxGroups, activeGroups.length);

  if (numGroups === 0) {
    console.log("Not enough players for any viable group");
    return;
  }

  // Distribute players evenly across groups using round-robin
  // This spreads players like: 7 players / 3 groups → 3+2+2
  shuffledPlayers.forEach((player, i) => {
    const groupIndex = i % numGroups;
    player.set("current_group", activeGroups[groupIndex]);
  });

  console.log(`Reshuffled ${numPlayers} players into ${numGroups} groups`);
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

      // Count correct listeners
      const correctListeners = listeners.filter(
        (p) => p.round.get("clicked") === target
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
