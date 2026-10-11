# H4: the downstream trade-off in Phase 2 of the two social conditions. Does
# anticipating the social task buy higher social-identification accuracy
# (H4a, social_first > social_mixed) at the cost of referential accuracy
# (H4b, social_mixed > social_first)? Both outcomes are proportions of
# eligible listener response opportunities, coded by the pipeline: a correct
# answer received by the server's scoring cutoff is 1; an incorrect answer, a
# timeout and a late arrival are 0; a trial with no opportunity leaves the
# denominator; a documented technical failure is missing. Each is fit as
#
#   correct ~ condition + blockNum_c + (1 | gameId) + (1 | playerId)
#                                    + (1 | speakerId) + (1 | target)
#
# with crossed listener and speaker intercepts, and the contrast is the odds
# ratio between conditions on the response scale. Both are tested whatever H3
# showed, and neither establishes mediation through the Phase 1 measures.
# The intercepts-only structure is deliberate (models/R/contrasts.R explains
# why no block slopes).
#
# Beside the two tests, the descriptive summaries the preregistration
# promises: the response opportunities and nonresponse per condition for each
# outcome, the documented technical exclusions, and the signal-detection
# components of social identification (in-group and out-group opportunities,
# on-time rate, hit rate, false-alarm rate, balanced accuracy).
#
# Writes results/estimates/primary/h4.csv (the two contrasts),
# primary/h4_coefficients.csv, primary/h4_response_opportunities.csv and
# primary/h4_social_components.csv, and saves the two fitted models in
# data/<dataset>/cache/fits/ for robustness.R and bayes_factors.R.

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

# ── Response opportunities and nonresponse ────────────────────────────────
ref_p2 <- listener_trials(trials, games, phase = 2, conditions = SOCIAL_CONDITIONS)
social_p2 <- social_guess_trials(social_guesses, games, SOCIAL_CONDITIONS)
opportunities <- bind_rows(
  response_opportunity_summary(ref_p2) |> mutate(outcome = "referential", .before = 1),
  response_opportunity_summary(social_p2) |> mutate(outcome = "social", .before = 1)
)
cat("Response opportunities and nonresponse by condition:\n")
print(knitr::kable(opportunities, digits = 3))
write_estimates(opportunities, "primary/h4_response_opportunities", source = "models/primary/h4.R")

excl <- technical_exclusions()
if (nrow(excl) == 0) {
  cat("\nNo technical failures recorded.\n")
} else {
  cat("\nRecorded technical failures:\n")
  print(knitr::kable(excl |> count(outcome, reason, name = "observations")))
}

# ── Social-identification components ──────────────────────────────────────
if (has_rows(social_p2)) {
  social_components <- social_identification_components(social_p2, trials)
  cat("\nSignal-detection components of social identification, by condition:\n")
  print(knitr::kable(social_components, digits = 3))
  if (any(social_components$speaker_unknown > 0)) {
    cat(sprintf(
      "\n%d scored opportunit(ies) have no recorded speaker group and count in neither the in-group nor the out-group column.\n",
      sum(social_components$speaker_unknown)
    ))
  }
  write_estimates(social_components, "primary/h4_social_components", source = "models/primary/h4.R")
} else {
  cat("\nNo social-identification opportunities in the social conditions.\n")
}

# ── H4a: social-identification accuracy ───────────────────────────────────
rows <- tibble()
coefficient_rows <- tibble()
if (has_rows(social_p2) && n_distinct(social_p2$condition) >= 2) {
  cat("\n=== H4a: social-identification accuracy ===\n")
  m_h4a <- fit_progressively(H4_FORMULA, data = social_p2, family = binomial)
  print(summary(m_h4a))
  report_effect_sizes(m_h4a)
  if (inherits(m_h4a, "glmerMod")) {
    contrast_h4a <- contrast(
      emmeans(m_h4a, "condition", type = "response"),
      list(H4a_socialfirst_gt_socialmixed = c(-1, 1))
    )
    print(summary(contrast_h4a, infer = c(TRUE, TRUE)))
    support_sentence(contrast_h4a, "H4a (social_first > social_mixed)", null = 1)
    save_fit(m_h4a, "h4a")
    rows <- bind_rows(rows, tidy_contrasts(
      contrast_h4a, "h4a", scale = "odds_ratio",
      n_obs = nobs(m_h4a), n_games = n_distinct(social_p2$gameId),
      random_effects = random_effects_structure(m_h4a)
    ))
    coefficient_rows <- bind_rows(coefficient_rows, tidy_coefficients(m_h4a, "h4a"))
  }
} else {
  cat("\nInsufficient data for H4a (need both social conditions).\n")
}

# ── H4b: referential accuracy ─────────────────────────────────────────────
p2_listener_social <- ref_p2 |> attach_speaker()
if (nrow(p2_listener_social) > 0 && n_distinct(p2_listener_social$condition) >= 2) {
  cat("\n=== H4b: referential accuracy ===\n")
  m_h4b <- fit_progressively(H4_FORMULA, data = p2_listener_social, family = binomial)
  print(summary(m_h4b))
  report_effect_sizes(m_h4b)
  if (inherits(m_h4b, "glmerMod")) {
    contrast_h4b <- contrast(
      emmeans(m_h4b, "condition", type = "response"),
      list(H4b_socialmixed_gt_socialfirst = c(1, -1))
    )
    print(summary(contrast_h4b, infer = c(TRUE, TRUE)))
    support_sentence(contrast_h4b, "H4b (social_mixed > social_first)", null = 1)
    save_fit(m_h4b, "h4b")
    rows <- bind_rows(rows, tidy_contrasts(
      contrast_h4b, "h4b", scale = "odds_ratio",
      n_obs = nobs(m_h4b), n_games = n_distinct(p2_listener_social$gameId),
      random_effects = random_effects_structure(m_h4b)
    ))
    coefficient_rows <- bind_rows(coefficient_rows, tidy_coefficients(m_h4b, "h4b"))
  }
} else {
  cat("\nInsufficient data for H4b (need both social conditions with Phase 2 listener trials).\n")
}

write_estimates(rows, "primary/h4", source = "models/primary/h4.R")
write_estimates(coefficient_rows, "primary/h4_coefficients", source = "models/primary/h4.R")
