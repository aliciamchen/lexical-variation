# Reshuffle health: what the Phase 2 reassignment produced in each game.
#
# In Phase 2 of the mixed conditions the server reassigns players to groups on
# every trial so that each speaker has exactly one listener from their original
# group (experiment/server/src/reshuffling.js). After dropout that is not always
# possible, and the block's designated speaker may have to be replaced.
# `reshuffle_health()` summarizes, per game, what actually happened: the Phase 2
# roster, how many group-trials were trios and pairs, the share of trios that
# met the rule, and how many speaker reassignments there were. Everything is
# computed from the trio membership in trials.csv, so it works for exports from
# before the server recorded these facts itself; the reassignment count uses
# the exported `speakerReassigned` flag when present and otherwise each
# speaker's rotation index from players.csv.
#
# Tests: analysis/tests/test_reshuffle.R

MIXED_CONDITIONS <- c("refer_mixed", "social_mixed", "social_first")

# One row per game x round x current group: its size, speaker, and how many
# listeners share the speaker's original group.
group_trials <- function(trials) {
  trials |>
    group_by(gameId, roundId, phaseNum, blockNum, currentGroup) |>
    summarise(
      size = n_distinct(playerId),
      speakerId = first(playerId[role == "speaker"]),
      speakerGroup = first(originalGroup[role == "speaker"]),
      n_in_group = sum(
        role == "listener" & originalGroup == speakerGroup,
        na.rm = TRUE
      ),
      .groups = "drop"
    )
}

# Speaker reassignments per game: group-trials whose speaker was not the
# block's designated one (rotation index blockNum %% 3).
speaker_reassignments <- function(trials, players = NULL) {
  speakers <- trials |>
    filter(role == "speaker") |>
    distinct(
      gameId,
      roundId,
      currentGroup,
      playerId,
      blockNum,
      .keep_all = TRUE
    )
  if ("speakerReassigned" %in% names(trials)) {
    speakers |>
      group_by(gameId) |>
      summarise(
        speaker_reassignments = sum(
          speakerReassigned %in% c(TRUE, "true", "True")
        ),
        .groups = "drop"
      )
  } else if (!is.null(players) && "playerIndex" %in% names(players)) {
    speakers |>
      left_join(
        players |> select(gameId, playerId, playerIndex),
        by = c("gameId", "playerId")
      ) |>
      group_by(gameId) |>
      summarise(
        speaker_reassignments = sum(playerIndex != blockNum %% 3, na.rm = TRUE),
        .groups = "drop"
      )
  } else {
    tibble(gameId = character(), speaker_reassignments = integer())
  }
}

# Per-game summary of the Phase 2 reshuffling. Columns:
#   activeGroups            original groups still active at the end of the game
#   phase2_players_start/end  distinct players in the first and last Phase 2 round
#   group_trials, trios, pairs   Phase 2 group-trials by size
#   trios_one_in_group      trios whose speaker had exactly one in-group listener
#   prop_trios_one_in_group that share (NA outside the mixed conditions)
#   speaker_reassignments   group-trials, both phases, with a replaced speaker
reshuffle_health <- function(trials, games, players = NULL) {
  gt <- group_trials(trials)
  order_col <- if ("trialNum" %in% names(trials)) "trialNum" else "blockNum"
  rounds <- trials |>
    filter(phaseNum == 2) |>
    group_by(gameId, roundId) |>
    summarise(
      active = n_distinct(playerId),
      order = min(.data[[order_col]]),
      .groups = "drop"
    )
  roster <- rounds |>
    group_by(gameId) |>
    summarise(
      phase2_rounds = n(),
      phase2_players_start = active[which.min(order)],
      phase2_players_end = active[which.max(order)],
      .groups = "drop"
    )
  per_game <- gt |>
    filter(phaseNum == 2) |>
    group_by(gameId) |>
    summarise(
      group_trials = n(),
      trios = sum(size >= 3),
      trios_one_in_group = sum(size >= 3 & n_in_group == 1),
      pairs = sum(size == 2),
      .groups = "drop"
    )
  games |>
    filter(!is.na(condition)) |>
    select(gameId, condition, activeGroups) |>
    left_join(roster, by = "gameId") |>
    left_join(per_game, by = "gameId") |>
    left_join(speaker_reassignments(trials, players), by = "gameId") |>
    mutate(
      prop_trios_one_in_group = if_else(
        condition %in% MIXED_CONDITIONS & trios > 0,
        trios_one_in_group / trios,
        NA_real_
      )
    ) |>
    arrange(condition, gameId)
}
