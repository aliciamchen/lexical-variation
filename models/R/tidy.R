# Tidy rows for the estimates tables.
#
# Every model script writes what it estimated in one shape, so that the
# formatter (report/inferential.py) and the figure scripts read every table the
# same way. One row is one estimated quantity:
#
#   analysis        which model or comparison the row belongs to (a short id
#                   the script chooses, such as "h1_h2" or "h1_h2_wls")
#   kind            "coefficient" (a fixed effect of a fitted model),
#                   "contrast" (an emmeans contrast) or "test" (an htest)
#   term            the coefficient, contrast or test name
#   estimate        the estimate on the reported scale (a difference, a log
#                   odds, or an odds ratio for a response-scale contrast)
#   std_error, statistic, df, lower, upper, p_value
#                   the usual companions; the interval is the 95% interval
#                   emmeans reports (Satterthwaite for lmer fits, asymptotic
#                   for glmer fits), empty for a coefficient
#   odds_ratio, or_lower, or_upper
#                   the Wald odds ratio of a logistic coefficient, empty
#                   otherwise
#   n_obs, n_games, random_effects
#                   the observations the model used, the games they came from,
#                   and the random-effects structure that converged
#
# Extra columns a script passes through `...` (a sample size, a measure
# label) are added to every row. A NULL model or contrast gives no rows, so
# a comparison the dataset cannot support contributes no estimate and, in
# turn, no macro.
#
# Tests: models/tests/test_tidy.R

is_logistic <- function(model) {
  inherits(model, "glmerMod") ||
    (inherits(model, "glm") && isTRUE(family(model)$family == "binomial"))
}

tidy_contrasts <- function(ct, analysis, ...) {
  if (is.null(ct)) {
    return(tibble())
  }
  sm <- as.data.frame(summary(ct, infer = c(TRUE, TRUE)))
  if (nrow(sm) == 0) {
    return(tibble())
  }
  pick <- function(candidates) {
    hit <- intersect(candidates, names(sm))
    if (length(hit) == 0) rep(NA_real_, nrow(sm)) else as.numeric(sm[[hit[1]]])
  }
  term <- if ("contrast" %in% names(sm)) {
    as.character(sm$contrast)
  } else {
    labels <- sm[, !vapply(sm, is.numeric, logical(1)), drop = FALSE]
    apply(labels, 1, paste, collapse = " ")
  }
  tibble(
    analysis = analysis,
    kind = "contrast",
    term = term,
    estimate = pick(c("estimate", "odds.ratio", "ratio")),
    std_error = pick("SE"),
    statistic = pick(c("t.ratio", "z.ratio")),
    df = pick("df"),
    lower = pick(c("lower.CL", "asymp.LCL")),
    upper = pick(c("upper.CL", "asymp.UCL")),
    p_value = pick("p.value"),
    ...
  )
}

# The same rows from a contrast_table() data frame (the robustness reruns
# return those rather than emmeans objects).
tidy_contrast_table <- function(tab, analysis, ...) {
  if (is.null(tab) || nrow(tab) == 0) {
    return(tibble())
  }
  tibble(
    analysis = analysis,
    kind = "contrast",
    term = as.character(tab$contrast),
    estimate = as.numeric(tab$estimate),
    std_error = as.numeric(tab$SE),
    statistic = NA_real_,
    df = NA_real_,
    lower = as.numeric(tab$lower),
    upper = as.numeric(tab$upper),
    p_value = as.numeric(tab$p.value),
    ...
  )
}

# The fixed effects of an lm, lmer (lmerTest) or glmer fit, or the ones named
# in `terms`; logistic models also get Wald odds ratios.
tidy_coefficients <- function(model, analysis, terms = NULL, ...) {
  if (is.null(model)) {
    return(tibble())
  }
  s <- as.data.frame(coef(summary(model)))
  s$term <- rownames(s)
  if (!is.null(terms)) {
    s <- s[s$term %in% terms, , drop = FALSE]
  }
  if (nrow(s) == 0) {
    return(tibble())
  }
  stat_col <- intersect(c("t value", "z value"), names(s))
  p_col <- intersect(c("Pr(>|t|)", "Pr(>|z|)"), names(s))
  out <- tibble(
    analysis = analysis,
    kind = "coefficient",
    term = s$term,
    estimate = as.numeric(s$Estimate),
    std_error = as.numeric(s[["Std. Error"]]),
    statistic = if (length(stat_col)) as.numeric(s[[stat_col[1]]]) else NA_real_,
    df = if ("df" %in% names(s)) as.numeric(s$df) else NA_real_,
    lower = NA_real_,
    upper = NA_real_,
    p_value = if (length(p_col)) as.numeric(s[[p_col[1]]]) else NA_real_,
    odds_ratio = NA_real_,
    or_lower = NA_real_,
    or_upper = NA_real_
  )
  if (is_logistic(model)) {
    or <- odds_ratio_table(model)
    idx <- match(out$term, or$term)
    out$odds_ratio <- or$odds_ratio[idx]
    out$or_lower <- or$lower[idx]
    out$or_upper <- or$upper[idx]
  }
  structure_label <- random_effects_structure(model)
  out |>
    mutate(
      n_obs = as.integer(stats::nobs(model)),
      random_effects = if (is.null(structure_label)) NA_character_ else structure_label,
      ...
    )
}

# One row for a classical test (chisq.test, fisher.test, kruskal.test):
# Fisher's exact test has a p-value only.
tidy_htest <- function(test, analysis, ...) {
  if (is.null(test)) {
    return(tibble())
  }
  tibble(
    analysis = analysis,
    kind = "test",
    term = as.character(test$method),
    estimate = NA_real_,
    std_error = NA_real_,
    statistic = if (is.null(test$statistic)) NA_real_ else unname(as.numeric(test$statistic)),
    df = if (is.null(test$parameter)) NA_integer_ else as.integer(unname(test$parameter)),
    lower = NA_real_,
    upper = NA_real_,
    p_value = as.numeric(test$p.value),
    ...
  )
}
