# Tests for the group-specificity estimates and permutation test in
# analysis/R/group_specificity.R, on simulated pairwise similarities.

if (!exists("fit_group_specificity")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

set.seed(11)

# Nine speakers in three groups, six targets: every unordered speaker pair per
# target, with similarity = base + effect * sameGroup + noise
simulate_pairs <- function(
  game_id,
  effect,
  window = "phase1_final",
  base = 0.3,
  sd = 0.05
) {
  speakers <- sprintf("%s_p%d", game_id, 1:9)
  groups <- setNames(rep(c("A", "B", "C"), each = 3), speakers)
  pairs <- t(combn(speakers, 2))
  map_dfr(sprintf("t%d", 1:6), function(target) {
    tibble(
      gameId = game_id,
      target = target,
      speaker1 = pairs[, 1],
      speaker2 = pairs[, 2],
      group1 = groups[pairs[, 1]],
      group2 = groups[pairs[, 2]]
    )
  }) |>
    mutate(
      sameGroup = as.integer(group1 == group2),
      similarity = base + effect * sameGroup + rnorm(n(), 0, sd),
      window = window
    )
}

games <- tibble(
  gameId = c("g_effect", "g_null"),
  condition = c("refer_separated", "refer_mixed")
)

pw_effect <- simulate_pairs("g_effect", effect = 0.4)
pw_null <- simulate_pairs("g_null", effect = 0)

# ── fit_group_specificity ────────────────────────────────────────────────────

fit <- fit_group_specificity(bind_rows(pw_effect, pw_null))
check("one row per game", nrow(fit) == 2 && setequal(fit$gameId, games$gameId))
check(
  "the coefficient recovers the within-minus-between difference",
  abs(fit$coefficient[fit$gameId == "g_effect"] - 0.4) < 0.05 &&
    abs(fit$coefficient[fit$gameId == "g_null"]) < 0.05
)

fit_cov <- fit_group_specificity(
  pw_effect |> mutate(lengthDiff = rnorm(n()), meanLength = rnorm(n())),
  covariates = c("lengthDiff", "meanLength")
)
check(
  "covariates enter the model without changing the sameGroup estimate much",
  abs(fit_cov$coefficient - fit$coefficient[fit$gameId == "g_effect"]) < 0.02
)

# ── permutation_test ─────────────────────────────────────────────────────────

perm <- permutation_test(bind_rows(pw_effect, pw_null), n_perm = 200)
check(
  "a real group effect is significant",
  perm$p_value[perm$gameId == "g_effect"] < 0.05
)
check(
  "no group effect is not significant",
  perm$p_value[perm$gameId == "g_null"] > 0.05
)
check(
  "the permutation null is centered near zero",
  all(abs(perm$perm_mean) < 0.05)
)
check(
  "the observed coefficient matches the direct fit",
  abs(
    perm$obs_coefficient[perm$gameId == "g_effect"] -
      fit$coefficient[fit$gameId == "g_effect"]
  ) <
    1e-8
)

runif(50) # disturb the RNG stream
perm_again <- permutation_test(bind_rows(pw_effect, pw_null), n_perm = 200)
check(
  "the permutation test is seeded and reproducible regardless of the RNG state",
  isTRUE(all.equal(perm$p_value, perm_again$p_value))
)

# ── game_specificity_table, endpoint coverage, and gs_wide ──────────────────

pw_both <- bind_rows(
  pw_effect,
  pw_null,
  simulate_pairs("g_effect", effect = 0.2, window = "phase2_final"),
  simulate_pairs("g_null", effect = 0.1, window = "phase2_final")
)
tab <- game_specificity_table(pw_both, games)
check(
  "game_specificity_table has one row per game and window with condition and coverage flags",
  nrow(tab) == 4 &&
    all(
      c("gameId", "window", "coefficient", "std_error", "condition",
        "eligible", "estimable", "note", "n_groups_two_speakers") %in%
        names(tab)
    ) &&
    is.factor(tab$condition) && all(tab$eligible) && all(tab$estimable) &&
    all(is.na(tab$note)) && all(tab$n_groups_two_speakers == 3)
)
wide <- gs_wide(tab)
check(
  "gs_wide has one row per game with both phases and the inverse-variance weights",
  nrow(wide) == 2 &&
    all(
      c("gs_phase1", "se_phase1", "gs_phase2", "se_phase2", "weight",
        "weight_p1", "condition", "both_endpoints") %in%
        names(wide)
    ) &&
    isTRUE(all.equal(wide$weight, 1 / wide$se_phase2^2)) &&
    all(wide$both_endpoints)
)

# A game with only the Phase 1 window keeps its row: the Phase 2 endpoint is
# NA (H1/H2 drop it, H3a keeps it), never imputed from another window.
tab_p1 <- game_specificity_table(bind_rows(pw_effect, pw_null), games)
check(
  "a window with no pairs is an ineligible row with a reason, not a missing row",
  nrow(tab_p1) == 4 &&
    all(!tab_p1$eligible[tab_p1$window == "phase2_final"]) &&
    all(grepl("no analyzable pairs", tab_p1$note[tab_p1$window == "phase2_final"])) &&
    all(tab_p1$eligible[tab_p1$window == "phase1_final"])
)
wide_p1 <- gs_wide(tab_p1)
check(
  "gs_wide keeps a game that lacks a window, with NA for that endpoint",
  nrow(wide_p1) == 2 && all(is.na(wide_p1$gs_phase2)) &&
    all(is.finite(wide_p1$gs_phase1)) && !any(wide_p1$both_endpoints) &&
    all(wide_p1$eligible_phase1) && !any(wide_p1$eligible_phase2)
)

# The endpoint rule: at least two original groups with at least two speakers
# each, and both sameGroup levels present.
one_group_two <- pw_effect |>
  filter(speaker1 %in% c("g_effect_p1", "g_effect_p2", "g_effect_p4", "g_effect_p7"),
         speaker2 %in% c("g_effect_p1", "g_effect_p2", "g_effect_p4", "g_effect_p7"))
cov_one <- endpoint_coverage(one_group_two, games, "phase1_final")
check(
  "a window where only one group has two speakers is ineligible with the reason recorded",
  !cov_one$eligible[cov_one$gameId == "g_effect"] &&
    cov_one$n_groups_two_speakers[cov_one$gameId == "g_effect"] == 1 &&
    grepl("fewer than two original groups", cov_one$coverage_note[cov_one$gameId == "g_effect"])
)
two_groups_two <- pw_effect |>
  filter(speaker1 %in% c("g_effect_p1", "g_effect_p2", "g_effect_p4", "g_effect_p5"),
         speaker2 %in% c("g_effect_p1", "g_effect_p2", "g_effect_p4", "g_effect_p5"))
cov_two <- endpoint_coverage(two_groups_two, games, "phase1_final")
check(
  "two groups with two speakers each and both pair types is the minimum eligible window",
  cov_two$eligible[cov_two$gameId == "g_effect"] &&
    cov_two$n_speakers[cov_two$gameId == "g_effect"] == 4
)
within_only <- pw_effect |> filter(sameGroup == 1)
cov_within <- endpoint_coverage(within_only, games, "phase1_final")
check(
  "a window without between-group pairs is ineligible",
  !cov_within$eligible[cov_within$gameId == "g_effect"] &&
    grepl("within-group or between-group", cov_within$coverage_note[cov_within$gameId == "g_effect"])
)
tab_min <- game_specificity_table(two_groups_two, games)
check(
  "ineligible game-windows are reported with NA estimates rather than fit",
  nrow(tab_min) == 4 && sum(tab_min$estimable) == 1 &&
    is.finite(tab_min$coefficient[tab_min$gameId == "g_effect" & tab_min$window == "phase1_final"]) &&
    sum(!is.na(tab_min$note)) == 3
)

# A test game without a condition is not part of the coverage report
games_test <- bind_rows(games, tibble(gameId = "g_test", condition = NA))
check(
  "games without a condition are left out of the coverage table",
  nrow(game_specificity_table(pw_both, games_test)) == 4
)

cov_summary <- endpoint_coverage_summary(tab_min)
check(
  "the coverage summary counts games, eligible and estimable windows, and lists reasons by condition",
  all(c("window", "condition", "games", "eligible", "estimable", "reasons") %in% names(cov_summary)) &&
    nrow(cov_summary) == 4 &&
    cov_summary$estimable[cov_summary$window == "phase1_final" &
                            cov_summary$condition == "refer_separated"] == 1 &&
    grepl("no analyzable pairs", cov_summary$reasons[cov_summary$window == "phase2_final" &
                                                        cov_summary$condition == "refer_mixed"])
)

check(
  "the measure label and file names follow the similarity measure",
  all(tab$measure == "sbert") &&
    pairwise_file("jaccard") == "pairwise_similarities_jaccard.csv" &&
    block_pairwise_file("sbert") == "block_pairwise_similarities.csv"
)
check(
  "empty input gives empty output",
  nrow(game_specificity_table(tibble(), games)) == 0 && nrow(gs_wide(tibble())) == 0
)

# ── similarity_coverage (the Jaccard robustness check omits pairs without content words) ──

cov_games <- tibble(gameId = c("j1", "j2"), condition = c("refer_mixed", "social_mixed"))
cov_pairs <- tibble(
  gameId = c("j1", "j1", "j1", "j2", "j2"),
  window = c("phase1_final", "phase1_final", "phase2_final", "phase1_final", "phase1_final"),
  similarity = c(0.5, NA, 0.2, NaN, 1)
)
cov <- similarity_coverage(cov_pairs, cov_games)
check(
  "similarity_coverage counts pairs with and without a similarity by window and condition",
  nrow(cov) == 3 &&
    cov$pairs[cov$window == "phase1_final" & cov$condition == "refer_mixed"] == 2 &&
    cov$omitted[cov$window == "phase1_final" & cov$condition == "refer_mixed"] == 1 &&
    abs(cov$prop_omitted[cov$window == "phase1_final" & cov$condition == "social_mixed"] - 0.5) < 1e-12 &&
    cov$omitted[cov$window == "phase2_final"] == 0
)
check(
  "similarity_coverage is empty for an empty table",
  nrow(similarity_coverage(tibble(), cov_games)) == 0
)
