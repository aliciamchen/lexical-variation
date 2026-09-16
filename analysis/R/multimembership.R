# Multiple-membership speaker intercept for the pairwise-similarity model.
#
# Each observation is a pair of speakers describing the same tangram, so a
# speaker appears in many rows, sometimes as speaker1 and sometimes as
# speaker2. The earlier model gave the two pair positions separate random
# intercepts, `(1 | speaker1) + (1 | speaker2)`, which splits one person's
# effect across two variance components and makes the fit depend on an
# arbitrary ordering within each pair. The preregistered structure instead
# gives every speaker one random effect shared across both positions, with a
# common variance and equal weights of 1/2:
#
#   similarity ~ same_group + (1 | target) + (1 | speaker[multiple membership])
#
# lme4 has no formula syntax for this, but it does not need one: a multiple
# membership term is an ordinary scalar random effect whose transposed design
# matrix Zt holds two nonzero entries per observation instead of one. So the
# model is built through lme4's modular interface (lFormula -> mkLmerDevfun ->
# optimizeLmer -> mkMerMod), replacing that one block of Zt and leaving
# Lambdat, Lind, theta, and the bounds untouched. Fitting is by REML, as the
# preregistration specifies.
#
# The GitHub-only lmerMultiMember package does the same thing in general form.
# It is deliberately not a dependency here: the analysis has to be
# reproducible from renv.lock by reviewers, and this case (a scalar intercept,
# exactly two members, fixed equal weights) is small enough to own outright.
#
# Tests: analysis/tests/test_multimembership.R
# Design-matched simulations: analysis/simulate_mm_speaker.R

suppressPackageStartupMessages({
  library(lme4)
  library(Matrix)
})

MM_PLACEHOLDER <- ".mm_group"

#' Membership weight matrix for a two-member multiple-membership term.
#'
#' @param members  A list of character vectors, one per observation, naming
#'   that observation's members. Every vector must be the same length.
#' @param levels   The full set of member ids, in the order the random
#'   effects should be indexed.
#' @return A sparse (levels x observations) matrix whose columns each sum to
#'   1, with equal weight on each member.
membership_weights <- function(members, levels) {
  n <- length(members)
  sizes <- lengths(members)
  if (n == 0L) {
    stop("No observations to build memberships from.", call. = FALSE)
  }
  if (any(sizes == 0L)) {
    stop("Every observation needs at least one member.", call. = FALSE)
  }
  flat <- unlist(members, use.names = FALSE)
  idx <- match(flat, levels)
  if (anyNA(idx)) {
    stop(
      "Members absent from `levels`: ",
      paste(unique(flat[is.na(idx)]), collapse = ", "),
      call. = FALSE
    )
  }
  # Equal weights summing to 1 per observation: 1/2 each for a speaker pair.
  sparseMatrix(
    i = idx,
    j = rep(seq_len(n), times = sizes),
    x = rep(1 / sizes, times = sizes),
    dims = c(length(levels), n),
    dimnames = list(levels, NULL)
  )
}

#' The weight matrix for an unordered pair of speakers, 1/2 each.
speaker_pair_weights <- function(speaker1, speaker2, levels = NULL) {
  if (length(speaker1) != length(speaker2)) {
    stop("speaker1 and speaker2 must be the same length.", call. = FALSE)
  }
  if (is.null(levels)) {
    levels <- sort(unique(c(speaker1, speaker2)))
  }
  if (any(speaker1 == speaker2)) {
    stop(
      "A pair cannot have the same speaker in both positions.",
      call. = FALSE
    )
  }
  membership_weights(
    Map(c, as.character(speaker1), as.character(speaker2)),
    levels
  )
}

#' Fit an lmer model in which one grouping factor is a multiple-membership term.
#'
#' @param formula   An ordinary lmer formula containing `(1 | <name>)`, where
#'   `<name>` is the name used in `memberships`. The column itself need not
#'   exist in `data`; a placeholder is added so lme4 can build a scalar term
#'   with the right number of levels, and its block of Zt is then replaced.
#' @param data      The model frame.
#' @param memberships  A named list of weight matrices, as returned by
#'   `speaker_pair_weights()`. Each must have one column per row of `data`.
#' @param REML      Restricted maximum likelihood, the preregistered default.
#' @return A merMod. `coef(summary(.))` gives the fixed effects with standard
#'   errors; `ranef(.)` is indexed by member, not by pair position.
lmer_multimember <- function(
  formula,
  data,
  memberships,
  REML = TRUE,
  control = lmerControl(optimizer = "bobyqa")
) {
  stopifnot(
    is.list(memberships),
    length(memberships) >= 1L,
    !is.null(names(memberships))
  )

  # A placeholder grouping column per membership term, carrying the right
  # levels in the right order. Its values are arbitrary: every entry of the
  # block is overwritten below. Using level 1 everywhere would make lme4 drop
  # the unused levels, so cycle through them instead.
  for (nm in names(memberships)) {
    w <- memberships[[nm]]
    if (ncol(w) != nrow(data)) {
      stop(
        "Membership matrix '",
        nm,
        "' has ",
        ncol(w),
        " columns for ",
        nrow(data),
        " observations.",
        call. = FALSE
      )
    }
    levs <- rownames(w)
    data[[nm]] <- factor(
      levs[(seq_len(nrow(data)) - 1L) %% length(levs) + 1L],
      levels = levs
    )
  }

  lf <- lFormula(formula, data = data, REML = REML, control = control)
  terms_by_name <- names(lf$reTrms$cnms)
  Gp <- lf$reTrms$Gp

  for (nm in names(memberships)) {
    i <- which(terms_by_name == nm)
    if (length(i) != 1L) {
      stop(
        "Expected exactly one random-effects term for '",
        nm,
        "'.",
        call. = FALSE
      )
    }
    if (length(lf$reTrms$cnms[[i]]) != 1L) {
      stop(
        "Multiple membership is only implemented for a scalar intercept ",
        "term, but '",
        nm,
        "' has ",
        length(lf$reTrms$cnms[[i]]),
        " columns.",
        call. = FALSE
      )
    }
    rows <- (Gp[i] + 1L):Gp[i + 1L]
    w <- memberships[[nm]]
    if (length(rows) != nrow(w)) {
      stop(
        "Membership matrix '",
        nm,
        "' has ",
        nrow(w),
        " levels but lme4 ",
        "built ",
        length(rows),
        ".",
        call. = FALSE
      )
    }
    lf$reTrms$Zt[rows, ] <- w
  }
  lf$reTrms$Zt <- drop0(lf$reTrms$Zt)

  devfun <- do.call(mkLmerDevfun, lf)
  opt <- optimizeLmer(
    devfun,
    optimizer = control$optimizer,
    control = control$optCtrl
  )
  model <- mkMerMod(environment(devfun), opt, lf$reTrms, fr = lf$fr)
  model@call$formula <- formula
  model
}

#' Did a fit converge cleanly enough to trust its standard error?
#'
#' A singular speaker or tangram variance is reported rather than hidden: the
#' inverse-variance weight for the game-level regression depends on the
#' standard error, and a boundary fit can understate it.
mm_fit_diagnostics <- function(model) {
  vc <- as.data.frame(VarCorr(model))
  list(
    singular = isSingular(model),
    converged = length(model@optinfo$conv$lme4$messages) == 0L,
    messages = model@optinfo$conv$lme4$messages %||% character(0),
    sd_speaker = vc$sdcor[match(MM_SPEAKER, vc$grp)],
    sd_target = vc$sdcor[match("target", vc$grp)],
    sigma = sigma(model)
  )
}

`%||%` <- function(x, y) if (is.null(x)) y else x

MM_SPEAKER <- "speaker"

#' Per-game group-specificity with the shared multiple-membership speaker
#' intercept.
#'
#' Same contract as fit_group_specificity() in R/group_specificity.R: one row
#' per game with the same_group coefficient, its standard error, and t value.
#' Fits that fail are dropped, and the reason is returned in `note` so a game
#' cannot silently disappear from the game-level regression.
#' @param pair_term  Add a random intercept for the unordered speaker pair.
#'   The speaker effects alone only approximate the dependence among
#'   similarities that share a speaker: two particular speakers can also be
#'   unusually similar to each other for reasons belonging to neither one.
#'   The design-matched simulations show what this costs and buys -- with such
#'   pair-level dependence present, omitting the term leaves 95% intervals
#'   covering about 86%, and adding it restores about 94%; with no pair
#'   dependence at all, adding it only makes the intervals slightly
#'   conservative. Point estimates are unaffected either way, which is exactly
#'   why the standard errors have to be checked separately.
fit_group_specificity_mm <- function(
  pairwise_df,
  covariates = NULL,
  pair_term = FALSE,
  verbose = FALSE
) {
  # A typed empty frame, so a window with no games still comes back with the
  # columns callers select on rather than a zero-column tibble.
  empty <- tibble(
    gameId = character(),
    coefficient = numeric(),
    std_error = numeric(),
    t_value = numeric(),
    n_speakers = integer(),
    singular = logical(),
    sd_speaker = numeric(),
    note = character()
  )
  if (!is.data.frame(pairwise_df) || nrow(pairwise_df) == 0) {
    return(empty)
  }

  rhs <- paste(c("sameGroup", covariates), collapse = " + ")
  re <- c(
    "(1 | target)",
    if (pair_term) "(1 | speakerPair)",
    paste0("(1 | ", MM_SPEAKER, ")")
  )
  model_formula <- as.formula(
    paste("similarity ~", rhs, "+", paste(re, collapse = " + "))
  )

  bind_rows(
    empty,
    map_dfr(unique(pairwise_df$gameId), function(gid) {
      game_data <- as.data.frame(pairwise_df[pairwise_df$gameId == gid, ])
      # Built here rather than taken from the exported participantPair column
      # so the id is guaranteed to be unordered whatever the caller passes.
      game_data$speakerPair <- paste(
        pmin(game_data$speaker1, game_data$speaker2),
        pmax(game_data$speaker1, game_data$speaker2)
      )
      if (nrow(game_data) < 5) {
        return(NULL)
      }
      if (n_distinct(game_data$sameGroup) < 2) {
        return(NULL)
      }

      fit <- tryCatch(
        {
          w <- speaker_pair_weights(game_data$speaker1, game_data$speaker2)
          model <- lmer_multimember(
            model_formula,
            game_data,
            memberships = setNames(list(w), MM_SPEAKER)
          )
          coefs <- coef(summary(model))
          diag <- mm_fit_diagnostics(model)
          tibble(
            gameId = gid,
            coefficient = coefs["sameGroup", "Estimate"],
            std_error = coefs["sameGroup", "Std. Error"],
            t_value = coefs["sameGroup", "t value"],
            n_speakers = nrow(w),
            singular = diag$singular,
            sd_speaker = diag$sd_speaker,
            note = NA_character_
          )
        },
        error = function(e) {
          if (verbose) {
            message("Game ", gid, ": ", conditionMessage(e))
          }
          tibble(
            gameId = gid,
            coefficient = NA_real_,
            std_error = NA_real_,
            t_value = NA_real_,
            n_speakers = NA_integer_,
            singular = NA,
            sd_speaker = NA_real_,
            note = conditionMessage(e)
          )
        }
      )
      fit
    })
  )
}
