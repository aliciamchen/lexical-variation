# Data loading and preparation shared by the model scripts.
#
# The pipeline writes the facts the models need. The coded accuracy outcome
# (`correct`, `onTime`), the condition, the 1-indexed block numbers, the
# speaker of each listener trial and the in-group flag are columns of the
# processed tables (pipeline/preprocessing.py), and the model inputs (the
# within-group block means, each speaker's final-phase description
# properties, the per-listener in-group advantage) are tables in the
# model_inputs directory (pipeline/build_model_inputs.py). What is left to do here is what a
# model needs at fitting time: subsetting to a phase, a role or a set of
# conditions, factor levels, centering, the game-qualified group id, and the
# reporting flags beside the outcome. Column names the scripts use:
#
#   correct        0/1 outcome under the response-opportunity rule, NA where
#                  an exclusion made the observation missing (from the table)
#   onTime         whether a scored answer reached the server by the cutoff
#   group          game-qualified original group id ("<gameId> <A|B|C>")
#   blockNum_c     block number centered within the returned table
#   condition      factor with levels CONDITION_ORDER, or the subset asked for
#   inGroupSpeaker factor out_group/in_group, from attach_speaker()
#
# `load_tables()` reads every processed table, measure and model input for the
# active dataset (see use_dataset() in config.R); missing files come back as
# empty tibbles so a script can test `has_rows(x)` instead of file paths.
#
# Tests: models/tests/test_prepare.R, models/tests/test_accuracy_denominator.R

# ── Loading ──────────────────────────────────────────────────────────────────

read_table <- function(name, dir = tables_dir) {
  path <- file.path(dir, name)
  if (!file.exists(path)) {
    return(tibble())
  }
  # Every row is read before a column's type is guessed: a column that is
  # empty for its first thousand rows (exclusionReason) would otherwise be
  # read as logical and lose its text.
  read_csv(path, show_col_types = FALSE, guess_max = Inf)
}

has_rows <- function(df) is.data.frame(df) && nrow(df) > 0

load_tables <- function() {
  list(
    games = read_table("games.csv"),
    players = read_table("players.csv"),
    trials = read_table("trials.csv"),
    messages = read_table("messages.csv"),
    speaker_utts = read_table(utterances_file),
    social_guesses = read_table("social_guesses.csv"),
    # Player records that never played a real game (quiz failures, lobby
    # timeouts, late arrivals), written by combine_runs.py
    dropouts = read_table("dropouts.csv"),
    # The measures: similarities and description properties
    adjacent_sim = read_table("adjacent_similarities.csv", measures_dir),
    pairwise_sim = read_table(pairwise_file("sbert"), measures_dir),
    block_pairwise_sim = read_table(block_pairwise_file("sbert"), measures_dir),
    # The content-word Jaccard counterparts (same pairs, `similarity` is the
    # Jaccard overlap, NA where a description has no content words), for the
    # preregistered robustness check; empty when compute_measures.py has not
    # written them
    pairwise_sim_jaccard = read_table(pairwise_file("jaccard"), measures_dir),
    block_pairwise_sim_jaccard = read_table(
      block_pairwise_file("jaccard"),
      measures_dir
    ),
    phase_change = read_table("phase_change_similarities.csv", measures_dir),
    desc_props = read_table("description_properties.csv", measures_dir),
    lex_uniq = read_table("lexical_uniqueness.csv", measures_dir),
    # The model inputs (pipeline/build_model_inputs.py)
    within_group_means = read_table(
      "within_group_block_means.csv",
      model_inputs_dir
    ),
    within_group_means_jaccard = read_table(
      "within_group_block_means_jaccard.csv",
      model_inputs_dir
    ),
    final_props = read_table("final_phase_properties.csv", model_inputs_dir),
    ingroup_adv = read_table("ingroup_advantage.csv", model_inputs_dir)
  )
}

# A table processed before a column existed cannot be analyzed; say so rather
# than silently fitting on something else.
require_columns <- function(df, needed, table_name) {
  missing <- setdiff(needed, names(df))
  if (length(missing)) {
    stop(
      table_name,
      " is missing ",
      paste(missing, collapse = ", "),
      ". Re-run the pipeline (make process) so the current columns are written.",
      call. = FALSE
    )
  }
  df
}

# ── Column recodes ───────────────────────────────────────────────────────────

add_group_id <- function(df) mutate(df, group = paste(gameId, originalGroup))

center_block <- function(df) {
  mutate(df, blockNum_c = blockNum - mean(blockNum, na.rm = TRUE))
}

# Join condition from the games table (or reuse a condition column already on
# the table) and make it a factor; `levels` restricts and orders the conditions.
add_condition <- function(df, games, levels = CONDITION_ORDER) {
  if (!"condition" %in% names(df)) {
    df <- left_join(df, games |> select(gameId, condition), by = "gameId")
  }
  df |>
    filter(condition %in% levels) |>
    mutate(condition = factor(as.character(condition), levels = levels))
}

# ── Accuracy outcomes: the response-opportunity denominator ──────────────────
#
# Both accuracy outcomes are proportions of *eligible listener response
# opportunities*, not of submitted answers. The rule is applied once, in
# pipeline/preprocessing.py: an active listener on a played trial whose speaker
# sent a message is an opportunity (`responseOpportunity`); a correct answer
# received by the server's scoring cutoff is 1, an incorrect answer, a timeout
# and a late arrival are 0 (`correct`), and an observation a post-hoc
# participant exclusion or a documented technical failure made unanswerable is
# missing. `onTime` says whether a scored answer arrived by the cutoff. The
# helpers here keep the opportunity rows and add the reporting flags the
# summaries use. None of this touches the live Phase 1 accuracy screening in
# experiment/server/src/accuracy.js.

# Documented technical failures, one row per affected observation, recorded in
# data/<dataset>/technical_exclusions.csv before the primary contrasts are
# examined and applied by the pipeline. Columns: gameId, playerId, roundId,
# outcome ("referential", "social", or "both"), reason. Read here to report
# them; a missing file means none.
technical_exclusions <- function(dir = dataset_dir) {
  ex <- read_table("technical_exclusions.csv", dir)
  if (!has_rows(ex)) {
    return(tibble(
      gameId = character(),
      playerId = character(),
      roundId = character(),
      outcome = character(),
      reason = character()
    ))
  }
  require_columns(
    ex,
    c("gameId", "playerId", "roundId", "outcome", "reason"),
    "technical_exclusions.csv"
  )
  bad <- setdiff(unique(ex$outcome), c("referential", "social", "both"))
  if (length(bad)) {
    stop(
      "technical_exclusions.csv has unknown outcome(s): ",
      paste(bad, collapse = ", "),
      call. = FALSE
    )
  }
  # A blank cell is read as NA, and nzchar(NA) is TRUE, so test for both.
  if (any(is.na(ex$reason) | !nzchar(trimws(ex$reason)))) {
    stop("Every technical exclusion needs a recorded reason.", call. = FALSE)
  }
  ex
}

# The reporting flags beside the coded outcome: whether an answer was
# submitted and whether it arrived late (from the table's own columns), and
# the two kinds of missing outcome, a post-hoc participant exclusion (flagged
# on the row, with its reason) and a documented technical failure (the only
# other reason an opportunity has no outcome).
coded_outcome <- function(df, submitted, late) {
  excluded <- if ("excluded" %in% names(df)) {
    df$excluded %in% c(TRUE, "true", "True")
  } else {
    rep(FALSE, nrow(df))
  }
  reason <- if ("exclusionReason" %in% names(df)) {
    as.character(df$exclusionReason)
  } else {
    rep(NA_character_, nrow(df))
  }
  df |>
    mutate(
      submitted = {{ submitted }},
      lateArrival = {{ late }} %in% c(TRUE, "true", "True"),
      onTime = onTime %in% c(TRUE, "true", "True"),
      correct = suppressWarnings(as.numeric(correct)),
      participantExcluded = excluded,
      exclusionReason = ifelse(
        participantExcluded,
        ifelse(
          !is.na(reason) & nzchar(reason),
          reason,
          "excluded (no reason recorded)"
        ),
        NA_character_
      ),
      technicalFailure = is.na(correct) & !participantExcluded
    )
}

# ── Phase 1 tables for convention-formation checks ───────────────────────────

phase1_utterances <- function(speaker_utts) {
  speaker_utts |>
    filter(phaseNum == 1) |>
    center_block() |>
    add_group_id() |>
    mutate(participant = playerId, tangram = target)
}

phase1_listener_trials <- function(trials) {
  trials |>
    require_columns(
      c("responseOpportunity", "correct", "onTime", "lateClick", "clicked"),
      "trials"
    ) |>
    filter(phaseNum == 1, role == "listener", responseOpportunity %in% TRUE) |>
    mutate(tangram = target) |>
    add_group_id() |>
    coded_outcome(!is.na(clicked), lateClick)
}

# Proportion of listeners correct per round (the unit of the accuracy model)
phase1_round_accuracy <- function(trials) {
  phase1_listener_trials(trials) |>
    group_by(gameId, roundId, blockNum, tangram, group) |>
    summarise(
      ref_accuracy = mean(correct, na.rm = TRUE),
      opportunities = sum(!is.na(correct)),
      .groups = "drop"
    ) |>
    filter(opportunities > 0) |>
    center_block()
}

phase1_adjacent <- function(adjacent_sim) {
  if (!has_rows(adjacent_sim)) {
    return(tibble())
  }
  adjacent_sim |>
    filter(phaseNum == 1, !is.na(simAdjacent)) |>
    center_block() |>
    add_group_id() |>
    mutate(participant = playerId, tangram = target)
}

# Keep all four conditions for descriptive reporting, but only the shared
# Phase 1 procedure for the H1/H2 starting-state trend checks. No check outcome
# determines eligibility here.
#
# `accuracy` is the round-level proportion correct (for the descriptive
# tables); `listener_trials` is the listener-trial frame with the 0/1 `correct`
# outcome under the response-opportunity rule, which the logistic accuracy
# trend model is fit to (the paper fits binary outcomes with glmer).
convention_check_data <- function(speaker_utts, trials, adjacent_sim, games) {
  all_conditions <- list(
    utterances = phase1_utterances(speaker_utts) |> add_condition(games),
    accuracy = phase1_round_accuracy(trials) |> add_condition(games),
    listener_trials = phase1_listener_trials(trials) |> add_condition(games),
    adjacent = if (has_rows(adjacent_sim)) {
      phase1_adjacent(adjacent_sim) |> add_condition(games)
    } else {
      tibble()
    }
  )
  shared_phase1 <- lapply(all_conditions, function(df) {
    if (!has_rows(df)) {
      return(df)
    }
    df |>
      add_condition(games, H12_CONDITIONS) |>
      center_block()
  })
  list(all_conditions = all_conditions, shared_phase1 = shared_phase1)
}

# Turn the `window` column of a similarity table into an ordered display
# factor. An unrecognized window is an error rather than a silent relabel: the
# three windows differ substantively, and folding phase2_early into the
# Phase 2 bars would go unnoticed in a descriptive figure.
label_window <- function(df, windows = names(WINDOW_LABELS)) {
  if (!has_rows(df)) {
    return(df)
  }
  unknown <- setdiff(unique(df$window), names(WINDOW_LABELS))
  if (length(unknown)) {
    stop(
      "Unknown similarity window: ",
      paste(unknown, collapse = ", "),
      call. = FALSE
    )
  }
  df |>
    filter(window %in% windows) |>
    mutate(
      window_label = factor(
        unname(WINDOW_LABELS[window]),
        levels = unname(WINDOW_LABELS[windows])
      )
    )
}

# ── Trial-level tables with condition ────────────────────────────────────────

# Listener response opportunities of one phase with the coded outcome,
# condition, and centered block. `conditions` restricts to a subset (e.g.
# SOCIAL_CONDITIONS) and sets the factor levels; block is centered after that
# restriction.
listener_trials <- function(
  trials,
  games,
  phase = 2,
  conditions = NULL
) {
  levels <- if (is.null(conditions)) CONDITION_ORDER else conditions
  # `.env$phase`: the trials table has its own `phase` column ("refgame"), which
  # the data mask would otherwise pick over this argument
  trials |>
    require_columns(
      c("responseOpportunity", "correct", "onTime", "lateClick", "clicked"),
      "trials"
    ) |>
    filter(
      phaseNum == .env$phase,
      role == "listener",
      responseOpportunity %in% TRUE
    ) |>
    coded_outcome(!is.na(clicked), lateClick) |>
    add_condition(games, levels) |>
    center_block()
}

# ── Response-opportunity reporting ──────────────────────────────────────────
#
# The descriptive summaries the preregistration promises alongside each
# accuracy outcome: opportunity counts, on-time response rates, and accuracy
# among on-time submitted answers, by condition and phase. They separate
# nonresponse from incorrect answers and are not alternative support criteria
# for any hypothesis.
response_opportunity_summary <- function(df, by = c("condition", "phaseNum")) {
  if (!has_rows(df)) {
    return(tibble())
  }
  by <- intersect(by, names(df))
  # The two kinds of missing outcome, reported separately: a documented
  # technical failure (technicalFailure, from coded_outcome()) and a post-hoc
  # participant exclusion (participantExcluded). Either column is absent when
  # there were none.
  df <- df |>
    mutate(
      .participant = if ("participantExcluded" %in% names(df)) {
        participantExcluded %in% TRUE
      } else {
        FALSE
      },
      .technical = if ("technicalFailure" %in% names(df)) {
        technicalFailure %in% TRUE & !.participant
      } else {
        is.na(correct) & !.participant
      }
    )
  df |>
    group_by(across(all_of(by))) |>
    summarise(
      opportunities = n(),
      excluded_technical = sum(.technical),
      excluded_participant = sum(.participant),
      scored = sum(!is.na(correct)),
      on_time = sum(onTime & !is.na(correct)),
      on_time_rate = on_time / scored,
      accuracy = mean(correct, na.rm = TRUE),
      accuracy_on_time = mean(correct[onTime & !is.na(correct)], na.rm = TRUE),
      .groups = "drop"
    )
}

# The post-hoc participant exclusions present in a coded opportunity frame:
# rows by reason, distinguishing the excluded participants' own rows from the
# rows of listeners they spoke to. Empty when nothing was excluded.
participant_exclusion_summary <- function(df, by = "condition") {
  if (!has_rows(df) || !"participantExcluded" %in% names(df)) {
    return(tibble())
  }
  by <- intersect(by, names(df))
  df |>
    filter(participantExcluded) |>
    mutate(
      kind = ifelse(
        startsWith(exclusionReason, "speaker excluded"),
        "listener of an excluded speaker",
        "excluded participant's own"
      )
    ) |>
    count(across(all_of(by)), kind, exclusionReason, name = "observations")
}

# Late arrivals, reported by condition when any are found. A late answer
# counts as unsuccessful in the primary coding; this is what the sensitivity
# analysis below removes. Lateness is outcome-specific, so `late` names the
# flag for the outcome in hand (lateClick or lateSocialGuess).
late_arrival_summary <- function(df, late = lateClick, by = "condition") {
  if (!has_rows(df)) {
    return(tibble())
  }
  by <- intersect(by, names(df))
  df |>
    mutate(.late = {{ late }}) |>
    group_by(across(all_of(by))) |>
    summarise(
      opportunities = n(),
      late_arrivals = sum(.late, na.rm = TRUE),
      late_rate = late_arrivals / opportunities,
      .groups = "drop"
    )
}

# The sensitivity analysis: repeat a primary accuracy comparison with late
# arrivals dropped rather than counted as unsuccessful.
drop_late_arrivals <- function(df, late = lateClick) {
  if (!has_rows(df)) {
    return(df)
  }
  df |> mutate(.late = {{ late }}) |> filter(!.late %in% TRUE) |> select(-.late)
}

# The speaker of each listener trial is on the row (`speakerId`, from the trio
# membership of the round, computed in pipeline/preprocessing.py and checked
# against the server's own record by the integrity suite); this turns the
# in-group flag into the factor the models use, with out_group as the
# reference level.
attach_speaker <- function(listener_df) {
  require_columns(listener_df, c("speakerId", "inGroupSpeaker"), "trials")
  in_group <- listener_df$inGroupSpeaker %in% c(TRUE, "true", "True")
  out_group <- listener_df$inGroupSpeaker %in% c(FALSE, "false", "False")
  listener_df |>
    mutate(
      inGroupSpeaker = factor(
        ifelse(
          in_group,
          "in_group",
          ifelse(out_group, "out_group", NA_character_)
        ),
        levels = c("out_group", "in_group")
      )
    )
}

# Per-listener in-group advantage: mean referential accuracy when the speaker
# came from the listener's own original group, minus mean accuracy when they
# did not (pipeline/build_model_inputs.py computes it from the coded outcome).
#
# Why aggregate rather than model this at the trial level. `inGroupSpeaker` is
# the only tested predictor in this design that varies WITHIN every grouping
# factor -- the reshuffle rule gives each trio exactly one in-group listener,
# so a listener is an in-group listener on some trials and not on others. By
# the rule used everywhere else that calls for by-game and by-listener random
# slopes, and a trial-level model without them is anticonservative (simulated
# on this design: a nominal .05 test runs near .26 for the in-group effect and
# .28 for its interaction with condition). But those slopes cannot be
# estimated: a listener contributes only about a dozen Bernoulli trials per
# cell, and across simulated slope SDs from 0.2 to 0.8 the simplification
# ladder dropped them every time.
#
# Taking the difference per listener is the paired-comparison form of the same
# contrast, and it is estimable: the within-listener dimension is collapsed
# into the outcome, so what remains is a between-listener model. The same
# simulations put this at .083 and .058. Hawkins et al. (2020) use exactly
# this device for their within- versus across-speaker comparison, analysing a
# per-speaker difference score with speaker-level intercepts.
#
# Returns one row per listener of the requested conditions with both cells
# observed: `advantage`, the two cell means, and the two cell sizes so
# coverage and precision can be reported. `min_trials` drops listeners with a
# thin cell, for the sensitivity check; the default keeps everyone who has
# both.
ingroup_advantage <- function(
  advantage,
  conditions = SOCIAL_CONDITIONS,
  min_trials = 1L
) {
  if (!has_rows(advantage)) {
    return(tibble())
  }
  require_columns(
    advantage,
    c(
      "gameId",
      "condition",
      "playerId",
      "acc_in",
      "acc_out",
      "n_in",
      "n_out",
      "advantage"
    ),
    "ingroup_advantage.csv"
  )
  advantage |>
    filter(
      condition %in% conditions,
      n_in >= min_trials,
      n_out >= min_trials
    ) |>
    mutate(condition = factor(as.character(condition), levels = conditions)) |>
    select(gameId, condition, playerId, acc_in, acc_out, n_in, n_out, advantage)
}

# Social-guess response opportunities (Phase 2 of the social conditions) with
# the coded outcome, condition, and centered block
social_guess_trials <- function(
  social_guesses,
  games,
  conditions = SOCIAL_CONDITIONS
) {
  if (!has_rows(social_guesses)) {
    return(tibble())
  }
  levels <- if (is.null(conditions)) CONDITION_ORDER else conditions
  social_guesses |>
    require_columns(
      c(
        "responseOpportunity",
        "correct",
        "onTime",
        "socialTimeout",
        "lateSocialGuess"
      ),
      "social_guesses"
    ) |>
    filter(responseOpportunity %in% TRUE) |>
    coded_outcome(
      !(socialTimeout %in% c(TRUE, "true", "True")),
      lateSocialGuess
    ) |>
    add_condition(games, levels) |>
    center_block()
}

phase2_utterances <- function(speaker_utts, games, conditions = NULL) {
  levels <- if (is.null(conditions)) CONDITION_ORDER else conditions
  speaker_utts |>
    filter(phaseNum == 2) |>
    add_condition(games, levels) |>
    add_group_id() |>
    center_block()
}

# ── Derived-metric tables ────────────────────────────────────────────────────

# The rows of block_pairwise_similarities.csv on which group specificity is
# defined: the cells where every original group has at least two participants
# who have described the tangram, so every group contributes a within-group
# pair. compute_measures.py marks them `allGroupsPaired`; it keeps the rest in
# the table because a descriptive within-vs-between panel can still plot them
# (the first block of each phase holds between-group pairs alone). A table
# without the column is taken as eligible throughout.
specificity_eligible <- function(block_pairwise_sim) {
  if (
    !has_rows(block_pairwise_sim) ||
      !"allGroupsPaired" %in% names(block_pairwise_sim)
  ) {
    return(block_pairwise_sim)
  }
  block_pairwise_sim |> filter(allGroupsPaired == 1)
}

# ── Model inputs ─────────────────────────────────────────────────────────────

# One mean per original group, tangram and 1-indexed block over the group's
# within-group pairs, for one phase and a set of conditions: the H3b unit.
# pipeline/build_model_inputs.py computes the means (overlapping speaker pairs are
# not independent observations; a cell with no pair has no row and nothing is
# filled from another block; every within-group pair enters, because the
# `allGroupsPaired` start rule of the specificity trajectory does not apply to
# a group's own convergence). The paper counts blocks from 1, so `block` is
# the column the H3b models use and `blockNum` is kept for traceability.
within_group_block_means <- function(
  means,
  phase = 1,
  conditions = SOCIAL_CONDITIONS
) {
  if (!has_rows(means)) {
    return(tibble())
  }
  require_columns(
    means,
    c(
      "gameId",
      "condition",
      "group",
      "target",
      "phaseNum",
      "blockNum",
      "block",
      "similarity",
      "n_pairs"
    ),
    "within_group_block_means.csv"
  )
  means |>
    filter(phaseNum == .env$phase, condition %in% conditions) |>
    mutate(
      condition = factor(as.character(condition), levels = conditions),
      block = as.integer(block),
      blockNum = as.integer(blockNum),
      group_target = interaction(group, target, drop = TRUE)
    )
}

# The H3c measures (concreteness, word frequency, lexical uniqueness) for each
# speaker's final description of each tangram in one phase, with the
# game-qualified original group id the H3c models' group intercept uses
# (`group`); pipeline/build_model_inputs.py keeps the last block per speaker and
# tangram within the phase.
final_phase_properties <- function(
  props,
  phase = 1,
  conditions = CONDITION_ORDER
) {
  if (!has_rows(props)) {
    return(tibble())
  }
  require_columns(
    props,
    c(
      "gameId",
      "playerId",
      "target",
      "phaseNum",
      "blockNum",
      "condition",
      "group",
      "n_content_words"
    ),
    "final_phase_properties.csv"
  )
  props |>
    filter(phaseNum == .env$phase, condition %in% conditions) |>
    mutate(condition = factor(as.character(condition), levels = conditions))
}

# The H3c comparison: final Phase 1 descriptions in the social conditions
final_phase1_properties <- function(props, conditions = SOCIAL_CONDITIONS) {
  final_phase_properties(props, phase = 1, conditions = conditions)
}

# One row per description, reshaped for a binomial H3c model: `k` successes
# out of `n_content_words`, plus a per-description identifier for the
# observation-level random intercept. Descriptions with no content words have
# no proportion to model and are dropped, as they are under the Gaussian
# version. Errors rather than silently dropping everything when the counts
# are missing from the measures.
binomial_measure <- function(props, numerator) {
  if (!has_rows(props)) {
    return(tibble())
  }
  missing <- setdiff(c("n_content_words", numerator), names(props))
  if (length(missing)) {
    stop(
      "binomial_measure needs ",
      paste(missing, collapse = " and "),
      "; re-run compute_measures.py to regenerate the H3c files.",
      call. = FALSE
    )
  }
  props |>
    filter(
      !is.na(.data[[numerator]]),
      !is.na(n_content_words),
      n_content_words > 0
    ) |>
    mutate(
      descriptionId = paste(gameId, playerId, target, sep = ":"),
      k = as.integer(.data[[numerator]]),
      n_minus_k = as.integer(n_content_words) - as.integer(.data[[numerator]])
    )
}

# One row per content word, for the H3c models.
#
# `binomial_measure()` above gives k successes out of n per description;
# this expands that to the n individual binary observations, so the model is
# literally "is this content word concrete?" rather than a count. The two are
# the same likelihood -- a binomial on (k, n-k) with a per-description
# intercept is exactly n Bernoulli draws with a by-description random effect,
# and they return identical estimates and standard errors (verified in
# models/tests/test_prepare.R). The word-level form is the one we fit
# because it states the outcome plainly; the aggregated form remains
# available and is much faster if the expanded frame ever becomes unwieldy.
#
# Which words are 1 and which are 0 is not recorded, only how many of each,
# because nothing in the model distinguishes them. An analysis that needs the
# tokens themselves should recompute from the utterances.
word_level_measure <- function(props, numerator, outcome = "is_target") {
  counts <- binomial_measure(props, numerator)
  if (!has_rows(counts)) {
    return(tibble())
  }
  hits <- counts |> filter(k > 0) |> tidyr::uncount(k)
  hits[[outcome]] <- 1L
  misses <- counts |> filter(n_minus_k > 0) |> tidyr::uncount(n_minus_k)
  misses[[outcome]] <- 0L
  bind_rows(hits, misses) |>
    select(-any_of(c("k", "n_minus_k")))
}
