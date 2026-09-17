# Social-identification components (preregistration, "Social-identification
# components and opportunities").
#
# Overall social-identification accuracy over eligible response opportunities
# is the primary H4a outcome. These descriptive summaries break it into its
# parts, by condition: the actual in-group and out-group response
# opportunities, the on-time response rate, accuracy among on-time answers,
# the in-group hit rate (answering "same group" to an in-group speaker), the
# out-group false-alarm rate (answering "same group" to an out-group speaker),
# and balanced accuracy, the mean of the hit rate and the out-group
# correct-rejection rate. They separate the components of accuracy and show
# how the opportunity composition changes after dropout; they are not
# alternative support criteria for H4a.
#
# Input is the coded opportunity frame from social_guess_trials(): one row per
# eligible listener, with `correct` (NA for an excluded observation), `onTime`,
# and `socialGuess`.
#
# Tests: analysis/tests/test_social.R

SAME_GROUP_GUESS <- "same_group"

# Whether the speaker of each social-guess opportunity was in the guesser's
# original group. social_guesses.csv carries `speakerWasSameGroup` since
# September 2026; for an earlier export it is derived from the speaker's
# original group in trials.csv (the speaker row of the same game and round).
speaker_same_group <- function(guesses, trials = NULL) {
  if ("speakerWasSameGroup" %in% names(guesses)) {
    v <- guesses$speakerWasSameGroup
    return(ifelse(
      is.na(v),
      NA,
      v == TRUE | tolower(as.character(v)) == "true"
    ))
  }
  if (
    is.null(trials) || !all(c("speakerId", "originalGroup") %in% names(guesses))
  ) {
    stop(
      "social_guesses has no speakerWasSameGroup column; pass trials so the ",
      "speaker's original group can be looked up.",
      call. = FALSE
    )
  }
  speakers <- trials |>
    filter(role == "speaker") |>
    select(
      gameId,
      roundId,
      speakerId = playerId,
      speakerGroup = originalGroup
    ) |>
    distinct()
  joined <- guesses |>
    select(gameId, roundId, speakerId, originalGroup) |>
    left_join(speakers, by = c("gameId", "roundId", "speakerId"))
  ifelse(
    is.na(joined$speakerGroup),
    NA,
    joined$speakerGroup == joined$originalGroup
  )
}

# One row per `by` group (condition by default). Rates are over scored
# opportunities (excluded observations are counted in `excluded` and left out
# of every rate); the hit and false-alarm rates are over on-time answers, as
# the preregistration specifies. A rate with an empty denominator is NA.
social_identification_components <- function(
  guesses,
  trials = NULL,
  by = "condition"
) {
  if (!has_rows(guesses)) {
    return(tibble())
  }
  needed <- c("correct", "onTime", "socialGuess")
  missing <- setdiff(needed, names(guesses))
  if (length(missing)) {
    stop(
      "social_identification_components needs the coded opportunity frame ",
      "from social_guess_trials(); missing: ",
      paste(missing, collapse = ", "),
      call. = FALSE
    )
  }
  rate <- function(num, den) ifelse(den > 0, num / den, NA_real_)
  by <- intersect(by, names(guesses))
  guesses |>
    mutate(
      speaker_in_group = speaker_same_group(guesses, trials),
      scored = !is.na(correct),
      answered = scored & onTime %in% TRUE,
      said_same = answered & socialGuess %in% SAME_GROUP_GUESS,
      in_group = scored & speaker_in_group %in% TRUE,
      out_group = scored & speaker_in_group %in% FALSE
    ) |>
    group_by(across(all_of(by))) |>
    summarise(
      opportunities = n(),
      excluded = sum(!scored),
      scored = sum(scored),
      in_group_opportunities = sum(in_group),
      out_group_opportunities = sum(out_group),
      speaker_unknown = scored -
        in_group_opportunities -
        out_group_opportunities,
      on_time = sum(answered),
      on_time_rate = rate(on_time, scored),
      accuracy = rate(sum(correct, na.rm = TRUE), scored),
      accuracy_on_time = rate(sum(correct[answered]), on_time),
      in_group_answered = sum(answered & in_group),
      out_group_answered = sum(answered & out_group),
      hit_rate = rate(sum(said_same & in_group), in_group_answered),
      false_alarm_rate = rate(sum(said_same & out_group), out_group_answered),
      balanced_accuracy = (hit_rate + (1 - false_alarm_rate)) / 2,
      .groups = "drop"
    )
}

# The columns the data overview prints; the primary notebook prints them all.
SOCIAL_COMPONENT_COLUMNS_SHORT <- c(
  "condition",
  "in_group_opportunities",
  "out_group_opportunities",
  "on_time_rate",
  "accuracy",
  "hit_rate",
  "false_alarm_rate",
  "balanced_accuracy"
)
