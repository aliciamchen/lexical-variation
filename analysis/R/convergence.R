# H3b: within-group convergence during Phase 1, as a rate and as a level.
#
# Two preregistered contrasts, both `social_first` minus `social_mixed`, both
# read off one fitted model and reported separately -- there is no omnibus
# support decision for H3b:
#
#   1. Rate      the condition-by-block interaction, as a slope contrast.
#   2. Alignment the condition difference at Phase 1 block 3, when every
#                original group member has had one scheduled turn as speaker,
#                as an emmeans contrast evaluated after the fit.
#
#   within_group_similarity ~ condition * block
#                             + (block | group) + (block | tangram)
#
# Block is continuous, because a rate is a slope, and it is NOT centered: the
# block-3 quantity comes from emmeans at `block = H3B_BLOCK` rather than from
# the intercept, so there is nothing for centering to buy. Centering is a pure
# reparameterization here -- it moves the `condition` coefficient but leaves
# both contrasts identical -- so the model says what it means with raw blocks
# and the `condition` row is simply not interpreted (at raw block 0 it is an
# extrapolation outside the data).
#
# Because block enters linearly, the block-3 level is a point on the fitted
# line and so is not independent of the slope. That is the accepted cost of
# the linear form; a categorical block would estimate the two separately.
#
# Both grouping factors carry a block slope: block is the effect under test
# and it varies within each of them. There is no game term -- in Phase 1 the
# three groups of a game never interact, so the group is the conversing unit
# (see the convention checks in 01_outcome_neutral.qmd for the same reasoning
# and the simulation behind it).
#
# Block indexing. The exported `blockNum` is 0-indexed (the first block of a
# phase is 0), and block_pairwise_similarities.csv starts at 0-indexed block 1
# (the first block in which two speakers per group have described a target),
# so its Phase 1 rows are 0-indexed 1..5. The paper counts blocks from 1, so
# those become 2..6. The conversion happens once, in
# within_group_block_pairs() (R/prepare.R), which adds a 1-indexed `block`
# column (blockNum + 1); everything here works on that column.
#
# Tests: analysis/tests/test_convergence.R

# Phase 1 blocks entering the model, on the paper's 1-indexed scale.
H3B_BLOCKS <- 2:6

# The alignment milestone, 1-indexed as in the paper: the end of the first
# speaker cycle. On the exported 0-indexed scale this is blockNum 2.
H3B_BLOCK <- 3L

# Raw, uncentered block. See the header on why there is no `block_c`.
H3B_FORMULA <- similarity ~ condition *
  block +
  (block | group) +
  (block | target)

# Both contrasts are built apart from the fit so they can be checked on known
# trajectories without running the random-effects simplification each time.
# `pairwise_weights` orders the weights by the levels emmeans reports, so
# neither contrast depends on the factor's level order.
h3b_levels <- function(grid) {
  levs <- as.character(as.data.frame(grid)$condition)
  if (!setequal(levs, SOCIAL_CONDITIONS) || length(levs) != 2L) {
    stop("H3b requires exactly social_mixed and social_first.", call. = FALSE)
  }
  levs
}

# Contrast 1, the rate: the social_first slope on block minus the social_mixed
# slope. Positive means faster convergence in social_first.
h3b_slope_contrast <- function(model) {
  sl <- emmeans::emtrends(
    model,
    "condition",
    var = "block",
    lmer.df = "satterthwaite",
    lmerTest.limit = Inf
  )
  levs <- h3b_levels(sl)
  emmeans::contrast(
    sl,
    list(
      H3b_slope_socialfirst_gt_socialmixed = pairwise_weights(
        levs,
        "social_first",
        "social_mixed"
      )
    ),
    adjust = "none"
  )
}

# Contrast 2, the level: the condition difference in within-group similarity
# at block H3B_BLOCK, evaluated on the fitted model. Positive means
# social_first is more closely aligned at that milestone. `at` names a value
# of the continuous predictor, which is why the model needs no centering.
h3b_block_contrast <- function(model, block = H3B_BLOCK) {
  em <- emmeans::emmeans(
    model,
    "condition",
    at = list(block = block),
    lmer.df = "satterthwaite",
    lmerTest.limit = Inf
  )
  levs <- h3b_levels(em)
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

# Support for either contrast: significant in the predicted direction. Applied
# to each of the two separately, because H3b has no omnibus decision.
h3b_supported <- function(contrast_summary) {
  nrow(contrast_summary) == 1L &&
    is.finite(contrast_summary$estimate) &&
    is.finite(contrast_summary$p.value) &&
    contrast_summary$estimate > 0 &&
    contrast_summary$p.value < 0.05
}

# `block_means` comes from within_group_block_means() and carries the
# 1-indexed `block`. Require game-level replication in both conditions before
# fitting; retain the data for descriptive plots either way.
#
# `contrast`/`summary`/`supported` are the rate; `block_contrast`/
# `block_summary`/`block_supported` are the level at H3B_BLOCK. Neither is
# privileged -- the rate keeps the unprefixed names only because the notebook
# and the macro block already read them.
fit_h3b <- function(block_means, verbose = TRUE) {
  empty <- function(d, note) {
    list(
      data = d,
      model = NULL,
      contrast = NULL,
      summary = NULL,
      supported = NA,
      block_contrast = NULL,
      block_summary = NULL,
      block_supported = NA,
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
      condition = factor(as.character(condition), levels = SOCIAL_CONDITIONS)
    )
  if (!has_rows(d)) {
    return(empty(d, "no Phase 1 within-group means in the social conditions"))
  }
  if (n_distinct(d$block) < 2L) {
    return(empty(d, "fewer than two observed Phase 1 blocks"))
  }
  games_per_condition <- d |> distinct(condition, gameId) |> count(condition)
  if (nrow(games_per_condition) < 2L || any(games_per_condition$n < 2L)) {
    return(empty(d, "fewer than two games per condition"))
  }
  model <- fit_progressively(H3B_FORMULA, data = d, verbose = verbose)
  tidy_contrast <- function(ct) {
    as.data.frame(summary(
      ct,
      infer = c(TRUE, TRUE),
      level = 0.95,
      adjust = "none"
    ))
  }
  ct <- h3b_slope_contrast(model)
  sm <- tidy_contrast(ct)
  block_ct <- h3b_block_contrast(model)
  block_sm <- tidy_contrast(block_ct)
  list(
    data = d,
    model = model,
    contrast = ct,
    summary = sm,
    supported = h3b_supported(sm),
    block_contrast = block_ct,
    block_summary = block_sm,
    block_supported = h3b_supported(block_sm),
    note = NULL
  )
}
