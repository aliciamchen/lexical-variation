# Secondary analysis 3: within the social conditions, do listeners understand
# speakers from their own original group better, and does anticipating the
# social task amplify that advantage? The preregistered trial-level model
# would need by-game and by-listener random slopes on in-group status, which
# a dozen Bernoulli trials per listener per cell cannot support (a model
# without them runs a nominal .05 test near .26 on this design). So the
# contrast is taken in its paired form: one in-group advantage score per
# listener (mean accuracy with an in-group speaker minus with an out-group
# speaker, from the model_inputs step), modeled as
#
#   advantage ~ condition + (1 | gameId)
#
# The intercept is the advantage pooled over conditions; the condition
# contrast (social_first minus social_mixed) is whether anticipation
# amplifies it. Listeners with at least five trials in each cell are the
# sensitivity rerun. The in-group and out-group accuracy rates are reported
# descriptively beside the test.
#
# Writes results/estimates/secondary/ingroup_advantage.csv (the
# pooled advantage, the amplification contrast and the sensitivity rerun) and
# secondary/ingroup_advantage_by_condition.csv (per-listener accuracy by
# condition and listener type).

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

adv <- ingroup_advantage(ingroup_adv, SOCIAL_CONDITIONS)
if (nrow(adv) < 4 || n_distinct(adv$condition) < 2) {
  stop("Too few listeners with both in-group and out-group trials for the advantage model.", call. = FALSE)
}
cat(sprintf(
  "In-group advantage scores: %d listeners in %d games (median %d in-group and %d out-group trials each)\n",
  nrow(adv), n_distinct(adv$gameId), median(adv$n_in), median(adv$n_out)
))

m_adv <- fit_progressively(advantage ~ condition + (1 | gameId), data = adv)
print(summary(m_adv))
ca <- coef(summary(m_adv))
cat(sprintf(
  "\nIn-group advantage pooled over conditions: %+.3f (SE %.3f, p = %s)\n",
  ca["(Intercept)", "Estimate"], ca["(Intercept)", "Std. Error"], fmt_pval(ca["(Intercept)", "Pr(>|t|)"])
))
cat("Does the anticipated social goal amplify it? (condition contrast)\n")
print(emmeans(m_adv, "condition"))
ct_adv <- contrast(emmeans(m_adv, "condition"), list(
  socialfirst_minus_socialmixed = pairwise_weights(SOCIAL_CONDITIONS, "social_first", "social_mixed")
))
print(summary(ct_adv, infer = c(TRUE, TRUE)))

rows <- bind_rows(
  tidy_coefficients(m_adv, "ingroup_advantage", terms = "(Intercept)",
                    n_games = n_distinct(adv$gameId), min_trials = 1L),
  tidy_contrasts(ct_adv, "ingroup_advantage_amplification",
                 n_obs = nrow(adv), n_games = n_distinct(adv$gameId), min_trials = 1L,
                 random_effects = random_effects_structure(m_adv))
)

# Thin cells are noisier; rerun on listeners with at least five trials in each.
adv5 <- ingroup_advantage(ingroup_adv, SOCIAL_CONDITIONS, min_trials = 5L)
if (nrow(adv5) >= 4 && n_distinct(adv5$condition) >= 2) {
  m_adv5 <- fit_progressively(advantage ~ condition + (1 | gameId), data = adv5, verbose = FALSE)
  cat(sprintf("\nSensitivity, cells of >= 5 trials (%d listeners): intercept %+.3f, p = %s\n",
              nrow(adv5), coef(summary(m_adv5))["(Intercept)", "Estimate"],
              fmt_pval(coef(summary(m_adv5))["(Intercept)", "Pr(>|t|)"])))
  rows <- bind_rows(rows, tidy_coefficients(
    m_adv5, "ingroup_advantage_min_five", terms = "(Intercept)",
    n_games = n_distinct(adv5$gameId), min_trials = 5L
  ))
}

by_condition <- adv |>
  tidyr::pivot_longer(c(acc_in, acc_out), names_to = "listener_type", values_to = "accuracy") |>
  mutate(listener_type = ifelse(listener_type == "acc_in", "in_group", "out_group")) |>
  group_by(condition, listener_type) |>
  summarise(listeners = dplyr::n(), accuracy = mean(accuracy), .groups = "drop")
cat("\nDescriptive accuracy by condition and listener type (per-listener means):\n")
print(knitr::kable(by_condition, digits = 3))

write_estimates(rows, "secondary/ingroup_advantage", source = "models/secondary/ingroup_advantage.R")
write_estimates(by_condition, "secondary/ingroup_advantage_by_condition", source = "models/secondary/ingroup_advantage.R")
