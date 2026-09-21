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
# - BF10 is the ratio of marginal likelihoods of a full and a null model,
#   estimated by bridge sampling (bridgesampling::bf). The null removes
#   exactly the planned contrast and nothing else.
# - Game-level regressions (H1, H2, H3a): the full model is the primary
#   equal-weight OLS model refit in brms with every condition of that model
#   (three for H1/H2, two for H3a) and the same covariates, unweighted; the
#   null equates the two contrasted conditions. The outcome and continuous
#   covariates are z-scored so the condition coefficients are in SD units and
#   the Cauchy(0, sqrt(2)/2) prior on them is a prior on a standardized
#   effect (two-sided). It is placed on the condition coefficients by name;
#   the covariates are nuisance terms with a weakly informative prior.
# - Bayes factors are computed for the primary hypotheses H1, H2, H3a, H4a,
#   and H4b only; H3b, H3c, and the secondary analyses report frequentist
#   results without Bayes factors.
# - Trial-level logistic mixed models: the Cauchy prior is placed on the
#   condition coefficients only, rescaled to the log-odds scale by pi/sqrt(3)
#   so that it is the same prior on Cohen's d that the game-level models get
#   by z-scoring (see EFFECT_SIZE_PRIOR_LOGODDS). Other population-level
#   coefficients are nuisance terms with a weakly informative prior. The
#   random-effects structure is the one that converged in the frequentist
#   fit, and is kept identical in the full and null models so the BF concerns
#   the condition effect only.
# - Fits are cached as RDS files keyed by a hash of the data and formula, so
#   a changed dataset never reuses an old fit.
#
# Controlled by BAYES_FACTORS in config.R: "auto" (only when a contrast has
# p >= .05), "always", or "never" (skip, e.g. for quick renders).

# brms and bridgesampling are attached on first use, not when this file is
# sourced, so notebooks that never compute a Bayes factor do not pay for them.
.load_bf_packages <- function() {
  suppressPackageStartupMessages({
    library(brms)
    library(bridgesampling)
  })
}

bf_cache_dir <- function() file.path(derived_dir, "bayes_factors")

# The preregistered decision: compute a Bayes factor when a planned contrast
# is non-significant (or always / never, per BAYES_FACTORS). `p_values` are the
# contrast p-values, `fit` a function that returns the bf_* result. Undefined
# p-values (a saturated model, as on pilot data) are reported and skipped.
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

EFFECT_SIZE_PRIOR <- "cauchy(0, 0.7071068)" # sqrt(2)/2

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
EFFECT_SIZE_PRIOR_LOGODDS <- sprintf(
  "cauchy(0, %.7f)",
  (sqrt(2) / 2) * (pi / sqrt(3))
)

# Coefficients other than the tested contrast are nuisance terms (block
# number, and the other conditions in a three-condition model). They are not
# standardized on the logistic scale and the plan says nothing about them, so
# they get a weakly informative prior rather than the effect-size prior. They
# are identical in the full and null models, so they do not drive the Bayes
# factor; the point is not to impose an effect-size prior where no effect size
# is defined.
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

fit_bf_pair <- function(
  formula_full,
  formula_null,
  data,
  family,
  priors_full,
  priors_null,
  name,
  cache_dir,
  iter,
  warmup,
  chains,
  seed
) {
  fit <- function(f, priors, tag) {
    brm(
      f,
      data = data,
      family = family,
      prior = priors,
      save_pars = save_pars(all = TRUE),
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
        paste(name, tag, sep = "_"),
        data,
        deparse(f),
        priors,
        iter,
        seed
      ),
      file_refit = "on_change"
    )
  }
  full <- fit(formula_full, priors_full, "full")
  null <- fit(formula_null, priors_null, "null")
  ml_full <- bridge_sampler(full, silent = TRUE)
  ml_null <- bridge_sampler(null, silent = TRUE)
  bf10 <- bridgesampling::bf(ml_full, ml_null)$bf
  list(
    bf10 = bf10,
    interpretation = interpret_bf(bf10),
    full = full,
    null = null
  )
}

# Bayes factor for one planned contrast of a game-level regression, e.g. H1 in
# gs_phase2 ~ condition + gs_phase1 on the three shared-Phase-1 conditions.
#
# The full model is the primary OLS model refit in brms: all `levels` of the
# condition factor, the same covariates, every game with equal weight
# (unweighted, like the primary analysis). The null model for the contrast
# "a minus b" equates conditions a and b (their two levels are merged into
# one), keeping every other condition and covariate, so BF10 concerns exactly
# the planned contrast and nothing else in the model. With two conditions the
# merged factor has one level and the null drops condition altogether.
#
# The outcome and continuous covariates are z-scored so the condition
# coefficients are standardized, and the Cauchy(0, sqrt(2)/2) prior is placed
# on every population-level coefficient (two-sided).
#   data        game-level data frame (gs_wide() output restricted as in the
#               primary fit; rows with a missing outcome/covariate are dropped)
#   outcome     outcome column
#   condition   condition column (character or factor)
#   levels      every condition in the primary model, in factor order
#   contrast    c(a, b): the two conditions the planned contrast compares
#   covariates  continuous covariates (z-scored)
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
  d[[condition]] <- factor(d[[condition]], levels = levels)
  d[[outcome]] <- as.numeric(scale(d[[outcome]]))
  for (cv in covariates) {
    d[[cv]] <- as.numeric(scale(d[[cv]]))
  }
  # The null equates the two contrasted conditions
  merged <- paste(contrast, collapse = "_eq_")
  null_levels <- as.character(d[[condition]])
  null_levels[null_levels %in% contrast] <- merged
  # Same level order as the full model, with the merged level taking the
  # place of the first contrasted condition (so the reference level is the
  # same whenever the contrast includes it)
  d[["condition_null"]] <- factor(
    null_levels,
    levels = unique(ifelse(levels %in% contrast, merged, levels))
  )
  cov_txt <- if (length(covariates)) {
    paste(covariates, collapse = " + ")
  } else {
    NULL
  }
  f_full <- as.formula(paste(
    outcome,
    "~",
    paste(c(condition, cov_txt), collapse = " + ")
  ))
  null_terms <- c(
    if (nlevels(d[["condition_null"]]) > 1) "condition_null",
    cov_txt
  )
  f_null <- as.formula(paste(
    outcome,
    "~",
    if (length(null_terms)) paste(null_terms, collapse = " + ") else "1"
  ))
  base_priors <- c(
    set_prior("normal(0, 1)", class = "Intercept"),
    set_prior("exponential(1)", class = "sigma")
  )
  # As in the logistic case, the effect-size prior belongs to the condition
  # coefficients, which are the contrast being tested. The covariates are
  # z-scored too, so a Cauchy on them would not be on the wrong scale, but it
  # would still be an effect-size prior on a nuisance term; they get the
  # weakly informative prior instead. Both appear identically in the full and
  # null models.
  cond_prior <- function(f) {
    gp <- get_prior(f, data = d, family = gaussian())
    b <- gp[gp$class == "b" & nzchar(gp$coef), , drop = FALSE]
    cond_coefs <- b$coef[
      startsWith(b$coef, condition) |
        startsWith(b$coef, "condition_null")
    ]
    pr <- c(set_prior("normal(0, 1)", class = "b"), base_priors)
    for (cf in cond_coefs) {
      pr <- c(pr, set_prior(EFFECT_SIZE_PRIOR, class = "b", coef = cf))
    }
    pr
  }
  priors_full <- cond_prior(f_full)
  priors_null <- if (length(null_terms)) cond_prior(f_null) else base_priors
  fit_bf_pair(
    f_full,
    f_null,
    d,
    gaussian(),
    priors_full,
    priors_null,
    name,
    cache_dir,
    iter,
    warmup,
    chains,
    seed
  )
}

# Bayes factor for the condition effect in a trial-level logistic mixed
# model. `formula_full` should be the formula that converged in the
# frequentist analysis (e.g. formula(m_h4a)); the null drops the fixed effect
# of `condition` and keeps the random-effects structure.
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
  f_full <- lme4::nobars(formula_full)
  re_terms <- vapply(
    lme4::findbars(formula_full),
    function(t) paste0("(", deparse(t), ")"),
    character(1)
  )
  fixed_full <- attr(terms(f_full), "term.labels")
  fixed_null <- setdiff(fixed_full, condition)
  rhs <- function(fixed) {
    paste(c(if (length(fixed)) fixed else "1", re_terms), collapse = " + ")
  }
  lhs <- deparse(f_full[[2]])
  formula_full_b <- as.formula(sprintf("%s ~ %s", lhs, rhs(fixed_full)))
  formula_null_b <- as.formula(sprintf("%s ~ %s", lhs, rhs(fixed_null)))
  # Build priors from the classes each model actually has (a "cor" prior only
  # when there are random slopes, a "b" prior only when there are population-
  # level coefficients), so brms does not reject an unused prior.
  #
  # The effect-size prior goes on the condition coefficients alone, converted
  # to the log-odds scale (EFFECT_SIZE_PRIOR_LOGODDS); every other
  # population-level coefficient is a nuisance term and gets the weakly
  # informative prior. The default for class "b" covers any coefficient not
  # named explicitly, so a term added to the formula later cannot silently
  # inherit an effect-size prior.
  build_priors <- function(f) {
    gp <- get_prior(f, data = d, family = bernoulli())
    classes <- unique(gp$class)
    pr <- c(
      set_prior("normal(0, 1.5)", class = "Intercept"),
      set_prior("exponential(1)", class = "sd")
    )
    if ("b" %in% classes) {
      pr <- c(pr, set_prior(NUISANCE_PRIOR_LOGODDS, class = "b"))
      # The dummy columns brms builds for the condition factor, if this model
      # has the condition term at all (the null model does not).
      cond_coefs <- setdiff(
        gp$coef[gp$class == "b" & startsWith(gp$coef, condition)],
        ""
      )
      for (cf in cond_coefs) {
        pr <- c(
          pr,
          set_prior(EFFECT_SIZE_PRIOR_LOGODDS, class = "b", coef = cf)
        )
      }
    }
    if ("cor" %in% classes) {
      pr <- c(pr, set_prior("lkj(2)", class = "cor"))
    }
    pr
  }
  fit_bf_pair(
    formula_full_b,
    formula_null_b,
    d,
    bernoulli(),
    build_priors(formula_full_b),
    build_priors(formula_null_b),
    name,
    cache_dir,
    iter,
    warmup,
    chains,
    seed
  )
}

report_bf <- function(result, label) {
  cat(sprintf(
    "%s: BF10 = %s (%s)\n",
    label,
    if (is.na(result$bf10)) {
      "NA"
    } else {
      formatC(result$bf10, digits = 3, format = "g")
    },
    result$interpretation
  ))
  invisible(result)
}
