# Secondary analysis 5: does social identification improve over Phase 2
# blocks? Social-guess opportunities of the two social conditions, modeled as
#
#   correct ~ blockNum_c + (1 | gameId) + (1 | playerId) + (1 | target)
#
# with the overall accuracy (chance is 50%) reported beside the slope.
#
# Writes results/estimates/secondary/social_accuracy_trend.csv: the
# block coefficient with the overall accuracy and the number of scored
# opportunities.

source(here::here("models", "config.R"))
suppressPackageStartupMessages(library(lme4))
list2env(load_tables(), envir = globalenv())

if (!has_rows(social_guesses)) {
  stop("No social guess data.", call. = FALSE)
}
social_guesses_model <- social_guess_trials(social_guesses, games)
if (n_distinct(social_guesses_model$gameId) < 2) {
  stop("The trend model needs at least two games.", call. = FALSE)
}
m_social_acc <- fit_progressively(
  correct ~ blockNum_c + (1 | gameId) + (1 | playerId) + (1 | target),
  data = social_guesses_model,
  family = binomial
)
print(summary(m_social_acc))
report_effect_sizes(m_social_acc)
mean_correct <- mean(social_guesses_model$correct, na.rm = TRUE)
n_scored <- sum(!is.na(social_guesses_model$correct))
cat(sprintf("\nOverall social accuracy: %.1f%% over %d scored opportunities (chance 50%%)\n",
            100 * mean_correct, n_scored))

rows <- tidy_coefficients(
  m_social_acc, "social_accuracy_trend", terms = "blockNum_c",
  n_games = n_distinct(social_guesses_model$gameId),
  outcome_mean = mean_correct, n_scored = n_scored
)
write_estimates(rows, "secondary/social_accuracy_trend", source = "models/secondary/social_accuracy_trend.R")
