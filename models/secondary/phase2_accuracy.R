# Secondary analysis 2: referential accuracy in Phase 2. Three preregistered
# predictions: accuracy above chance (1/16) in every condition, a positive
# block effect, and the ordering refer_separated > refer_mixed > social_mixed
# > social_first. The listener-trial model is
#
#   correct ~ condition * blockNum_c + (blockNum_c | gameId) + (blockNum_c | playerId)
#                                    + (1 | target) + (1 | gameId:target)
#
# where the item cell is game by tangram rather than group by tangram: in the
# mixed conditions the listener is usually not from the speaker's original
# group, so what matters is whether the game as a whole has converged on a
# figure. The ordering is tested as consecutive contrasts of the condition
# marginal means at the mean block, on the log-odds scale.
#
# Writes results/estimates/secondary/phase2_accuracy.csv (the
# ordering contrasts and the block slope), secondary/phase2_accuracy_coefficients.csv
# and secondary/phase2_accuracy_by_condition.csv (each condition's estimated
# accuracy with its one-sided test against chance).

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

p2_listener <- listener_trials(trials, games, phase = 2)
n_cond <- n_distinct(p2_listener$condition)
n_games <- n_distinct(p2_listener$gameId)
if (n_cond < 2 || n_games < 2) {
  stop("The Phase 2 accuracy model needs at least two conditions and two games.", call. = FALSE)
}

m_ref_accuracy <- fit_progressively(
  correct ~ condition * blockNum_c + (blockNum_c | gameId) + (blockNum_c | playerId) +
    (1 | target) + (1 | gameId:target),
  data = p2_listener,
  family = binomial
)
print(summary(m_ref_accuracy))
report_effect_sizes(m_ref_accuracy)

rows <- tibble()
by_condition <- tibble()
if (inherits(m_ref_accuracy, "glmerMod")) {
  em_acc <- emmeans(m_ref_accuracy, "condition") # at the mean block
  cat("\nAbove chance? One-sided test of each condition's accuracy against 1/16 (logit scale):\n")
  chance_tests <- as.data.frame(test(em_acc, null = qlogis(1 / 16), side = ">"))
  print(chance_tests)
  cat("\nEstimated accuracy by condition (response scale):\n")
  acc_response <- as.data.frame(summary(em_acc, type = "response"))
  print(acc_response)
  by_condition <- acc_response |>
    transmute(condition = as.character(condition), accuracy = prob, std_error = SE,
              lower = asymp.LCL, upper = asymp.UCL) |>
    left_join(
      chance_tests |> transmute(condition = as.character(condition), log_odds = emmean,
                                z_vs_chance = z.ratio, p_vs_chance = p.value),
      by = "condition"
    )

  cat("\nBlock slope averaged over conditions (log-odds per block), then per condition:\n")
  print(test(emtrends(m_ref_accuracy, ~ 1, var = "blockNum_c")))
  print(test(emtrends(m_ref_accuracy, ~ condition, var = "blockNum_c")))

  lv <- levels(droplevels(p2_listener$condition))
  ordering <- list()
  if (all(c("refer_separated", "refer_mixed") %in% lv)) ordering$sep_gt_mixed <- pairwise_weights(lv, "refer_separated", "refer_mixed")
  if (all(c("refer_mixed", "social_mixed") %in% lv)) ordering$mixed_gt_social <- pairwise_weights(lv, "refer_mixed", "social_mixed")
  if (all(c("social_mixed", "social_first") %in% lv)) ordering$social_gt_socialfirst <- pairwise_weights(lv, "social_mixed", "social_first")
  if (length(ordering)) {
    ordering_contrasts <- contrast(em_acc, ordering)
    cat("\nPredicted ordering, consecutive contrasts (positive = predicted direction, log-odds):\n")
    print(summary(ordering_contrasts, infer = c(TRUE, TRUE)))
    rows <- tidy_contrasts(ordering_contrasts, "phase2_accuracy_ordering", scale = "log_odds",
                           n_obs = nobs(m_ref_accuracy), n_games = n_games,
                           random_effects = random_effects_structure(m_ref_accuracy))
  }
} else {
  cat("\nThe preregistered accuracy tests need the condition-by-block mixed model.\n")
}
rows <- bind_rows(
  rows,
  tidy_coefficients(m_ref_accuracy, "phase2_accuracy", terms = "blockNum_c", n_games = n_games)
)

write_estimates(rows, "secondary/phase2_accuracy", source = "models/secondary/phase2_accuracy.R")
write_estimates(tidy_coefficients(m_ref_accuracy, "phase2_accuracy", n_games = n_games),
                "secondary/phase2_accuracy_coefficients", source = "models/secondary/phase2_accuracy.R")
write_estimates(by_condition, "secondary/phase2_accuracy_by_condition", source = "models/secondary/phase2_accuracy.R")
