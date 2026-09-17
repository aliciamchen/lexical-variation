# Attrition: who was removed, which games ran to completion, and whether
# dropout differs across conditions.
#
# The preregistration commits to reporting attrition rates by condition,
# testing whether dropout is differential across conditions, and rerunning the
# Phase 2 analyses on complete nine-player games (see robustness_rerun()).
#
# Definitions (from the server's callbacks and the players table):
#   removed          isActive is FALSE: the player was taken out of the game
#                    (idle, low accuracy, disbanded group, or too few groups)
#   reason           the exitReason of a removed player, or "completed"
#   ran to completion  a game whose remaining groups reached the end
#                    (activeGroups >= 2); these games enter the primary analyses
#   complete nine-player game  a game that ended with all nine players active
#
# Tests: analysis/tests/test_attrition.R

# The server's exit reasons (EXIT_REASONS in experiment/shared/constants.js)
# and the report category each one falls in. "insufficient groups" (too few
# viable groups left mid-game) and "game terminated" (the researcher stopped
# the batch) were added in September 2026.
REMOVAL_REASONS <- c(
  "player timeout" = "idle",
  "low accuracy" = "low accuracy",
  "group disbanded" = "group disbanded",
  "insufficient groups" = "insufficient groups",
  "insufficient groups after accuracy check" = "insufficient groups",
  "game terminated" = "game terminated"
)
REASON_LEVELS <- c("completed", unique(unname(REMOVAL_REASONS)))

# Removals that are not the participant's fault: their own group fell apart,
# too few groups remained for the game to go on, or the batch was stopped.
# These players are compensated for their time
# (experiment/server/src/compensation.js) and are reported apart from the
# players removed for their own inactivity or their group's low accuracy.
NO_FAULT_REASONS <- c(
  "group disbanded",
  "insufficient groups",
  "game terminated"
)

# One row per player of a real game: condition, removed, reason, whether the
# removal was through no fault of their own, and the AI-use flag when present
player_attrition <- function(players, games) {
  real <- games |> filter(!is.na(condition)) |> select(gameId, condition)
  out <- players |>
    inner_join(real, by = "gameId") |>
    mutate(
      condition = factor(as.character(condition), levels = CONDITION_ORDER),
      removed = !(isActive == TRUE | isActive == "true"),
      reason = ifelse(
        removed,
        unname(REMOVAL_REASONS[as.character(exitReason)]),
        "completed"
      ),
      reason = ifelse(removed & is.na(reason), "other", reason),
      reason = factor(reason, levels = c(REASON_LEVELS, "other")),
      no_fault = removed & reason %in% NO_FAULT_REASONS
    )
  if (!"lengthIncreaseFlag" %in% names(out)) {
    out$lengthIncreaseFlag <- NA
  }
  out |>
    mutate(
      lengthIncreaseFlag = lengthIncreaseFlag == TRUE |
        lengthIncreaseFlag == "true"
    ) |>
    select(
      gameId,
      playerId,
      condition,
      originalGroup,
      removed,
      reason,
      no_fault,
      idleRounds,
      lengthIncreaseFlag
    )
}

# Per-condition player counts: removed overall, removed through no fault of
# their own, by reason, and flagged for a Phase 1 length increase
attrition_by_condition <- function(pa) {
  by_reason <- pa |>
    filter(removed) |>
    count(condition, reason, .drop = FALSE) |>
    filter(reason != "completed") |>
    pivot_wider(names_from = reason, values_from = n, values_fill = 0)
  pa |>
    group_by(condition, .drop = FALSE) |>
    summarise(
      players = n(),
      removed = sum(removed),
      prop_removed = if (n() > 0) removed / players else NA_real_,
      removed_no_fault = sum(no_fault),
      length_flagged = sum(lengthIncreaseFlag, na.rm = TRUE),
      .groups = "drop"
    ) |>
    left_join(by_reason, by = "condition")
}

# One row per original group of a real game: its players, how many were still
# active at the end, removals by kind, whether the group failed the Phase 1
# accuracy screen or disbanded, and whether it was lost (fewer than
# MIN_GROUP_SIZE = 2 active members at the end, the server's rule for
# removing a group's remaining member)
group_attrition <- function(players, games) {
  player_attrition(players, games) |>
    group_by(gameId, condition, originalGroup) |>
    summarise(
      players = n(),
      active_at_end = sum(!removed),
      removed = sum(removed),
      removed_no_fault = sum(no_fault),
      low_accuracy = any(reason == "low accuracy"),
      disbanded = any(reason == "group disbanded"),
      lost = active_at_end < 2,
      .groups = "drop"
    )
}

# Per-condition group counts: groups, intact groups (no removal), groups lost,
# and the two ways a whole group leaves the game
groups_by_condition <- function(ga) {
  ga |>
    group_by(condition, .drop = FALSE) |>
    summarise(
      groups = n(),
      intact = sum(removed == 0),
      lost = sum(lost),
      prop_lost = if (n() > 0) lost / groups else NA_real_,
      low_accuracy = sum(low_accuracy),
      disbanded = sum(disbanded),
      .groups = "drop"
    )
}

# ── Players who never played a real game ─────────────────────────────────────
#
# data/<dataset>/dropouts.csv (combine_runs.py): one row per player record
# with no real game, with how Empirica ended it, the exit reason the server
# set, and the number of quiz attempts. These players have no condition, so
# the counts are for the dataset as a whole.

DROPOUT_LABELS <- c(
  "quiz failed" = "failed the comprehension quiz (three attempts)",
  "game failed" = "lobby timed out before a game started",
  "no more games" = "arrived after the games were full",
  "game terminated" = "batch stopped before a game started",
  "game ended" = "left before being assigned to a game"
)

# Counts by outcome (the exit reason when the server set one, otherwise how
# Empirica ended the record), with the mean number of quiz attempts where
# recorded
dropout_summary <- function(dropouts) {
  if (!has_rows(dropouts)) {
    return(tibble())
  }
  dropouts |>
    mutate(
      outcome = coalesce(as.character(exitReason), as.character(ended)),
      outcome = ifelse(is.na(outcome) | !nzchar(outcome), "unknown", outcome),
      label = ifelse(
        outcome %in% names(DROPOUT_LABELS),
        unname(DROPOUT_LABELS[outcome]),
        outcome
      )
    ) |>
    group_by(outcome, label) |>
    summarise(
      players = n(),
      mean_quiz_attempts = if (all(is.na(quizAttempts))) {
        NA_real_
      } else {
        mean(as.numeric(quizAttempts), na.rm = TRUE)
      },
      .groups = "drop"
    ) |>
    arrange(desc(players))
}

quiz_failures <- function(dropouts) {
  if (!has_rows(dropouts)) {
    return(0L)
  }
  sum(dropouts$exitReason %in% "quiz failed")
}

# One row per real game: players, removed players, active groups at the end,
# whether the game ran to completion, and whether all nine players stayed
game_status <- function(players, games) {
  pa <- player_attrition(players, games)
  per_game <- pa |>
    group_by(gameId) |>
    summarise(players = n(), removed = sum(removed), .groups = "drop")
  games |>
    filter(!is.na(condition)) |>
    select(gameId, condition, activeGroups) |>
    mutate(
      condition = factor(as.character(condition), levels = CONDITION_ORDER)
    ) |>
    left_join(per_game, by = "gameId") |>
    mutate(
      players = coalesce(players, 0L),
      removed = coalesce(removed, 0L),
      ran_to_completion = !is.na(activeGroups) & activeGroups >= 2,
      complete_nine = ran_to_completion & players == 9 & removed == 0
    )
}

complete_games <- function(players, games) {
  game_status(players, games) |> filter(complete_nine) |> pull(gameId)
}

games_by_condition <- function(status) {
  status |>
    group_by(condition, .drop = FALSE) |>
    summarise(
      games = n(),
      ran_to_completion = sum(ran_to_completion),
      complete_nine = sum(complete_nine),
      prop_complete_nine = if (n() > 0) complete_nine / games else NA_real_,
      .groups = "drop"
    )
}

# Is dropout differential across conditions? Two tests: a chi-square on
# players removed by condition (players are clustered in games, so its p-value
# is anticonservative and is reported as descriptive), and Fisher's exact test
# on games that stayed complete by condition (the game is the unit of
# replication).
differential_dropout_tests <- function(pa, status) {
  out <- list()
  if (
    n_distinct(pa$condition[!is.na(pa$condition)]) >= 2 &&
      any(pa$removed) &&
      !all(pa$removed)
  ) {
    tab <- table(droplevels(pa$condition), pa$removed)
    out$players <- suppressWarnings(chisq.test(tab))
  }
  if (
    n_distinct(status$condition) >= 2 &&
      any(status$complete_nine) &&
      !all(status$complete_nine)
  ) {
    tab <- table(droplevels(status$condition), status$complete_nine)
    out$games <- fisher.test(tab)
  }
  out
}
