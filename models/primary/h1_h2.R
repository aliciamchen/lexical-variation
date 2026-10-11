# H1 and H2: does Phase 2 group-specificity depend on condition? The
# preregistered game-level regression
#
#   gs_phase2 ~ condition + gs_phase1
#
# is fit by ordinary least squares with equal weight for every game whose two
# endpoints are estimable, restricted to the three conditions that share the
# Phase 1 procedure (in social_first the manipulation precedes Phase 1, so its
# Phase 1 score is an outcome rather than a baseline). The two planned
# contrasts, each a two-tailed test at alpha = .05 with support requiring the
# predicted direction, are
#
#   H1  refer_separated > refer_mixed
#   H2  social_mixed > refer_mixed
#
# Beside them: the inverse-variance rerun (each game weighted by
# 1 / SE_phase2^2, a robustness check, never the primary fit), the same
# contrasts on the content-word Jaccard estimates (the preregistered
# robustness measure), and the unadjusted game-level Cohen's d, which is the
# only number on the scale of the sampling plan's effect sizes and is not a
# second test. The per-game estimates come from group_specificity.R; nothing
# is refit here.
#
# Writes results/<dataset>/estimates/primary/h1_h2.csv (the contrasts, with
# the games in each model), primary/h1_h2_coefficients.csv (the OLS
# coefficients) and primary/h1_h2_effect_sizes.csv (Cohen's d).

source(here::here("models", "config.R"))
suppressPackageStartupMessages(library(emmeans))

gs <- gs_wide(require_estimates("primary/group_specificity", "models/primary/group_specificity.R"))

# ── Ordinary least squares and the planned contrasts ──────────────────────
h12 <- fit_h12(gs)
if (is.null(h12$model)) {
  stop(sprintf("The H1/H2 model cannot be fit: %s.", h12$note), call. = FALSE)
}
cat(sprintf("Games in the H1/H2 model: %d\n", nrow(h12$data)))
print(knitr::kable(h12$data |> count(condition, name = "games")))
print(summary(h12$model))
report_effect_sizes(h12$model)
if (is.null(h12$contrasts)) {
  stop("The planned contrasts need all three H1/H2 conditions.", call. = FALSE)
}
print(summary(h12$contrasts, infer = c(TRUE, TRUE)))
support_sentence(h12$contrasts, "H1 (refer_separated > refer_mixed)", row = 1)
support_sentence(h12$contrasts, "H2 (social_mixed > refer_mixed)", row = 2)

# The primary effect size is the adjusted difference in the contrast above,
# in group-specificity units; the unadjusted d is for comparison with the
# sampling plan only.
effect_sizes <- rbind(
  cohens_d_games(h12$data, "gs_phase2", "condition", "refer_separated", "refer_mixed"),
  cohens_d_games(h12$data, "gs_phase2", "condition", "social_mixed", "refer_mixed")
) |>
  mutate(analysis = "h1_h2", quantity = "unadjusted two-sample d (power-analysis scale)", .before = 1)
cat("\nUnadjusted game-level Cohen's d (the sampling plan's scale):\n")
print(effect_sizes)

# ── Robustness: inverse-variance weights ──────────────────────────────────
h12_wls <- fit_h12(gs, weights = "weight")
cat("\nRobustness: inverse-variance weights (1 / SE_phase2^2):\n")
print_weighted_check(h12, h12_wls)

# ── Robustness: content-word Jaccard similarity ───────────────────────────
gs_jaccard <- gs_wide(read_estimates("primary/group_specificity_jaccard"))
h12_jaccard <- if (has_rows(gs_jaccard)) fit_h12(gs_jaccard) else list(contrasts = NULL, data = tibble())
h12_jaccard_reported <- !is.null(h12_jaccard$contrasts) &&
  all(table(h12_jaccard$data$condition) >= 2)
if (h12_jaccard_reported) {
  cat(sprintf("\nH1/H2 on Jaccard similarity (%d games):\n", nrow(h12_jaccard$data)))
  print(knitr::kable(bind_rows(
    contrast_table(h12$contrasts, "primary (SBERT)"),
    contrast_table(h12_jaccard$contrasts, "Jaccard")
  ), digits = 3))
} else {
  cat("\nH1/H2 on Jaccard similarity needs at least two games per condition; skipped",
      if (!is.null(h12_jaccard$note)) paste0(" (", h12_jaccard$note, ")"), ".\n", sep = "")
}

# ── Estimates ─────────────────────────────────────────────────────────────
rows <- bind_rows(
  tidy_contrasts(h12$contrasts, "h1_h2", n_games = nrow(h12$data), measure = "sbert"),
  tidy_contrasts(h12_wls$contrasts, "h1_h2_wls", n_games = nrow(h12_wls$data), measure = "sbert"),
  if (h12_jaccard_reported) {
    tidy_contrasts(h12_jaccard$contrasts, "h1_h2_jaccard", n_games = nrow(h12_jaccard$data), measure = "jaccard")
  }
)
write_estimates(rows, "primary/h1_h2", source = "models/primary/h1_h2.R")
write_estimates(
  bind_rows(
    tidy_coefficients(h12$model, "h1_h2", n_games = nrow(h12$data)),
    tidy_coefficients(h12_wls$model, "h1_h2_wls", n_games = nrow(h12_wls$data))
  ),
  "primary/h1_h2_coefficients",
  source = "models/primary/h1_h2.R"
)
write_estimates(effect_sizes, "primary/h1_h2_effect_sizes", source = "models/primary/h1_h2.R")
