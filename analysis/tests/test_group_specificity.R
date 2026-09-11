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

# ── game_specificity_table and gs_wide ───────────────────────────────────────

pw_both <- bind_rows(
  pw_effect,
  pw_null,
  simulate_pairs("g_effect", effect = 0.2, window = "phase2_final"),
  simulate_pairs("g_null", effect = 0.1, window = "phase2_final")
)
tab <- game_specificity_table(pw_both, games)
check(
  "game_specificity_table has one row per game and window with condition",
  nrow(tab) == 4 &&
    all(
      c("gameId", "window", "coefficient", "std_error", "condition") %in%
        names(tab)
    ) &&
    is.factor(tab$condition)
)
wide <- gs_wide(tab)
check(
  "gs_wide has one row per game with both phases and the H1/H2 weight",
  nrow(wide) == 2 &&
    all(
      c(
        "gs_phase1",
        "se_phase1",
        "gs_phase2",
        "se_phase2",
        "weight",
        "condition"
      ) %in%
        names(wide)
    ) &&
    isTRUE(all.equal(wide$weight, 1 / wide$se_phase2^2))
)
check(
  "gs_wide drops a game that lacks a window",
  nrow(gs_wide(game_specificity_table(bind_rows(pw_effect, pw_null), games))) ==
    0
)
check(
  "empty input gives empty output",
  nrow(game_specificity_table(tibble(), games)) == 0
)
