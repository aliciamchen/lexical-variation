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
# - BF10 compares the full model with the null that fixes exactly the planned
#   contrast at zero and changes nothing else. Because the null is nested in
#   the full model that way, the Bayes factor is the Savage-Dickey density
#   ratio: the prior density of the contrast at zero divided by its posterior
#   density at zero, both from the one fit of the full model. The prior
#   density is the Cauchy density, known exactly; the posterior density is a
#   kernel estimate from the coefficient's draws, and a normal approximation
#   to the same draws is kept beside it as a check (savage_dickey_ratio()).
# - Game-level regressions (H1, H2, H3a): the full model is the primary
#   equal-weight OLS model refit in brms with every condition of that model
#   (three for H1/H2, two for H3a) and the same covariates, unweighted. The
#   outcome and continuous covariates are z-scored. The tested difference is
#   a single coefficient with a Cauchy(0, sqrt(2)/2) prior (two-sided), in
#   outcome SD units; the intercept, the other conditions and the covariates
#   are nuisance terms with weakly informative priors.
# - Bayes factors are computed for the primary hypotheses H1, H2, H3a, H4a,
#   and H4b only; H3b, H3c, and the secondary analyses report frequentist
#   results without Bayes factors.
# - Trial-level logistic mixed models: the Cauchy prior is placed on the
#   condition coefficient only, rescaled to the log-odds scale by pi/sqrt(3)
#   to express the effect in latent logistic SD units (see
#   EFFECT_SIZE_PRIOR_LOGODDS). Other population-level coefficients are
#   nuisance terms with a weakly informative prior, and the random-effects
#   structure is the one that converged in the frequentist fit.
# - Fits are cached as RDS files keyed by a hash of the data and formula, so
#   a changed dataset never reuses an old fit.
#
# Controlled by BAYES_FACTORS in config.R: "auto" (only when a contrast has
# p >= .05), "always", or "never" (skip; stats/primary/bayes_factors.R then
# leaves its earlier estimates in place).

# brms is attached on first use, not when this file is sourced, so scripts
# that never compute a Bayes factor do not pay for it.
.load_bf_packages <- function() {
  suppressPackageStartupMessages(library(brms))
}

bf_cache_dir <- function() file.path(cache_dir, "bayes_factors")

# The preregistered decision: compute a Bayes factor when a planned contrast
# is non-significant (or always / never, per BAYES_FACTORS). `p_values` are the
# contrast p-values, `fit` a function that returns the bf_* result. Undefined
# p-values (a saturated model) are reported and skipped.
maybe_bayes_factor <- function(p_values, label, fit) {
  if (BAYES_FACTORS == "never") {
    return(invisible(NULL))
  }
  if (length(p_values) == 0 || any(is.na(p_values))) {
    cat(sprintf(
      "%s: contrast p-value undefined; Bayes factor skipped.\n",
      label
    ))
    return(invisible(NULL))
  }
  if (BAYES_FACTORS == "always" || any(p_values >= 0.05)) {
    report_bf(fit(), label)
  } else {
    cat(sprintf(
      "%s: contrast significant; Bayes factor not required.\n",
      label
    ))
    invisible(NULL)
  }
}

# The preregistered prior on the standardized effect, Cauchy(0, sqrt(2)/2),
# as the scale the density ratio needs and as the string brms takes.
EFFECT_SIZE_PRIOR_SCALE <- sqrt(2) / 2
EFFECT_SIZE_PRIOR <- sprintf("cauchy(0, %.7f)", EFFECT_SIZE_PRIOR_SCALE)

# The same prior, expressed on the log-odds scale for the logistic models.
#
# The preregistration places Cauchy(0, sqrt(2)/2) on a standardized effect
# size. For the game-level regressions that is literal: the outcome and
# covariates are z-scored, so a coefficient is already in SD units. A logistic
# model has no such scale -- its coefficient is a log odds ratio -- so putting
# the same numbers on it would be a different, and much tighter, prior than
# the one the analysis plan specifies.
#
# Under the latent-variable view of logistic regression the residual follows a
# standard logistic distribution, whose SD is pi/sqrt(3). A coefficient b on
# that latent scale therefore corresponds to d = b * sqrt(3)/pi, the usual
# conversion between a log odds ratio and Cohen's d. A Cauchy is closed under
# scaling, so a Cauchy(0, s) prior on d is exactly a Cauchy(0, s * pi/sqrt(3))
# prior on b. With s = sqrt(2)/2 that scale is 1.2825. Placing the original
# 0.7071 on the log odds instead would imply a prior on d with scale 0.39,
# roughly half as wide as intended.
EFFECT_SIZE_PRIOR_SCALE_LOGODDS <- EFFECT_SIZE_PRIOR_SCALE * pi / sqrt(3)
EFFECT_SIZE_PRIOR_LOGODDS <- sprintf("cauchy(0, %.7f)", EFFECT_SIZE_PRIOR_SCALE_LOGODDS)

# Coefficients other than the tested contrast are nuisance terms (block
# number, and the other conditions in a three-condition model). They are not
# standardized on the logistic scale and the plan says nothing about them, so
# they get a weakly informative prior rather than the effect-size prior.
# Their choice can still affect the Bayes factor, but only the tested
# contrast is fixed at zero under the null.
NUISANCE_PRIOR_LOGODDS <- "normal(0, 2.5)"

interpret_bf <- function(bf10) {
  if (is.na(bf10)) {
    return("not computed")
  }
  if (bf10 > 10) {
    return("strong evidence for the alternative")
  }
  if (bf10 > 3) {
    return("moderate evidence for the alternative")
  }
  if (bf10 < 1 / 10) {
    return("strong evidence for the null")
  }
  if (bf10 < 1 / 3) {
    return("moderate evidence for the null")
  }
  "inconclusive"
}

bf_cache_path <- function(cache_dir, name, ...) {
  if (is.null(cache_dir)) {
    return(NULL)
  }
  dir.create(cache_dir, showWarnings = FALSE, recursive = TRUE)
  file.path(
    cache_dir,
    sprintf("bf_%s_%s", name, substr(rlang::hash(list(...)), 1, 12))
  )
}

# The Savage-Dickey density ratio for posterior draws of a coefficient whose
# prior is Cauchy(0, prior_scale): BF10 is the prior density at zero over the
# posterior density at zero. The posterior density is a kernel estimate from
# the draws; a normal approximation from their mean and SD is returned beside
# it, and a warning is raised when the two disagree by more than a fifth,
# because then the draws near zero are too sparse to pin the ratio down and
# the Bayes factor should not be reported as it stands.
savage_dickey_ratio <- function(draws, prior_scale) {
  prior_at_zero <- stats::dcauchy(0, 0, prior_scale)
  kernel <- stats::density(draws, n = 8192)
  posterior_at_zero <- stats::approx(kernel$x, kernel$y, xout = 0)$y
  bf10 <- prior_at_zero / posterior_at_zero
  bf10_normal <- prior_at_zero / stats::dnorm(0, mean(draws), stats::sd(draws))
  if (is.na(bf10) || abs(bf10 - bf10_normal) > 0.2 * bf10_normal) {
    warning(sprintf(
      "the posterior density at zero is poorly determined: kernel BF10 %s, normal approximation %s",
      fmt_bf(bf10), fmt_bf(bf10_normal)
    ))
  }
  list(bf10 = bf10, bf10_normal = bf10_normal)
}

# The ratio for one coefficient of a fitted brms model, with its reading.
savage_dickey <- function(fit, coef, prior_scale) {
  draws <- as.vector(as_draws_matrix(fit, variable = paste0("b_", coef)))
  ratio <- savage_dickey_ratio(draws, prior_scale)
  c(ratio, list(interpretation = interpret_bf(ratio$bf10), fit = fit))
}

# Fit the full model in brms, or load the cached fit of the same data,
# formula and priors, and return the Savage-Dickey Bayes factor of `coef`.
fit_bf_model <- function(
  formula,
  data,
  family,
  priors,
  coef,
  prior_scale,
  name,
  cache_dir,
  iter,
  warmup,
  chains,
  seed
) {
  fit <- brm(
    formula,
    data = data,
    family = family,
    prior = priors,
    iter = iter,
    warmup = warmup,
    chains = chains,
    cores = min(chains, 4),
    seed = seed,
    refresh = 0,
    silent = 2,
    control = list(adapt_delta = 0.95), # fewer divergent transitions in the hierarchical fits
    file = bf_cache_path(
      cache_dir,
      paste(name, "full", sep = "_"),
      data,
      deparse(formula),
      priors,
      iter,
      seed
    ),
    file_refit = "on_change"
  )
  savage_dickey(fit, coef, prior_scale)
}

# Build an explicit contrast parameterization without sampling. For A minus
# B, +/- 1/2 coding makes the coefficient exactly the adjusted A-B difference.
# Other conditions are offsets from the A/B midpoint. An explicit constant
# keeps the intercept's meaning fixed whatever the two conditions' sample
# sizes.
bf_game_level_specification <- function(
  data, outcome, condition, levels, contrast, covariates = character()
) {
  stopifnot(length(contrast) == 2L, !anyDuplicated(contrast),
            all(contrast %in% levels))
  d <- data
  d[[outcome]] <- as.numeric(scale(d[[outcome]]))
  for (cv in covariates) {
    d[[cv]] <- as.numeric(scale(d[[cv]]))
  }
  d$bf_intercept <- 1
  d$bf_contrast <- ifelse(d[[condition]] == contrast[1], 0.5,
                         ifelse(d[[condition]] == contrast[2], -0.5, 0))
  other_levels <- sort(setdiff(levels, contrast))
  other_terms <- character()
  for (i in seq_along(other_levels)) {
    term <- paste0("bf_other_", i)
    d[[term]] <- as.numeric(d[[condition]] == other_levels[i])
    other_terms <- c(other_terms, term)
  }
  nuisance_terms <- c("bf_intercept", other_terms, covariates)
  nuisance_priors <- c(
    brms::set_prior("normal(0, 1)", class = "b"),
    brms::set_prior("exponential(1)", class = "sigma")
  )
  list(
    data = d,
    formula = stats::reformulate(c(nuisance_terms, "bf_contrast"),
                                 response = outcome, intercept = FALSE),
    priors = c(nuisance_priors,
               brms::set_prior(EFFECT_SIZE_PRIOR, class = "b",
                               coef = "bf_contrast")),
    coef = "bf_contrast"
  )
}

# Bayes factor for one planned contrast of a game-level regression. Retain
# all conditions of the primary model and the same covariates, with equal
# weight per game. Only the tested contrast is fixed at zero under the null.
#
# `contrast = c(a, b)` tests a minus b. The outcome and continuous covariates
# are z-scored; the Cauchy prior is on this single difference in outcome SD
# units, regardless of the condition factor's reference level.
bf_game_level_contrast <- function(
  data,
  outcome,
  condition = "condition",
  levels,
  contrast,
  covariates = character(),
  name = "contrast",
  cache_dir = bf_cache_dir(),
  iter = 10000,
  warmup = 2000,
  chains = 4,
  seed = 67
) {
  .load_bf_packages()
  stopifnot(length(contrast) == 2, all(contrast %in% levels))
  d <- data[data[[condition]] %in% levels, , drop = FALSE]
  keep <- stats::complete.cases(d[, c(outcome, covariates), drop = FALSE])
  d <- d[keep, , drop = FALSE]
  counts <- table(factor(d[[condition]], levels = levels))
  if (nrow(d) < 4 || any(counts < 2)) {
    return(list(
      bf10 = NA_real_,
      interpretation = "not computed (fewer than two games per condition)"
    ))
  }
  spec <- bf_game_level_specification(
    d, outcome, condition, levels, contrast, covariates
  )
  fit_bf_model(
    spec$formula,
    spec$data,
    gaussian(),
    spec$priors,
    spec$coef,
    EFFECT_SIZE_PRIOR_SCALE,
    name,
    cache_dir,
    iter,
    warmup,
    chains,
    seed
  )
}

# Bayes factor for the condition effect in a trial-level logistic mixed
# model with two conditions. `formula_full` should be the formula that
# converged in the frequentist analysis (e.g. formula(m_h4a)); the
# random-effects structure is kept as it is and the Bayes factor concerns
# the one condition coefficient.
bf_glmm_condition <- function(
  data,
  formula_full,
  condition = "condition",
  levels,
  name = "contrast",
  cache_dir = bf_cache_dir(),
  iter = 6000,
  warmup = 2000,
  chains = 4,
  seed = 67
) {
  .load_bf_packages()
  d <- data[data[[condition]] %in% levels, , drop = FALSE]
  if (nrow(d) == 0 || any(table(d[[condition]]) == 0)) {
    return(list(
      bf10 = NA_real_,
      interpretation = "not computed (a condition has no trials)"
    ))
  }
  d[[condition]] <- factor(d[[condition]], levels = levels)
  f_fixed <- .re_nobars(formula_full)
  re_terms <- vapply(
    .re_findbars(formula_full),
    function(t) paste0("(", deparse(t), ")"),
    character(1)
  )
  fixed <- attr(terms(f_fixed), "term.labels")
  formula_b <- as.formula(sprintf(
    "%s ~ %s", deparse(f_fixed[[2]]), paste(c(fixed, re_terms), collapse = " + ")
  ))
  # Build the priors from the classes the model actually has (a "cor" prior
  # only when there are random slopes), so brms does not reject an unused
  # prior.
  #
  # The effect-size prior goes on the condition coefficient alone, converted
  # to the log-odds scale (EFFECT_SIZE_PRIOR_LOGODDS); every other
  # population-level coefficient is a nuisance term and gets the weakly
  # informative prior. The default for class "b" covers any coefficient not
  # named explicitly, so a term added to the formula later cannot silently
  # inherit an effect-size prior.
  gp <- get_prior(formula_b, data = d, family = bernoulli())
  cond_coefs <- setdiff(gp$coef[gp$class == "b" & startsWith(gp$coef, condition)], "")
  if (length(cond_coefs) != 1) {
    stop(sprintf(
      "%s: the Savage-Dickey ratio here is for one condition coefficient; the model has %d (%s)",
      name, length(cond_coefs), paste(cond_coefs, collapse = ", ")
    ))
  }
  priors <- c(
    set_prior("normal(0, 1.5)", class = "Intercept"),
    set_prior("exponential(1)", class = "sd"),
    set_prior(NUISANCE_PRIOR_LOGODDS, class = "b"),
    set_prior(EFFECT_SIZE_PRIOR_LOGODDS, class = "b", coef = cond_coefs)
  )
  if ("cor" %in% gp$class) {
    priors <- c(priors, set_prior("lkj(2)", class = "cor"))
  }
  fit_bf_model(
    formula_b,
    d,
    bernoulli(),
    priors,
    cond_coefs,
    EFFECT_SIZE_PRIOR_SCALE_LOGODDS,
    name,
    cache_dir,
    iter,
    warmup,
    chains,
    seed
  )
}

# A Bayes factor to two significant digits and with no padding, for the
# printed report (the manuscript's macros are formatted in report/stats_tex.py
# by the same rule): 0.052, 0.18, 1.0, 3.2, 12.
fmt_bf <- function(bf10) {
  if (is.null(bf10) || length(bf10) == 0 || is.na(bf10)) {
    return("NA")
  }
  x <- signif(bf10, 2)
  if (x >= 10) {
    return(formatC(x, digits = 0, format = "f"))
  }
  if (x >= 1) {
    return(formatC(x, digits = 1, format = "f"))
  }
  if (x >= 0.1) {
    return(formatC(x, digits = 2, format = "f"))
  }
  if (x >= 0.01) {
    return(formatC(x, digits = 3, format = "f"))
  }
  trimws(formatC(x, digits = 2, format = "g"))
}

report_bf <- function(result, label) {
  cat(sprintf(
    "%s: BF10 = %s (%s)%s\n",
    label,
    fmt_bf(result$bf10),
    result$interpretation,
    if (is.null(result$bf10_normal)) "" else sprintf("; normal approximation %s", fmt_bf(result$bf10_normal))
  ))
  invisible(result)
}
