# Check the Bayes-factor model specification and the Savage-Dickey density
# ratio without running Bayesian sampling.
if (!exists("bf_game_level_specification")) {
  source(here::here("stats", "config.R"))
}
if (!exists("check")) {
  source(here::here("stats", "tests", "check.R"))
}

set.seed(108)
bf_data <- data.frame(
  condition = rep(c("refer_separated", "refer_mixed", "social_mixed"), c(7, 11, 9)),
  baseline = rnorm(27),
  outcome = rnorm(27)
)
bf_levels <- c("refer_separated", "refer_mixed", "social_mixed")
bf_h2 <- c("social_mixed", "refer_mixed")
spec <- bf_game_level_specification(
  bf_data, "outcome", "condition", bf_levels, bf_h2, "baseline"
)
design <- model.matrix(spec$formula, spec$data)
nuisance_columns <- setdiff(colnames(design), spec$coef)

check("the BF model preserves the adjusted OLS contrast", {
  original <- lm(outcome ~ condition + baseline, data = spec$data)
  explicit <- lm(spec$formula, data = spec$data)
  em <- emmeans::emmeans(original, "condition")
  ct <- emmeans::contrast(em, list(H2 = pairwise_weights(
    as.character(as.data.frame(em)$condition), bf_h2[1], bf_h2[2]
  )))
  abs(coef(explicit)[["bf_contrast"]] - as.data.frame(ct)$estimate) < 1e-12 &&
    max(abs(fitted(original) - fitted(explicit))) < 1e-12
})
check("the tested contrast is one named column and everything else is nuisance", {
  identical(spec$coef, "bf_contrast") &&
    identical(nuisance_columns, c("bf_intercept", "bf_other_1", "baseline"))
})
check("fixing the contrast at zero equates the tested conditions and keeps the third", {
  equal_covariates <- spec$data
  equal_covariates$baseline <- 0
  mm <- model.matrix(spec$formula, equal_covariates)[, nuisance_columns]
  a <- mm[which(equal_covariates$condition == bf_h2[1])[1], ]
  b <- mm[which(equal_covariates$condition == bf_h2[2])[1], ]
  other <- mm[which(equal_covariates$condition == "refer_separated")[1], ]
  identical(unname(a), unname(b)) && !identical(unname(a), unname(other))
})
check("the tested contrast has exactly the stated prior and the nuisance terms do not", {
  pr <- as.data.frame(spec$priors)
  target <- pr$coef == "bf_contrast"
  sum(target) == 1L && pr$prior[target] == EFFECT_SIZE_PRIOR &&
    pr$class[target] == "b" && all(pr$coef[!target] == "") &&
    !any(grepl("cauchy", pr$prior[!target], fixed = TRUE))
})
check("condition level order cannot change the BF design or priors", {
  reordered <- bf_data
  reordered$condition <- factor(reordered$condition, levels = rev(bf_levels))
  other <- bf_game_level_specification(
    reordered, "outcome", "condition", rev(bf_levels), bf_h2, "baseline"
  )
  identical(model.matrix(other$formula, other$data), design) &&
    identical(other$priors, spec$priors)
})
check("reversing the contrast reverses only its coefficient column", {
  reverse <- bf_game_level_specification(
    bf_data, "outcome", "condition", bf_levels, rev(bf_h2), "baseline"
  )
  mm <- model.matrix(reverse$formula, reverse$data)
  identical(mm[, "bf_contrast"], -design[, "bf_contrast"]) &&
    isTRUE(all.equal(mm[, nuisance_columns], design[, nuisance_columns],
                     check.attributes = FALSE))
})
check("two-condition models have a common intercept and no other-condition column", {
  d <- bf_data[bf_data$condition %in% bf_h2, ]
  two <- bf_game_level_specification(d, "outcome", "condition", bf_h2, bf_h2)
  mm <- model.matrix(two$formula, two$data)
  identical(colnames(mm), c("bf_intercept", "bf_contrast")) &&
    all(mm[, "bf_intercept"] == 1) && !any(grepl("bf_other", names(two$data)))
})
check("brms accepts the specification with proper priors and no centered intercept", {
  code <- brms::make_stancode(
    spec$formula, data = spec$data, family = stats::gaussian(), prior = spec$priors
  )
  !grepl("real Intercept;", code, fixed = TRUE) && grepl("cauchy_lpdf", code, fixed = TRUE)
})
check("a trial-level model with more than one condition coefficient is refused", {
  d <- data.frame(
    correct = rbinom(60, 1, 0.5),
    condition = rep(c("refer_mixed", "social_mixed", "social_first"), 20),
    gameId = rep(sprintf("g%d", 1:6), 10)
  )
  tryCatch(
    {
      bf_glmm_condition(d, correct ~ condition + (1 | gameId),
                        levels = unique(d$condition), cache_dir = NULL)
      FALSE
    },
    error = function(e) grepl("one condition coefficient", conditionMessage(e), fixed = TRUE)
  )
})

# ── The density ratio ─────────────────────────────────────────────────────
quietly <- function(expr) {
  warned <- character()
  value <- withCallingHandlers(expr, warning = function(w) {
    warned <<- c(warned, conditionMessage(w))
    invokeRestart("muffleWarning")
  })
  list(value = value, warnings = warned)
}
check("the Savage-Dickey ratio recovers the exact value for normal draws", {
  exact <- dcauchy(0, 0, EFFECT_SIZE_PRIOR_SCALE) / dnorm(0, 0.2, 0.5)
  r <- quietly(savage_dickey_ratio(rnorm(40000, 0.2, 0.5), EFFECT_SIZE_PRIOR_SCALE))
  length(r$warnings) == 0 &&
    abs(r$value$bf10 / exact - 1) < 0.05 && abs(r$value$bf10_normal / exact - 1) < 0.05
})
check("a posterior concentrated at zero is strong evidence for the null", {
  wide <- savage_dickey_ratio(rnorm(40000, 0, 1), EFFECT_SIZE_PRIOR_SCALE)$bf10
  narrow <- savage_dickey_ratio(rnorm(40000, 0, 0.05), EFFECT_SIZE_PRIOR_SCALE)$bf10
  narrow < wide && interpret_bf(narrow) == "strong evidence for the null" &&
    interpret_bf(wide) == "inconclusive"
})
check("a posterior the normal approximation misdescribes keeps its value but warns", {
  skewed <- exp(rnorm(40000)) - 1
  r <- quietly(savage_dickey_ratio(skewed, EFFECT_SIZE_PRIOR_SCALE))
  is.finite(r$value$bf10) && length(r$warnings) == 1 &&
    grepl("poorly determined", r$warnings, fixed = TRUE)
})
check("a posterior with no draws near zero gives no Bayes factor and warns", {
  r <- quietly(savage_dickey_ratio(rnorm(40000, 50, 0.1), EFFECT_SIZE_PRIOR_SCALE))
  is.na(r$value$bf10) && length(r$warnings) == 1 &&
    interpret_bf(r$value$bf10) == "not computed"
})
