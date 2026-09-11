# Planned contrasts and the robustness reruns of the Phase 2 analyses.
#
# fit_h12_wls()       the preregistered H1/H2 weighted regression
#                     (gs_phase2 ~ condition + gs_phase1, weights 1/SE^2) on
#                     the three conditions that share the Phase 1 procedure,
#                     with the two planned contrasts
# contrast_table()    an emmeans contrast summary as a small labeled table
# pairwise_weights()  contrast weights for "a minus b" over a set of levels
# robustness_rerun()  refit H1/H2 and the H4 models on a subset of games and
#                     print each contrast beside the primary one; used for the
#                     complete-games and significant-Phase-1-specificity checks
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
# either way the table gets an `estimate` column.
contrast_table <- function(contrasts, label) {
  if (is.null(contrasts)) {
    return(NULL)
  }
  as.data.frame(summary(contrasts, infer = c(TRUE, TRUE))) |>
    rename(estimate = any_of(c("odds.ratio", "ratio"))) |>
    select(contrast, estimate, SE, p.value) |>
    mutate(analysis = label, .before = 1)
}

# The H1/H2 model. `gs` is a game-level table with condition, the outcome, the
# covariate, and a weight column (see gs_wide()). Returns the restricted data,
# the lm, and the planned contrasts (NULL when a condition is missing).
fit_h12_wls <- function(
  gs,
  outcome = "gs_phase2",
  covariate = "gs_phase1",
  weights = "weight"
) {
  d <- gs |>
    filter(condition %in% H12_CONDITIONS) |>
    mutate(condition = factor(as.character(condition), levels = H12_CONDITIONS))
  n_cond <- n_distinct(d$condition)
  if (n_cond < 2) {
    return(list(
      data = d,
      model = NULL,
      contrasts = NULL,
      note = sprintf("only %d H1/H2 condition(s) present", n_cond)
    ))
  }
  f <- as.formula(sprintf("%s ~ condition + %s", outcome, covariate))
  model <- lm(f, data = d, weights = d[[weights]])
  contrasts <- NULL
  if (n_cond == length(H12_CONDITIONS)) {
    contrasts <- contrast(
      emmeans(model, "condition"),
      list(
        H1_sep_vs_mixed = pairwise_weights(
          H12_CONDITIONS,
          "refer_separated",
          "refer_mixed"
        ),
        H2_social_vs_mixed = pairwise_weights(
          H12_CONDITIONS,
          "social_mixed",
          "refer_mixed"
        )
      )
    )
  }
  list(data = d, model = model, contrasts = contrasts, note = NULL)
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
# planned H1/H2 contrasts of the primary analysis (or NULL), and `h4` a list of
# specs for rerun_h4().
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
  h12 <- fit_h12_wls(sub)
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
