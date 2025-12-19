library(lme4)

fit_group_specificity_by_game <- function(pairwise_df, condition_name) {
  games <- unique(pairwise_df$gameId)
  results <- data.frame()

  for (game in games) {
    game_data <- pairwise_df[pairwise_df$gameId == game, ]

    if (nrow(game_data) < 5) next
    if (length(unique(game_data$same_group)) < 2) next

    tryCatch(
      {
        model <- lmer(similarity ~ same_group + (1 | target) + (1 | participant_pair),
          data = game_data
        )

        coefs <- coef(summary(model))

        results <- rbind(results, data.frame(
          gameId = game,
          condition = condition_name,
          coefficient = coefs["same_group", "Estimate"],
          std_error = coefs["same_group", "Std. Error"],
          t_value = coefs["same_group", "t value"],
          n_pairs = nrow(game_data)
        ))
      },
      error = function(e) {
        message(paste("Warning: Could not fit model for game", game, ":", e$message))
      }
    )
  }

  cat(paste0("\n=== ", condition_name, " Condition ===\n"))
  cat(paste0("Games with fitted models: ", nrow(results), "\n"))
  cat(paste0("Mean coefficient: ", round(mean(results$coefficient), 4), "\n"))
  cat(paste0("SD coefficient: ", round(sd(results$coefficient), 4), "\n"))
  cat(paste0(
    "Range: [", round(min(results$coefficient), 4), ", ",
    round(max(results$coefficient), 4), "]\n"
  ))

  return(results)
}

pairwise_mixed <- read.csv("analysis/pairwise_mixed.csv")
pairwise_separate <- read.csv("analysis/pairwise_separate.csv")

results_mixed <- fit_group_specificity_by_game(pairwise_mixed, "Mixed")
results_separate <- fit_group_specificity_by_game(pairwise_separate, "Separate")

write.csv(results_mixed, "analysis/results_mixed.csv", row.names = FALSE)
write.csv(results_separate, "analysis/results_separate.csv", row.names = FALSE)
