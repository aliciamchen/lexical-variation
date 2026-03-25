# Group-specificity estimation and permutation testing.
#
# Shared by SI_pilot.qmd and 01_outcome_neutral.qmd.
# Results are cached as RDS files in data_dir to avoid re-running
# the expensive permutation test on every notebook render.
#
# Usage:
#   source(here::here("analysis", "group_specificity.R"))
#   results <- compute_group_specificity(pairwise_df, derived_dir, n_perm = 1000)
#   # returns list(gs_results, perm_results) — loaded from cache if available

library(lme4)
library(lmerTest)
library(tidyverse)

fit_group_specificity <- function(pairwise_df) {
  game_ids <- unique(pairwise_df$gameId)

  results <- map_dfr(game_ids, function(gid) {
    game_data <- pairwise_df |> filter(gameId == gid)
    if (nrow(game_data) < 5) return(NULL)
    if (n_distinct(game_data$sameGroup) < 2) return(NULL)

    tryCatch({
      model <- lmer(
        similarity ~ sameGroup + (1 | target) + (1 | speaker1) + (1 | speaker2),
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

permutation_test <- function(pairwise_df, n_perm = 1000) {
  game_ids <- unique(pairwise_df$gameId)

  results <- map_dfr(game_ids, function(gid) {
    game_data <- pairwise_df |> filter(gameId == gid)
    if (nrow(game_data) < 5) return(NULL)
    if (n_distinct(game_data$sameGroup) < 2) return(NULL)

    obs_model <- tryCatch(
      lmer(similarity ~ sameGroup + (1 | target) + (1 | speaker1) + (1 | speaker2),
           data = game_data, control = lmerControl(optimizer = "bobyqa")),
      error = function(e) NULL
    )
    if (is.null(obs_model)) return(NULL)
    obs_coef <- coef(summary(obs_model))["sameGroup", "Estimate"]

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

      tryCatch({
        perm_model <- lmer(
          similarity ~ sameGroup + (1 | target) + (1 | speaker1) + (1 | speaker2),
          data = perm_data, control = lmerControl(optimizer = "bobyqa")
        )
        coef(summary(perm_model))["sameGroup", "Estimate"]
      }, error = function(e) NA_real_)
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
                                      force = FALSE) {
  gs_cache <- file.path(cache_dir, "gs_results.rds")
  perm_cache <- file.path(cache_dir, "perm_results.rds")

  if (!force && file.exists(gs_cache) && file.exists(perm_cache)) {
    cat("Loading cached group-specificity results from", cache_dir, "\n")
    return(list(
      gs_results = readRDS(gs_cache),
      perm_results = readRDS(perm_cache)
    ))
  }

  cat("Computing group-specificity (this may take a few minutes)...\n")
  gs_results <- fit_group_specificity(pairwise_df)
  perm_results <- permutation_test(pairwise_df, n_perm = n_perm)

  saveRDS(gs_results, gs_cache)
  saveRDS(perm_results, perm_cache)
  cat("Cached results to", cache_dir, "\n")

  list(gs_results = gs_results, perm_results = perm_results)
}
