# Check the actual model specification without running Bayesian sampling.
if (!exists("bf_game_level_specification")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
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
full_matrix <- model.matrix(spec$formula_full, spec$data)
null_matrix <- model.matrix(spec$formula_null, spec$data)

check("the BF full model preserves the adjusted OLS contrast", {
  original <- lm(outcome ~ condition + baseline, data = spec$data)
  explicit <- lm(spec$formula_full, data = spec$data)
  em <- emmeans::emmeans(original, "condition")
  ct <- emmeans::contrast(em, list(H2 = pairwise_weights(
    as.character(as.data.frame(em)$condition), bf_h2[1], bf_h2[2]
  )))
  abs(coef(explicit)[["bf_contrast"]] - as.data.frame(ct)$estimate) < 1e-12 &&
    max(abs(fitted(original) - fitted(explicit))) < 1e-12
})
check("the null removes only the tested contrast, even with unequal sample sizes", {
  isTRUE(all.equal(full_matrix[, colnames(null_matrix), drop = FALSE],
                   null_matrix, check.attributes = FALSE)) &&
    identical(setdiff(colnames(full_matrix), colnames(null_matrix)), "bf_contrast")
})
check("the null equates the tested conditions and retains the third condition", {
  equal_covariates <- spec$data
  equal_covariates$baseline <- 0
  mm <- model.matrix(spec$formula_null, equal_covariates)
  a <- mm[which(equal_covariates$condition == bf_h2[1])[1], ]
  b <- mm[which(equal_covariates$condition == bf_h2[2])[1], ]
  other <- mm[which(equal_covariates$condition == "refer_separated")[1], ]
  identical(unname(a), unname(b)) && !identical(unname(a), unname(other))
})
check("the direct contrast has exactly the stated prior and all nuisance priors match", {
  full <- as.data.frame(spec$priors_full)
  null <- as.data.frame(spec$priors_null)
  target <- full$coef == "bf_contrast"
  nuisance <- full[!target, , drop = FALSE]
  rownames(nuisance) <- rownames(null) <- NULL
  sum(target) == 1L && full$prior[target] == EFFECT_SIZE_PRIOR &&
    full$class[target] == "b" && identical(nuisance, null)
})
check("condition level order cannot change the BF design or priors", {
  reordered <- bf_data
  reordered$condition <- factor(reordered$condition, levels = rev(bf_levels))
  other <- bf_game_level_specification(
    reordered, "outcome", "condition", rev(bf_levels), bf_h2, "baseline"
  )
  identical(model.matrix(other$formula_full, other$data), full_matrix) &&
    identical(other$priors_full, spec$priors_full)
})
check("reversing the contrast reverses only its coefficient column", {
  reverse <- bf_game_level_specification(
    bf_data, "outcome", "condition", bf_levels, rev(bf_h2), "baseline"
  )
  mm <- model.matrix(reverse$formula_full, reverse$data)
  identical(mm[, "bf_contrast"], -full_matrix[, "bf_contrast"]) &&
    isTRUE(all.equal(mm[, colnames(null_matrix)], null_matrix,
                     check.attributes = FALSE))
})
check("two-condition models retain a common intercept under the null", {
  d <- bf_data[bf_data$condition %in% bf_h2, ]
  two <- bf_game_level_specification(d, "outcome", "condition", bf_h2, bf_h2)
  mm <- model.matrix(two$formula_null, two$data)
  identical(colnames(mm), "bf_intercept") && all(mm == 1) &&
    !any(grepl("bf_other", names(two$data)))
})
check("brms accepts both specifications with proper priors and no centered intercept", {
  codes <- lapply(c("full", "null"), function(which) {
    brms::make_stancode(
      spec[[paste0("formula_", which)]], data = spec$data,
      family = stats::gaussian(), prior = spec[[paste0("priors_", which)]]
    )
  })
  all(vapply(codes, function(code) !grepl("real Intercept;", code, fixed = TRUE),
             logical(1))) &&
    grepl("cauchy_lpdf", codes[[1]], fixed = TRUE) &&
    !grepl("cauchy_lpdf", codes[[2]], fixed = TRUE)
})
