# Tests for the social-identification components in analysis/R/social.R.

if (!exists("social_identification_components")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

soc_games <- tibble(
  gameId = c("g1", "g2"),
  condition = c("social_mixed", "social_first")
)

# g1: three in-group speakers (same, same, different) and three out-group
# speakers (different, same, timeout); one excluded row on top. g2: a single
# out-group opportunity whose speaker status is unknown.
soc_guesses <- tibble(
  gameId = c(rep("g1", 7), "g2"),
  playerId = paste0("p", 1:8),
  roundId = c("r1", "r1", "r2", "r2", "r3", "r3", "r4", "r9"),
  originalGroup = "A",
  currentGroup = "X",
  phaseNum = 2,
  blockNum = c(0, 0, 1, 1, 2, 2, 3, 0),
  target = "t1",
  speakerId = c("sA", "sA", "sA", "sB", "sB", "sB", "sA", "sZ"),
  speakerWasSameGroup = c(TRUE, TRUE, TRUE, FALSE, FALSE, FALSE, TRUE, NA),
  socialGuess = c(
    "same_group",
    "same_group",
    "different_group",
    "different_group",
    "same_group",
    NA,
    "same_group",
    "different_group"
  ),
  socialGuessCorrect = c(TRUE, TRUE, FALSE, TRUE, FALSE, NA, TRUE, TRUE),
  socialTimeout = c(FALSE, FALSE, FALSE, FALSE, FALSE, TRUE, FALSE, FALSE),
  lateSocialGuess = FALSE,
  responseOpportunity = TRUE,
  excluded = c(rep(FALSE, 6), TRUE, FALSE),
  exclusionReason = c(rep("", 6), "bot-like responses", "")
)
no_exclusions <- technical_exclusions(tempdir())
soc_frame <- social_guess_trials(
  soc_guesses,
  soc_games,
  exclusions = no_exclusions
)
comp <- social_identification_components(soc_frame)
sm <- comp |> filter(condition == "social_mixed")
sf <- comp |> filter(condition == "social_first")

check(
  "one row per condition with the opportunity composition",
  nrow(comp) == 2 &&
    sm$opportunities == 7 &&
    sm$excluded == 1 &&
    sm$scored == 6 &&
    sm$in_group_opportunities == 3 &&
    sm$out_group_opportunities == 3 &&
    sm$speaker_unknown == 0
)
check(
  "on-time rate and the two accuracies are over scored opportunities and on-time answers",
  sm$on_time == 5 &&
    abs(sm$on_time_rate - 5 / 6) < 1e-12 &&
    abs(sm$accuracy - 0.5) < 1e-12 &&
    abs(sm$accuracy_on_time - 3 / 5) < 1e-12
)
check(
  "hit rate, false-alarm rate, and balanced accuracy follow the preregistered definitions",
  sm$in_group_answered == 3 &&
    sm$out_group_answered == 2 &&
    abs(sm$hit_rate - 2 / 3) < 1e-12 &&
    abs(sm$false_alarm_rate - 1 / 2) < 1e-12 &&
    abs(sm$balanced_accuracy - (2 / 3 + 1 / 2) / 2) < 1e-12
)
check(
  "an unknown speaker status is counted and gives NA component rates, not zero",
  sf$scored == 1 &&
    sf$speaker_unknown == 1 &&
    is.na(sf$hit_rate) &&
    is.na(sf$false_alarm_rate) &&
    is.na(sf$balanced_accuracy) &&
    sf$accuracy == 1
)

# Derivation of the speaker's group from trials.csv when the column is absent
# One speaker row per (round, speaker): in a mixed game a round has one
# speaker per current group, so r2 has two.
soc_trials <- tibble(
  gameId = "g1",
  roundId = c("r1", "r2", "r2", "r3", "r4"),
  playerId = c("sA", "sA", "sB", "sB", "sA"),
  originalGroup = c("A", "A", "B", "B", "A"),
  role = "speaker"
)
derived <- social_identification_components(
  soc_frame |> select(-speakerWasSameGroup),
  trials = soc_trials
) |>
  filter(condition == "social_mixed")
check(
  "without speakerWasSameGroup the speaker's group is looked up in trials.csv",
  derived$in_group_opportunities == 3 &&
    derived$out_group_opportunities == 3 &&
    abs(derived$hit_rate - 2 / 3) < 1e-12
)
check(
  "without either source the function refuses rather than guessing",
  inherits(
    try(
      social_identification_components(
        soc_frame |> select(-speakerWasSameGroup)
      ),
      silent = TRUE
    ),
    "try-error"
  )
)
check(
  "the components need the coded opportunity frame",
  inherits(
    try(social_identification_components(soc_guesses), silent = TRUE),
    "try-error"
  )
)
check(
  "empty input gives an empty table",
  nrow(social_identification_components(tibble())) == 0
)
check(
  "the short column set exists in the full table",
  all(SOCIAL_COMPONENT_COLUMNS_SHORT %in% names(comp))
)
