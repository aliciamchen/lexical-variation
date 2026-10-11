# Convention-formation check 4: did each game's groups develop their own way
# of describing the tangrams by the end of Phase 1? Per game, the
# group-specificity coefficient of the final Phase 1 window (the within-group
# minus between-group similarity, from the preregistered per-game model with
# tangram and speaker-pair intercepts) and a permutation p-value from
# reshuffling speakers across groups. Reported by condition and pooled over
# the three conditions that share the Phase 1 procedure; neither a positive
# mean nor a share of significant games is a pass/fail threshold.
#
# The per-game fits and the thousand permutations per game take several
# minutes, so compute_group_specificity() caches them in data/<dataset>/cache/
# keyed by a hash of the pairwise data; a rebuild that changes the pairwise
# table recomputes them.
#
# Writes results/estimates/checks/phase1_group_specificity.csv: one
# row per game with the coefficient, its standard error, whether the fit sat
# at a variance boundary, the permutation p-value and whether the game is in
# the shared-Phase-1 conditions.

source(here::here("models", "config.R"))
list2env(load_tables(), envir = globalenv())

p1_pairwise <- pairwise_sim |> filter(window == "phase1_final")
if (!has_rows(p1_pairwise)) {
  stop("No Phase 1 final pairwise similarities; run the measures step first.", call. = FALSE)
}

gs_cached <- compute_group_specificity(p1_pairwise, cache_dir)
gs_results <- gs_cached$gs_results
perm_results <- gs_cached$perm_results
if (!has_rows(gs_results)) {
  gs_results <- tibble(gameId = character(), coefficient = numeric(), std_error = numeric(), singular = logical())
}
if (!has_rows(perm_results)) {
  perm_results <- tibble(gameId = character(), p_value = numeric(), perm_mean = numeric(), perm_sd = numeric())
}

# Every real game keeps its row; a game without an estimable coefficient or a
# permutation result stays NA rather than counting as a success or a failure.
gs_by_game <- games |>
  filter(!is.na(condition)) |>
  select(gameId, condition) |>
  left_join(
    gs_results |> select(gameId, coefficient, std_error, any_of("singular")),
    by = "gameId"
  ) |>
  left_join(
    perm_results |> select(gameId, p_value, any_of(c("perm_mean", "perm_sd"))),
    by = "gameId"
  ) |>
  mutate(
    condition = factor(condition, levels = CONDITION_ORDER),
    shared_phase1 = condition %in% H12_CONDITIONS
  )

cat("Group-specificity estimates and permutation p-values by game:\n")
print(knitr::kable(gs_by_game, digits = 4))

n_perm_all <- sum(!is.na(gs_by_game$p_value))
n_sig_all <- sum(gs_by_game$p_value < 0.05, na.rm = TRUE)
n_perm_shared <- sum(!is.na(gs_by_game$p_value) & gs_by_game$shared_phase1)
n_sig_shared <- sum(gs_by_game$p_value < 0.05 & gs_by_game$shared_phase1, na.rm = TRUE)
cat(sprintf(
  paste(
    "\nPhase 1 group-specificity above the permutation null (p < .05):",
    "%d of %d games in all conditions; %d of %d in the three shared-Phase-1 conditions.\n"
  ),
  n_sig_all, n_perm_all, n_sig_shared, n_perm_shared
))
if ("singular" %in% names(gs_by_game)) {
  cat(sprintf(
    paste(
      "%d of %d per-game fits sat at a variance boundary (the tangram or",
      "speaker-pair variance estimated at zero); their estimates are kept.\n"
    ),
    sum(gs_by_game$singular %in% TRUE), sum(is.finite(gs_by_game$coefficient))
  ))
}

summarise_gs <- function(d) {
  d |>
    summarise(
      games = n(),
      estimable = sum(is.finite(coefficient)),
      mean_specificity = if (any(is.finite(coefficient))) mean(coefficient[is.finite(coefficient)]) else NA_real_,
      median_specificity = if (any(is.finite(coefficient))) median(coefficient[is.finite(coefficient)]) else NA_real_,
      .groups = "drop"
    )
}
cat("\nDescriptive group-specificity summaries by condition:\n")
print(knitr::kable(gs_by_game |> group_by(condition) |> summarise_gs(), digits = 4))
cat("\nShared Phase 1 procedure, pooled (a description, not a pass/fail test):\n")
print(knitr::kable(gs_by_game |> filter(shared_phase1) |> summarise_gs(), digits = 4))

write_estimates(
  gs_by_game,
  "checks/phase1_group_specificity",
  source = "models/checks/phase1_group_specificity.R"
)
