# The per-game group-specificity estimates every game-level analysis rests
# on. For each real game and endpoint window (the final Phase 1 and final
# Phase 2 windows), the preregistered per-game model
#
#   similarity ~ sameGroup + (1 | target) + (1 | speakerPair)
#
# is fit to the pairwise similarities between descriptions of the same
# tangram, and the sameGroup coefficient is the game's group-specificity
# score: how much more alike two speakers of one original group describe a
# tangram than two speakers of different groups. The speaker-pair intercept
# is the term the design-matched simulations (simulations/) showed to matter
# for interval calibration and is kept even at a variance boundary, so the
# structure never depends on the data.
#
# An endpoint estimate requires analyzable descriptions from at least two
# speakers in each of at least two original groups within the window, and
# both within-group and between-group pairs; a missing endpoint is never
# replaced from another window. Every game-window is listed with its
# eligibility and, where there is no estimate, the reason.
#
# Three versions are written, all with one row per game and window:
#   primary/group_specificity.csv                  sentence-embedding (SBERT)
#                                                  cosine, the primary measure
#   primary/group_specificity_jaccard.csv          content-word Jaccard
#                                                  overlap, the preregistered
#                                                  robustness measure (pairs
#                                                  without content words on
#                                                  one side are omitted)
#   primary/group_specificity_length_adjusted.csv  SBERT with the pair's
#                                                  length difference and mean
#                                                  length as covariates, for
#                                                  the description-length
#                                                  robustness check
# plus primary/group_specificity_jaccard_coverage.csv, the share of pairs the
# Jaccard table omits, by window and condition. The game-level regressions
# (h1_h2.R, h3a.R, robustness.R, bayes_factors.R and the secondary
# specificity-versus-social-accuracy script) read these tables rather than
# refitting.

source(here::here("stats", "config.R"))
list2env(load_tables(), envir = globalenv())

if (!has_rows(pairwise_sim)) {
  stop("No pairwise similarities; run the measures step first.", call. = FALSE)
}

# ── SBERT, the primary measure ────────────────────────────────────────────
gs_table <- game_specificity_table(pairwise_sim, games)
cat("Endpoint coverage by window and condition:\n")
print(knitr::kable(endpoint_coverage_summary(gs_table)))
cat(paste(
  "\nPer-game fits at a variance boundary (the tangram or speaker-pair variance",
  "estimated at zero; the sameGroup estimate is kept), by window and condition:\n"
))
print(knitr::kable(singular_fit_summary(gs_table), digits = 2))
not_estimable <- gs_table |> filter(!estimable)
if (nrow(not_estimable) > 0) {
  cat("\nGame-windows without an estimate:\n")
  print(knitr::kable(
    not_estimable |>
      mutate(gameId = substr(gameId, 1, 10)) |>
      select(condition, gameId, window, n_pairs, n_speakers, n_groups_two_speakers, both_levels, note)
  ))
} else {
  cat("\nEvery game-window is eligible and estimable.\n")
}
gs <- gs_wide(gs_table)
cat(sprintf(
  "\nGames with both endpoints (H1/H2): %d of %d; with the Phase 1 endpoint (H3a): %d.\n",
  sum(gs$both_endpoints), nrow(gs), sum(gs$eligible_phase1 %in% TRUE)
))
write_estimates(gs_table, "primary/group_specificity", source = "stats/primary/group_specificity.R")

# ── Content-word Jaccard, the robustness measure ──────────────────────────
if (has_rows(pairwise_sim_jaccard)) {
  coverage <- similarity_coverage(pairwise_sim_jaccard, games)
  cat("\nEndpoint pairs with and without a Jaccard similarity:\n")
  print(knitr::kable(coverage, digits = 3))
  write_estimates(
    coverage, "primary/group_specificity_jaccard_coverage",
    source = "stats/primary/group_specificity.R"
  )
  gs_table_jaccard <- game_specificity_table(
    pairwise_sim_jaccard |> filter(is.finite(similarity)),
    games,
    measure = "jaccard"
  )
  cat("\nEndpoint coverage on the Jaccard table:\n")
  print(knitr::kable(endpoint_coverage_summary(gs_table_jaccard)))
  write_estimates(
    gs_table_jaccard, "primary/group_specificity_jaccard",
    source = "stats/primary/group_specificity.R"
  )
} else {
  cat("\nNo Jaccard pairwise similarities; the robustness tables are not written.\n")
}

# ── SBERT with description length as a covariate ──────────────────────────
if (all(c("length1", "length2") %in% names(pairwise_sim))) {
  pw_len <- pairwise_sim |>
    mutate(lengthDiff = abs(length1 - length2), meanLength = (length1 + length2) / 2)
  gs_table_adjusted <- game_specificity_table(
    pw_len, games,
    covariates = c("lengthDiff", "meanLength"),
    measure = "sbert_length_adjusted"
  )
  write_estimates(
    gs_table_adjusted, "primary/group_specificity_length_adjusted",
    source = "stats/primary/group_specificity.R"
  )
} else {
  cat("\npairwise_similarities.csv has no length columns; the length-adjusted table is not written.\n")
}
