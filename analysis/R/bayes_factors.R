# Bayes factors for the preregistered contrasts.
#
# The analysis plan commits to Bayes factors whenever a planned contrast is
# non-significant, to distinguish evidence for the null from insufficient
# power: refit the model in brms, standardize the estimates, and place a
# Cauchy(0, sqrt(2)/2) prior on the effect size under the alternative.
# Thresholds: BF10 > 10 strong and > 3 moderate evidence for the alternative;
# BF10 < 1/10 strong and < 1/3 moderate evidence for the null; otherwise
# inconclusive.
#
# Implementation notes
# - Each contrast is tested on the two conditions it compares: the full model
#   includes `condition`, the null model drops it, and BF10 is the ratio of
#   marginal likelihoods estimated by bridge sampling (bridgesampling::bf).
# - Game-level weighted regressions: the outcome and continuous covariates
#   are z-scored so the condition coefficient is in SD units, and the
#   inverse-variance weights are rescaled to mean 1. With mean-1 weights the
#   brms weighted likelihood equals the WLS likelihood up to a constant that
#   is identical in the full and null models, so it cancels in the BF.
# - Trial-level logistic mixed models: the Cauchy prior is placed on the
#   condition log-odds coefficient; the random-effects structure is kept
#   identical in the full and null models so the BF concerns the fixed
#   effect only.
# - Fits are cached as RDS files keyed by a hash of the data and formula, so
#   a changed dataset never reuses an old fit.
#
# Controlled by BAYES_FACTORS in config.R: "auto" (only when a contrast has
# p >= .05), "always", or "never" (skip, e.g. for quick renders).

suppressPackageStartupMessages({
  library(brms)
  library(bridgesampling)
})

EFFECT_SIZE_PRIOR <- "cauchy(0, 0.7071068)"  # sqrt(2)/2

interpret_bf <- function(bf10) {
  if (is.na(bf10)) return("not computed")
  if (bf10 > 10) return("strong evidence for the alternative")
  if (bf10 > 3) return("moderate evidence for the alternative")
  if (bf10 < 1 / 10) return("strong evidence for the null")
  if (bf10 < 1 / 3) return("moderate evidence for the null")
  "inconclusive"
}

bf_cache_path <- function(cache_dir, name, ...) {
  if (is.null(cache_dir)) return(NULL)
  dir.create(cache_dir, showWarnings = FALSE, recursive = TRUE)
  file.path(cache_dir, sprintf("bf_%s_%s", name, substr(rlang::hash(list(...)), 1, 12)))
}

fit_bf_pair <- function(formula_full, formula_null, data, family, priors_full,
                        priors_null, name, cache_dir, iter, warmup, chains, seed) {
  fit <- function(f, priors, tag) {
    brm(
      f, data = data, family = family, prior = priors,
      save_pars = save_pars(all = TRUE),
      iter = iter, warmup = warmup, chains = chains, cores = min(chains, 4),
      seed = seed, refresh = 0, silent = 2,
      control = list(adapt_delta = 0.95),  # fewer divergent transitions in the hierarchical fits
      file = bf_cache_path(cache_dir, paste(name, tag, sep = "_"), data, deparse(f), priors, iter, seed),
      file_refit = "on_change"
    )
  }
  full <- fit(formula_full, priors_full, "full")
  null <- fit(formula_null, priors_null, "null")
  ml_full <- bridge_sampler(full, silent = TRUE)
  ml_null <- bridge_sampler(null, silent = TRUE)
  bf10 <- bridgesampling::bf(ml_full, ml_null)$bf
  list(bf10 = bf10, interpretation = interpret_bf(bf10), full = full, null = null)
}

# Bayes factor for a game-level weighted regression contrast between two
# conditions, e.g. gs_phase2 ~ condition + gs_phase1 weighted by 1/SE^2.
#   data       game-level data frame
#   outcome    outcome column
#   condition  condition column (character or factor)
#   levels     the two conditions compared; the second is the "treatment"
#   covariates continuous covariates (z-scored)
#   weights    column with inverse-variance weights (rescaled to mean 1)
bf_wls_contrast <- function(data, outcome, condition = "condition", levels,
                            covariates = character(), weights = NULL,
                            name = "contrast", cache_dir = NULL,
                            iter = 10000, warmup = 2000, chains = 4, seed = 67) {
  d <- data[data[[condition]] %in% levels, , drop = FALSE]
  if (nrow(d) < 4 || any(table(d[[condition]]) < 2)) {
    return(list(bf10 = NA_real_, interpretation = "not computed (fewer than two games per condition)"))
  }
  d[[condition]] <- factor(d[[condition]], levels = levels)
  d[[outcome]] <- as.numeric(scale(d[[outcome]]))
  for (cv in covariates) d[[cv]] <- as.numeric(scale(d[[cv]]))
  lhs <- outcome
  if (!is.null(weights)) {
    d[[".w"]] <- d[[weights]] / mean(d[[weights]])
    lhs <- sprintf("%s | weights(.w)", outcome)
  }
  rhs_null <- if (length(covariates)) paste(covariates, collapse = " + ") else "1"
  f_full <- as.formula(sprintf("%s ~ %s + %s", lhs, condition, rhs_null))
  f_null <- as.formula(sprintf("%s ~ %s", lhs, rhs_null))
  base_priors <- c(
    set_prior("normal(0, 1)", class = "Intercept"),
    set_prior("exponential(1)", class = "sigma")
  )
  priors_full <- c(set_prior(EFFECT_SIZE_PRIOR, class = "b"), base_priors)
  priors_null <- if (length(covariates)) c(set_prior(EFFECT_SIZE_PRIOR, class = "b"), base_priors) else base_priors
  fit_bf_pair(f_full, f_null, d, gaussian(), priors_full, priors_null,
              name, cache_dir, iter, warmup, chains, seed)
}

# Bayes factor for the condition effect in a trial-level logistic mixed
# model. `formula_full` should be the formula that converged in the
# frequentist analysis (e.g. formula(m_h4a)); the null drops the fixed effect
# of `condition` and keeps the random-effects structure.
bf_glmm_condition <- function(data, formula_full, condition = "condition",
                              levels, name = "contrast", cache_dir = NULL,
                              iter = 6000, warmup = 2000, chains = 4, seed = 67) {
  d <- data[data[[condition]] %in% levels, , drop = FALSE]
  if (nrow(d) == 0 || any(table(d[[condition]]) == 0)) {
    return(list(bf10 = NA_real_, interpretation = "not computed (a condition has no trials)"))
  }
  d[[condition]] <- factor(d[[condition]], levels = levels)
  f_full <- lme4::nobars(formula_full)
  re_terms <- vapply(lme4::findbars(formula_full), function(t) paste0("(", deparse(t), ")"), character(1))
  fixed_full <- attr(terms(f_full), "term.labels")
  fixed_null <- setdiff(fixed_full, condition)
  rhs <- function(fixed) paste(c(if (length(fixed)) fixed else "1", re_terms), collapse = " + ")
  lhs <- deparse(f_full[[2]])
  formula_full_b <- as.formula(sprintf("%s ~ %s", lhs, rhs(fixed_full)))
  formula_null_b <- as.formula(sprintf("%s ~ %s", lhs, rhs(fixed_null)))
  # Build priors from the classes each model actually has (a "cor" prior only
  # when there are random slopes, a "b" prior only when there are population-
  # level coefficients), so brms does not reject an unused prior.
  build_priors <- function(f) {
    classes <- unique(get_prior(f, data = d, family = bernoulli())$class)
    pr <- c(set_prior("normal(0, 1.5)", class = "Intercept"),
            set_prior("exponential(1)", class = "sd"))
    if ("b" %in% classes) pr <- c(pr, set_prior(EFFECT_SIZE_PRIOR, class = "b"))
    if ("cor" %in% classes) pr <- c(pr, set_prior("lkj(2)", class = "cor"))
    pr
  }
  fit_bf_pair(formula_full_b, formula_null_b, d, bernoulli(),
              build_priors(formula_full_b), build_priors(formula_null_b),
              name, cache_dir, iter, warmup, chains, seed)
}

report_bf <- function(result, label) {
  cat(sprintf("%s: BF10 = %s (%s)\n", label,
              if (is.na(result$bf10)) "NA" else formatC(result$bf10, digits = 3, format = "g"),
              result$interpretation))
  invisible(result)
}
