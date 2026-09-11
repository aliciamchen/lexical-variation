# Tests for the attrition helpers in analysis/R/attrition.R.

if (!exists("player_attrition")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

# Three games: g1 complete, g2 lost one idle player and one low-accuracy group
# member but ran on, g3 terminated (fewer than two groups left). g0 is a test
# game without a condition and must be ignored.
games <- tibble(
  gameId = c("g1", "g2", "g3", "g0"),
  condition = c("refer_separated", "refer_mixed", "social_mixed", NA),
  activeGroups = c(3, 2, 1, 3)
)
mk_players <- function(game, removed_reasons) {
  tibble(
    gameId = game,
    playerId = sprintf("%s_p%d", game, 1:9),
    originalGroup = rep(c("A", "B", "C"), each = 3),
    isActive = c(
      rep(FALSE, length(removed_reasons)),
      rep(TRUE, 9 - length(removed_reasons))
    ),
    exitReason = c(removed_reasons, rep(NA, 9 - length(removed_reasons))),
    idleRounds = 0,
    lengthIncreaseFlag = c(TRUE, rep(FALSE, 8))
  )
}
players <- bind_rows(
  mk_players("g1", character(0)),
  mk_players("g2", c("player timeout", "low accuracy")),
  mk_players(
    "g3",
    c(
      "player timeout",
      "player timeout",
      "group disbanded",
      "insufficient groups after accuracy check"
    )
  ),
  mk_players("g0", character(0))
)

pa <- player_attrition(players, games)
check(
  "players of test games are dropped",
  nrow(pa) == 27 && !"g0" %in% pa$gameId
)
check("removed players are those no longer active", sum(pa$removed) == 6)
check(
  "exit reasons map to the report categories",
  identical(
    sort(as.character(pa$reason[pa$gameId == "g3"])),
    sort(c(
      "idle",
      "idle",
      "group disbanded",
      "insufficient groups",
      rep("completed", 5)
    ))
  )
)

abc <- attrition_by_condition(pa)
check(
  "attrition_by_condition has one row per condition, including conditions with no games",
  nrow(abc) == 4 && identical(as.character(abc$condition), CONDITION_ORDER)
)
check(
  "removal counts and proportions are right",
  abc$removed[abc$condition == "refer_mixed"] == 2 &&
    abs(abc$prop_removed[abc$condition == "refer_mixed"] - 2 / 9) < 1e-12 &&
    abc$removed[abc$condition == "refer_separated"] == 0
)
check(
  "reason columns are counts by condition",
  abc$idle[abc$condition == "social_mixed"] == 2 &&
    abc$`low accuracy`[abc$condition == "refer_mixed"] == 1
)
check(
  "the AI-use flag is counted per condition",
  all(abc$length_flagged[abc$games_present <- abc$players > 0] == 1)
)

status <- game_status(players, games)
check("game_status has one row per real game", nrow(status) == 3)
check(
  "a game with two groups left ran to completion but is not a complete nine-player game",
  status$ran_to_completion[status$gameId == "g2"] &&
    !status$complete_nine[status$gameId == "g2"]
)
check(
  "a terminated game neither ran to completion nor is complete",
  !status$ran_to_completion[status$gameId == "g3"] &&
    !status$complete_nine[status$gameId == "g3"]
)
check(
  "complete_games returns the games that kept all nine players",
  identical(complete_games(players, games), "g1")
)

gbc <- games_by_condition(status)
check(
  "games_by_condition counts complete games per condition",
  gbc$complete_nine[gbc$condition == "refer_separated"] == 1 &&
    gbc$games[gbc$condition == "social_first"] == 0
)

tests <- differential_dropout_tests(pa, status)
check(
  "both dropout tests run when there is variation",
  all(c("players", "games") %in% names(tests)) &&
    inherits(tests$players, "htest") &&
    inherits(tests$games, "htest")
)
none <- differential_dropout_tests(
  pa |> mutate(removed = FALSE),
  status |> mutate(complete_nine = TRUE)
)
check("no test is run when nobody dropped out", length(none) == 0)
