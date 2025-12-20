import { ClassicListenersCollector } from "@empirica/core/admin/classic";
export const Empirica = new ClassicListenersCollector();
import _ from "lodash";
import {
  tangram_sets,
  names,
  name_colors,
  conditions,
  avatar_names,
  bonus_per_point,
} from "./constants";

Empirica.onGameStart(({ game }) => {
  console.log(`Game ${game.id} started`);
  game.set("justStarted", true);
  // Assign tangram set
  const tangram_set = _.random(0, 2);
  const context = tangram_sets[tangram_set];
  game.set("tangram_set", tangram_set);
  game.set("context", context);

  game.players.forEach((player, i) => {
    player.set("name", names[i]);
    player.set("tangram_set", tangram_set);
    player.set("context", context);
    player.set("score", 0); // Max score: 12 * 6 * 3 + 18 * 3 + 36 * 6 = 216 + 54 + 216 = 486
    player.set("phase3score", 0);
    player.set("bonus", 0);
    player.set("num_stages_inactive", 0);
  });

  // Randomly assign 4 of the players to the red group and the other 4 to the blue group
  const red_players = _.sampleSize(game.players, game.players.length / 2);
  const blue_players = _.difference(game.players, red_players);
  red_players.forEach((player, i) => {
    player.set("group", "red");
    player.set("other_group", "blue");
    player.set("player_index", i);
    player.set("avatar_name", avatar_names["red"][i]);
    player.set("avatar", `/${avatar_names["red"][i]}.png`);
    player.set("name_color", name_colors["red"][i]);
    const shuffled_tangrams = _.shuffle(context);
    player.set("shuffled_tangrams", shuffled_tangrams);
    player.set(
      "tangramURLs",
      shuffled_tangrams.map((tangram) => `/tangram_${tangram}.png`)
    );
  });
  blue_players.forEach((player, i) => {
    player.set("group", "blue");
    player.set("other_group", "red");
    player.set("player_index", i);
    player.set("avatar_name", avatar_names["blue"][i]);
    player.set("avatar", `/${avatar_names["blue"][i]}.png`);
    player.set("name_color", name_colors["blue"][i]);
    const shuffled_tangrams = _.shuffle(context);
    player.set("shuffled_tangrams", shuffled_tangrams);
    player.set(
      "tangramURLs",
      shuffled_tangrams.map((tangram) => `/tangram_${tangram}.png`)
    );
  });

  // PHASE 1: REFERENCE GAME
  // Players play a reference game within their group
  // The speaker has to refer to each tangram in the context before the speaker role moves to the next player for the next block of trials.
  // There are 8 blocks total (so each player will be in the speaker role twice, and each tangram will appear as the target exactly 8 times)
  _.times(2, (i) => {
    // loop through each speaker twice
    _.times(4, (player_index) => {
      // loop through each player in the group
      const shuffled_context = _.shuffle(context);
      _.times(shuffled_context.length, (target_num) => {
        // in each round (repetition block), loop through each tangram in the context
        const round = game.addRound({
          name: `Phase 1: Reference Game`,
          phase: "refgame",
          speaker: player_index,
          target_order: shuffled_context,
          target: shuffled_context[target_num],
          target_num: target_num,
          rep_num: i * 4 + player_index,
        });
        round.addStage({
          name: "Selection",
          duration: 120,
        });
        round.addStage({
          name: "Feedback",
          duration: 15,
        });
      });
    });
  });

  const transition_1 = game.addRound({
    phase: "transition",
  });

  transition_1.addStage({
    name: "phase_2_transition",
    duration: 60,
  });

  // PHASE 2: SPEAKER PRODUCTION

  const phase_2 = game.addRound({
    name: "Phase 2", // change later
    phase: "speaker_prod",
  });
  const tangram_combos = _.flatten(
    context.map((tangram) =>
      conditions.map((condition) => [tangram, condition])
    )
  ); // all combos of tangrams and conditions
  // for each player, add the randomized order of tangram-condition pairs
  game.players.forEach((player) => {
    player.set("phase_2_trial_order", _.shuffle(tangram_combos)); // TODO: change to object rather than indexing into list
  });
  _.times(tangram_combos.length, (i) => {
    // _.times(2, (i) => {
    // for testing
    phase_2.addStage({
      name: "Production",
      duration: 30,
      trial_num: i,
    }); // each player sees a different order of tangram-condition pairs, so the trial number is used to index into the player's order in Stage.jsx
  });

  const transition_2 = game.addRound({
    phase: "transition",
  });

  transition_2.addStage({
    name: "phase_3_transition",
    duration: 60,
  });

  // PHASE 3: LISTENER INTERPRETATION

  // Create phase 3 trials
  const phase_3 = game.addRound({
    name: "Phase 3",
    phase: "comprehension",
  });
  // add placeholder stages
  _.times(36, (i) => {
    phase_3.addStage({
      name: "Comprehension",
      duration: 30,
      trial_num: i,
    });
  });

  const transition_3 = game.addRound({
    phase: "transition",
  });

  transition_3.addStage({
    name: "bonus_info",
    duration: 60,
  });
});

Empirica.onRoundStart(({ round }) => {
  round.set("justStarted", true);
  // On refgame round starts, set player roles
  if (round.get("phase") == "refgame") {
    const players = round.currentGame.players;
    const red_players = players.filter(
      (player) => player.get("group") == "red"
    );
    const blue_players = players.filter(
      (player) => player.get("group") == "blue"
    );
    const speaker = round.get("speaker");
    red_players.forEach((player, i) => {
      player.round.set("role", i == speaker ? "speaker" : "listener");
    });
    blue_players.forEach((player, i) => {
      player.round.set("role", i == speaker ? "speaker" : "listener");
    });

    // save group, target in player round
    players.forEach((player) => {
      player.round.set("name", player.get("name"));
      player.round.set("phase", "refgame");
      player.round.set("group", player.get("group"));
      player.round.set("rep_num", round.get("rep_num")); // TODO: change.. what is this doing
      player.round.set("target", round.get("target"));
    });
  }

  if (round.get("phase") == "speaker_prod") {
    console.log(
      `Speaker production round started for game ${round.currentGame.id}`
    );
  }

  if (round.get("phase") == "comprehension") {
    console.log(`Comprehension round started for game ${round.currentGame.id}`);
  }
});

Empirica.onStageStart(({ stage }) => {
  const game = stage.currentGame;
  // const round = stage.round;
  const players = game.players;
  players.forEach((player) => {
    if (player.get("ended") === "player timeout") {
      player.stage.set("submit", "true");
      if (player.round.get("role") == "speaker") {
        players.forEach((p) => {
          if (p.round.get("role") == "listener") {
            p.stage.set("submit", "true");
          }
        });
      }
    }
  });

  // Each participant sees the trials in a different order, so we want to add that information to player stages
  if (stage.get("name") === "Production") {
    // const game = stage.currentGame;
    // const players = game.players;

    players.forEach((player) => {
      const trial_num = stage.get("trial_num");
      const trial = player.get("phase_2_trial_order")[trial_num];
      player.stage.set("name", "production");
      player.stage.set("target", trial[0]);
      player.stage.set("condition", trial[1]);
    });
  }
  if (stage.get("name") === "Comprehension") {
    // const game = stage.currentGame;
    // const players = game.players;

    players.forEach((player) => {
      const trial_num = stage.get("trial_num");
      const trial = player.get("phase_3_trials")[trial_num];

      player.stage.set("name", "comprehension");
      player.stage.set("target", trial.target);
      player.stage.set("condition", trial.condition);
      player.stage.set("matched", trial.matched);
      player.stage.set("speaker", trial.speaker);
      player.stage.set("player_group", player.get("group"));
      player.stage.set("speaker_group", trial.speaker_group);
      player.stage.set("speaker_name", trial.speaker_name);
      player.stage.set("description", trial.description);
    });
  }
});

Empirica.onStageEnded(({ stage }) => {
  const game = stage.currentGame;
  const players = game.players;

  // handle inactive players
  players.forEach((player) => {
    const isActive = player.stage.get("submit");
    if (!isActive) {
      const consecutive_inactive = player.get("num_consecutive_inactive") || 0;
      player.set("num_consecutive_inactive", consecutive_inactive + 1);
      player.set("num_stages_inactive", player.get("num_stages_inactive") + 1);
      if (consecutive_inactive >= 2) {
        console.log(
          `Player ${player.id} in Game ${game.id} was inactive for 2 consecutive stages and has been kicked`
        );
        player.set("ended", "player timeout");
      }
    } else {
      player.set("num_consecutive_inactive", 0); // reset consecutive inactive count
    }
  });

  if (stage.get("name") === "Selection") {
    // during refgame phase
    // Calculate score for the current stage
    // Listeners get 1 point when they correctly identify the target
    // The speaker gets the average of the listeners' scores, in that group.

    const round = stage.round;

    const target = round.get("target");
    const red_players = players.filter(
      (player) => player.get("group") == "red"
    );
    const blue_players = players.filter(
      (player) => player.get("group") == "blue"
    );

    const red_listeners = red_players.filter(
      (player) => player.round.get("role") == "listener"
    );
    const blue_listeners = blue_players.filter(
      (player) => player.round.get("role") == "listener"
    );

    const red_speaker = red_players.find(
      (player) => player.round.get("role") == "speaker"
    );
    const blue_speaker = blue_players.find(
      (player) => player.round.get("role") == "speaker"
    );

    const red_correct = red_listeners.filter(
      (player) => player.round.get("clicked") == target
    );
    const blue_correct = blue_listeners.filter(
      (player) => player.round.get("clicked") == target
    );

    red_correct.forEach((player) => {
      player.set("score", player.get("score") + 3);
    });
    blue_correct.forEach((player) => {
      player.set("score", player.get("score") + 3);
    });

    const red_avg_score = red_listeners.length
      ? (red_correct.length * 3) / red_listeners.length
      : 0;
    const blue_avg_score = blue_listeners.length
      ? (blue_correct.length * 3) / blue_listeners.length
      : 0;

    red_speaker.set("score", red_speaker.get("score") + red_avg_score);
    red_speaker.round.set("round_score", red_avg_score);
    blue_speaker.set("score", blue_speaker.get("score") + blue_avg_score);
    blue_speaker.round.set("round_score", blue_avg_score);

    // save chat in round
    red_players.forEach((player) => {
      const chat = stage.get("red_chat");
      player.round.set("chat", chat);
    });
    blue_players.forEach((player) => {
      const chat = stage.get("blue_chat");
      player.round.set("chat", chat);
    });
  }

  // Add Phase 2 speaker utterances to player's round data (for collecting later)
  if (stage.get("name") === "Production") {
    const game = stage.currentGame;
    const players = game.players;

    players.forEach((player) => {
      const utterance = player.stage.get("utterance");
      // console.log(utterance);

      if (!player.round.get("utterances")) {
        player.round.set("utterances", {});
      }

      const player_utterances = player.round.get("utterances");
      // PROBLEM - no utterances available, set to player...

      const condition = player.stage.get("condition");
      const tangram = player.stage.get("target");

      if (utterance) {
        // create condition, tangram keys if they don't exist
        if (!player_utterances[condition]) {
          player_utterances[condition] = {};
        }
        if (!player_utterances[condition][tangram]) {
          player_utterances[condition][tangram] = {};
        }

        // add utterance to player's utterances
        player_utterances[condition][tangram] = utterance;
        player.round.set("utterances", player_utterances);
        // console.log(player_utterances); // TODO: test
      }
    });
  }

  // TODO: for the comprehnsion phase, assess accuracy (one point for each correct answer)
  // Assign score to both the listener and the speaker that had produced the utterance

  if (stage.get("name") === "Comprehension") {
    const players = stage.currentGame.players;
    players.forEach((player) => {
      const phase3score = player.get("phase3score") || 0;

      const thisTrialScore =
        (player.stage.get("correctTangram") ? 3 : 0) +
        (player.stage.get("correctGroup") ? 3 : 0);

      player.set("phase3score", phase3score + thisTrialScore);

      // Find the speaker by ID
      const speakerId = player.stage.get("speaker");
      const speaker = players.find((p) => p.id === speakerId);

      if (speaker) {
        let speaker_phase3score = speaker.get("phase3score") || 0;
        let speakerReward = 0;

        // If condition is 'refer own' or 'refer other', reward speaker for correct tangram guess
        // If condition is 'social own', reward speaker for correct group guess
        const condition = player.stage.get("condition");

        if (condition && condition.includes("refer")) {
          speakerReward = player.stage.get("correctTangram") ? 3 : 0;
        } else {
          speakerReward = player.stage.get("correctGroup") ? 3 : 0;
        }

        // Update speaker's phase3score
        speaker.set("phase3score", speaker_phase3score + speakerReward);
      } else {
        console.error(`Speaker with ID ${speakerId} not found`);
      }
    });
  }
});

Empirica.onRoundEnded(({ round }) => {
  // TODO: If we are at the end of phase 2, collect the utterances based on condition and group, and make the phase 3 trials.

  // In Phase 3, all participants will now be in the listener role, shown expressions from Phase 2 of the task, and,
  // for each expression, asked to submit two responses: choose the corresponding tangram, and guess the
  // correct speaker group. Listeners will be equally rewarded for all correct answers on all trials. In order to test the
  // extent to which expressions are more informative for the intended audience (e.g. the in-group) relative to an
  // unintended audience (e.g. the out-group), participants will be delivered expressions that were produced for
  // both their own group and for the opposite group.

  // Thus, participants will see 6 expressions per tangram — one expression for each of the 3 conditions
  // (social+own, refer+own, refer+other) x 2 speaker-recipient mappings (‘matched’ vs. ‘unmatched’). There are 6
  // tangrams, so this results in a total of 36 trials in Phase 3. We will balance the assignment of players to
  // condition so that each of the six expressions for each tangram will originate from a different player. There are 3
  // other players from the participant's own group and 4 other players from the other group, so for the expressions
  // that originate from the other group, one of the players will be excluded for each tangram. This exclusion will be
  // balanced across tangrams to ensure even representation of other-group players. The order of the 36 trials will
  // be randomized.

  // Trial count:

  // ‘Matched’ speaker-recipient (delivered to intended audience):
  // 6 trials social+own (from own group)
  // +  6 trials refer+own (from own group)
  // +  6 trials refer+other (from other group)
  // = 18 phase 3 ‘matched’ trials

  // ‘Unmatched’ speaker-recipient (delivered to unintended audience):
  // 6 trials social+own (from other group)
  // +  6 trials refer+own (from other group)
  // +  6 trials refer+other (from own group)
  // = 18 phase 3 ‘unmatched’ trials

  if (round.get("phase") == "speaker_prod") {
    const game = round.currentGame;
    const players = game.players;
    const context = game.get("context");

    // Collect the utterances from phase 2
    let all_utterances = { red: {}, blue: {} };
    players.forEach((player) => {
      const utterances = player.round.get("utterances");
      const player_group = player.get("group");
      console.log(utterances);
      if (utterances) {
        if (!all_utterances[player_group]) {
          all_utterances[player_group] = {};
        }
        all_utterances[player_group][player.id] = utterances;
      }
      player.set("all_utterances", all_utterances);
    });
    console.log(`Utterances collected for game ${game.id}:`);
    console.log(all_utterances);

    players.forEach((player) => {
      const player_group = player.get("group");
      const other_group = player_group == "red" ? "blue" : "red";
      const own_group_players = players.filter(
        (p) => p.get("group") == player_group && p.id !== player.id
      );
      const other_group_players = players.filter(
        (p) => p.get("group") == other_group
      );

      // Create the 36 trials (6 tangrams x 3 conditions x 2 speaker-recipient mappings)
      const phase_3_trials = [];
      context.forEach((tangram, tangramIndex) => {
        const shuffled_other_group_players = _.shuffle(other_group_players);
        const shuffled_own_group_players = _.shuffle(own_group_players);
        shuffled_other_group_players.pop(); // exclude one player from the other group

        // Helper function to safely get utterance or provide fallback
        const safeGetUtterance = (
          groupId,
          playerId,
          condition,
          targetTangram
        ) => {
          try {
            if (
              all_utterances[groupId] &&
              all_utterances[groupId][playerId] &&
              all_utterances[groupId][playerId][condition] &&
              all_utterances[groupId][playerId][condition][targetTangram]
            ) {
              return all_utterances[groupId][playerId][condition][
                targetTangram
              ];
            }
            return `[No description provided]`;
          } catch (e) {
            console.error(`Error getting utterance: ${e.message}`);
            return `[Error retrieving description]`;
          }
        };

        // social + own, from own group
        if (shuffled_own_group_players.length > 0) {
          const speaker = shuffled_own_group_players[0];
          phase_3_trials.push({
            condition: "social own",
            matched: "matched",
            speaker: speaker.id,
            speaker_group: player_group,
            speaker_name: speaker.get("name"),
            description: safeGetUtterance(
              player_group,
              speaker.id,
              "social own",
              tangram
            ),
            target: tangram,
          });
        }
        // console.log(phase_3_trials);

        // refer + own, from own group
        if (shuffled_own_group_players.length > 0) {
          const speaker = shuffled_own_group_players[1];
          phase_3_trials.push({
            condition: "refer own",
            matched: "matched",
            speaker: speaker.id,
            speaker_group: player_group,
            speaker_name: speaker.get("name"),
            description: safeGetUtterance(
              player_group,
              speaker.id,
              "refer own",
              tangram
            ),
            target: tangram,
          });
        }

        // refer + other, from other group
        if (shuffled_other_group_players.length > 0) {
          const speaker = shuffled_other_group_players[0];
          phase_3_trials.push({
            condition: "refer other",
            matched: "matched",
            speaker: speaker.id,
            speaker_group: other_group,
            speaker_name: speaker.get("name"),
            description: safeGetUtterance(
              other_group,
              speaker.id,
              "refer other",
              tangram
            ),
            target: tangram,
          });
        }

        // social + own, from other group
        if (shuffled_other_group_players.length > 0) {
          const speaker = shuffled_other_group_players[1];
          phase_3_trials.push({
            condition: "social own",
            matched: "unmatched",
            speaker: speaker.id,
            speaker_group: other_group,
            speaker_name: speaker.get("name"),
            description: safeGetUtterance(
              other_group,
              speaker.id,
              "social own",
              tangram
            ),
            target: tangram,
          });
        }

        // refer + own, from other group
        if (shuffled_other_group_players.length > 0) {
          const speaker = shuffled_other_group_players[2];
          phase_3_trials.push({
            condition: "refer own",
            matched: "unmatched",
            speaker: speaker.id,
            speaker_group: other_group,
            speaker_name: speaker.get("name"),
            description: safeGetUtterance(
              other_group,
              speaker.id,
              "refer own",
              tangram
            ),
            target: tangram,
          });
        }

        // refer + other, from own group
        if (shuffled_own_group_players.length > 0) {
          const speaker = shuffled_own_group_players[2];
          phase_3_trials.push({
            condition: "refer other",
            matched: "unmatched",
            speaker: speaker.id,
            speaker_group: player_group,
            speaker_name: speaker.get("name"),
            description: safeGetUtterance(
              player_group,
              speaker.id,
              "refer other",
              tangram
            ),
            target: tangram,
          });
        }
      });
      // console.log(phase_3_trials);
      const shuffled_phase_3_trials = _.shuffle(phase_3_trials);
      player.set("phase_3_trials", shuffled_phase_3_trials);
    });
  }

  // Collect the phase 3 scores and add them to total score
  if (round.get("phase") == "comprehension") {
    const game = round.currentGame;
    const players = game.players;
    players.forEach((player) => {
      const phase3score = player.get("phase3score") || 0;
      player.set("score", player.get("score") + phase3score);
      player.set("bonus", player.get("score") * bonus_per_point);
    });
  }
});

Empirica.onGameEnded(({ game }) => {
  console.log(`Game ${game.id} ended`);
});
