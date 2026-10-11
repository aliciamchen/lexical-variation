# H3b: do groups that anticipate the social task converge faster, and are
# they more aligned after the first speaker cycle? Two predictions, both
# social_first minus social_mixed, in separate models on the within-group
# similarity means of Phase 1 (one mean per original group, tangram and
# block, from the model_inputs step):
#
#   rate       similarity ~ condition * block + (block | group) + (block | target)
#              over blocks 2 to 6, tested as a slope contrast
#   alignment  similarity ~ condition + (1 | group) + (1 | target)
#              on block 3 alone
#
# Neither has a game term, because in Phase 1 the group is the conversing
# unit. Each requires at least two games per condition. The same two
# contrasts are then fit to the content-word Jaccard means as the
# preregistered robustness check. Details of the models are in
# models/R/convergence.R.
#
# Writes results/estimates/primary/h3b.csv: the rate and alignment
# contrasts for each measure, with whether each was supported.

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

report_h3b <- function(h3b, label) {
  if (!is.null(h3b$model)) {
    print(summary(h3b$model))
    cat(sprintf("\nConvergence rate by condition (%s; similarity per block):\n", label))
    print(emtrends(h3b$model, "condition", var = "block",
                   lmer.df = "satterthwaite", lmerTest.limit = Inf))
    cat("\nDifference in rates (social_first minus social_mixed):\n")
    print(h3b$summary)
    cat("H3b rate supported:", h3b$supported, "\n")
  } else {
    cat(sprintf("H3b rate inference skipped (%s): %s\n", label, h3b$note))
  }
  if (!is.null(h3b$block_model)) {
    print(summary(h3b$block_model))
    cat(sprintf("\nWithin-group similarity at block %d by condition (%s):\n", H3B_BLOCK, label))
    print(emmeans(h3b$block_model, "condition", lmer.df = "satterthwaite", lmerTest.limit = Inf))
    cat("\nDifference at block", H3B_BLOCK, "(social_first minus social_mixed):\n")
    print(h3b$block_summary)
    cat("H3b alignment supported:", h3b$block_supported, "\n")
  } else {
    cat(sprintf("H3b alignment inference skipped (%s): %s\n", label, h3b$block_note))
  }
}

h3b_rows <- function(h3b, measure) {
  n_games <- if (has_rows(h3b$data)) n_distinct(h3b$data$gameId) else NA_integer_
  n_block_games <- if (has_rows(h3b$block_data)) n_distinct(h3b$block_data$gameId) else NA_integer_
  bind_rows(
    tidy_contrasts(
      h3b$contrast, "h3b_rate",
      measure = measure, supported = isTRUE(h3b$supported), n_games = n_games,
      n_obs = if (has_rows(h3b$data)) nrow(h3b$data) else NA_integer_,
      random_effects = if (is.null(h3b$model)) NA_character_ else random_effects_structure(h3b$model)
    ),
    tidy_contrasts(
      h3b$block_contrast, "h3b_block3",
      measure = measure, supported = isTRUE(h3b$block_supported), n_games = n_block_games,
      n_obs = if (has_rows(h3b$block_data)) nrow(h3b$block_data) else NA_integer_,
      random_effects = if (is.null(h3b$block_model)) NA_character_ else random_effects_structure(h3b$block_model)
    )
  )
}

if (!has_rows(within_group_means)) {
  stop("within_group_block_means.csv is missing; run the model_inputs step first.", call. = FALSE)
}
cat("=== H3b on sentence-embedding similarity ===\n")
h3b <- fit_h3b(within_group_block_means(within_group_means, phase = 1, conditions = SOCIAL_CONDITIONS))
report_h3b(h3b, "SBERT")
rows <- h3b_rows(h3b, "sbert")

if (has_rows(within_group_means_jaccard)) {
  cat("\n=== H3b on content-word Jaccard similarity (robustness) ===\n")
  h3b_jaccard <- fit_h3b(within_group_block_means(within_group_means_jaccard, phase = 1, conditions = SOCIAL_CONDITIONS))
  report_h3b(h3b_jaccard, "Jaccard")
  rows <- bind_rows(rows, h3b_rows(h3b_jaccard, "jaccard"))
} else {
  cat("\nwithin_group_block_means_jaccard.csv is missing; the Jaccard robustness check is skipped.\n")
}

write_estimates(rows, "primary/h3b", source = "models/primary/h3b.R")
