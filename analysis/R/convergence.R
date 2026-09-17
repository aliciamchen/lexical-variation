# H3b: early within-group alignment at a fixed Phase 1 milestone.
#
# The primary contrast is social_first minus social_mixed at block 3, when
# every original group member has had one scheduled turn as speaker. Time is
# categorical, so a linear trend is not imposed on the population trajectory.
# The continuous-block interaction is a separate secondary description, not
# an alternative route to primary H3b support.
#
# Block indexing. The exported `blockNum` is 0-indexed (the first block of a
# phase is 0), and block_pairwise_similarities.csv starts at 0-indexed block 1
# (the first block in which two speakers per group have described a target),
# so its Phase 1 rows are 0-indexed 1..5. The paper counts blocks from 1: the
# model uses blocks 2-6 and the milestone is block 3. The conversion happens
# once, in within_group_block_pairs() (R/prepare.R), which adds a 1-indexed
# `block` column (blockNum + 1); everything here works on that column. On the
# exported 0-indexed scale the milestone is blockNum 2.
#
# Tests: analysis/tests/test_convergence.R

H3B_BLOCK <- 3L # 1-indexed, as in the paper
H3B_BLOCKS <- 2:6 # 1-indexed Phase 1 blocks entering the model

# `block` is the categorical 1-indexed block; `block_c` the same block as a
# number, centered at the milestone (block - H3B_BLOCK), for the secondary
# linear-trend description.
H3B_FORMULA <- similarity ~ condition *
  block +
  (block | gameId) +
  (block | group) +
  (condition * block | target) +
  (1 | group_target)

H3B_TREND_FORMULA <- similarity ~ condition *
  block_c +
  (block_c | gameId) +
  (block_c | group) +
  (condition * block_c | target) +
  (1 | group_target)

# Keep the contrast construction separate so it can be checked on known
# trajectories without running the random-effects simplification each time.
h3b_block_contrast <- function(model) {
  em <- emmeans::emmeans(
    model,
    "condition",
    by = "block",
    at = list(block = as.character(H3B_BLOCK)),
    lmer.df = "satterthwaite",
    lmerTest.limit = Inf
  )
  levs <- as.character(as.data.frame(em)$condition)
  if (!setequal(levs, SOCIAL_CONDITIONS) || length(levs) != 2L) {
    stop("H3b requires exactly social_mixed and social_first.", call. = FALSE)
  }
  emmeans::contrast(
    em,
    list(
      H3b_block3_socialfirst_gt_socialmixed = pairwise_weights(
        levs,
        "social_first",
        "social_mixed"
      )
    ),
    adjust = "none"
  )
}

h3b_supported <- function(contrast_summary) {
  nrow(contrast_summary) == 1L &&
    is.finite(contrast_summary$estimate) &&
    is.finite(contrast_summary$p.value) &&
    contrast_summary$estimate > 0 &&
    contrast_summary$p.value < 0.05
}

# `block_means` comes from within_group_block_means() and carries the
# 1-indexed `block`. Require replication at the game level in both conditions
# at the actual primary milestone. Retain the full trajectory for descriptive
# plots even if inference is skipped.
fit_h3b <- function(block_means, verbose = TRUE) {
  empty <- function(d, note) {
    list(
      data = d,
      model = NULL,
      contrast = NULL,
      summary = NULL,
      supported = NA,
      note = note
    )
  }
  if (!has_rows(block_means)) {
    return(empty(tibble(), "no within-group block means"))
  }
  if (!"block" %in% names(block_means)) {
    stop(
      "fit_h3b needs the 1-indexed `block` column from within_group_block_means().",
      call. = FALSE
    )
  }
  d <- block_means |>
    filter(
      condition %in% SOCIAL_CONDITIONS,
      block %in% H3B_BLOCKS,
      is.finite(similarity)
    ) |>
    mutate(
      condition = factor(as.character(condition), levels = SOCIAL_CONDITIONS),
      block_c = block - H3B_BLOCK,
      block = factor(block, levels = H3B_BLOCKS)
    )
  at_milestone <- d |>
    filter(block == as.character(H3B_BLOCK)) |>
    distinct(condition, gameId)
  if (any(table(at_milestone$condition) < 2L)) {
    return(empty(
      d,
      sprintf(
        "fewer than two games per condition with block-%d data",
        H3B_BLOCK
      )
    ))
  }
  d$block <- droplevels(d$block)
  if (nlevels(d$block) < 2L) {
    return(empty(d, "fewer than two observed Phase 1 blocks"))
  }
  model <- fit_progressively(H3B_FORMULA, data = d, verbose = verbose)
  ct <- h3b_block_contrast(model)
  sm <- as.data.frame(summary(
    ct,
    infer = c(TRUE, TRUE),
    level = 0.95,
    adjust = "none"
  ))
  list(
    data = d,
    model = model,
    contrast = ct,
    summary = sm,
    supported = h3b_supported(sm),
    note = NULL
  )
}
