# Bayes factors for the primary planned contrasts, as the preregistration
# commits to them: whenever a contrast is non-significant, to distinguish
# evidence for the null from insufficient power, the model is refit in brms
# with a Cauchy(0, sqrt(2)/2) prior on the standardized effect and BF10 is
# the ratio of marginal likelihoods of the full model and the null that
# removes exactly that contrast, estimated by bridge sampling. Preregistered
# for H1, H2, H3a, H4a and H4b only. stats/R/bayes_factors.R holds the
# models and priors.
#
# The game-level fits are quick; the trial-level H4 fits took about twenty
# minutes on the full sample, so brms caches every fit in
# data/<dataset>/cache/bayes_factors/ keyed by its data and formula and a run
# on unchanged data loads them. BAYES_FACTORS controls the script: "auto"
# (the default) computes a Bayes factor for each contrast with p >= .05,
# "always" for every contrast, and "never" leaves without writing, so the
# estimates of the last real run stay in place for the formatter.
#
# A bridgesampling warning that the marginal likelihood could not be
# estimated within its iteration limit means the Bayes factor printed after
# it is unreliable; the warnings are recorded beside each result and the
# formatter refuses to write a macro for a Bayes factor that carries one.
#
# Writes results/estimates/primary/bayes_factors.csv: one row per
# hypothesis with the p-value that decided whether to compute it, BF10, its
# interpretation and any warnings.

source(here::here("stats", "config.R"))
if (BAYES_FACTORS == "never") {
  cat("BAYES_FACTORS=never: the Bayes factors are not computed and primary/bayes_factors.csv is left as it is.\n")
  quit(save = "no", status = 0)
}
suppressPackageStartupMessages({
  library(lme4)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

gs <- gs_wide(require_estimates("primary/group_specificity", "stats/primary/group_specificity.R"))
h4_estimates <- require_estimates("primary/h4", "stats/primary/h4.R")
h4_p <- function(analysis) {
  p <- h4_estimates$p_value[h4_estimates$analysis == analysis]
  if (length(p) == 0) NA_real_ else p[1]
}

rows <- tibble()
# Run one Bayes factor under the preregistered rule, with its own seed so
# bridge sampling reproduces, recording the warnings it raised.
run_bf <- function(hypothesis, contrast_label, p_value, fit) {
  warnings <- character()
  result <- NULL
  if (!is.na(p_value)) {
    set.seed(67)
    result <- withCallingHandlers(
      maybe_bayes_factor(p_value, contrast_label, fit),
      warning = function(w) {
        # Package deprecation notices are not about the estimate
        if (!grepl("has moved to the", conditionMessage(w), fixed = TRUE)) {
          warnings <<- c(warnings, conditionMessage(w))
        }
        invokeRestart("muffleWarning")
      }
    )
  } else {
    cat(sprintf("%s: contrast p-value undefined; Bayes factor skipped.\n", contrast_label))
  }
  computed <- !is.null(result) && !is.null(result$bf10) && !is.na(result$bf10)
  rows <<- bind_rows(rows, tibble(
    hypothesis = hypothesis,
    contrast = contrast_label,
    p_value = p_value,
    computed = computed,
    reason = if (computed) {
      NA_character_
    } else if (!is.na(p_value) && p_value < 0.05 && BAYES_FACTORS == "auto") {
      "contrast significant; not required under the preregistered rule"
    } else if (is.na(p_value)) {
      "contrast p-value undefined"
    } else if (!is.null(result$interpretation)) {
      result$interpretation
    } else {
      "not computed"
    },
    bf10 = if (computed) result$bf10 else NA_real_,
    interpretation = if (computed) result$interpretation else NA_character_,
    method = "bridge sampling",
    warnings = if (length(warnings)) paste(unique(warnings), collapse = " | ") else NA_character_
  ))
  invisible(result)
}

# ── H1 and H2: the three-condition OLS model refit in brms ────────────────
h12 <- fit_h12(gs)
if (!is.null(h12$contrasts)) {
  p <- as.data.frame(summary(h12$contrasts, infer = c(TRUE, TRUE)))$p.value
  run_bf("H1", "H1 refer_separated vs refer_mixed", p[1], function() {
    bf_game_level_contrast(h12$data, "gs_phase2", levels = H12_CONDITIONS,
                           contrast = c("refer_separated", "refer_mixed"),
                           covariates = "gs_phase1", name = "H1")
  })
  run_bf("H2", "H2 social_mixed vs refer_mixed", p[2], function() {
    bf_game_level_contrast(h12$data, "gs_phase2", levels = H12_CONDITIONS,
                           contrast = c("social_mixed", "refer_mixed"),
                           covariates = "gs_phase1", name = "H2")
  })
} else {
  cat("H1/H2 contrasts not available; their Bayes factors are skipped.\n")
}

# ── H3a: the two-condition OLS model refit in brms ────────────────────────
h3a <- fit_h3a(gs)
if (!is.null(h3a$contrasts) && nrow(h3a$data) >= 4) {
  p_h3a <- as.data.frame(summary(h3a$contrasts, infer = c(TRUE, TRUE)))$p.value
  run_bf("H3a", "H3a social_first vs social_mixed", p_h3a, function() {
    bf_game_level_contrast(h3a$data, "gs_phase1", levels = SOCIAL_CONDITIONS,
                           contrast = c("social_first", "social_mixed"), name = "H3a")
  })
} else {
  cat("H3a contrast not available; its Bayes factor is skipped.\n")
}

# ── H4a and H4b: the logistic models that converged, refit in brms ────────
# The null drops the fixed effect of condition and keeps the random effects.
social_h4 <- social_guess_trials(social_guesses, games, SOCIAL_CONDITIONS)
m_h4a <- load_fit("h4a", "stats/primary/h4.R")
run_bf("H4a", "H4a social_first vs social_mixed", h4_p("h4a"), function() {
  bf_glmm_condition(social_h4, formula(m_h4a), levels = SOCIAL_CONDITIONS, name = "H4a")
})
p2_listener_social <- listener_trials(trials, games, phase = 2, conditions = SOCIAL_CONDITIONS) |>
  attach_speaker()
m_h4b <- load_fit("h4b", "stats/primary/h4.R")
run_bf("H4b", "H4b social_mixed vs social_first", h4_p("h4b"), function() {
  bf_glmm_condition(p2_listener_social, formula(m_h4b), levels = SOCIAL_CONDITIONS, name = "H4b")
})

print(knitr::kable(rows |> select(hypothesis, p_value, computed, bf10, interpretation, reason), digits = 4))
if (any(!is.na(rows$warnings))) {
  cat("\nWarnings raised while computing:\n")
  for (i in which(!is.na(rows$warnings))) cat(sprintf("  %s: %s\n", rows$hypothesis[i], rows$warnings[i]))
}
write_estimates(rows, "primary/bayes_factors", source = "stats/primary/bayes_factors.R")
