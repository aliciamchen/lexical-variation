# Tests for the tidy estimates rows in stats/R/tidy.R.

if (!exists("tidy_contrasts")) {
  source(here::here("stats", "config.R"))
}
if (!exists("check")) {
  source(here::here("stats", "tests", "check.R"))
}

tidy_df <- tibble(
  gameId = paste0("m", 1:9),
  condition = rep(
    c("refer_separated", "refer_mixed", "social_mixed"),
    each = 3
  ),
  gs_phase1 = c(0.1, 0.2, 0.3, 0.1, 0.25, 0.3, 0.12, 0.2, 0.31),
  gs_phase2 = c(0.5, 0.6, 0.7, 0.1, 0.2, 0.3, 0.4, 0.5, 0.55)
)
fit <- fit_h12(tidy_df)
sm <- as.data.frame(summary(fit$contrasts, infer = c(TRUE, TRUE)))
rows <- tidy_contrasts(fit$contrasts, "h1_h2", n_games = 9L)
check(
  "tidy_contrasts gives one row per contrast with the emmeans estimate, interval and p-value",
  nrow(rows) == 2 &&
    all(rows$kind == "contrast") &&
    identical(rows$term, as.character(sm$contrast)) &&
    all(abs(rows$estimate - sm$estimate) < 1e-12) &&
    all(abs(rows$lower - sm$lower.CL) < 1e-12) &&
    all(abs(rows$p_value - sm$p.value) < 1e-12) &&
    all(rows$n_games == 9L)
)
check(
  "a NULL contrast gives no rows",
  nrow(tidy_contrasts(NULL, "x")) == 0 &&
    nrow(tidy_contrast_table(NULL, "x")) == 0
)
tab_rows <- tidy_contrast_table(contrast_table(fit$contrasts, "label"), "h1_h2")
check(
  "tidy_contrast_table gives the same estimates from the contrast_table() form",
  all(abs(tab_rows$estimate - rows$estimate) < 1e-12) &&
    all(abs(tab_rows$upper - rows$upper) < 1e-12)
)
coefs <- tidy_coefficients(fit$model, "h1_h2")
s <- coef(summary(fit$model))
check(
  "tidy_coefficients gives every fixed effect with its statistic and p-value, and the model's n",
  nrow(coefs) == nrow(s) &&
    identical(coefs$term, rownames(s)) &&
    all(abs(coefs$estimate - s[, "Estimate"]) < 1e-12) &&
    all(abs(coefs$statistic - s[, "t value"]) < 1e-12) &&
    all(coefs$n_obs == 9L) &&
    all(is.na(coefs$odds_ratio))
)
check(
  "terms restricts the rows, and a term the model lacks gives none",
  nrow(tidy_coefficients(fit$model, "x", terms = "gs_phase1")) == 1 &&
    nrow(tidy_coefficients(fit$model, "x", terms = "not_there")) == 0 &&
    nrow(tidy_coefficients(NULL, "x")) == 0
)
logit <- glm(
  c(0, 1, 0, 1, 1, 0, 1, 1) ~ c(1, 2, 3, 4, 1, 2, 3, 4),
  family = binomial
)
lrows <- tidy_coefficients(logit, "logit")
or <- odds_ratio_table(logit)
check(
  "a logistic model's rows carry Wald odds ratios",
  all(abs(lrows$odds_ratio - or$odds_ratio) < 1e-12) &&
    all(abs(lrows$or_upper - or$upper) < 1e-12)
)
chi <- suppressWarnings(chisq.test(matrix(c(10, 5, 4, 11), 2)))
fisher <- fisher.test(matrix(c(10, 5, 4, 11), 2))
trow <- tidy_htest(chi, "dropout_players")
frow <- tidy_htest(fisher, "dropout_games")
check(
  "tidy_htest records statistic, integer df and p-value, and Fisher's test the p-value alone",
  trow$kind == "test" &&
    abs(trow$statistic - unname(chi$statistic)) < 1e-12 &&
    identical(trow$df, 1L) &&
    abs(trow$p_value - chi$p.value) < 1e-12 &&
    is.na(frow$statistic) &&
    is.na(frow$df) &&
    abs(frow$p_value - fisher$p.value) < 1e-12 &&
    nrow(tidy_htest(NULL, "x")) == 0
)

ci_lm <- stats::confint(fit$model)
check(
  "an lm coefficient carries its t interval on the residual degrees of freedom",
  all(coefs$df == stats::df.residual(fit$model)) &&
    all(abs(coefs$lower - ci_lm[, 1]) < 1e-12) &&
    all(abs(coefs$upper - ci_lm[, 2]) < 1e-12)
)
check(
  "a logistic coefficient carries the Wald interval whose exponent is the odds-ratio interval",
  all(abs(exp(lrows$lower) - lrows$or_lower) < 1e-12) &&
    all(abs(exp(lrows$upper) - lrows$or_upper) < 1e-12) &&
    all(is.na(lrows$df))
)
sleep <- lme4::sleepstudy
m_sat <- lmerTest::lmer(Reaction ~ Days + (1 | Subject), data = sleep)
srows <- tidy_coefficients(m_sat, "sleep", terms = "Days")
ssum <- coef(summary(m_sat))
check(
  "an lmer coefficient carries its t interval on the Satterthwaite degrees of freedom",
  abs(srows$df - ssum["Days", "df"]) < 1e-9 &&
    abs(
      srows$lower -
        (ssum["Days", "Estimate"] -
          stats::qt(0.975, ssum["Days", "df"]) * ssum["Days", "Std. Error"])
    ) <
      1e-9
)

# A condition-by-slope model whose groups have known, different slopes: the
# averaged slope is the mean of the three, not the reference group's.
trend_df <- tibble(
  g = factor(rep(c("a", "b", "c"), each = 20)),
  x = rep(1:20, 3)
) |>
  mutate(
    y = c(a = 1, b = 2, c = 6)[as.character(g)] *
      x +
      rep(c(0.3, -0.2, 0.1, -0.4, 0.2), 12)
  )
m_trend <- lm(y ~ g * x, data = trend_df)
overall <- tidy_trends(
  emmeans::emtrends(m_trend, ~1, var = "x"),
  "slope",
  n_games = 3L
)
by_group <- tidy_trends(emmeans::emtrends(m_trend, ~g, var = "x"), "slope")
check(
  "tidy_trends gives the averaged slope as one row named for the variable, with its interval and test",
  nrow(overall) == 1 &&
    overall$kind == "trend" &&
    overall$term == "x" &&
    abs(overall$estimate - mean(by_group$estimate)) < 1e-9 &&
    abs(overall$estimate - coef(m_trend)[["x"]]) > 1 &&
    overall$lower < overall$estimate &&
    overall$upper > overall$estimate &&
    is.finite(overall$p_value) &&
    overall$n_games == 3L
)
check(
  "tidy_trends gives one row per level, named by the level and the variable",
  identical(by_group$term, c("a x", "b x", "c x")) &&
    nrow(tidy_trends(NULL, "x")) == 0
)
