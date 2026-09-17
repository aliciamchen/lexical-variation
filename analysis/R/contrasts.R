# Planned contrasts and the robustness reruns of the Phase 2 analyses.
#
# The game-level regressions (H1/H2, H3a, and the secondary social-accuracy
# regression) are ordinary least squares with equal weight for each eligible
# game; inverse-variance weighting is a robustness check, never the primary
# fit (preregistration, "Analysis plan").
#
# fit_game_level()    one game-level regression: restrict to a set of
#                     conditions, drop games missing the outcome or a
#                     predictor, fit lm (OLS when `weights` is NULL, WLS when it
#                     names a weight column), and compute planned contrasts
#                     between conditions when every condition is present
# fit_h12()           the H1/H2 model gs_phase2 ~ condition + gs_phase1 on the
#                     three conditions that share the Phase 1 procedure, with
#                     the two planned contrasts
# fit_h3a()           the H3a model gs_phase1 ~ condition on the two social
#                     conditions, with the planned contrast
# contrast_table()    an emmeans contrast summary as a small labeled table
# pairwise_weights()  contrast weights for "a minus b" over a set of levels
# robustness_rerun()  refit H1/H2 and the H4 models on a subset of games and
#                     print each contrast beside the primary one; used for the
#                     complete-games and roster-size checks
#
# Tests: analysis/tests/test_contrasts.R

suppressPackageStartupMessages(library(emmeans))

pairwise_weights <- function(levels, a, b) {
  v <- setNames(rep(0, length(levels)), levels)
  v[a] <- 1
  v[b] <- -1
  unname(v)
}

# emmeans reports an odds ratio when a logistic contrast is back-transformed;
# either way the table gets an `estimate` column and a confidence interval
# (`lower`, `upper`; asymptotic for glmer fits).
contrast_table <- function(contrasts, label) {
  if (is.null(contrasts)) {
    return(NULL)
  }
  as.data.frame(summary(contrasts, infer = c(TRUE, TRUE))) |>
    rename(
      estimate = any_of(c("odds.ratio", "ratio")),
      lower = any_of(c("lower.CL", "asymp.LCL")),
      upper = any_of(c("upper.CL", "asymp.UCL"))
    ) |>
    select(contrast, estimate, SE, lower, upper, p.value) |>
    mutate(analysis = label, .before = 1)
}

# The planned contrasts of the game-level regressions, as "a minus b" pairs.
H12_CONTRASTS <- list(
  H1_sep_vs_mixed = c("refer_separated", "refer_mixed"),
  H2_social_vs_mixed = c("social_mixed", "refer_mixed")
)
H3A_CONTRASTS <- list(
  H3a_socialfirst_gt_socialmixed = c("social_first", "social_mixed")
)

# One game-level regression.
#   gs          game-level table with gameId, condition, the outcome, the
#               predictors, and (for WLS) the weight column; see gs_wide()
#   outcome     outcome column
#   predictors  character vector of additional right-hand-side terms
#               (e.g. "gs_phase1", or "gs_phase1 + activeGroupsMin")
#   conditions  the conditions the model is restricted to, in factor order
#   weights     NULL for ordinary least squares (the primary analyses), or the
#               name of a weight column for the inverse-variance robustness
#               check
#   contrasts   named list of c(a, b) pairs, each "a minus b"; computed only
#               when every condition in `conditions` is present
# Games missing the outcome, a predictor, or the weight are dropped, so a game
# whose Phase 2 endpoint is not estimable never enters the H1/H2 model.
# Returns list(data, model, contrasts, note, weights).
fit_game_level <- function(
  gs,
  outcome,
  predictors = character(),
  conditions,
  weights = NULL,
  contrasts = list()
) {
  rhs_terms <- c("condition", predictors)
  needed <- unique(c(
    outcome,
    all.vars(stats::reformulate(rhs_terms)),
    weights
  ))
  needed <- setdiff(needed, "condition")
  d <- gs |>
    filter(condition %in% conditions) |>
    mutate(condition = factor(as.character(condition), levels = conditions))
  missing_cols <- setdiff(needed, names(d))
  if (length(missing_cols)) {
    return(list(
      data = d,
      model = NULL,
      contrasts = NULL,
      note = sprintf(
        "missing column(s): %s",
        paste(missing_cols, collapse = ", ")
      ),
      weights = weights
    ))
  }
  d <- d |> filter(if_all(all_of(needed), ~ !is.na(.x)))
  n_cond <- n_distinct(d$condition)
  if (n_cond < 2) {
    return(list(
      data = d,
      model = NULL,
      contrasts = NULL,
      note = sprintf("only %d condition(s) with usable games", n_cond),
      weights = weights
    ))
  }
  f <- stats::reformulate(rhs_terms, response = outcome)
  model <- if (is.null(weights)) {
    lm(f, data = d)
  } else {
    lm(f, data = d, weights = d[[weights]])
  }
  ct <- NULL
  if (n_cond == length(conditions) && length(contrasts)) {
    ct <- contrast(
      emmeans(model, "condition"),
      lapply(contrasts, function(pair) {
        pairwise_weights(conditions, pair[1], pair[2])
      })
    )
  }
  list(data = d, model = model, contrasts = ct, note = NULL, weights = weights)
}

# The H1/H2 model. `gs` is a game-level table with condition, gs_phase2,
# gs_phase1, and (for the robustness check) the weight column (see gs_wide()).
# `covariate` is the right-hand side beyond condition, so a sensitivity
# analysis can pass "gs_phase1 + activeGroupsMin". OLS by default.
fit_h12 <- function(
  gs,
  outcome = "gs_phase2",
  covariate = "gs_phase1",
  weights = NULL
) {
  fit_game_level(
    gs,
    outcome = outcome,
    predictors = covariate,
    conditions = H12_CONDITIONS,
    weights = weights,
    contrasts = H12_CONTRASTS
  )
}

# The H3a model on the Phase 1 endpoint of the two social conditions. A game
# needs only its Phase 1 estimate here. OLS by default; weights = "weight_p1"
# is the inverse-variance robustness check.
fit_h3a <- function(
  gs,
  outcome = "gs_phase1",
  covariate = character(),
  weights = NULL
) {
  fit_game_level(
    gs,
    outcome = outcome,
    predictors = covariate,
    conditions = SOCIAL_CONDITIONS,
    weights = weights,
    contrasts = H3A_CONTRASTS
  )
}

# Print a primary fit and its weighted robustness rerun side by side.
print_weighted_check <- function(
  primary,
  weighted,
  label = "inverse-variance weights"
) {
  if (is.null(weighted$model)) {
    cat(sprintf("Weighted robustness check not fit: %s.\n", weighted$note))
    return(invisible(NULL))
  }
  print(knitr::kable(
    bind_rows(
      contrast_table(primary$contrasts, "primary (OLS)"),
      contrast_table(weighted$contrasts, label)
    ),
    digits = 3
  ))
  invisible(NULL)
}

# ── Robustness reruns ────────────────────────────────────────────────────────

H4_FORMULA <- correct ~ condition +
  blockNum_c +
  (blockNum_c | gameId) +
  (blockNum_c | playerId) +
  (blockNum_c | speakerId) +
  (condition | target)

# One H4 model on the games in `keep_games`, with its contrast next to the
# primary model's. `spec` is list(name, data, model, weights).
rerun_h4 <- function(spec, keep_games, label) {
  if (is.null(spec$data) || is.null(spec$model)) {
    cat(sprintf("%s: primary model not available; skipping.\n", spec$name))
    return(invisible(NULL))
  }
  sub <- spec$data |> filter(gameId %in% keep_games)
  if (n_distinct(sub$condition) < 2 || n_distinct(sub$gameId) < 2) {
    cat(sprintf(
      "%s: too few games under this restriction; skipping.\n",
      spec$name
    ))
    return(invisible(NULL))
  }
  m_sub <- fit_progressively(H4_FORMULA, data = sub, family = binomial)
  if (!inherits(m_sub, "glmerMod")) {
    return(invisible(NULL))
  }
  primary <- if (inherits(spec$model, "glmerMod")) {
    contrast_table(
      contrast(
        emmeans(spec$model, "condition", type = "response"),
        spec$weights
      ),
      "primary"
    )
  }
  restricted <- contrast_table(
    contrast(emmeans(m_sub, "condition", type = "response"), spec$weights),
    label
  )
  cat(sprintf(
    "\n%s on %d games (%s):\n",
    spec$name,
    n_distinct(sub$gameId),
    random_effects_structure(m_sub)
  ))
  print(knitr::kable(bind_rows(primary, restricted), digits = 3))
  invisible(m_sub)
}

# `gs` is the full game-level table (all conditions), `primary_contrasts` the
# planned H1/H2 contrasts of the primary OLS analysis (or NULL), and `h4` a
# list of specs for rerun_h4(). The H1/H2 rerun is the same equal-weight OLS
# model as the primary analysis.
robustness_rerun <- function(
  keep_games,
  label,
  gs,
  primary_contrasts = NULL,
  h4 = list()
) {
  cat(sprintf("\n=== Robustness check: %s ===\n", label))
  excluded <- gs |> filter(!gameId %in% keep_games)
  if (nrow(excluded) == 0) {
    cat(
      "No games are excluded under this restriction; the results are identical to the primary analyses.\n"
    )
    return(invisible(NULL))
  }
  cat("Excluded games by condition:\n")
  print(knitr::kable(excluded |> count(condition, name = "excluded")))

  sub <- gs |> filter(gameId %in% keep_games)
  h12 <- fit_h12(sub)
  enough <- !is.null(h12$contrasts) && all(table(h12$data$condition) >= 2)
  if (enough) {
    cat(sprintf("\nH1/H2 on %d games:\n", nrow(h12$data)))
    print(knitr::kable(
      bind_rows(
        contrast_table(primary_contrasts, "primary"),
        contrast_table(h12$contrasts, label)
      ),
      digits = 3
    ))
  } else {
    cat(
      "H1/H2: too few games per condition under this restriction; skipping.\n"
    )
  }
  for (spec in h4) {
    rerun_h4(spec, keep_games, label)
  }
  invisible(NULL)
}
