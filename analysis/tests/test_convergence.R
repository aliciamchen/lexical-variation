# Tests for H3b: block indexing, aggregation, and the convergence-rate
# support criterion.

if (!exists("fit_h3b")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

set.seed(31)

check(
  "H3b spans 1-indexed Phase 1 blocks 2-6",
  identical(H3B_BLOCKS, 2:6)
)

# ── Aggregation and block indexing ──────────────────────────────────────────
# The exported blockNum is 0-indexed; the paper counts from 1.
games_h3b <- tibble(
  gameId = c("g1", "g2", "g3"),
  condition = c("social_mixed", "social_first", "refer_mixed")
)
pairs_h3b <- tibble(
  gameId = c("g1", "g1", "g1", "g1", "g1", "g2", "g3", "g1", "g1"),
  group1 = "A",
  group2 = c("A", "A", "A", "A", "B", "A", "A", "A", "A"),
  target = "t1",
  blockNum = c(1, 2, 2, 2, 2, 2, 2, 2, 3),
  phaseNum = c(1, 1, 1, 1, 1, 1, 1, 2, 1),
  sameGroup = c(1, 1, 1, 1, 0, 1, 1, 1, 1),
  similarity = c(0.2, 0.4, 0.8, NA, 0.1, 0.9, 0.6, 0.7, 0.95)
)
means_h3b <- within_group_block_means(pairs_h3b, games_h3b)
check(
  "H3b aggregates only Phase 1 within-group pairs in the two social conditions",
  nrow(means_h3b) == 4L && all(means_h3b$gameId %in% c("g1", "g2"))
)
check(
  "the 1-indexed block is the exported blockNum plus one",
  all(means_h3b$block == means_h3b$blockNum + 1L) &&
    setequal(means_h3b$block[means_h3b$gameId == "g1"], c(2L, 3L, 4L))
)
check("overlapping within-group pairs give one finite mean per group-tangram-block", {
  g1b3 <- means_h3b |> filter(gameId == "g1", block == 3L)
  nrow(g1b3) == 1L && abs(g1b3$similarity - 0.6) < 1e-12
})
check(
  "fit_h3b refuses a frame without the 1-indexed block column",
  inherits(
    try(fit_h3b(means_h3b |> select(-block), verbose = FALSE), silent = TRUE),
    "try-error"
  )
)

# compute_derived.py keeps the rows the specificity start rule excludes -- the
# first block of a phase, and later cells where one group has a single
# describer -- so the descriptive within-vs-between panel can plot them, and
# flags them `allGroupsPaired = 0`. The H3b aggregation must not pick them up.
flagged_h3b <- pairs_h3b |>
  mutate(allGroupsPaired = if_else(blockNum == 2, 0, 1))
check(
  "within-group block means drop the rows the start rule excludes",
  {
    m <- within_group_block_means(flagged_h3b, games_h3b)
    nrow(m) > 0L && !any(m$blockNum == 2)
  }
)
check(
  "a table written before the flag existed is eligible throughout",
  nrow(within_group_block_means(pairs_h3b, games_h3b)) == nrow(means_h3b)
)

exported_scale <- expand_grid(
  gameId = c("g1", "g2"),
  blockNum = 1:5,
  pair = 1:2
) |>
  mutate(
    group1 = "A",
    group2 = "A",
    target = "t1",
    phaseNum = 1,
    sameGroup = 1,
    similarity = 0.5
  )
exported_means <- within_group_block_means(exported_scale, games_h3b)
check(
  "exported 0-indexed blockNum 1..5 maps onto the paper's blocks 2..6",
  setequal(unique(exported_means$block), 2:6)
)

# ── The model structure ─────────────────────────────────────────────────────
bars_h3b <- .re_findbars(H3B_FORMULA)
check(
  "H3b carries by-block slopes on group and tangram, and no game term",
  setequal(
    vapply(bars_h3b, function(x) deparse(x[[3]]), character(1)),
    c("group", "target")
  ) &&
    all(vapply(
      bars_h3b,
      function(x) grepl("block", deparse(x[[2]]), fixed = TRUE),
      logical(1)
    ))
)
check(
  "H3b models a rate: block enters continuously and interacts with condition",
  "block" %in%
    all.vars(H3B_FORMULA) &&
    any(grepl(
      "condition:block|block:condition",
      attr(terms(lme4::nobars(H3B_FORMULA)), "term.labels")
    ))
)
check(
  "block enters raw, so no centered copy is fitted",
  !any(grepl("block_c", all.vars(H3B_FORMULA), fixed = TRUE))
)
check(
  "the alignment milestone is 1-indexed block 3, inside the fitted window",
  H3B_BLOCK == 3L && H3B_BLOCK %in% H3B_BLOCKS
)

# ── The two contrasts ───────────────────────────────────────────────────────
# Known population: social_first rises at 0.10/block from an intercept of 0.4,
# social_mixed at 0.04 from the same intercept, block entering raw. So the
# slope contrast must recover +0.06, and the block-3 contrast must recover the
# difference in fitted levels there, 3 * (0.10 - 0.04) = +0.18.
d_h3b <- expand_grid(
  condition = SOCIAL_CONDITIONS,
  block = 2:6,
  rep = 1:30
) |>
  mutate(
    condition = factor(condition, levels = SOCIAL_CONDITIONS),
    similarity = 0.4 +
      ifelse(condition == "social_first", 0.10, 0.04) * block +
      rnorm(n(), sd = 0.02)
  )
m_h3b_lm <- lm(similarity ~ condition * block, data = d_h3b)
sm_h3b <- as.data.frame(summary(
  h3b_slope_contrast(m_h3b_lm),
  infer = c(TRUE, TRUE)
))
check(
  "the contrast is the social-first minus social-mixed difference in slopes",
  nrow(sm_h3b) == 1L &&
    abs(sm_h3b$estimate - 0.06) < 0.01 &&
    sm_h3b$lower.CL > 0 &&
    sm_h3b$p.value < 0.05
)
m_h3b_block_lm <- lm(similarity ~ condition, data = filter(d_h3b, block == H3B_BLOCK))
sm_h3b_block <- as.data.frame(summary(
  h3b_block_contrast(m_h3b_block_lm),
  infer = c(TRUE, TRUE)
))
check(
  "the block contrast is the condition difference at block 3, not elsewhere",
  nrow(sm_h3b_block) == 1L &&
    abs(sm_h3b_block$estimate - 0.18) < 0.02 &&
    sm_h3b_block$lower.CL > 0 &&
    sm_h3b_block$p.value < 0.05
)
check("centering block leaves the slope contrast unchanged", {
  d_c <- d_h3b |> mutate(block = block - mean(2:6))
  m_c <- lm(similarity ~ condition * block, data = d_c)
  sl_c <- as.data.frame(summary(h3b_slope_contrast(m_c)))
  abs(sl_c$estimate - sm_h3b$estimate) < 1e-8
})
check("reversing factor levels does not reverse the hypothesis", {
  rev_h3b <- d_h3b |>
    mutate(condition = factor(condition, levels = rev(SOCIAL_CONDITIONS)))
  m_rev <- lm(similarity ~ condition * block, data = rev_h3b)
  sm_rev <- as.data.frame(summary(h3b_slope_contrast(m_rev)))
  m_block_rev <- lm(similarity ~ condition, data = filter(rev_h3b, block == H3B_BLOCK))
  block_rev <- as.data.frame(summary(h3b_block_contrast(m_block_rev)))
  abs(sm_rev$estimate - sm_h3b$estimate) < 1e-8 &&
    abs(block_rev$estimate - sm_h3b_block$estimate) < 1e-8
})
check("a steeper social-mixed slope does not support H3b", {
  flipped <- d_h3b |>
    mutate(
      similarity = 0.4 +
        ifelse(condition == "social_first", 0.04, 0.10) * block +
        rnorm(n(), sd = 0.02)
    )
  m_f <- lm(similarity ~ condition * block, data = flipped)
  sm_f <- as.data.frame(summary(
    h3b_slope_contrast(m_f),
    infer = c(TRUE, TRUE)
  ))
  m_block_f <- lm(similarity ~ condition, data = filter(flipped, block == H3B_BLOCK))
  block_f <- as.data.frame(summary(
    h3b_block_contrast(m_block_f),
    infer = c(TRUE, TRUE)
  ))
  sm_f$estimate < 0 &&
    !h3b_supported(sm_f) &&
    block_f$estimate < 0 &&
    !h3b_supported(block_f)
})
check(
  "non-significant and non-estimable contrasts do not support H3b",
  !h3b_supported(data.frame(estimate = 0.2, p.value = 0.2)) &&
    !h3b_supported(data.frame(estimate = NA_real_, p.value = NA_real_))
)
check(
  "a significant difference in the wrong direction does not support H3b",
  !h3b_supported(data.frame(estimate = -0.2, p.value = 0.001))
)

# ── Replication requirement and the end-to-end fit ──────────────────────────
check(
  "one game per condition is not enough to fit",
  is.null(fit_h3b(exported_means, verbose = FALSE)$model)
)

window_means <- expand_grid(
  gameId = paste0("w", 1:4),
  group_num = 1:3,
  target = paste0("t", 1:6),
  block = 2:6
) |>
  mutate(
    condition = factor(
      ifelse(gameId %in% c("w1", "w2"), "social_mixed", "social_first"),
      levels = SOCIAL_CONDITIONS
    ),
    group = paste(gameId, group_num, sep = ":"),
    # Both conditions start together at block 2 and diverge from there, so
    # social_first leads by 0.06 at block 3 as well as rising 0.06 faster.
    # Anchoring the divergence at the start of the window rather than its
    # middle is what makes the level and the rate separately checkable.
    similarity = 0.4 +
      ifelse(condition == "social_first", 0.10, 0.04) * (block - 2) +
      rnorm(n(), sd = 0.05)
  )
h3b_fit <- fit_h3b(window_means, verbose = FALSE)
check(
  "fit_h3b recovers the simulated rate difference and supports H3b",
  !is.null(h3b_fit$model) &&
    abs(h3b_fit$summary$estimate - 0.06) < 0.02 &&
    isTRUE(h3b_fit$supported)
)
check(
  "fit_h3b also returns the block-3 level contrast, separately decided",
  !is.null(h3b_fit$block_contrast) &&
    nrow(h3b_fit$block_summary) == 1L &&
    abs(h3b_fit$block_summary$estimate - 0.06) < 0.03 &&
    isTRUE(h3b_fit$block_supported)
)
check(
  "block is fitted raw, with no centered column added to the data",
  !"block_c" %in% names(h3b_fit$data) &&
    setequal(unique(h3b_fit$data$block), H3B_BLOCKS)
)
check(
  "the whole blocks 2-6 window is kept for the trajectory plot",
  setequal(unique(h3b_fit$data$block), 2:6)
)

check("the block-3 model uses only group and tangram intercepts", {
  bars <- .re_findbars(formula(h3b_fit$block_model))
  setequal(vapply(bars, function(x) deparse(x[[3]]), character(1)),
           c("group", "target")) &&
    all(vapply(bars, function(x) identical(x[[2]], 1), logical(1))) &&
    identical(unique(h3b_fit$block_data$block), H3B_BLOCK)
})
check("changing later blocks leaves block-3 estimates and uncertainty unchanged", {
  changed <- window_means |>
    mutate(similarity = ifelse(block > H3B_BLOCK,
                              0.9 - 0.07 * block, similarity))
  refit <- fit_h3b(changed, verbose = FALSE)
  isTRUE(all.equal(h3b_fit$block_summary, refit$block_summary)) &&
    abs(refit$summary$estimate - h3b_fit$summary$estimate) > 0.02
})
check("block-3 inference remains available without a longitudinal window", {
  fit <- fit_h3b(filter(window_means, block == H3B_BLOCK), verbose = FALSE)
  is.null(fit$model) && !is.null(fit$note) &&
    isTRUE(all.equal(fit$block_summary, h3b_fit$block_summary))
})
check("missing block 3 skips alignment while retaining the rate model", {
  fit <- fit_h3b(filter(window_means, block != H3B_BLOCK), verbose = FALSE)
  !is.null(fit$model) && is.null(fit$block_model) &&
    identical(fit$block_note, "no observations at Phase 1 block 3")
})
check("block-3 replication is checked in its own analysis subset", {
  fit <- fit_h3b(filter(window_means, !(block == H3B_BLOCK & gameId == "w4")),
                 verbose = FALSE)
  !is.null(fit$model) && is.null(fit$block_model) &&
    identical(fit$block_note, "fewer than two games per condition")
})
