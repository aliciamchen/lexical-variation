# Convention-formation checks 1 to 3: over Phase 1 blocks, descriptions get
# shorter, listeners get more accurate and successive descriptions of a
# tangram grow more alike. The trend models pool the three conditions that
# share the Phase 1 procedure (refer_separated, refer_mixed, social_mixed);
# social_first is left out because its manipulation precedes Phase 1. The
# checks inform how H1 and H2 are read and gate nothing: no estimate here
# decides whether a primary analysis is run or reported.
#
# Length is log-transformed (word counts are heavy-tailed) and modeled with
# by-participant, by-group and by-tangram block slopes plus a group-by-tangram
# intercept. Accuracy is the listener-trial outcome under the
# response-opportunity rule, fit as a logistic model with a by-group block
# slope, a tangram intercept and a group-by-tangram intercept, the structure
# Boyce et al. (2024) preregistered mapped onto this design. Adjacent
# similarity has the same structure as accuracy. None of the three has a game
# term: in Phase 1 the three groups of a game never interact, so the group is
# the conversing unit and any game-level variance is absorbed into the group
# term. fit_progressively() simplifies a structure only when it does not
# converge and records the structure it kept.
#
# Writes results/estimates/checks/convention_trends.csv: the block
# coefficient of each model, with the pooled sample sizes.

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
})
list2env(load_tables(), envir = globalenv())

check_data <- convention_check_data(speaker_utts, trials, adjacent_sim, games)
p1_utts <- check_data$shared_phase1$utterances |>
  mutate(logUttLength = log(uttLength))
p1_listener <- check_data$shared_phase1$listener_trials
p1_adjacent <- check_data$shared_phase1$adjacent
cat("Pooled trend-model conditions:", paste(H12_CONDITIONS, collapse = ", "), "\n")
cat(sprintf(
  "%d games, %d Phase 1 descriptions, %d listener trials with an outcome\n",
  n_distinct(p1_utts$gameId), nrow(p1_utts), sum(!is.na(p1_listener$correct))
))

# ── 1. Description length decreases over blocks ───────────────────────────
cat("\n=== Description length ===\n")
m_length <- fit_progressively(
  logUttLength ~ blockNum_c + (blockNum_c | participant) + (blockNum_c | group) +
    (blockNum_c | tangram) + (1 | group:tangram),
  data = p1_utts |> filter(is.finite(logUttLength))
)
print(summary(m_length))
report_effect_sizes(m_length)
cat(sprintf(
  "\nBlock effect on the word scale: x%.3f per block (%.1f%% change).\n",
  exp(fixef(m_length)[["blockNum_c"]]),
  100 * (exp(fixef(m_length)[["blockNum_c"]]) - 1)
))

# ── 2. Listener accuracy increases over blocks ────────────────────────────
cat("\n=== Listener accuracy ===\n")
m_accuracy <- fit_progressively(
  correct ~ blockNum_c + (blockNum_c | group) + (1 | tangram) + (1 | group:tangram),
  data = p1_listener,
  family = binomial
)
print(summary(m_accuracy))
report_odds_ratios(m_accuracy)

# ── 3. Conventions stabilize: adjacent similarity increases ───────────────
m_adjacent <- NULL
p1_adjacent_valid <- tibble()
if (has_rows(p1_adjacent)) {
  cat("\n=== Adjacent similarity ===\n")
  p1_adjacent_valid <- p1_adjacent |> filter(!is.na(simAdjacent))
  m_adjacent <- fit_progressively(
    simAdjacent ~ blockNum_c + (blockNum_c | group) + (1 | tangram) + (1 | group:tangram),
    data = p1_adjacent_valid
  )
  print(summary(m_adjacent))
  report_effect_sizes(m_adjacent)
} else {
  cat("\nNo shared-Phase-1 adjacent similarity observations; check 3 skipped.\n")
}

# ── Estimates ─────────────────────────────────────────────────────────────
# `n_rows` is the size of the frame each model was fit to (the pooled
# descriptions, the listener trials with an outcome, the adjacent pairs);
# `n_obs` is what the fit used.
rows <- bind_rows(
  tidy_coefficients(
    m_length, "length", terms = "blockNum_c",
    n_games = n_distinct(p1_utts$gameId), n_rows = nrow(p1_utts)
  ),
  tidy_coefficients(
    m_accuracy, "accuracy", terms = "blockNum_c",
    n_games = n_distinct(p1_listener$gameId), n_rows = sum(!is.na(p1_listener$correct))
  ),
  tidy_coefficients(
    m_adjacent, "adjacent_similarity", terms = "blockNum_c",
    n_games = n_distinct(p1_adjacent_valid$gameId), n_rows = nrow(p1_adjacent_valid)
  )
)
write_estimates(rows, "checks/convention_trends", source = "models/checks/convention_trends.R")
