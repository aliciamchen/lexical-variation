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

# Cohen's d between two conditions on game-level estimates (the unit of the
# weighted regressions for H1, H2, and H3a), with a pooled SD and 95% CI.
# This is the unadjusted between-condition difference that the power analysis
# was based on; the WLS contrast remains the inferential test. Returns NA when
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
