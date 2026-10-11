# H3a: does anticipating the social-identification task shape Phase 1
# conventions? The preregistered game-level regression
#
#   gs_phase1 ~ condition
#
# by ordinary least squares, restricted to the two social conditions, with
# equal weight for every game whose Phase 1 endpoint is estimable (the Phase 2
# endpoint is not required). The planned contrast is
# social_first > social_mixed. Because the model has no covariate, the
# contrast and a two-sample comparison of the game-level estimates are the
# same test, so the unadjusted Cohen's d is the effect size of the test
# itself. Beside it: the inverse-variance rerun (weights 1 / SE_phase1^2) and
# the contrast on the content-word Jaccard estimates. The per-game estimates
# come from group_specificity.R.
#
# Writes results/estimates/primary/h3a.csv (the contrasts, with the
# games in each model), primary/h3a_coefficients.csv and
# primary/h3a_effect_sizes.csv.

source(here::here("models", "config.R"))
suppressPackageStartupMessages(library(emmeans))

gs <- gs_wide(require_estimates("primary/group_specificity", "models/primary/group_specificity.R"))

enough <- function(fit) {
  !is.null(fit$model) && !is.null(fit$contrasts) && nrow(fit$data) >= 4
}

h3a <- fit_h3a(gs)
if (!enough(h3a)) {
  stop(
    "Insufficient data for H3a (both social conditions with at least two games each): ",
    if (!is.null(h3a$note)) h3a$note else "",
    call. = FALSE
  )
}
cat(sprintf("Games in the H3a model: %d\n", nrow(h3a$data)))
print(knitr::kable(h3a$data |> count(condition, name = "games")))
print(summary(h3a$model))
report_effect_sizes(h3a$model)
print(summary(h3a$contrasts, infer = c(TRUE, TRUE)))
support_sentence(h3a$contrasts, "H3a (social_first > social_mixed)")
effect_sizes <- cohens_d_games(h3a$data, "gs_phase1", "condition", "social_first", "social_mixed") |>
  mutate(analysis = "h3a", quantity = "two-sample d (the effect size of the test)", .before = 1)
cat("\nCohen's d:\n")
print(effect_sizes)

cat("\nRobustness: inverse-variance weights (1 / SE_phase1^2):\n")
h3a_wls <- fit_h3a(gs, weights = "weight_p1")
print_weighted_check(h3a, h3a_wls)

gs_jaccard <- gs_wide(read_estimates("primary/group_specificity_jaccard"))
h3a_jaccard <- if (has_rows(gs_jaccard)) fit_h3a(gs_jaccard) else list(contrasts = NULL, data = tibble())
h3a_jaccard_reported <- !is.null(h3a_jaccard$contrasts) && nrow(h3a_jaccard$data) >= 4
if (h3a_jaccard_reported) {
  cat(sprintf("\nH3a on Jaccard similarity (%d games):\n", nrow(h3a_jaccard$data)))
  print(knitr::kable(bind_rows(
    contrast_table(h3a$contrasts, "primary (SBERT)"),
    contrast_table(h3a_jaccard$contrasts, "Jaccard")
  ), digits = 3))
} else {
  cat("\nH3a on Jaccard similarity needs both social conditions with at least two games each; skipped",
      if (!is.null(h3a_jaccard$note)) paste0(" (", h3a_jaccard$note, ")"), ".\n", sep = "")
}

rows <- bind_rows(
  tidy_contrasts(h3a$contrasts, "h3a", n_games = nrow(h3a$data), measure = "sbert"),
  tidy_contrasts(h3a_wls$contrasts, "h3a_wls", n_games = nrow(h3a_wls$data), measure = "sbert"),
  if (h3a_jaccard_reported) {
    tidy_contrasts(h3a_jaccard$contrasts, "h3a_jaccard", n_games = nrow(h3a_jaccard$data), measure = "jaccard")
  }
)
write_estimates(rows, "primary/h3a", source = "models/primary/h3a.R")
write_estimates(
  bind_rows(
    tidy_coefficients(h3a$model, "h3a", n_games = nrow(h3a$data)),
    tidy_coefficients(h3a_wls$model, "h3a_wls", n_games = nrow(h3a_wls$data))
  ),
  "primary/h3a_coefficients",
  source = "models/primary/h3a.R"
)
write_estimates(effect_sizes, "primary/h3a_effect_sizes", source = "models/primary/h3a.R")
