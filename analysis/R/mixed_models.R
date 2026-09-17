# Mixed-effects model fitting with the preregistered simplification procedure.
#
# The preregistration (writing/preregistration/main.tex, "Analysis plan") commits to the maximal
# random-effects structure supported by the design, simplified only when a
# model fails to converge: first by removing the correlations between random
# effects, then by removing random slopes starting with the smallest variance
# component (Barr et al., 2013). `fit_progressively()` implements exactly that
# sequence for a single maximal formula and records every step it took, so a
# notebook can report which structure the reported estimates come from.
#
# Definitions used here:
#   - "fails to converge" means the fit raised an error, lme4 issued a
#     convergence warning, or the fit is singular (`isSingular()`): a variance
#     component estimated at zero or a correlation at +/-1 means the structure
#     is not supported by the data.
#   - Correlations are removed by expanding every random-effects term into an
#     intercept term plus one uncorrelated term per slope column. Factor
#     slopes are expanded into their treatment-contrast dummy columns first
#     (lme4's `||` syntax leaves factor slopes correlated), which also lets the
#     slope for each level be dropped on its own.
#   - Slopes are dropped one at a time, always the one with the smallest
#     estimated variance in the last fit that produced variance estimates.
#   - Random intercepts are never dropped. The preregistration specifies game
#     and original-group intercepts in several models and commits to retaining
#     them during simplification; here every intercept term in the maximal
#     formula (for any grouping factor) survives every step, because the
#     procedure only removes correlations and slopes. A grouping factor that
#     appears with slopes but without an intercept, `(0 + x | g)`, keeps that
#     form and loses only the slope.
#   - The random-intercepts-only model is the end of the procedure: it is
#     returned even if singular (a zero intercept variance is a valid, if
#     uninformative, estimate), with the problem recorded in the log. There is
#     no silent fall-back to a model without random effects; if even the
#     intercepts-only model cannot be fit (for example a grouping factor with
#     a single level), the function stops unless `fallback = "fixed"` is asked
#     for explicitly, in which case an lm/glm is returned and flagged.
#
# Usage:
#   m <- fit_progressively(y ~ x + (x | group) + (x | item), data = d)
#   simplification_log(m)      # data frame of the steps taken
#   summary(m)
#
# Tests: analysis/tests/test_mixed_models.R (Rscript analysis/tests/run_all.R)

suppressPackageStartupMessages({
  library(lme4)
})

.re_findbars <- function(f) {
  if (requireNamespace("reformulas", quietly = TRUE)) {
    reformulas::findbars(f)
  } else {
    lme4::findbars(f)
  }
}
.re_nobars <- function(f) {
  if (requireNamespace("reformulas", quietly = TRUE)) {
    reformulas::nobars(f)
  } else {
    lme4::nobars(f)
  }
}

# ── Random-effects term bookkeeping ───────────────────────────────────────────
#
# A term is a list(group = "g", intercept = TRUE, slopes = c("col1", ...),
# correlated = TRUE/FALSE); `slopes` are column names in the (augmented) data.

.parse_re_terms <- function(formula) {
  lapply(.re_findbars(formula), function(bar) {
    lhs <- bar[[2]]
    grp <- deparse(bar[[3]])
    list(group = grp, lhs = lhs, correlated = TRUE)
  })
}

# Expand the left-hand side of one random-effects term into numeric slope
# columns, adding dummy columns to `data` where needed. Returns list(data,
# intercept, slopes).
.expand_re_lhs <- function(lhs, data) {
  f <- stats::as.formula(paste("~", deparse(lhs)))
  mm <- stats::model.matrix(f, data = data)
  cols <- colnames(mm)
  has_intercept <- "(Intercept)" %in% cols
  cols <- setdiff(cols, "(Intercept)")
  slopes <- character(0)
  for (col in cols) {
    if (col %in% names(data) && is.numeric(data[[col]])) {
      slopes <- c(slopes, col) # a numeric predictor used as is
    } else {
      new_name <- make.names(col)
      if (!new_name %in% names(data)) {
        # model.matrix drops rows with NA; align by row name
        v <- rep(NA_real_, nrow(data))
        v[match(rownames(mm), rownames(data))] <- mm[, col]
        data[[new_name]] <- v
      }
      slopes <- c(slopes, new_name)
    }
  }
  list(data = data, intercept = has_intercept, slopes = slopes)
}

.re_term_text <- function(term) {
  if (term$correlated) {
    parts <- c(if (term$intercept) "1" else "0", term$slopes)
    return(sprintf("(%s | %s)", paste(parts, collapse = " + "), term$group))
  }
  pieces <- character(0)
  if (term$intercept) {
    pieces <- c(pieces, sprintf("(1 | %s)", term$group))
  }
  for (s in term$slopes) {
    pieces <- c(pieces, sprintf("(0 + %s | %s)", s, term$group))
  }
  if (length(pieces) == 0) {
    return(NULL)
  }
  paste(pieces, collapse = " + ")
}

.build_formula <- function(fixed, terms, env = parent.frame()) {
  fixed_txt <- paste(deparse(fixed, width.cutoff = 500), collapse = " ")
  re_txt <- unlist(lapply(terms, .re_term_text))
  re_txt <- re_txt[!vapply(re_txt, is.null, logical(1))]
  txt <- if (length(re_txt)) {
    paste(fixed_txt, "+", paste(re_txt, collapse = " + "))
  } else {
    fixed_txt
  }
  stats::as.formula(txt, env = env)
}

# ── One fit, with convergence problems captured ───────────────────────────────

.default_control <- function(family) {
  if (is.null(family)) {
    lmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 1e5))
  } else {
    glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 1e5))
  }
}

.fit_once <- function(formula, data, family, control) {
  warnings <- character(0)
  model <- tryCatch(
    withCallingHandlers(
      {
        if (is.null(family)) {
          if (requireNamespace("lmerTest", quietly = TRUE)) {
            lmerTest::lmer(formula, data = data, control = control)
          } else {
            lme4::lmer(formula, data = data, control = control)
          }
        } else {
          lme4::glmer(formula, data = data, family = family, control = control)
        }
      },
      message = function(m) {
        if (grepl("singular", conditionMessage(m))) {
          invokeRestart("muffleMessage")
        }
      },
      warning = function(w) {
        warnings <<- c(warnings, conditionMessage(w))
        invokeRestart("muffleWarning")
      }
    ),
    error = function(e) {
      structure(list(message = conditionMessage(e)), class = "fit_error")
    }
  )
  if (inherits(model, "fit_error")) {
    return(list(
      model = NULL,
      ok = FALSE,
      problem = paste("error:", model$message)
    ))
  }
  conv <- c(warnings, unlist(model@optinfo$conv$lme4$messages))
  conv <- unique(conv[grepl(
    "converge|Hessian|gradient|eigenvalue|rescale|scale",
    conv,
    ignore.case = TRUE
  )])
  singular <- isSingular(model)
  problem <- c(
    if (length(conv)) paste("convergence:", paste(conv, collapse = "; ")),
    if (singular) "singular fit"
  )
  list(
    model = model,
    ok = length(problem) == 0,
    problem = if (length(problem)) {
      paste(problem, collapse = "; ")
    } else {
      "converged"
    }
  )
}

# Variance of each random slope in a fitted (uncorrelated) model, keyed by
# "group:slope"; intercepts are excluded.
.slope_variances <- function(model) {
  vc <- VarCorr(model)
  out <- c()
  for (nm in names(vc)) {
    block <- vc[[nm]]
    grp <- sub("\\.[0-9]+$", "", nm) # lme4 suffixes repeated groups g, g.1, g.2
    vars <- diag(as.matrix(block))
    for (slope in setdiff(names(vars), "(Intercept)")) {
      out[paste(grp, slope, sep = ":")] <- unname(vars[slope])
    }
  }
  out
}

# ── The procedure ─────────────────────────────────────────────────────────────

fit_progressively <- function(
  formula,
  data,
  family = NULL,
  control = NULL,
  verbose = TRUE,
  fallback = c("error", "fixed")
) {
  fallback <- match.arg(fallback)
  control <- if (is.null(control)) .default_control(family) else control
  data <- as.data.frame(data)
  fixed <- .re_nobars(formula)
  env <- environment(formula)
  if (is.null(env)) {
    env <- parent.frame()
  }

  log <- data.frame(
    step = character(0),
    formula = character(0),
    outcome = character(0),
    stringsAsFactors = FALSE
  )
  note <- function(step, f, outcome) {
    log[nrow(log) + 1, ] <<- list(
      step,
      paste(deparse(f, width.cutoff = 500), collapse = " "),
      outcome
    )
    if (verbose) cat(sprintf("[%s] %s\n", step, outcome))
  }
  finish <- function(model, structure) {
    attr(model, "simplification") <- log
    attr(model, "random_effects_structure") <- structure
    if (verbose && nrow(log) > 1) {
      cat(sprintf("Reported model: %s\n", structure))
    }
    model
  }

  # Step 1: the maximal model as written
  fit <- .fit_once(formula, data, family, control)
  note("maximal", formula, fit$problem)
  if (fit$ok) {
    return(finish(fit$model, "maximal"))
  }

  # Step 2: remove correlations between random effects
  terms <- .parse_re_terms(formula)
  if (length(terms) == 0) {
    stop(
      "fit_progressively: the formula has no random effects; use lm/glm directly."
    )
  }
  for (i in seq_along(terms)) {
    ex <- .expand_re_lhs(terms[[i]]$lhs, data)
    data <- ex$data
    terms[[i]]$intercept <- ex$intercept
    terms[[i]]$slopes <- ex$slopes
    terms[[i]]$correlated <- FALSE
  }
  has_slopes <- function(ts) {
    any(vapply(ts, function(t) length(t$slopes) > 0, logical(1)))
  }
  last_variances <- NULL

  if (has_slopes(terms)) {
    f <- .build_formula(fixed, terms, env)
    fit <- .fit_once(f, data, family, control)
    note("uncorrelated slopes", f, fit$problem)
    if (fit$ok) {
      return(finish(fit$model, "uncorrelated random slopes"))
    }
    if (!is.null(fit$model)) last_variances <- .slope_variances(fit$model)
  }

  # Step 3: drop random slopes, smallest variance component first
  while (has_slopes(terms)) {
    all_slopes <- unlist(lapply(terms, function(t) {
      paste(t$group, t$slopes, sep = ":")
    }))
    if (
      !is.null(last_variances) && any(all_slopes %in% names(last_variances))
    ) {
      cand <- last_variances[intersect(all_slopes, names(last_variances))]
      victim <- names(cand)[which.min(cand)]
    } else {
      victim <- all_slopes[length(all_slopes)] # no variance estimates available (fit errored)
    }
    grp <- sub(":.*$", "", victim)
    slope <- sub("^[^:]*:", "", victim)
    for (i in seq_along(terms)) {
      if (terms[[i]]$group == grp) {
        terms[[i]]$slopes <- setdiff(terms[[i]]$slopes, slope)
      }
    }
    f <- .build_formula(fixed, terms, env)
    fit <- .fit_once(f, data, family, control)
    note(sprintf("drop slope %s", victim), f, fit$problem)
    if (fit$ok) {
      return(finish(
        fit$model,
        if (has_slopes(terms)) {
          "reduced random slopes"
        } else {
          "random intercepts only"
        }
      ))
    }
    if (!is.null(fit$model)) last_variances <- .slope_variances(fit$model)
  }

  # Step 4: random intercepts only is the end of the procedure
  if (!is.null(fit$model)) {
    if (verbose) {
      cat(sprintf(
        "Random-intercepts-only model kept despite: %s\n",
        fit$problem
      ))
    }
    return(finish(fit$model, paste("random intercepts only;", fit$problem)))
  }

  msg <- sprintf(
    "fit_progressively: even the random-intercepts-only model could not be fit (%s).",
    fit$problem
  )
  if (fallback == "error") {
    stop(msg, call. = FALSE)
  }
  if (verbose) {
    cat(
      msg,
      "\nFalling back to a model WITHOUT random effects; do not report this as the preregistered model.\n"
    )
  }
  model <- if (is.null(family)) {
    stats::lm(fixed, data = data)
  } else {
    stats::glm(fixed, data = data, family = family)
  }
  note("fixed effects only", fixed, "fallback")
  finish(model, "NO RANDOM EFFECTS (fallback)")
}

simplification_log <- function(model) {
  attr(model, "simplification")
}

# The grouping factors that carry a random intercept in a formula (or a fitted
# merMod). Used to check that simplification retained every specified
# intercept term.
re_intercept_groups <- function(x) {
  f <- if (inherits(x, "merMod")) formula(x) else x
  bars <- .re_findbars(f)
  keep <- vapply(
    bars,
    function(bar) {
      lhs <- bar[[2]]
      # An intercept is present unless the left-hand side removes it with 0 or -1
      txt <- paste(deparse(lhs), collapse = "")
      !grepl("(^|\\+)\\s*0\\s*(\\+|$)|-\\s*1", txt)
    },
    logical(1)
  )
  unique(vapply(bars[keep], function(bar) deparse(bar[[3]]), character(1)))
}

random_effects_structure <- function(model) {
  attr(model, "random_effects_structure")
}
