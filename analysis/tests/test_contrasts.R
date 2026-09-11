# Tests for the planned-contrast helpers in analysis/R/contrasts.R.

if (!exists("fit_h12_wls")) {
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
# condition and tracks Phase 1
gs <- map_dfr(CONDITION_ORDER, function(cond) {
  shift <- c(
    refer_separated = 0.3,
    refer_mixed = 0.1,
    social_mixed = 0.25,
    social_first = 0.25
  )[cond]
  tibble(
    gameId = sprintf("%s_%d", cond, 1:5),
    condition = cond,
    gs_phase1 = rnorm(5, 0.4, 0.03),
    se_phase1 = 0.03
  ) |>
    mutate(
      gs_phase2 = shift + 0.5 * (gs_phase1 - 0.4) + rnorm(5, 0, 0.02),
      se_phase2 = 0.03,
      weight = 1 / se_phase2^2
    )
})

h12 <- fit_h12_wls(gs)
check(
  "the H1/H2 model uses only the three shared-Phase-1 conditions",
  identical(levels(h12$data$condition), H12_CONDITIONS) && nrow(h12$data) == 15
)
ct <- contrast_table(h12$contrasts, "primary")
check(
  "both planned contrasts are returned with the expected signs",
  identical(ct$contrast, c("H1_sep_vs_mixed", "H2_social_vs_mixed")) &&
    all(ct$estimate > 0) &&
    all(ct$analysis == "primary")
)
check(
  "the contrasts recover the simulated differences",
  abs(ct$estimate[1] - 0.2) < 0.05 && abs(ct$estimate[2] - 0.15) < 0.05
)

two <- fit_h12_wls(gs |> filter(condition != "social_mixed"))
check(
  "with a missing H1/H2 condition the model fits but the contrasts are NULL",
  !is.null(two$model) && is.null(two$contrasts)
)
none <- fit_h12_wls(gs |> filter(condition == "social_first"))
check(
  "with fewer than two conditions nothing is fit",
  is.null(none$model) && !is.null(none$note)
)

check(
  "contrast_table is NULL for NULL contrasts",
  is.null(contrast_table(NULL, "x"))
)
