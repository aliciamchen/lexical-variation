# Tests for the preregistered random-effects simplification in mixed_models.R.
#
# Plain stopifnot checks on simulated data so no test framework is needed.
#
# Run with:
#   Rscript analysis/tests/run_all.R          # all R tests
#   Rscript analysis/tests/test_mixed_models.R

if (!exists("fit_progressively")) source(here::here("analysis", "config.R"))
if (!exists("check")) source(here::here("analysis", "tests", "check.R"))

set.seed(2026)

# ── Formula rewriting ────────────────────────────────────────────────────────

d <- expand.grid(item = factor(1:12), subj = factor(1:20))
d$x <- rnorm(nrow(d))
d$cond <- factor(sample(c("a", "b", "c"), nrow(d), replace = TRUE))
d$y <- rnorm(nrow(d))

ex <- .expand_re_lhs(quote(cond * x), d)
check(
  "factor and interaction slopes expand into dummy columns",
  setequal(ex$slopes, c("x", "condb", "condc", "condb.x", "condc.x")) &&
    all(c("condb", "condc", "condb.x", "condc.x") %in% names(ex$data)) &&
    ex$intercept
)
check(
  "dummy columns are 0/1 treatment contrasts",
  all(ex$data$condb == as.numeric(d$cond == "b"))
)

terms <- list(
  list(
    group = "item",
    intercept = TRUE,
    slopes = c("x", "condb"),
    correlated = FALSE
  ),
  list(
    group = "subj",
    intercept = TRUE,
    slopes = character(0),
    correlated = FALSE
  )
)
f <- .build_formula(y ~ cond * x, terms)
check(
  "uncorrelated terms are written as separate (0 + slope | group) terms",
  identical(
    paste(deparse(f, width.cutoff = 500), collapse = ""),
    "y ~ cond * x + (1 | item) + (0 + x | item) + (0 + condb | item) + (1 | subj)"
  )
)

# ── The procedure on data that support the maximal model ────────────────────

sim <- function(
  n_subj = 40,
  n_item = 20,
  slope_sd_subj = 1.5,
  slope_sd_item = 1.5,
  int_sd = 1,
  resid_sd = 0.5
) {
  d <- expand.grid(
    item = factor(seq_len(n_item)),
    subj = factor(seq_len(n_subj))
  )
  d$x <- rnorm(nrow(d))
  u_s <- rnorm(n_subj, 0, int_sd)
  b_s <- rnorm(n_subj, 0, slope_sd_subj)
  u_i <- rnorm(n_item, 0, int_sd)
  b_i <- rnorm(n_item, 0, slope_sd_item)
  d$y <- 1 +
    2 * d$x +
    u_s[d$subj] +
    b_s[d$subj] * d$x +
    u_i[d$item] +
    b_i[d$item] * d$x +
    rnorm(nrow(d), 0, resid_sd)
  d
}

d_rich <- sim()
m_rich <- fit_progressively(
  y ~ x + (x | subj) + (x | item),
  data = d_rich,
  verbose = FALSE
)
check(
  "a well-supported maximal model is kept as written",
  random_effects_structure(m_rich) == "maximal" &&
    nrow(simplification_log(m_rich)) == 1
)
check("the fixed effect is recovered", abs(fixef(m_rich)["x"] - 2) < 0.5)

# ── The procedure on data where a slope variance is zero ─────────────────────

d_flat <- sim(
  n_subj = 12,
  n_item = 6,
  slope_sd_subj = 0,
  slope_sd_item = 2,
  int_sd = 1,
  resid_sd = 1
)
m_flat <- fit_progressively(
  y ~ x + (x | subj) + (x | item),
  data = d_flat,
  verbose = FALSE
)
log_flat <- simplification_log(m_flat)
check(
  "a zero-variance slope forces simplification past the maximal model",
  nrow(log_flat) >= 2 &&
    log_flat$step[1] == "maximal" &&
    log_flat$outcome[1] != "converged"
)
check(
  "correlations are removed before any slope is dropped",
  log_flat$step[2] == "uncorrelated slopes"
)
if (nrow(log_flat) >= 3) {
  check(
    "the first slope dropped is the one with the smallest variance (the subject slope)",
    grepl("^drop slope subj:x", log_flat$step[3])
  )
}
check(
  "the returned model is not singular or is intercepts-only",
  !isSingular(m_flat) ||
    grepl("intercepts only", random_effects_structure(m_flat))
)
check("the returned model still has random effects", inherits(m_flat, "merMod"))
refit <- lme4::lmer(
  formula(m_flat),
  data = m_flat@frame,
  control = lmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 1e5))
)
check(
  "the returned fit equals a direct fit of its final formula with the same optimizer",
  abs(fixef(m_flat)["x"] - fixef(refit)["x"]) < 1e-4
)

# ── Factor slopes ────────────────────────────────────────────────────────────

d_fac <- d_rich
d_fac$cond <- factor(rep(c("a", "b"), length.out = nrow(d_fac)))
d_fac$y <- d_fac$y + as.numeric(d_fac$cond == "b") * 0.5
m_fac <- fit_progressively(
  y ~ cond + (cond | item) + (1 | subj),
  data = d_fac,
  verbose = FALSE
)
check(
  "factor slopes fit through the procedure and return a mixed model",
  inherits(m_fac, "merMod") && "condb" %in% names(fixef(m_fac))
)

# ── The end of the procedure ─────────────────────────────────────────────────

d_one <- d_rich
d_one$subj <- factor("only")
err <- tryCatch(
  fit_progressively(y ~ x + (x | subj), data = d_one, verbose = FALSE),
  error = function(e) e
)
check(
  "a grouping factor with one level is an error, not a silent fixed-effects fit",
  inherits(err, "error") &&
    grepl("intercepts-only model could not be fit", conditionMessage(err))
)
m_fixed <- fit_progressively(
  y ~ x + (x | subj),
  data = d_one,
  verbose = FALSE,
  fallback = "fixed"
)
check(
  "the explicit fallback returns an lm flagged as having no random effects",
  inherits(m_fixed, "lm") &&
    grepl("NO RANDOM EFFECTS", random_effects_structure(m_fixed))
)

# ── glmer path ───────────────────────────────────────────────────────────────

d_bin <- sim(
  n_subj = 30,
  n_item = 10,
  slope_sd_subj = 0.3,
  slope_sd_item = 0.3,
  resid_sd = 1
)
d_bin$yb <- rbinom(
  nrow(d_bin),
  1,
  plogis(0.5 * d_bin$x + (as.numeric(d_bin$subj) %% 3 - 1))
)
m_bin <- fit_progressively(
  yb ~ x + (x | subj) + (x | item),
  data = d_bin,
  family = binomial,
  verbose = FALSE
)
check(
  "the binomial path returns a glmer fit with a simplification log",
  inherits(m_bin, "glmerMod") && is.data.frame(simplification_log(m_bin))
)

cat("\nAll mixed_models.R tests passed.\n")
