# Secondary analysis 1: how much does a speaker's description of a tangram
# change from the end of Phase 1 to the end of Phase 2? The outcome is the
# cosine similarity between a speaker's final Phase 1 and final Phase 2
# descriptions of the same tangram (higher means less change), modeled as
#
#   simPhase1Phase2 ~ condition + (1 | gameId) + (1 | group) + (1 | playerId)
#                               + (1 | target)
#
# with the planned contrasts refer_separated > refer_mixed and
# social_mixed > refer_mixed. The condition means average speakers who kept
# their description and speakers who adopted another one, so the share of
# speaker-tangram observations below 0.5 (the switched tail) is reported by
# condition beside the quantiles.
#
# Writes results/<dataset>/estimates/secondary/semantic_change.csv (the two
# contrasts), secondary/semantic_change_coefficients.csv and
# secondary/semantic_change_switched.csv (the distribution by condition).

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

SWITCH_THRESHOLD <- 0.5

if (!has_rows(phase_change)) {
  stop("phase_change_similarities.csv is missing; run the measures step first.", call. = FALSE)
}
phase_change <- phase_change |>
  mutate(condition = factor(condition, levels = CONDITION_ORDER)) |>
  add_group_id()

rows <- tibble()
coefficient_rows <- tibble()
if (n_distinct(phase_change$condition) >= 2) {
  m_semantic <- fit_progressively(
    simPhase1Phase2 ~ condition + (1 | gameId) + (1 | group) + (1 | playerId) + (1 | target),
    data = phase_change
  )
  print(summary(m_semantic))
  report_effect_sizes(m_semantic)
  coefficient_rows <- tidy_coefficients(m_semantic, "semantic_change", n_games = n_distinct(phase_change$gameId))
  if (all(c("refer_separated", "refer_mixed", "social_mixed") %in% phase_change$condition)) {
    lv <- levels(droplevels(phase_change$condition))
    contrasts_semantic <- contrast(emmeans(m_semantic, "condition"), list(
      sep_gt_mixed = pairwise_weights(lv, "refer_separated", "refer_mixed"),
      social_gt_mixed = pairwise_weights(lv, "social_mixed", "refer_mixed")
    ))
    cat("\nPlanned contrasts (positive = predicted direction):\n")
    print(summary(contrasts_semantic, infer = c(TRUE, TRUE)))
    rows <- tidy_contrasts(
      contrasts_semantic, "semantic_change",
      n_obs = nobs(m_semantic), n_games = n_distinct(phase_change$gameId),
      random_effects = random_effects_structure(m_semantic)
    )
  } else {
    cat("\nThe planned contrasts need refer_separated, refer_mixed and social_mixed.\n")
  }
} else {
  cat("Only one condition; the condition model is not fit.\n")
}

switched <- phase_change |>
  filter(!is.na(simPhase1Phase2)) |>
  group_by(condition, .drop = FALSE) |>
  summarise(
    n = n(),
    q10 = quantile(simPhase1Phase2, 0.10),
    median = median(simPhase1Phase2),
    q90 = quantile(simPhase1Phase2, 0.90),
    prop_switched = mean(simPhase1Phase2 < SWITCH_THRESHOLD),
    .groups = "drop"
  ) |>
  filter(n > 0) |>
  mutate(switch_threshold = SWITCH_THRESHOLD)
cat(sprintf("\nPhase 1 to Phase 2 self-similarity by condition (switched: below %.1f):\n", SWITCH_THRESHOLD))
print(knitr::kable(switched, digits = 3))

write_estimates(rows, "secondary/semantic_change", source = "models/secondary/semantic_change.R")
write_estimates(coefficient_rows, "secondary/semantic_change_coefficients", source = "models/secondary/semantic_change.R")
write_estimates(switched, "secondary/semantic_change_switched", source = "models/secondary/semantic_change.R")
