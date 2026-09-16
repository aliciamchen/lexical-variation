# Design-matched simulations for the shared multiple-membership speaker
# intercept (analysis/R/multimembership.R).
#
#   Rscript analysis/simulate_mm_speaker.R [--reps N] [--out FILE]
#
# The preregistration commits to checking, before submission, that the
# multiple-membership structure converges, is invariant to pair ordering, and
# gives calibrated uncertainty in design-matched simulations, "including
# incomplete endpoint coverage and dependence beyond additive speaker
# effects", and to assessing the inverse-variance weights it produces. A
# successful fit or a similar point estimate is explicitly not enough: what
# has to hold is that the standard errors are the right size, because they
# become the weights in the game-level regression.
#
# So each scenario reports, over many simulated games:
#
#   converged / singular  did the fit come back usable
#   bias                  mean estimate minus the true same_group effect
#   emp_sd                the actual spread of the estimate across replicates
#   mean_se               the standard error the model reports
#   se_ratio              mean_se / emp_sd -- 1 means honest, < 1 overconfident
#   coverage              share of 95% intervals containing the truth
#
# and a second stage takes whole studies of 20 games per condition through
# the H1/H2 inverse-variance regression, so the weights are judged by whether
# the condition contrast they produce has nominal coverage.
#
# The design matches the real games: 9 speakers in 3 groups of 3, 6 tangrams,
# every unordered speaker pair once per tangram (36 pairs x 6 = 216 rows), and
# variance components taken from the pilot fits (sd_speaker 0.00-0.12,
# sd_target 0.06-0.12, sigma 0.18-0.20, same_group 0.36-0.42).

suppressPackageStartupMessages({
  source(here::here("analysis", "config.R"))
})

# ── Design and truth ────────────────────────────────────────────────────────

SIM_SPEAKERS <- 9L
SIM_GROUPS <- c("A", "B", "C")
SIM_TARGETS <- 6L

# Taken from the four pilot games (see the header). sd_speaker is the
# component the multiple-membership term estimates, and the pilot range
# includes 0, so the simulations have to cover a boundary case as well.
TRUTH <- list(
  intercept = 0.30,
  same_group = 0.40,
  sd_speaker = 0.10,
  sd_target = 0.12,
  sigma = 0.19,
  sd_dyad = 0.08 # only used by the scenarios with extra dependence
)

sim_design <- function(n_speakers = SIM_SPEAKERS, n_targets = SIM_TARGETS) {
  speakers <- sprintf("s%02d", seq_len(n_speakers))
  group <- setNames(
    rep(SIM_GROUPS, length.out = n_speakers)[order(rep(
      seq_len(ceiling(
        n_speakers / length(SIM_GROUPS)
      )),
      length.out = n_speakers
    ))],
    speakers
  )
  # Three groups of three, in blocks: s01-s03 = A, s04-s06 = B, s07-s09 = C
  group <- setNames(
    rep(SIM_GROUPS, each = ceiling(n_speakers / length(SIM_GROUPS)))[seq_len(
      n_speakers
    )],
    speakers
  )
  pairs <- as.data.frame(t(combn(speakers, 2)), stringsAsFactors = FALSE)
  names(pairs) <- c("speaker1", "speaker2")
  design <- do.call(
    rbind,
    lapply(sprintf("t%02d", seq_len(n_targets)), function(tg) {
      transform(pairs, target = tg)
    })
  )
  design$group1 <- group[design$speaker1]
  design$group2 <- group[design$speaker2]
  design$sameGroup <- as.numeric(design$group1 == design$group2)
  design$speakers <- NULL
  attr(design, "speakers") <- speakers
  design
}

#' Simulate one game's pairwise similarities.
#'
#' @param dyad_sd  Standard deviation of a pair-specific effect the analysis
#'   model does not include. Non-zero is the "dependence beyond additive
#'   speaker effects" case: two speakers can be unusually similar to each
#'   other for reasons that are not a property of either one alone.
#' @param drop_frac  Share of (speaker, target) descriptions that are
#'   missing, which removes every pair involving them. This is the
#'   "incomplete endpoint coverage" case: coverage is then unbalanced across
#'   speakers rather than missing at random across rows.
#' @param n_speakers  Fewer than 9 represents a game that lost a participant.
sim_game <- function(
  effect = TRUTH$same_group,
  dyad_sd = 0,
  drop_frac = 0,
  n_speakers = SIM_SPEAKERS,
  truth = TRUTH
) {
  d <- sim_design(n_speakers = n_speakers)
  speakers <- attr(d, "speakers")
  targets <- unique(d$target)

  b_speaker <- setNames(
    rnorm(length(speakers), sd = truth$sd_speaker),
    speakers
  )
  b_target <- setNames(rnorm(length(targets), sd = truth$sd_target), targets)

  d$similarity <- truth$intercept +
    effect * d$sameGroup +
    0.5 * (b_speaker[d$speaker1] + b_speaker[d$speaker2]) +
    b_target[d$target] +
    rnorm(nrow(d), sd = truth$sigma)

  if (dyad_sd > 0) {
    pair_id <- paste(d$speaker1, d$speaker2)
    b_dyad <- setNames(
      rnorm(length(unique(pair_id)), sd = dyad_sd),
      unique(pair_id)
    )
    d$similarity <- d$similarity + b_dyad[pair_id]
  }

  if (drop_frac > 0) {
    # Drop whole descriptions, not rows: a speaker who never described a
    # tangram is absent from every pair for it.
    grid <- expand.grid(
      speaker = speakers,
      target = targets,
      stringsAsFactors = FALSE
    )
    missing <- grid[runif(nrow(grid)) < drop_frac, , drop = FALSE]
    if (nrow(missing)) {
      gone <- paste(missing$speaker, missing$target)
      d <- d[
        !(paste(d$speaker1, d$target) %in% gone) &
          !(paste(d$speaker2, d$target) %in% gone),
        ,
        drop = FALSE
      ]
    }
  }

  d$gameId <- "sim"
  d
}

# ── Fitting one simulated game under each structure ─────────────────────────

fit_mm <- function(d) {
  d <- as.data.frame(d)
  model <- lmer_multimember(
    similarity ~ sameGroup + (1 | target) + (1 | speaker),
    data = d,
    memberships = list(speaker = speaker_pair_weights(d$speaker1, d$speaker2))
  )
  cs <- coef(summary(model))
  list(
    estimate = cs["sameGroup", "Estimate"],
    se = cs["sameGroup", "Std. Error"],
    singular = isSingular(model),
    df = df.residual(model)
  )
}

# The multiple-membership speaker effect plus a pair-level intercept. The
# speaker term alone only approximates the dependence among similarities that
# share a speaker; two particular speakers can also be unusually similar to
# each other for reasons that belong to neither of them. Each unordered pair
# is observed once per tangram, so this term is estimable, and the question
# these simulations answer is whether it is needed: an omitted pair effect
# would make the standard errors too small, and an unnecessary one could make
# them too large.
fit_mm_pair <- function(d) {
  d <- as.data.frame(d)
  d$participantPair <- paste(pmin(d$speaker1, d$speaker2),
                             pmax(d$speaker1, d$speaker2))
  model <- lmer_multimember(
    similarity ~ sameGroup + (1 | target) + (1 | participantPair) + (1 | speaker),
    data = d,
    memberships = list(speaker = speaker_pair_weights(d$speaker1, d$speaker2))
  )
  cs <- coef(summary(model))
  list(
    estimate = cs["sameGroup", "Estimate"],
    se = cs["sameGroup", "Std. Error"],
    singular = isSingular(model),
    df = df.residual(model)
  )
}

fit_separate <- function(d) {
  model <- lmer(
    similarity ~ sameGroup + (1 | target) + (1 | speaker1) + (1 | speaker2),
    data = as.data.frame(d),
    control = lmerControl(optimizer = "bobyqa")
  )
  cs <- coef(summary(model))
  list(
    estimate = cs["sameGroup", "Estimate"],
    se = cs["sameGroup", "Std. Error"],
    singular = isSingular(model),
    df = df.residual(model)
  )
}

# Randomly relabel which speaker of each pair is listed first. An unordered
# pair carries no such information, so nothing about the fit may change.
shuffle_pair_order <- function(d) {
  flip <- runif(nrow(d)) < 0.5
  out <- d
  out$speaker1[flip] <- d$speaker2[flip]
  out$speaker2[flip] <- d$speaker1[flip]
  out$group1[flip] <- d$group2[flip]
  out$group2[flip] <- d$group1[flip]
  out
}

safely_fit <- function(fitter, d) {
  tryCatch(fitter(d), error = function(e) {
    list(
      estimate = NA_real_,
      se = NA_real_,
      singular = NA,
      df = NA_real_,
      error = conditionMessage(e)
    )
  })
}

# ── Scenarios ───────────────────────────────────────────────────────────────

SCENARIOS <- list(
  list(
    name = "additive",
    note = "Model correct: additive speaker effects, complete coverage",
    args = list()
  ),
  list(
    name = "incomplete_coverage",
    note = "15% of descriptions missing, so pair coverage is unbalanced",
    args = list(drop_frac = 0.15)
  ),
  list(
    name = "eight_speakers",
    note = "A game that lost a participant: 8 speakers, 28 pairs",
    args = list(n_speakers = 8L)
  ),
  list(
    name = "dyad_dependence",
    note = "Pair-specific effects the model omits (sd 0.08)",
    args = list(dyad_sd = TRUTH$sd_dyad)
  ),
  list(
    name = "dyad_and_incomplete",
    note = "Both: omitted pair effects and 15% missing descriptions",
    args = list(dyad_sd = TRUTH$sd_dyad, drop_frac = 0.15)
  ),
  list(
    name = "no_speaker_variance",
    note = "Boundary case: true speaker variance is zero (one pilot game)",
    args = list(),
    truth = modifyList(TRUTH, list(sd_speaker = 0))
  )
)

# ── Stage 1: per-game estimation ────────────────────────────────────────────

run_scenario <- function(scenario, reps, check_ordering = TRUE) {
  truth <- scenario$truth %||% TRUTH
  rows <- lapply(seq_len(reps), function(i) {
    d <- do.call(sim_game, c(scenario$args, list(truth = truth)))
    mm <- safely_fit(fit_mm, d)
    mmpair <- safely_fit(fit_mm_pair, d)
    sep <- safely_fit(fit_separate, d)
    order_gap <- NA_real_
    order_gap_sep <- NA_real_
    if (check_ordering) {
      swapped <- shuffle_pair_order(d)
      mm_sw <- safely_fit(fit_mm, swapped)
      sep_sw <- safely_fit(fit_separate, swapped)
      order_gap <- abs(mm$estimate - mm_sw$estimate)
      order_gap_sep <- abs(sep$estimate - sep_sw$estimate)
    }
    tibble(
      scenario = scenario$name,
      rep = i,
      n_rows = nrow(d),
      mm_estimate = mm$estimate,
      mm_se = mm$se,
      mm_singular = mm$singular,
      mmpair_estimate = mmpair$estimate,
      mmpair_se = mmpair$se,
      mmpair_singular = mmpair$singular,
      sep_estimate = sep$estimate,
      sep_se = sep$se,
      sep_singular = sep$singular,
      order_gap = order_gap,
      order_gap_sep = order_gap_sep
    )
  })
  bind_rows(rows)
}

# Normal-approximation interval, matching how the game-level regression uses
# the estimate and its standard error.
summarise_structure <- function(draws, prefix, effect = TRUTH$same_group) {
  est <- draws[[paste0(prefix, "_estimate")]]
  se <- draws[[paste0(prefix, "_se")]]
  sing <- draws[[paste0(prefix, "_singular")]]
  ok <- is.finite(est) & is.finite(se) & se > 0
  lo <- est - 1.96 * se
  hi <- est + 1.96 * se
  tibble(
    structure = prefix,
    reps = length(est),
    converged = mean(ok),
    singular = mean(sing %in% TRUE),
    bias = mean(est[ok]) - effect,
    emp_sd = sd(est[ok]),
    mean_se = mean(se[ok]),
    se_ratio = mean(se[ok]) / sd(est[ok]),
    coverage = mean(lo[ok] <= effect & effect <= hi[ok])
  )
}

# ── Stage 2: the inverse-variance weights in the H1/H2 regression ───────────
#
# The per-game standard error is not an end in itself: 1/se^2 is the weight
# each game gets in the game-level regression, so the question is whether a
# contrast built from those weights has nominal coverage. Two conditions of
# `games_per_condition` games each, differing by `contrast_effect`.

run_weight_study <- function(
  scenario,
  studies,
  games_per_condition = 20,
  contrast_effect = 0.10,
  fitter = fit_mm
) {
  truth <- scenario$truth %||% TRUTH
  bind_rows(lapply(seq_len(studies), function(s) {
    per_game <- bind_rows(lapply(seq_len(2 * games_per_condition), function(g) {
      cond <- if (g <= games_per_condition) "a" else "b"
      effect <- truth$same_group + (cond == "b") * contrast_effect
      d <- do.call(
        sim_game,
        c(scenario$args, list(effect = effect, truth = truth))
      )
      fit <- safely_fit(fitter, d)
      tibble(condition = cond, estimate = fit$estimate, se = fit$se)
    })) |>
      filter(is.finite(estimate), is.finite(se), se > 0)

    if (n_distinct(per_game$condition) < 2) {
      return(tibble(
        study = s,
        estimate = NA_real_,
        se = NA_real_,
        covered = NA,
        weight_cv = NA_real_
      ))
    }
    w <- 1 / per_game$se^2
    m <- lm(estimate ~ condition, data = per_game, weights = w)
    cs <- coef(summary(m))["conditionb", ]
    ci <- cs[["Estimate"]] +
      c(-1, 1) * qt(0.975, df.residual(m)) * cs[["Std. Error"]]
    tibble(
      study = s,
      estimate = cs[["Estimate"]],
      se = cs[["Std. Error"]],
      covered = ci[1] <= contrast_effect && contrast_effect <= ci[2],
      # How unequal the weights are. Near-equal weights mean the weighting is
      # doing little; very unequal weights mean a few games dominate.
      weight_cv = sd(w) / mean(w)
    )
  }))
}

# ── Runner ──────────────────────────────────────────────────────────────────

main <- function(reps = 300, studies = 200, out = NULL, seed = 2026) {
  set.seed(seed)
  cat(sprintf(
    "Design-matched simulations: %d speakers, %d tangrams, %d reps per scenario\n",
    SIM_SPEAKERS,
    SIM_TARGETS,
    reps
  ))
  cat(sprintf("True same_group effect: %.2f\n\n", TRUTH$same_group))

  draws <- bind_rows(lapply(SCENARIOS, function(sc) {
    cat("  ", sc$name, "...\n", sep = "")
    run_scenario(sc, reps)
  }))

  stage1 <- bind_rows(lapply(SCENARIOS, function(sc) {
    d <- draws |> filter(scenario == sc$name)
    truth <- sc$truth %||% TRUTH
    bind_rows(
      summarise_structure(d, "mm", truth$same_group),
      summarise_structure(d, "mmpair", truth$same_group),
      summarise_structure(d, "sep", truth$same_group)
    ) |>
      mutate(scenario = sc$name, note = sc$note, .before = 1)
  }))

  ordering <- draws |>
    group_by(scenario) |>
    summarise(
      max_order_gap_mm = max(order_gap, na.rm = TRUE),
      max_order_gap_separate = max(order_gap_sep, na.rm = TRUE),
      .groups = "drop"
    )

  cat("\n== Stage 1: per-game estimation ==\n")
  print(as.data.frame(
    stage1 |>
      select(-note) |>
      mutate(across(where(is.numeric), \(x) round(x, 4)))
  ))

  cat("\n== Pair-ordering invariance (max |estimate difference|) ==\n")
  print(as.data.frame(
    ordering |>
      mutate(across(where(is.numeric), \(x) signif(x, 3)))
  ))

  cat(
    "\n== Stage 2: inverse-variance weights in the game-level regression ==\n"
  )
  fitters <- list(mm = fit_mm, mmpair = fit_mm_pair)
  stage2 <- bind_rows(lapply(SCENARIOS, function(sc) {
    bind_rows(lapply(names(fitters), function(fn) {
    cat("  ", sc$name, " / ", fn, "...\n", sep = "")
    run_weight_study(sc, studies, fitter = fitters[[fn]]) |>
      summarise(
        scenario = sc$name,
        structure = fn,
        studies = sum(is.finite(estimate)),
        mean_estimate = mean(estimate, na.rm = TRUE),
        emp_sd = sd(estimate, na.rm = TRUE),
        mean_se = mean(se, na.rm = TRUE),
        se_ratio = mean(se, na.rm = TRUE) / sd(estimate, na.rm = TRUE),
        coverage = mean(covered, na.rm = TRUE),
        mean_weight_cv = mean(weight_cv, na.rm = TRUE)
      )
    }))
  }))
  print(as.data.frame(
    stage2 |> mutate(across(where(is.numeric), \(x) round(x, 4)))
  ))

  result <- list(
    stage1 = stage1,
    ordering = ordering,
    stage2 = stage2,
    draws = draws,
    truth = TRUTH,
    reps = reps,
    studies = studies,
    seed = seed,
    run_at = Sys.time()
  )
  if (!is.null(out)) {
    saveRDS(result, out)
    cat("\nWrote", out, "\n")
  }
  invisible(result)
}

if (sys.nframe() == 0L || identical(environment(), globalenv())) {
  args <- commandArgs(trailingOnly = TRUE)
  get_arg <- function(flag, default) {
    i <- match(flag, args)
    if (is.na(i) || i == length(args)) default else args[i + 1]
  }
  if (!interactive()) {
    main(
      reps = as.integer(get_arg("--reps", "300")),
      studies = as.integer(get_arg("--studies", "200")),
      out = get_arg("--out", NULL)
    )
  }
}
