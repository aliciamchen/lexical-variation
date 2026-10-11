# Secondary analysis 7 (exploratory): the H3c description properties
# (concreteness, lexical uniqueness, word frequency) across all four
# conditions, for each speaker's final description of each tangram in each
# phase, to ask whether group-specific language maintained passively
# (refer_separated) differs from language maintained under a social goal
# (social_mixed). The same structures as H3c: the two proportions at the
# content-word level with a per-description intercept, word frequency as a
# linear model, each with game, group, participant and tangram intercepts.
# The named contrast is refer_separated minus social_mixed; all pairwise
# comparisons follow, Tukey-adjusted.
#
# Writes results/<dataset>/estimates/secondary/utterance_properties.csv (the
# named contrast and the pairwise comparisons, per phase and measure) and
# secondary/utterance_properties_by_condition.csv (the marginal means).

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

PROPERTY_LABELS <- c(concreteness = "Concreteness", uniqueness = "Lexical uniqueness",
                     mean_zipf_freq = "Word frequency (Zipf)")
# The count column behind each proportion; NULL means the measure is linear.
PROPERTY_NUMERATORS <- list(concreteness = "n_concrete", uniqueness = "n_unique_words", mean_zipf_freq = NULL)

if (!has_rows(final_props)) {
  stop("final_phase_properties.csv is missing; run the model_inputs step first.", call. = FALSE)
}

rows <- tibble()
means <- tibble()
for (ph in c(1, 2)) {
  props <- final_phase_properties(final_props, phase = ph)
  if (nrow(props) == 0 || n_distinct(props$condition) < 2) {
    cat(sprintf("Phase %d: not enough conditions with data.\n", ph))
    next
  }
  for (measure in names(PROPERTY_LABELS)) {
    numerator <- PROPERTY_NUMERATORS[[measure]]
    if (is.null(numerator)) {
      d <- props |> filter(!is.na(.data[[measure]]))
      f <- as.formula(sprintf("%s ~ condition + (1 | gameId) + (1 | group) + (1 | playerId) + (1 | target)", measure))
      fam <- NULL
    } else {
      d <- word_level_measure(props, numerator, "is_target")
      f <- is_target ~ condition + (1 | gameId) + (1 | group) + (1 | playerId) + (1 | target) + (1 | descriptionId)
      fam <- binomial
    }
    if (nrow(d) == 0) next
    cat(sprintf("\n=== Phase %d: %s ===\n", ph, PROPERTY_LABELS[[measure]]))
    m <- fit_progressively(f, data = d, family = fam)
    em <- if (is.null(fam)) emmeans(m, "condition") else emmeans(m, "condition", type = "response")
    em_table <- as.data.frame(summary(em))
    print(em_table)
    means <- bind_rows(means, tibble(
      phase = ph, measure = measure, condition = as.character(em_table$condition),
      estimate = if ("prob" %in% names(em_table)) em_table$prob else em_table$emmean,
      std_error = em_table$SE,
      lower = if ("asymp.LCL" %in% names(em_table)) em_table$asymp.LCL else em_table$lower.CL,
      upper = if ("asymp.UCL" %in% names(em_table)) em_table$asymp.UCL else em_table$upper.CL,
      scale = if (is.null(fam)) "mean" else "probability"
    ))
    lv <- levels(droplevels(d$condition))
    if (all(c("refer_separated", "social_mixed") %in% lv)) {
      cat("Passive vs active maintenance (refer_separated minus social_mixed):\n")
      named <- contrast(em, list(passive_minus_active = pairwise_weights(lv, "refer_separated", "social_mixed")))
      print(summary(named, infer = c(TRUE, TRUE)))
      rows <- bind_rows(rows, tidy_contrasts(
        named, "passive_vs_active", phase = ph, measure = measure, adjustment = "none",
        n_obs = nobs(m), random_effects = random_effects_structure(m)
      ))
    }
    cat("All pairwise comparisons (Tukey):\n")
    pw <- pairs(em)
    print(summary(pw))
    rows <- bind_rows(rows, tidy_contrasts(
      pw, "pairwise", phase = ph, measure = measure, adjustment = "tukey",
      n_obs = nobs(m), random_effects = random_effects_structure(m)
    ))
  }
}
write_estimates(rows, "secondary/utterance_properties", source = "models/secondary/utterance_properties.R")
write_estimates(means, "secondary/utterance_properties_by_condition", source = "models/secondary/utterance_properties.R")
