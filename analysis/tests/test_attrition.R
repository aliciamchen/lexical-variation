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

# ── The two September 2026 exit reasons and the no-fault label ───────────────

new_games <- tibble(
  gameId = c("g4", "g5"),
  condition = c("social_first", "refer_separated"),
  activeGroups = c(0, 2)
)
new_players <- bind_rows(
  mk_players("g4", c("game terminated", "game terminated", "player timeout")),
  mk_players("g5", c("insufficient groups", "low accuracy"))
)
pa_new <- player_attrition(new_players, new_games)
check(
  "game terminated and insufficient groups are labeled as their own categories",
  identical(
    as.character(pa_new$reason[pa_new$removed]),
    c("game terminated", "game terminated", "idle", "insufficient groups", "low accuracy")
  ) && all(REASON_LEVELS %in% levels(pa_new$reason))
)
check(
  "disbanded, insufficient groups, and game terminated are not the participant's fault; idle and low accuracy are",
  identical(pa_new$no_fault[pa_new$removed], c(TRUE, TRUE, FALSE, TRUE, FALSE)) &&
    setequal(NO_FAULT_REASONS, c("group disbanded", "insufficient groups", "game terminated")) &&
    pa$no_fault[pa$gameId == "g3" & pa$reason == "group disbanded"]
)
abc_new <- attrition_by_condition(pa_new)
check(
  "attrition_by_condition counts no-fault removals and the new reason columns",
  abc_new$removed_no_fault[abc_new$condition == "social_first"] == 2 &&
    abc_new$`game terminated`[abc_new$condition == "social_first"] == 2 &&
    abc_new$`insufficient groups`[abc_new$condition == "refer_separated"] == 1 &&
    abc_new$removed_no_fault[abc_new$condition == "refer_separated"] == 1
)

# ── Group level ──────────────────────────────────────────────────────────────

ga <- group_attrition(players, games)
check(
  "group_attrition has one row per original group of a real game",
  nrow(ga) == 9 && all(ga$players == 3) && !"g0" %in% ga$gameId
)
g3A <- ga |> filter(gameId == "g3", originalGroup == "A")
g3B <- ga |> filter(gameId == "g3", originalGroup == "B")
check(
  "a group with fewer than two active members at the end is lost; one removal alone is not",
  g3A$active_at_end == 0 && g3A$lost && g3A$disbanded && g3A$removed_no_fault == 1 &&
    g3B$active_at_end == 2 && !g3B$lost && g3B$removed_no_fault == 1
)
gbc_groups <- groups_by_condition(ga)
check(
  "groups_by_condition counts intact and lost groups per condition, including empty conditions",
  nrow(gbc_groups) == 4 &&
    gbc_groups$intact[gbc_groups$condition == "refer_separated"] == 3 &&
    gbc_groups$lost[gbc_groups$condition == "social_mixed"] == 1 &&
    gbc_groups$intact[gbc_groups$condition == "social_mixed"] == 1 &&
    gbc_groups$groups[gbc_groups$condition == "social_first"] == 0
)
check(
  "a group screened out for low accuracy is flagged as such",
  {
    screened <- group_attrition(
      mk_players("g6", c("low accuracy", "low accuracy", "low accuracy")),
      tibble(gameId = "g6", condition = "refer_mixed", activeGroups = 2)
    )
    screened$low_accuracy[screened$originalGroup == "A"] &&
      screened$lost[screened$originalGroup == "A"] &&
      all(screened$removed_no_fault == 0) &&
      groups_by_condition(screened)$low_accuracy[2] == 1
  }
)

# ── Players who never played a real game ─────────────────────────────────────

dropouts <- tibble(
  playerId = paste0("d", 1:6),
  batchId = NA_character_,
  ended = c("game failed", "game failed", "no more games", "game failed", "game ended", NA),
  exitReason = c("quiz failed", "quiz failed", NA, NA, NA, NA),
  quizAttempts = c(3, 3, NA, 1, NA, NA)
)
ds <- dropout_summary(dropouts)
check(
  "dropout_summary labels quiz failures, lobby timeouts, and late arrivals",
  nrow(ds) == 5 &&
    ds$players[ds$outcome == "quiz failed"] == 2 &&
    ds$label[ds$outcome == "quiz failed"] == "failed the comprehension quiz (three attempts)" &&
    ds$players[ds$outcome == "game failed"] == 1 &&
    ds$label[ds$outcome == "game failed"] == "lobby timed out before a game started" &&
    ds$players[ds$outcome == "no more games"] == 1 &&
    ds$players[ds$outcome == "unknown"] == 1
)
check(
  "the mean number of quiz attempts is reported where recorded",
  ds$mean_quiz_attempts[ds$outcome == "quiz failed"] == 3 &&
    is.na(ds$mean_quiz_attempts[ds$outcome == "no more games"])
)
check(
  "quiz_failures counts the players who failed the quiz, zero without a file",
  quiz_failures(dropouts) == 2 && quiz_failures(tibble()) == 0 &&
    nrow(dropout_summary(tibble())) == 0
)
