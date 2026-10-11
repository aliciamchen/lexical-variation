# Tests for the tidy estimates rows in models/R/tidy.R.

if (!exists("tidy_contrasts")) {
  source(here::here("models", "config.R"))
}
if (!exists("check")) {
  source(here::here("models", "tests", "check.R"))
}

tidy_df <- tibble(
  gameId = paste0("m", 1:9),
  condition = rep(c("refer_separated", "refer_mixed", "social_mixed"), each = 3),
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
  nrow(tidy_contrasts(NULL, "x")) == 0 && nrow(tidy_contrast_table(NULL, "x")) == 0
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
logit <- glm(c(0, 1, 0, 1, 1, 0, 1, 1) ~ c(1, 2, 3, 4, 1, 2, 3, 4), family = binomial)
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
    is.na(frow$statistic) && is.na(frow$df) &&
    abs(frow$p_value - fisher$p.value) < 1e-12 &&
    nrow(tidy_htest(NULL, "x")) == 0
)
