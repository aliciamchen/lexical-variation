# Tests for the game-level regressions and planned contrasts in
# analysis/R/contrasts.R.

if (!exists("fit_h12")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

set.seed(5)

check(
  "pairwise_weights puts +1 on a and -1 on b",
  identical(pairwise_weights(c("x", "y", "z"), "z", "y"), c(0, -1, 1))
)

# Game-level table: 5 games per condition, Phase 2 specificity differs by
# condition and tracks Phase 1. Standard errors vary so OLS and WLS differ.
gs <- map_dfr(CONDITION_ORDER, function(cond) {
  shift <- c(
    refer_separated = 0.3,
    refer_mixed = 0.1,
    social_mixed = 0.25,
    social_first = 0.35
  )[cond]
  tibble(
    gameId = sprintf("%s_%d", cond, 1:5),
    condition = cond,
    gs_phase1 = rnorm(5, 0.4, 0.03) + if (cond == "social_first") 0.1 else 0,
    se_phase1 = runif(5, 0.02, 0.08)
  ) |>
    mutate(
      gs_phase2 = shift + 0.5 * (gs_phase1 - 0.4) + rnorm(5, 0, 0.02),
      se_phase2 = runif(5, 0.02, 0.08),
      weight = 1 / se_phase2^2,
      weight_p1 = 1 / se_phase1^2
    )
})

# ── H1/H2 ────────────────────────────────────────────────────────────────────

h12 <- fit_h12(gs)
check(
  "the H1/H2 model uses only the three shared-Phase-1 conditions",
  identical(levels(h12$data$condition), H12_CONDITIONS) && nrow(h12$data) == 15
)
check(
  "the primary H1/H2 fit is ordinary least squares",
  is.null(h12$weights) &&
    is.null(h12$model$weights) &&
    isTRUE(all.equal(
      unname(coef(h12$model)),
      unname(coef(
        lm(gs_phase2 ~ condition + gs_phase1, data = h12$data)
      ))
    ))
)
ct <- contrast_table(h12$contrasts, "primary")
check(
  "both planned contrasts are returned with the expected signs and a CI",
  identical(ct$contrast, c("H1_sep_vs_mixed", "H2_social_vs_mixed")) &&
    all(ct$estimate > 0) &&
    all(ct$analysis == "primary") &&
    all(c("lower", "upper") %in% names(ct)) &&
    all(ct$lower < ct$estimate & ct$estimate < ct$upper)
)
check(
  "the contrasts recover the simulated differences",
  abs(ct$estimate[1] - 0.2) < 0.05 && abs(ct$estimate[2] - 0.15) < 0.05
)

h12_w <- fit_h12(gs, weights = "weight")
check(
  "the weighted rerun is WLS with the inverse-variance weights and differs from OLS",
  identical(h12_w$weights, "weight") &&
    isTRUE(all.equal(unname(h12_w$model$weights), h12_w$data$weight)) &&
    !isTRUE(all.equal(coef(h12_w$model), coef(h12$model)))
)

two <- fit_h12(gs |> filter(condition != "social_mixed"))
check(
  "with a missing H1/H2 condition the model fits but the contrasts are NULL",
  !is.null(two$model) && is.null(two$contrasts)
)
none <- fit_h12(gs |> filter(condition == "social_first"))
check(
  "with fewer than two conditions nothing is fit",
  is.null(none$model) && !is.null(none$note)
)

# A game without a Phase 2 endpoint (H3a-only coverage) is dropped from H1/H2
gs_gap <- gs |>
  mutate(
    gs_phase2 = ifelse(gameId == "refer_mixed_1", NA, gs_phase2),
    se_phase2 = ifelse(gameId == "refer_mixed_1", NA, se_phase2),
    weight = ifelse(gameId == "refer_mixed_1", NA, weight)
  )
h12_gap <- fit_h12(gs_gap)
check(
  "games missing an endpoint are dropped from H1/H2, not imputed",
  nrow(h12_gap$data) == 14 &&
    !"refer_mixed_1" %in% h12_gap$data$gameId &&
    !is.null(h12_gap$contrasts)
)

# ── H3a ──────────────────────────────────────────────────────────────────────

h3a <- fit_h3a(gs_gap)
check(
  "H3a uses the two social conditions and needs only the Phase 1 endpoint",
  identical(levels(h3a$data$condition), SOCIAL_CONDITIONS) &&
    nrow(h3a$data) == 10 &&
    is.null(h3a$weights)
)
ct3a <- contrast_table(h3a$contrasts, "primary")
check(
  "the H3a contrast is social_first minus social_mixed",
  ct3a$contrast == "H3a_socialfirst_gt_socialmixed" &&
    abs(ct3a$estimate - 0.1) < 0.05
)
h3a_w <- fit_h3a(gs, weights = "weight_p1")
check(
  "the H3a robustness rerun uses the Phase 1 inverse-variance weights",
  isTRUE(all.equal(unname(h3a_w$model$weights), h3a_w$data$weight_p1))
)

# ── fit_game_level with extra predictors ─────────────────────────────────────

gs_sa <- gs |> mutate(social_accuracy = runif(n(), 0.4, 0.9))
sa <- fit_game_level(
  gs_sa,
  outcome = "gs_phase2",
  predictors = c("social_accuracy", "gs_phase1"),
  conditions = SOCIAL_CONDITIONS
)
check(
  "a game-level regression with extra predictors keeps them in the fitted model",
  all(
    c("social_accuracy", "gs_phase1", "conditionsocial_first") %in%
      names(coef(sa$model))
  ) &&
    nrow(sa$data) == 10
)
missing_col <- fit_game_level(
  gs,
  outcome = "gs_phase2",
  predictors = "not_a_column",
  conditions = SOCIAL_CONDITIONS
)
check(
  "a missing predictor column is reported, not an error",
  is.null(missing_col$model) && grepl("not_a_column", missing_col$note)
)

check(
  "contrast_table is NULL for NULL contrasts",
  is.null(contrast_table(NULL, "x"))
)
