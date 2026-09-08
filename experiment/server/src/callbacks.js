import { ClassicListenersCollector } from "@empirica/core/admin/classic";
export const Empirica = new ClassicListenersCollector();
import _ from "lodash";
import {
  tangram_sets,
  all_tangrams,
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
  SOCIAL_SPEAKER_POINTS_PER_CORRECT,
  MAX_IDLE_ROUNDS,
  MIN_GROUP_SIZE,
  TEST_MODE,
  SELECTION_DURATION,
  PHASE2_SELECTION_DURATION,
  FEEDBACK_DURATION,
  TRANSITION_DURATION,
  BONUS_INFO_DURATION,
  isMixedCondition,
  hasSocialGuessing,
  GROUP_NAMES,
} from "./constants";
import { reshuffleGroups } from "./reshuffling";
import { scoreSelectionStage } from "./scoring";
import { applyPartialPay } from "./compensation";
import { resolveTangramSet } from "./tangrams";
import { classifyIdle, isLateClick, updateIdleRounds } from "./idle";
import { accuracyCheckBlocks, evaluateGroupAccuracy, playerAccuracyOverBlocks } from "./accuracy";

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

  // Tangram set (two sets of Ji et al. 2022 high-SND tangrams) is a treatment
  // factor chosen when the batch is created, so sets are counterbalanced
  // exactly across games within each condition. Defaults to set 0.
  const tangram_set = resolveTangramSet(treatment);
  const context = tangram_sets[tangram_set];
  console.log(`Game assigned to tangram set: ${tangram_set}`);
  game.set("tangram_set", tangram_set);
  game.set("context", context);
  game.set("all_tangrams", all_tangrams);
  game.set("numDisplayTangrams", all_tangrams.length);

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

    // Tangram shuffling - shuffle all 16 tangrams (6 targets + 4 permanent distractors + 6 from other set)
    const shuffled_tangrams = _.shuffle(all_tangrams);
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
    hasSocialGuessing(condition) ? BONUS_PER_POINT_SOCIAL : bonus_per_point,
  );
  game.set("listenerCorrectPoints", LISTENER_CORRECT_POINTS);
  game.set("speakerMaxPointsPerRound", SPEAKER_MAX_POINTS_PER_ROUND);

  // ============ PHASE 1: REFERENCE GAME ============
  // Players play within their original groups
  // Production: 6 blocks (each of 3 players speaks twice); test mode: 3

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
    name: "Phase 2 transition",
    duration: TRANSITION_DURATION,
  });

  // ============ PHASE 2: CONTINUED REFERENCE GAME ============
  // Behavior depends on condition:
  // - refer_separated: Same groups as Phase 1
  // - refer_mixed: Groups reshuffled at start of each trial, identities masked
  // - social_mixed: Same as refer_mixed + social guessing question
  // Production: 6 blocks (12 in total with Phase 1); test mode: 2

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
        duration: PHASE2_SELECTION_DURATION,
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
    transition_type: "Bonus info",
  });

  finalTransition.addStage({
    name: "Bonus info",
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

    // In Phase 2 with mixed conditions, reshuffle groups at start of each trial
    const targetNum = round.get("target_num");
    if (
      phase_num === 2 &&
      isMixedCondition(condition)
    ) {
      reshuffleGroups(game, players, blockNum);
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
        phase_num === 2 && isMixedCondition(condition);

      groupPlayers.forEach((player, i) => {
        // In mixed conditions, use anonymous avatars for both display and chat
        if (isMixedPhase2) {
          const anonIndex = activeGroups.indexOf(groupName) * GROUP_SIZE + i;
          const anonSeed = `anon_block${blockNum}_trial${targetNum}_player${anonIndex}`;
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
  // Speakers are idle if they don't send any chat message
  // Listeners are idle if they don't send any chat message AND don't click a tangram
  //
  // Defined here but CALLED AT THE END OF THE FEEDBACK STAGE (bottom of this
  // callback), not when the Selection timer expires. Two reasons: (1) idle
  // removal can disband a group or trigger a reshuffle, which mutates
  // is_active / current_group / active_groups, and scoring must run against
  // the groups as the trial was actually played; (2) a selection sent just
  // before the deadline can reach the server after the Selection stage has
  // ended. It earns no points (scoring is final at the deadline), but by the
  // end of Feedback it has arrived, so it must not count as an idle round.
  // Such late arrivals are flagged on the player's round as late_click.
  const runIdleDetection = () => {
    const activeGroups = game.get("active_groups") || GROUP_NAMES;

    players.forEach((player) => {
      if (!player.get("is_active")) return;

      const playerGroup = player.get("current_group");
      const role = player.round.get("role");
      // The group chat lives on the Selection stage; scoring copies it onto
      // every group member's round at the deadline, which is what we read here
      // (this runs at the end of the Feedback stage).
      const chat = player.round.get("chat") || [];

      // Check if player sent any message
      const sentMessage = chat.some((msg) => msg.sender?.id === player.id);

      // Check if player clicked a tangram (only relevant for listeners)
      const clickedTangram = player.round.get("clicked");
      if (
        isLateClick({
          role,
          clicked: clickedTangram,
          clickedAtDeadline: player.round.get("clicked_at_deadline"),
        })
      ) {
        // Arrived after the Selection deadline: unscored, but not idle.
        player.round.set("late_click", true);
        console.log(`Player ${player.id} late click (after deadline) in round ${player.round.get("target_num")}`);
      }

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

      // Idle this round? (see idle.js for the rule)
      const wasIdle = classifyIdle({
        role,
        sentMessage,
        clicked: clickedTangram,
        speakerSentMessage,
      });

      if (wasIdle) {
        const { idleRounds, remove } = updateIdleRounds(player.get("idle_rounds"), true);
        player.set("idle_rounds", idleRounds);
        console.log(
          `Player ${player.id} (${role}) idle round ${idleRounds}/${MAX_IDLE_ROUNDS}`,
        );

        if (remove) {
          const wasSpeak = role === "speaker";
          console.log(
            `Player ${player.id} (${role}) removed after ${MAX_IDLE_ROUNDS} idle rounds`,
          );
          player.set("is_active", false);
          player.set("ended", "player timeout");
          player.set("exitReason", "player timeout");
          player.set("gameEndTime", Date.now());
          // Inactivity removals are paid base pay prorated to time spent but
          // forfeit the bonus (see compensation.js).
          applyPartialPay(player, { includeBonus: false });
          console.log(
            `  -> Prorated base pay (no bonus): $${player.get("partialPay")} for ${player.get("minutesSpent")} minutes`,
          );

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
  };

  // ============ SCORING FOR SELECTION STAGE ============
  // Runs BEFORE idle detection so that removals, group disbanding, or a
  // mid-block reshuffle triggered by idle players cannot corrupt the scoring
  // of the trial that was just played. The "scored" sentinel guards against a
  // re-fired stage callback double-adding points.
  if (stage.get("name") === "Selection" && !stage.get("scored")) {
    stage.set("scored", true);
    scoreSelectionStage(game, stage);
    // Snapshot which listeners had a selection when the deadline passed, so
    // idle detection (end of Feedback) can tell a late arrival from no click.
    players.forEach((player) => {
      if (!player.get("is_active") || player.round.get("role") !== "listener") return;
      player.round.set("clicked_at_deadline", Boolean(player.round.get("clicked")));
    });
  }

  // Idle detection runs at the end of the Feedback stage (see the comment at
  // its definition): removals and any resulting disband/reshuffle must only
  // affect FUTURE rounds, and selections that arrive after the deadline must
  // not be counted as idleness.
  if (stageName === "Feedback" && !stage.get("idle_checked")) {
    stage.set("idle_checked", true);
    runIdleDetection();
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
    phase_num === 2 && isMixedCondition(condition);

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

        // Proportional pay: base prorated to time spent, plus earned bonus
        applyPartialPay(player);
        console.log(
          `  -> Proportional pay: $${player.get("partialPay")} (base: $${player.get("partialBasePay")} + bonus: $${player.get("partialBonus")}) for ${player.get("minutesSpent")} minutes`,
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

      // Proportional pay: base prorated to time spent, plus earned bonus
      applyPartialPay(player);
      console.log(
        `  -> Proportional pay: $${player.get("partialPay")} for ${player.get("minutesSpent")} minutes`,
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

        reshuffleGroups(game, activePlayers, currentBlock);
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

  // Last ACCURACY_CHECK_BLOCKS blocks of Phase 1 (see accuracy.js)
  const blocksToCheck = accuracyCheckBlocks();

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

    // Listener accuracy per player over the checked blocks (see accuracy.js)
    const playerAccuracies = groupPlayers.map((player) => ({
      playerId: player.id,
      playerName: player.get("original_name"),
      ...playerAccuracyOverBlocks(player.get("block_accuracy") || {}, blocksToCheck),
    }));

    const { playersMeetingThreshold, proportionMeeting, groupMeetsThreshold } =
      evaluateGroupAccuracy(playerAccuracies.map((p) => p.accuracy));

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

        applyPartialPay(player);
        console.log(
          `    -> Proportional pay: $${player.get("partialPay")} (base: $${player.get("partialBasePay")} + bonus: $${player.get("partialBonus")}) for ${player.get("minutesSpent")} minutes`,
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

      applyPartialPay(player);
      console.log(
        `  -> Proportional pay: $${player.get("partialPay")} for ${player.get("minutesSpent")} minutes`,
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
    hasSocialGuessing(condition) ? BONUS_PER_POINT_SOCIAL : bonus_per_point;

  players.forEach((player) => {
    const totalScore = player.get("score") || 0;
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
    hasSocialGuessing(condition) ? BONUS_PER_POINT_SOCIAL : bonus_per_point;

  players.forEach((player) => {
    const totalScore = player.get("score") || 0;
    player.set("bonus", totalScore * multiplier);
    console.log(
      `Player ${player.id}: TotalScore=${totalScore}, Bonus=$${player.get("bonus").toFixed(2)}`,
    );
  });
});
