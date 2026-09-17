# Tests for the exit-survey helpers in analysis/R/survey.R.

if (!exists("exit_survey_responses")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

games <- tibble(
  gameId = c("g1", "g2", "g0"),
  condition = c("social_mixed", "refer_separated", NA)
)

# Revamped survey: one completer with both pages, one removed player with page 1
# only, one player who never answered, one player in a test game
players_new <- tibble(
  gameId = c("g1", "g1", "g1", "g0"),
  playerId = c("p1", "p2", "p3", "p0"),
  originalName = c("Repi", "Minu", "Laju", "Hera"),
  originalGroup = "A",
  isActive = c(TRUE, FALSE, TRUE, TRUE),
  exitReason = c(NA, "low accuracy", NA, NA),
  exitSurvey_understood = c("yes", "yes", NA, "yes"),
  exitSurvey_groupIdentification = c("6", "3", NA, "7"),
  exitSurvey_groupCloseness = c("5", "2", NA, "7"),
  exitSurvey_groupLanguage = c("yes", "no", NA, "yes"),
  exitSurvey_strategy = c("short labels", "guessing", NA, "x"),
  exitSurvey_feltHuman = c("yes", NA, NA, "no"),
  exitSurvey_age = c("31", NA, NA, "40"),
  exitSurvey_gender = c("Female", NA, NA, "male"),
  exitSurvey_education = c("bachelor", NA, NA, "other"),
  exitSurvey_fair = c("yes", NA, NA, "yes"),
  exitSurvey_feedback = c("fun", NA, NA, "")
)
s <- exit_survey_responses(players_new, games)
check(
  "respondents are players of real games with any survey field answered, not only those with an age",
  nrow(s) == 2 && setequal(s$playerId, c("p1", "p2"))
)
check(
  "the exitSurvey_ prefix is removed and the Likert items are numeric",
  all(
    c("groupIdentification", "groupCloseness", "feltHuman", "strategy") %in%
      names(s)
  ) &&
    is.numeric(s$groupIdentification) &&
    s$groupIdentification[s$playerId == "p2"] == 3
)
check(
  "removed players are labeled as such",
  s$respondent[s$playerId == "p2"] == "removed" &&
    s$respondent[s$playerId == "p1"] == "completed"
)
check(
  "categorical answers are lower-cased",
  s$gender[s$playerId == "p1"] == "female"
)
check(
  "has_field is TRUE only for items with answers",
  has_field(s, "feltHuman") && !has_field(s, "nonexistent")
)

flags <- felt_human_flags(bind_rows(
  s,
  s |>
    mutate(
      gameId = "g2",
      condition = factor("refer_separated", levels = CONDITION_ORDER),
      feltHuman = "no",
      originalName = "Zuda"
    )
))
check(
  "felt_human_flags lists games with a no, who said it, and which groups",
  nrow(flags) == 1 &&
    flags$gameId == "g2" &&
    flags$said_no == 2 &&
    grepl("Zuda", flags$players_saying_no) &&
    flags$groups_saying_no == "A"
)
survey_groups <- bind_rows(
  s,
  s |>
    mutate(
      gameId = "g2",
      condition = factor("refer_separated", levels = CONDITION_ORDER),
      originalGroup = c("B", "C"),
      feltHuman = c("no", "yes"),
      originalName = c("Zuda", "Kemi")
    )
)
group_flags <- felt_human_flags(survey_groups, level = "group")
check(
  "felt_human_flags at the group level flags the original group that said no, not its game-mates",
  nrow(group_flags) == 1 &&
    group_flags$gameId == "g2" &&
    group_flags$originalGroup == "B" &&
    group_flags$said_no == 1 &&
    group_flags$players_saying_no == "Zuda"
)

lk <- likert_by_condition(s, "groupIdentification")
check(
  "likert_by_condition summarises per condition with a CI",
  lk$n[lk$condition == "social_mixed"] == 2 &&
    lk$mean[lk$condition == "social_mixed"] == 4.5 &&
    lk$ci_low[lk$condition == "social_mixed"] < 4.5
)

# Pilot-era survey: strategy under `strength`, no group or felt-human items
players_old <- tibble(
  gameId = "g2",
  playerId = c("q1", "q2"),
  originalName = c("Bavi", "Lika"),
  originalGroup = "B",
  isActive = TRUE,
  exitReason = NA,
  exitSurvey_age = c(25, 30),
  exitSurvey_gender = c("male", "female"),
  exitSurvey_education = "bachelor",
  exitSurvey_understood = "yes",
  exitSurvey_fair = "yes",
  exitSurvey_strength = c("describe shapes", "copy others"),
  exitSurvey_feedback = c("", "great")
)
o <- exit_survey_responses(players_old, games)
check(
  "the pilot's strength field becomes strategy",
  "strategy" %in%
    names(o) &&
    !"strength" %in% names(o) &&
    o$strategy[1] == "describe shapes"
)
check(
  "items the pilot never asked are absent",
  !has_field(o, "groupIdentification") && !has_field(o, "feltHuman")
)
check(
  "felt_human_flags is empty when the item was not asked",
  nrow(felt_human_flags(o)) == 0
)
check(
  "no survey columns gives an empty table",
  nrow(exit_survey_responses(
    players_old |> select(-starts_with("exitSurvey_")),
    games
  )) ==
    0
)
