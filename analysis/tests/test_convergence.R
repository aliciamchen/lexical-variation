# Tests for the H3b milestone, aggregation, and primary support criterion.

if (!exists("fit_h3b")) source(here::here("analysis", "config.R"))
if (!exists("check")) source(here::here("analysis", "tests", "check.R"))

set.seed(31)

games_h3b <- tibble(
  gameId = c("g1", "g2", "g3"),
  condition = c("social_mixed", "social_first", "refer_mixed")
)
pairs_h3b <- tibble(
  gameId = c("g1", "g1", "g1", "g1", "g1", "g2", "g3", "g1"),
  group1 = "A", group2 = c("A", "A", "A", "A", "B", "A", "A", "A"),
  target = "t1", blockNum = c(2, 3, 3, 3, 3, 3, 3, 3),
  phaseNum = c(1, 1, 1, 1, 1, 1, 1, 2),
  sameGroup = c(1, 1, 1, 1, 0, 1, 1, 1),
  similarity = c(0.2, 0.4, 0.8, NA, 0.1, 0.9, 0.6, 0.7)
)
means_h3b <- within_group_block_means(pairs_h3b, games_h3b)
check(
  "H3b aggregates only Phase 1 within-group pairs in the two social conditions",
  nrow(means_h3b) == 3L && all(means_h3b$gameId %in% c("g1", "g2"))
)
g1_b3 <- means_h3b |> filter(gameId == "g1", blockNum == H3B_BLOCK)
check(
  "block 3 is not reindexed and overlapping pairs contribute one finite mean",
  nrow(g1_b3) == 1L && abs(g1_b3$similarity - 0.6) < 1e-12 &&
    g1_b3$n_pairs == 2L && g1_b3$blockNum == 3L
)
check(
  "group and group--tangram ids distinguish the same label in different games",
  n_distinct(means_h3b$group) == 2L && n_distinct(means_h3b$group_target) == 2L
)
check(
  "no-pair observations are omitted without borrowing another block",
  nrow(within_group_block_means(
    pairs_h3b |> mutate(similarity = ifelse(blockNum == 3, NA, similarity)),
    games_h3b
  ) |> filter(blockNum == 3)) == 0L
)
check("empty pair input stays empty",
      !has_rows(within_group_block_means(tibble(), games_h3b)))
pilot_h3b <- fit_h3b(means_h3b, verbose = FALSE)
check(
  "one game per condition cannot trigger H3b inference",
  is.null(pilot_h3b$model) && is.na(pilot_h3b$supported) &&
    nrow(pilot_h3b$data) == 3L
)

# Known population means with an early advantage and a flatter social-first
# slope. The categorical contrast must recover block 3, not an average across
# blocks or the coefficient on the default reference block.
d_h3b <- expand_grid(condition = SOCIAL_CONDITIONS, blockNum = 2:6, rep = 1:24) |>
  mutate(
    condition = factor(condition, levels = SOCIAL_CONDITIONS),
    block = factor(blockNum),
    expected = ifelse(condition == "social_first", 0.8,
                      0.2 + 0.15 * (blockNum - 2)),
    similarity = expected + rnorm(n(), sd = 0.015)
  )
m_h3b_test <- lm(similarity ~ condition * block, data = d_h3b)
sm_h3b <- as.data.frame(summary(h3b_block_contrast(m_h3b_test),
                                infer = c(TRUE, TRUE)))
check(
  "the primary contrast is social-first minus social-mixed at block 3",
  nrow(sm_h3b) == 1L && abs(sm_h3b$estimate - 0.45) < 0.015 &&
    sm_h3b$lower.CL > 0 && sm_h3b$p.value < 0.05
)
linear_h3b <- lm(similarity ~ condition * blockNum, data = d_h3b)
check(
  "early alignment followed by a plateau supports H3b despite a negative slope difference",
  h3b_supported(sm_h3b) && coef(linear_h3b)["conditionsocial_first:blockNum"] < 0
)
reversed_h3b <- d_h3b |>
  mutate(condition = factor(condition, levels = rev(SOCIAL_CONDITIONS)))
sm_reversed <- as.data.frame(summary(h3b_block_contrast(
  lm(similarity ~ condition * block, data = reversed_h3b)
)))
check("reversing factor levels does not reverse the hypothesis",
      abs(sm_reversed$estimate - sm_h3b$estimate) < 1e-10)

# A late rise must not leak into the primary early contrast.
late_h3b <- d_h3b |>
  mutate(similarity = similarity + ifelse(condition == "social_first" &
                                           blockNum >= 4, 0.1, 0))
sm_late <- as.data.frame(summary(h3b_block_contrast(
  lm(similarity ~ condition * block, data = late_h3b)
)))
check("changing later block means does not change the fitted block-3 difference",
      abs(sm_late$estimate - sm_h3b$estimate) < 1e-10)
check("a significant difference in the opposite direction does not support H3b",
      !h3b_supported(data.frame(estimate = -0.2, p.value = 0.001)))
check("non-significant and non-estimable contrasts do not support H3b",
      !h3b_supported(data.frame(estimate = 0.2, p.value = 0.2)) &&
        !h3b_supported(data.frame(estimate = NA_real_, p.value = NA_real_)))

# Having enough games at other blocks is not enough at the milestone itself.
missing_b3 <- bind_rows(
  means_h3b,
  means_h3b |> mutate(gameId = paste0(gameId, "extra"), blockNum = 4)
)
check("later data cannot substitute for missing block-3 replication",
      is.null(fit_h3b(missing_b3, verbose = FALSE)$model))

# Check the full model's grouping structure and the actual mixed-model
# contrast on synthetic nested observations without running large pilot fits.
bars_h3b <- .re_findbars(H3B_FORMULA)
check("the primary model retains game, nested group, target, and repeated group--target effects",
      setequal(vapply(bars_h3b, function(x) deparse(x[[3]]), character(1)),
               c("gameId", "group", "target", "group_target")))
mixed_h3b <- expand_grid(gameId = 1:12, group_num = 1:3, target = 1:6,
                         blockNum = 2:6) |>
  mutate(
    condition = factor(ifelse(gameId <= 6, "social_mixed", "social_first"),
                       levels = SOCIAL_CONDITIONS),
    group = interaction(gameId, group_num),
    group_target = interaction(group, target),
    block = factor(blockNum),
    similarity = ifelse(condition == "social_first", 0.8,
                         0.2 + 0.15 * (blockNum - 2)) +
      rnorm(12, sd = 0.035)[gameId] +
      rnorm(36, sd = 0.03)[as.integer(group)] +
      rnorm(6, sd = 0.02)[target] +
      rnorm(216, sd = 0.025)[as.integer(group_target)] +
      rnorm(n(), sd = 0.03)
  )
mixed_fit_h3b <- lmerTest::lmer(
  similarity ~ condition * block + (1 | gameId) + (1 | group) +
    (1 | target) + (1 | group_target), data = mixed_h3b
)
mixed_sm_h3b <- as.data.frame(summary(h3b_block_contrast(mixed_fit_h3b),
                                      infer = c(TRUE, TRUE)))
check("the planned contrast works with nested mixed models and finite degrees of freedom",
      h3b_supported(mixed_sm_h3b) && is.finite(mixed_sm_h3b$df) &&
        abs(mixed_sm_h3b$estimate - 0.45) < 0.1)
