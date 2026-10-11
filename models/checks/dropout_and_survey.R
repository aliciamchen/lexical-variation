# Two further preregistered checks, neither of which gates anything. Dropout:
# whether removal differs across conditions, as a chi-square on removed
# players (players are clustered in games, so it is descriptive) and Fisher's
# exact test on the games that stayed complete (the game is the unit).
# Survey: the two 7-point group-identification items and whether participants
# noticed their group developing its own way of describing the pictures,
# compared across conditions with Kruskal-Wallis and chi-square tests. The
# counts and means themselves are descriptive statistics written by
# report/descriptives.py.
#
# Writes results/estimates/checks/dropout_and_survey.csv: one row
# per test with its statistic, degrees of freedom and p-value.

source(here::here("models", "config.R"))
list2env(load_tables(), envir = globalenv())

pa <- player_attrition(players, games)
status <- game_status(players, games)
dropout_tests <- differential_dropout_tests(pa, status)
if (!is.null(dropout_tests$players)) {
  cat("Players removed by condition (chi-square; descriptive, players are clustered in games):\n")
  print(dropout_tests$players)
}
if (!is.null(dropout_tests$games)) {
  cat("\nComplete nine-player games by condition (Fisher's exact test):\n")
  print(dropout_tests$games)
}

survey <- exit_survey_responses(players, games)
survey_tests <- list()
for (item in c("groupIdentification", "groupCloseness")) {
  if (has_field(survey, item)) {
    item_data <- survey |> filter(!is.na(.data[[item]]))
    if (n_distinct(item_data$condition) >= 2) {
      cat(sprintf("\n%s by condition (Kruskal-Wallis):\n", item))
      survey_tests[[item]] <- kruskal.test(item_data[[item]] ~ item_data$condition)
      print(survey_tests[[item]])
    }
  }
}
if (has_field(survey, "groupLanguage")) {
  item_data <- survey |> filter(!is.na(groupLanguage))
  if (n_distinct(item_data$condition) >= 2) {
    cat("\nNoticed group-specific language, by condition (chi-square):\n")
    survey_tests$groupLanguage <- suppressWarnings(
      chisq.test(table(droplevels(item_data$condition), item_data$groupLanguage))
    )
    print(survey_tests$groupLanguage)
  }
}

rows <- bind_rows(
  tidy_htest(dropout_tests$players, "dropout_players", n = nrow(pa)),
  tidy_htest(dropout_tests$games, "dropout_games", n = nrow(status)),
  tidy_htest(
    survey_tests$groupIdentification, "survey_identification",
    n = if (has_field(survey, "groupIdentification")) sum(!is.na(survey$groupIdentification)) else NA_integer_
  ),
  tidy_htest(
    survey_tests$groupCloseness, "survey_closeness",
    n = if (has_field(survey, "groupCloseness")) sum(!is.na(survey$groupCloseness)) else NA_integer_
  ),
  tidy_htest(
    survey_tests$groupLanguage, "survey_group_language",
    n = if (has_field(survey, "groupLanguage")) sum(!is.na(survey$groupLanguage)) else NA_integer_
  )
)
write_estimates(rows, "checks/dropout_and_survey", source = "models/checks/dropout_and_survey.R")
