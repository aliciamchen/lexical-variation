# Secondary analysis 4: in the two social conditions, do games whose
# listeners identify speakers' groups more accurately also keep more
# group-specific language, after accounting for Phase 1 group-specificity?
# The preregistered game-level regression
#
#   gs_phase2 ~ social_accuracy + gs_phase1
#
# by ordinary least squares over the games with both endpoints, without a
# condition term (the plan specifies an association across the two social
# conditions, not a comparison between them). The inverse-variance rerun
# (weights 1 / SE_phase2^2) is the robustness check. A positive coefficient
# is an association conditional on baseline specificity, not a causal claim.
# The per-game estimates come from models/primary/group_specificity.R.
#
# Writes results/<dataset>/estimates/secondary/specificity_vs_social_accuracy.csv:
# the social-accuracy coefficient of the OLS and the weighted fit.

source(here::here("models", "config.R"))
list2env(load_tables(), envir = globalenv())

if (!has_rows(social_guesses)) {
  stop("No social guess data.", call. = FALSE)
}
gs <- gs_wide(require_estimates("primary/group_specificity", "models/primary/group_specificity.R"))

# Mean social accuracy per game over eligible response opportunities
social_acc_by_game <- social_guess_trials(social_guesses, games) |>
  group_by(gameId) |>
  summarise(social_accuracy = mean(correct, na.rm = TRUE), .groups = "drop")
gs_social <- gs |> inner_join(social_acc_by_game, by = "gameId")

fit_gs_social <- function(weights = NULL) {
  fit_game_level(
    gs_social,
    outcome = "gs_phase2",
    predictors = c("social_accuracy", "gs_phase1"),
    conditions = SOCIAL_CONDITIONS,
    weights = weights,
    include_condition = FALSE
  )
}
ols <- fit_gs_social()
if (is.null(ols$model) || nrow(ols$data) < 4) {
  stop("Not enough games in the two social conditions for the regression",
       if (!is.null(ols$note)) paste0(" (", ols$note, ")"), call. = FALSE)
}
cat(sprintf("Games in the model: %d\n", nrow(ols$data)))
print(knitr::kable(ols$data |> count(condition, name = "games")))
print(summary(ols$model))
report_effect_sizes(ols$model)

# broom's interval is the t-based confidence interval of the coefficient
social_accuracy_row <- function(fit, analysis) {
  if (is.null(fit$model)) {
    return(tibble())
  }
  co <- broom::tidy(fit$model, conf.int = TRUE) |> filter(term == "social_accuracy")
  tidy_coefficients(fit$model, analysis, terms = "social_accuracy", n_games = nrow(fit$data)) |>
    mutate(lower = co$conf.low, upper = co$conf.high)
}
rows <- social_accuracy_row(ols, "specificity_vs_social_accuracy")
cat(sprintf(
  "\nSocial accuracy coefficient (OLS): %.3f, 95%% CI [%.3f, %.3f], p = %s\n",
  rows$estimate, rows$lower, rows$upper, fmt_pval(rows$p_value)
))
wls <- fit_gs_social(weights = "weight")
if (!is.null(wls$model)) {
  wls_row <- social_accuracy_row(wls, "specificity_vs_social_accuracy_wls")
  cat(sprintf(
    "Robustness, inverse-variance weights (1 / SE_phase2^2): %.3f, 95%% CI [%.3f, %.3f], p = %s\n",
    wls_row$estimate, wls_row$lower, wls_row$upper, fmt_pval(wls_row$p_value)
  ))
  rows <- bind_rows(rows, wls_row)
}
write_estimates(rows, "secondary/specificity_vs_social_accuracy",
                source = "models/secondary/specificity_vs_social_accuracy.R")
