# Group-specificity estimation and permutation testing.
#
# Shared by SI_pilot.qmd, 01_outcome_neutral.qmd, 02_primary_analysis.qmd, and 03_secondary_analysis.qmd.
# Results are cached as RDS files in data_dir to avoid re-running
# the expensive permutation test on every notebook render.
#
# Usage:
#   (sourced by config.R together with the other helpers in analysis/R/)
#   results <- compute_group_specificity(pairwise_df, derived_dir, n_perm = 1000)
#   # returns list(gs_results, perm_results) — loaded from cache if available
#   gs <- gs_wide(game_specificity_table(pairwise_sim, games))
#   # one row per game: gs_phase1, se_phase1, gs_phase2, se_phase2, weight, condition
#
# Tests: analysis/tests/test_group_specificity.R

suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
  library(tidyverse)
})

# The two speaker random-effect structures.
#
# "multimembership" is the preregistered full-sample structure: one random
# effect per speaker, shared across both pair positions with equal weights of
# 1/2 and a common variance (see R/multimembership.R). "separate" is the
# earlier structure, with an independent intercept for each pair position; the
# paper records that the pilot estimates and permutation results use it, so
# SI_pilot.qmd asks for it explicitly. Do not use it for the full sample: it
# splits one person's effect across two variance components and makes the
# estimate depend on an arbitrary ordering within each pair.
# "multimembership_pair" is the preregistered structure: the shared speaker
# effect plus a random intercept for the unordered speaker pair. The three
# random effects stand for the three sources of resemblance between two
# descriptions that are not the effect of interest -- the tangram, the two
# individual speakers, and the pair itself. The pair term is the one a
# shared convention lives in, and it cannot be recovered from the speakers'
# individual tendencies because those enter additively.
#
# The design-matched simulations (analysis/simulate_mm_speaker.R) are why it
# is the default: without it the standard error runs about 25% small when
# pair-level dependence is present (95% intervals covering 86%), and with it
# coverage is nominal at no real cost when no such dependence exists. Point
# estimates are the same either way, so the choice shows up only in the
# inverse-variance weights, which is exactly what it needs to get right.
# The pair variance sits at the boundary in many games; the term is kept
# anyway, so the model structure never depends on the data.
SPEAKER_STRUCTURES <- c("multimembership_pair", "multimembership", "separate")

# `covariates` adds fixed-effect terms to every game's similarity model; the
# preregistration uses this for the robustness check that includes description
# length (the pair's length difference and mean length).
fit_group_specificity <- function(pairwise_df, covariates = NULL,
                                  speaker_structure = "multimembership_pair") {
  speaker_structure <- match.arg(speaker_structure, SPEAKER_STRUCTURES)
  if (speaker_structure != "separate") {
    return(
      fit_group_specificity_mm(
        pairwise_df,
        covariates = covariates,
        pair_term = speaker_structure == "multimembership_pair"
      ) |>
        select(gameId, coefficient, std_error, t_value) |>
        filter(!is.na(coefficient))
    )
  }
  game_ids <- unique(pairwise_df$gameId)
  rhs <- paste(c("sameGroup", covariates), collapse = " + ")
  model_formula <- as.formula(paste(
    "similarity ~", rhs, "+ (1 | target) + (1 | speaker1) + (1 | speaker2)"
  ))

  results <- map_dfr(game_ids, function(gid) {
    game_data <- pairwise_df |> filter(gameId == gid)
    if (nrow(game_data) < 5) return(NULL)
    if (n_distinct(game_data$sameGroup) < 2) return(NULL)

    tryCatch({
      model <- lmer(
        model_formula,
        data = game_data,
        control = lmerControl(optimizer = "bobyqa")
      )
      coefs <- coef(summary(model))
      tibble(
        gameId = gid,
        coefficient = coefs["sameGroup", "Estimate"],
        std_error = coefs["sameGroup", "Std. Error"],
        t_value = coefs["sameGroup", "t value"]
      )
    }, error = function(e) NULL)
  })

  results
}

# The permutations are drawn from their own seeded RNG stream so the p-values
# are identical whichever notebook computes them (and the caller's RNG state is
# left untouched).
permutation_test <- function(pairwise_df, n_perm = 1000, seed = 67,
                             speaker_structure = "multimembership_pair") {
  speaker_structure <- match.arg(speaker_structure, SPEAKER_STRUCTURES)
  # One fitter, used for both the observed model and every permutation, so
  # the null distribution is always built from the same structure as the
  # observed coefficient it is compared against.
  fit_one <- function(d) {
    if (speaker_structure == "separate") {
      model <- lmer(
        similarity ~ sameGroup + (1 | target) + (1 | speaker1) + (1 | speaker2),
        data = d, control = lmerControl(optimizer = "bobyqa")
      )
      return(coef(summary(model))["sameGroup", "Estimate"])
    }
    d <- as.data.frame(d)
    d$speakerPair <- paste(pmin(d$speaker1, d$speaker2),
                           pmax(d$speaker1, d$speaker2))
    f <- if (speaker_structure == "multimembership_pair") {
      similarity ~ sameGroup + (1 | target) + (1 | speakerPair) + (1 | speaker)
    } else {
      similarity ~ sameGroup + (1 | target) + (1 | speaker)
    }
    model <- lmer_multimember(
      f, data = d,
      memberships = list(speaker = speaker_pair_weights(d$speaker1, d$speaker2))
    )
    coef(summary(model))["sameGroup", "Estimate"]
  }

  if (!is.null(seed)) {
    had_seed <- exists(".Random.seed", envir = globalenv(), inherits = FALSE)
    old_seed <- if (had_seed) get(".Random.seed", envir = globalenv()) else NULL
    set.seed(seed)
    on.exit(
      if (had_seed) assign(".Random.seed", old_seed, envir = globalenv()) else
        rm(".Random.seed", envir = globalenv()),
      add = TRUE
    )
  }
  game_ids <- unique(pairwise_df$gameId)

  results <- map_dfr(game_ids, function(gid) {
    game_data <- pairwise_df |> filter(gameId == gid)
    if (nrow(game_data) < 5) return(NULL)
    if (n_distinct(game_data$sameGroup) < 2) return(NULL)

    obs_coef <- tryCatch(fit_one(game_data), error = function(e) NULL)
    if (is.null(obs_coef)) return(NULL)

    speakers <- game_data |>
      select(speaker1, group1) |>
      rename(speaker = speaker1, group = group1) |>
      bind_rows(
        game_data |> select(speaker2, group2) |> rename(speaker = speaker2, group = group2)
      ) |>
      distinct()

    perm_coefs <- map_dbl(seq_len(n_perm), function(i) {
      perm_groups <- speakers |> mutate(perm_group = sample(group))
      perm_data <- game_data |>
        left_join(perm_groups |> select(speaker, perm_group),
                  by = c("speaker1" = "speaker")) |>
        rename(perm_group1 = perm_group) |>
        left_join(perm_groups |> select(speaker, perm_group),
                  by = c("speaker2" = "speaker")) |>
        rename(perm_group2 = perm_group) |>
        mutate(sameGroup = as.numeric(perm_group1 == perm_group2))

      tryCatch(fit_one(perm_data), error = function(e) NA_real_)
    })

    p_value <- mean(perm_coefs >= obs_coef, na.rm = TRUE)

    tibble(
      gameId = gid,
      obs_coefficient = obs_coef,
      perm_mean = mean(perm_coefs, na.rm = TRUE),
      perm_sd = sd(perm_coefs, na.rm = TRUE),
      p_value = p_value,
      perm_coefs = list(perm_coefs)
    )
  })

  results
}

#' Compute group-specificity with RDS caching.
#'
#' @param pairwise_df  Data frame of pairwise similarities (must have
#'   gameId, sameGroup, similarity, target, speaker1, speaker2 columns).
#' @param cache_dir    Directory to store/read the cached RDS files.
#' @param n_perm       Number of permutations (default 1000).
#' @param force        If TRUE, recompute even if cache exists.
#' @return A list with elements `gs_results` and `perm_results`.
compute_group_specificity <- function(pairwise_df, cache_dir, n_perm = 1000,
                                      force = FALSE, seed = 67,
                                      speaker_structure = "multimembership_pair") {
  speaker_structure <- match.arg(speaker_structure, SPEAKER_STRUCTURES)
  # One set of cache files per speaker structure. They must not share a name:
  # SI_pilot.qmd asks for "separate" and the full-sample notebooks use the
  # default, so a single set would be overwritten by whichever notebook
  # rendered last and the permutation test would rerun every time.
  suffix <- paste0("_", speaker_structure)
  gs_cache <- file.path(cache_dir, paste0("gs_results", suffix, ".rds"))
  perm_cache <- file.path(cache_dir, paste0("perm_results", suffix, ".rds"))
  key_file <- file.path(
    cache_dir, paste0("group_specificity_cache_key", suffix, ".txt")
  )

  # The cache is keyed by a hash of the input data and the permutation count,
  # so a change to the pairwise similarities (or a different dataset) can never
  # silently reuse stale fits. Force = TRUE recomputes regardless.
  # Only the columns the models use enter the hash, so adding descriptive
  # columns to the pairwise file does not invalidate the cache.
  key_cols <- intersect(c("gameId", "target", "speaker1", "speaker2", "sameGroup", "similarity"),
                        names(pairwise_df))
  key_df <- as.data.frame(pairwise_df)[order(pairwise_df$gameId, pairwise_df$target,
                                             pairwise_df$speaker1, pairwise_df$speaker2), key_cols]
  rownames(key_df) <- NULL
  # The structure is part of the key: the two speaker structures give
  # different coefficients, so a cache written under one must never be
  # reused under the other.
  key <- rlang::hash(list(key_df, n_perm, seed, speaker_structure))
  cached_key <- if (file.exists(key_file)) readLines(key_file, n = 1, warn = FALSE) else ""

  if (!force && file.exists(gs_cache) && file.exists(perm_cache) &&
      identical(cached_key, key)) {
    cat("Loading cached group-specificity results from", cache_dir, "\n")
    return(list(
      gs_results = readRDS(gs_cache),
      perm_results = readRDS(perm_cache)
    ))
  }

  if (file.exists(gs_cache) && !identical(cached_key, key)) {
    cat("Cached group-specificity results do not match the current data; recomputing.\n")
  }
  cat("Computing group-specificity (this may take a few minutes)...\n")
  gs_results <- fit_group_specificity(pairwise_df,
                                      speaker_structure = speaker_structure)
  perm_results <- permutation_test(pairwise_df, n_perm = n_perm, seed = seed,
                                   speaker_structure = speaker_structure)

  dir.create(cache_dir, showWarnings = FALSE, recursive = TRUE)
  saveRDS(gs_results, gs_cache)
  saveRDS(perm_results, perm_cache)
  writeLines(key, key_file)
  cat("Cached results to", cache_dir, "\n")

  list(gs_results = gs_results, perm_results = perm_results)
}


# ── Per-game estimates for the game-level analyses ────────────────────────────

# The group-specificity coefficient and its standard error for every game in
# each window, with condition. This is the one place the estimates that feed
# the H1/H2, H3a, and social-accuracy regressions are computed; `covariates`
# passes extra fixed effects (e.g. the description-length robustness check).
game_specificity_table <- function(pairwise_sim, games,
                                   windows = c("phase1_final", "phase2_final"),
                                   covariates = NULL,
                                   speaker_structure = "multimembership_pair") {
  if (!is.data.frame(pairwise_sim) || nrow(pairwise_sim) == 0) return(tibble())
  map_dfr(windows, function(w) {
    fit_group_specificity(pairwise_sim |> filter(window == w),
                          covariates = covariates,
                          speaker_structure = speaker_structure) |>
      mutate(window = w)
  }) |>
    left_join(games |> select(gameId, condition), by = "gameId") |>
    mutate(condition = factor(as.character(condition), levels = CONDITION_ORDER))
}

# One row per game with gs_phase1/se_phase1, gs_phase2/se_phase2, the H1/H2
# inverse-variance weight, and condition. Games missing either window are
# dropped.
gs_wide <- function(gs_table) {
  if (!is.data.frame(gs_table) || nrow(gs_table) == 0) return(tibble())
  p1 <- gs_table |> filter(window == "phase1_final") |>
    select(gameId, condition, gs_phase1 = coefficient, se_phase1 = std_error)
  p2 <- gs_table |> filter(window == "phase2_final") |>
    select(gameId, gs_phase2 = coefficient, se_phase2 = std_error)
  inner_join(p1, p2, by = "gameId") |>
    mutate(weight = 1 / se_phase2^2, weight_p1 = 1 / se_phase1^2) |>
    relocate(condition, .after = gameId)
}
