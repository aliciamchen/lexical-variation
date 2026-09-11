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

REMOVAL_REASONS <- c(
  "player timeout" = "idle",
  "low accuracy" = "low accuracy",
  "group disbanded" = "group disbanded",
  "insufficient groups after accuracy check" = "insufficient groups"
)
REASON_LEVELS <- c("completed", unname(REMOVAL_REASONS))

# One row per player of a real game: condition, removed, reason, and the
# AI-use flag when present
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
      reason = factor(reason, levels = c(REASON_LEVELS, "other"))
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
      idleRounds,
      lengthIncreaseFlag
    )
}

# Per-condition player counts: removed overall, by reason, and flagged for a
# Phase 1 length increase
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
      length_flagged = sum(lengthIncreaseFlag, na.rm = TRUE),
      .groups = "drop"
    ) |>
    left_join(by_reason, by = "condition")
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
