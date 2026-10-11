# Secondary analysis 6: how description length evolves over Phase 2 blocks by
# condition. The preregistration names the outcome but gives no Phase 2
# formula, so the model mirrors the Phase 1 length check with condition added:
#
#   log(uttLength) ~ condition * blockNum_c + (blockNum_c | gameId) + (1 | group)
#                  + (1 | playerId) + (blockNum_c | target) + (1 | group:target)
#
# with a by-game block slope because once mixing starts the game is the
# interacting population. Slopes and marginal means are back-transformed to
# the word scale for reporting.
#
# Writes results/<dataset>/estimates/secondary/phase2_length.csv (the block
# coefficient), secondary/phase2_length_coefficients.csv and
# secondary/phase2_length_by_condition.csv (each condition's slope and mean
# length at the mean block).

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

p2_utts <- phase2_utterances(speaker_utts, games) |>
  mutate(logUttLength = log(uttLength)) |>
  filter(is.finite(logUttLength))
n_cond <- n_distinct(p2_utts$condition)
if (n_cond < 2) {
  stop("The Phase 2 length model needs at least two conditions.", call. = FALSE)
}
m_p2_length <- fit_progressively(
  logUttLength ~ condition * blockNum_c + (blockNum_c | gameId) + (1 | group) + (1 | playerId) +
    (blockNum_c | target) + (1 | group:target),
  data = p2_utts
)
print(summary(m_p2_length))
report_effect_sizes(m_p2_length)

by_condition <- tibble()
if (inherits(m_p2_length, "merMod")) {
  cat("\nBlock slope by condition (log scale, and as a multiplier per block):\n")
  slopes <- as.data.frame(test(emtrends(m_p2_length, ~ condition, var = "blockNum_c")))
  slopes$per_block_multiplier <- exp(slopes$blockNum_c.trend)
  print(slopes)
  # The outcome is a precomputed log, which emmeans cannot back-transform
  # itself, so the marginal means are exponentiated here.
  # Above emmeans's lmerTest.limit the intervals are asymptotic and carry
  # the asymp.* names.
  means <- as.data.frame(summary(emmeans(m_p2_length, "condition")))
  lower_col <- intersect(c("lower.CL", "asymp.LCL"), names(means))[1]
  upper_col <- intersect(c("upper.CL", "asymp.UCL"), names(means))[1]
  means <- means |>
    mutate(mean_words = exp(emmean), words_lower = exp(.data[[lower_col]]), words_upper = exp(.data[[upper_col]]))
  cat("\nMean Phase 2 description length by condition, in words (at the mean block):\n")
  print(means |> select(condition, mean_words, words_lower, words_upper))
  by_condition <- slopes |>
    transmute(condition = as.character(condition), slope_log = blockNum_c.trend, slope_se = SE,
              slope_p = p.value, per_block_multiplier) |>
    left_join(
      means |> transmute(condition = as.character(condition), mean_log = emmean, mean_words, words_lower, words_upper),
      by = "condition"
    )
}

write_estimates(
  tidy_coefficients(m_p2_length, "phase2_length", terms = "blockNum_c", n_games = n_distinct(p2_utts$gameId)),
  "secondary/phase2_length", source = "models/secondary/phase2_length.R"
)
write_estimates(
  tidy_coefficients(m_p2_length, "phase2_length", n_games = n_distinct(p2_utts$gameId)),
  "secondary/phase2_length_coefficients", source = "models/secondary/phase2_length.R"
)
write_estimates(by_condition, "secondary/phase2_length_by_condition", source = "models/secondary/phase2_length.R")
