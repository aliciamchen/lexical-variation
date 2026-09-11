# Exit-survey responses.
#
# The survey was revamped in 2026: page 1 asks whether the instructions were
# understood, two 7-point items on identification with and closeness to the
# Phase 1 group, whether the group developed its own way of describing the
# pictures, and the strategy; page 2 asks whether the participant felt they
# were playing with humans, plus age, gender, education, pay fairness, and
# feedback. Players removed at the Phase 1 accuracy check answer both pages
# too. The pilot predates the revamp: it has the strategy under `strength`
# and none of the group or felt-human items, so every consumer must check
# `has_field()` before using an item.
#
# Tests: analysis/tests/test_survey.R

SURVEY_FIELDS <- c(
  "understood",
  "groupIdentification",
  "groupCloseness",
  "groupLanguage",
  "strategy",
  "feltHuman",
  "age",
  "gender",
  "education",
  "fair",
  "feedback"
)

# One row per respondent (any survey field answered) in a real game, with the
# exitSurvey_ prefix removed, condition, and whether the player completed the
# game or was removed. The pilot's `strength` is folded into `strategy`.
exit_survey_responses <- function(players, games) {
  survey_cols <- grep("^exitSurvey_", names(players), value = TRUE)
  if (length(survey_cols) == 0) {
    return(tibble())
  }
  real <- games |> filter(!is.na(condition)) |> select(gameId, condition)
  df <- players |>
    inner_join(real, by = "gameId") |>
    filter(if_any(
      all_of(survey_cols),
      ~ !is.na(.x) & as.character(.x) != ""
    )) |>
    rename_with(~ str_remove(.x, "^exitSurvey_"), all_of(survey_cols)) |>
    mutate(
      condition = factor(as.character(condition), levels = CONDITION_ORDER),
      respondent = ifelse(
        isActive == TRUE | isActive == "true",
        "completed",
        "removed"
      )
    )
  if ("strength" %in% names(df)) {
    df <- df |>
      mutate(
        strategy = if ("strategy" %in% names(df)) {
          coalesce(as.character(strategy), as.character(strength))
        } else {
          as.character(strength)
        }
      ) |>
      select(-strength)
  }
  for (item in c("groupIdentification", "groupCloseness", "age")) {
    if (item %in% names(df)) {
      df[[item]] <- suppressWarnings(as.numeric(df[[item]]))
    }
  }
  for (item in c(
    "gender",
    "education",
    "understood",
    "groupLanguage",
    "feltHuman"
  )) {
    if (item %in% names(df)) {
      df[[item]] <- str_to_lower(as.character(df[[item]]))
    }
  }
  df
}

has_field <- function(survey, field) {
  field %in% names(survey) && any(!is.na(survey[[field]]))
}

# Games in which any respondent answered "no" to playing with humans; the
# preregistration flags these for detailed inspection.
felt_human_flags <- function(survey) {
  if (!has_field(survey, "feltHuman")) {
    return(tibble())
  }
  survey |>
    group_by(gameId, condition) |>
    summarise(
      respondents = sum(!is.na(feltHuman)),
      said_no = sum(feltHuman == "no", na.rm = TRUE),
      players_saying_no = paste(
        originalName[feltHuman == "no" & !is.na(feltHuman)],
        collapse = ", "
      ),
      .groups = "drop"
    ) |>
    filter(said_no > 0)
}

# Mean, SD, and a normal-approximation 95% CI of a numeric item by condition
likert_by_condition <- function(survey, item) {
  survey |>
    filter(!is.na(.data[[item]])) |>
    group_by(condition, .drop = FALSE) |>
    summarise(
      n = n(),
      mean = mean(.data[[item]]),
      sd = sd(.data[[item]]),
      ci_low = mean - 1.96 * sd / sqrt(n),
      ci_high = mean + 1.96 * sd / sqrt(n),
      .groups = "drop"
    )
}
