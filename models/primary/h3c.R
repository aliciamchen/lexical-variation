# H3c: are the final Phase 1 descriptions of groups that anticipate the
# social task less concrete, more lexically unique and made of rarer words?
# Three separate predictions, each its own two-tailed test, comparing
# social_first with social_mixed on each speaker's final Phase 1 description
# of each tangram (the model_inputs step keeps the last block per speaker and
# tangram).
#
# Concreteness and lexical uniqueness are proportions of a description's
# content words, so they are modeled at the level of the content word, one
# binary observation each, with game, group, participant, tangram and
# description intercepts (a binomial on the counts with a per-description
# intercept is the same likelihood); the effect size is the odds ratio. Word
# frequency is the mean Zipf frequency of the content words and stays a
# linear model with game, group, participant and tangram intercepts. The game
# intercept stays although Phase 1 groups never interact: condition was
# assigned at the game level, so the game is what the contrast is tested
# against. Where a fit is singular, the variance components at zero are
# named; the estimate is then that of the same model without those terms.
#
# Writes results/estimates/primary/h3c.csv: the condition
# coefficient of each of the three models (social_first minus social_mixed,
# with the odds ratio for the two logistic ones).

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
})
list2env(load_tables(), envir = globalenv())

if (!has_rows(final_props)) {
  stop("final_phase_properties.csv is missing; run the model_inputs step first.", call. = FALSE)
}
p1_final_social <- final_phase1_properties(final_props, SOCIAL_CONDITIONS)
if (nrow(p1_final_social) == 0 || n_distinct(p1_final_social$condition) < 2) {
  stop("Insufficient data for H3c (both social conditions with Phase 1 utterances).", call. = FALSE)
}

word_level_model <- function(numerator, outcome, label) {
  d <- word_level_measure(p1_final_social, numerator, outcome)
  if (nrow(d) == 0) {
    return(NULL)
  }
  cat(sprintf("\n=== %s === (%d content words in %d descriptions)\n",
              label, nrow(d), n_distinct(d$descriptionId)))
  f <- as.formula(sprintf(
    "%s ~ condition + (1 | gameId) + (1 | group) + (1 | playerId) + (1 | target) + (1 | descriptionId)",
    outcome
  ))
  m <- fit_progressively(f, data = d, family = binomial)
  print(summary(m))
  report_variance_components(m)
  report_odds_ratios(m)
  list(model = m, n_descriptions = n_distinct(d$descriptionId))
}

concrete <- word_level_model("n_concrete", "is_concrete", "Concreteness")
unique_words <- word_level_model("n_unique_words", "is_unique", "Lexical uniqueness")

p1_freq <- p1_final_social |> filter(!is.na(mean_zipf_freq))
freq <- NULL
if (nrow(p1_freq) > 0) {
  cat("\n=== Word frequency ===\n")
  m_freq <- fit_progressively(
    mean_zipf_freq ~ condition + (1 | gameId) + (1 | group) + (1 | playerId) + (1 | target),
    data = p1_freq
  )
  print(summary(m_freq))
  report_variance_components(m_freq)
  report_effect_sizes(m_freq)
  freq <- list(model = m_freq, n_descriptions = nrow(p1_freq))
}

# The reference level is social_mixed, so the coefficient is social_first
# minus social_mixed.
h3c_rows <- function(fit, analysis) {
  if (is.null(fit)) {
    return(tibble())
  }
  tidy_coefficients(
    fit$model, analysis, terms = "conditionsocial_first",
    n_descriptions = fit$n_descriptions,
    n_games = n_distinct(p1_final_social$gameId)
  )
}
rows <- bind_rows(
  h3c_rows(concrete, "h3c_concreteness"),
  h3c_rows(unique_words, "h3c_uniqueness"),
  h3c_rows(freq, "h3c_word_frequency")
)
write_estimates(rows, "primary/h3c", source = "models/primary/h3c.R")
