library(lme4)
library(dplyr)

fit_group_specificity_by_game <- function(pairwise_df, condition_name) {
  games <- unique(pairwise_df$gameId)

  results <- purrr::map_dfr(games, function(game) {
    game_data <- pairwise_df |> filter(gameId == game)

    # Skip if not enough data
    if (nrow(game_data) < 5) return(NULL)
    if (n_distinct(game_data$same_group) < 2) return(NULL)

    # Capture warnings during model fitting
    warnings_list <- character(0)
    model <- tryCatch(
      withCallingHandlers(
        lmer(similarity ~ same_group + (1 | target) + (1 | participant_pair),
             data = game_data),
        warning = function(w) {
          warnings_list <<- c(warnings_list, conditionMessage(w))
          invokeRestart("muffleWarning")
        }
      ),
      error = function(e) {
        message(paste("Error fitting model for game", game, ":", e$message))
        return(NULL)
      }
    )

    if (is.null(model)) return(NULL)

    coefs <- coef(summary(model))

    # Check for convergence issues
    convergence_warning <- any(grepl("converg|singular", warnings_list, ignore.case = TRUE))

    tibble(
      gameId = game,
      condition = condition_name,
      coefficient = coefs["same_group", "Estimate"],
      std_error = coefs["same_group", "Std. Error"],
      t_value = coefs["same_group", "t value"],
      n_pairs = nrow(game_data),
      n_targets = n_distinct(game_data$target),
      n_participant_pairs = n_distinct(game_data$participant_pair),
      convergence_warning = convergence_warning,
      warnings = paste(warnings_list, collapse = "; ")
    )
  })

  # Print summary
  cat(paste0("\n=== ", condition_name, " Condition ===\n"))
  cat(paste0("Games with fitted models: ", nrow(results), "\n"))
  cat(paste0("Mean coefficient: ", round(mean(results$coefficient), 4), "\n"))
  cat(paste0("SD coefficient: ", round(sd(results$coefficient), 4), "\n"))
  cat(paste0("Range: [", round(min(results$coefficient), 4), ", ",
             round(max(results$coefficient), 4), "]\n"))

  # Report convergence issues
  n_convergence_issues <- sum(results$convergence_warning)
  if (n_convergence_issues > 0) {
    cat(paste0("WARNING: ", n_convergence_issues, " models had convergence warnings\n"))
  }

  # Validate n_pairs: should be C(n_speakers, 2) * n_targets
  # For 6 players: C(6,2) = 15 pairs per target
  # For 12 targets: 15 * 12 = 180 pairs
  cat(paste0("n_pairs per game: ", paste(unique(results$n_pairs), collapse = ", "), "\n"))

  return(results)
}

pairwise_mixed <- read.csv("analysis/power_analysis/pairwise_mixed.csv")
pairwise_separate <- read.csv("analysis/power_analysis/pairwise_separate.csv")

results_mixed <- fit_group_specificity_by_game(pairwise_mixed, "Mixed")
results_separate <- fit_group_specificity_by_game(pairwise_separate, "Separate")

write.csv(results_mixed, "analysis/power_analysis/results_mixed.csv", row.names = FALSE)
write.csv(results_separate, "analysis/power_analysis/results_separate.csv", row.names = FALSE)
