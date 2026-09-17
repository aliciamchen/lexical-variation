# Effect sizes and p-value formatting shared by the notebooks.

suppressPackageStartupMessages(library(effectsize))

fmt_pval <- function(p) {
  if (is.na(p)) {
    return("NA")
  }
  if (p < .001) {
    return("< .001")
  }
  sub("^0", "", sprintf("%.3f", p))
}

report_effect_sizes <- function(model) {
  cat("\nStandardized parameters (effect sizes):\n")
  std_params <- standardize_parameters(model, method = "basic")
  print(std_params)
  invisible(std_params)
}

# Odds ratios for the fixed effects of a logistic model (glmer or glm), the
# effect size the preregistration names for binary outcomes, with Wald
# confidence intervals on the log-odds scale exponentiated.
odds_ratio_table <- function(model, level = 0.95) {
  b <- if (inherits(model, "merMod")) lme4::fixef(model) else coef(model)
  se <- sqrt(diag(as.matrix(vcov(model))))
  z <- qnorm(1 - (1 - level) / 2)
  tibble(
    term = names(b),
    log_odds = unname(b),
    odds_ratio = exp(unname(b)),
    lower = exp(unname(b) - z * se),
    upper = exp(unname(b) + z * se),
    p.value = 2 * pnorm(-abs(unname(b) / se))
  )
}

report_odds_ratios <- function(model, level = 0.95) {
  cat(sprintf("\nOdds ratios (Wald %.0f%% CI):\n", 100 * level))
  tab <- odds_ratio_table(model, level)
  print(knitr::kable(tab, digits = 3))
  invisible(tab)
}

# Cohen's d between two conditions on game-level estimates (the unit of the
# equal-weight regressions for H1, H2, and H3a), with a pooled SD and 95% CI.
# This is the unadjusted between-condition difference that the power analysis
# was based on; the OLS contrast remains the inferential test. Returns NA when
# either condition has fewer than two games (e.g. the pilot).
cohens_d_games <- function(df, value, condition, a, b) {
  x <- df[[value]][df[[condition]] == a]
  y <- df[[value]][df[[condition]] == b]
  if (length(x) < 2 || length(y) < 2) {
    return(data.frame(
      contrast = paste(a, "-", b),
      d = NA_real_,
      CI_low = NA_real_,
      CI_high = NA_real_,
      note = "not estimable with fewer than two games per condition"
    ))
  }
  es <- effectsize::cohens_d(x, y, pooled_sd = TRUE)
  data.frame(
    contrast = paste(a, "-", b),
    d = es$Cohens_d,
    CI_low = es$CI_low,
    CI_high = es$CI_high,
    note = ""
  )
}
