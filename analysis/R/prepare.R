# Data loading and preparation shared by the notebooks.
#
# Every notebook used to repeat the same recodes: booleans exported as
# TRUE/"true", group labels that repeat across games, block centering, the join
# from a listener's trial to its speaker. Those live here once. All functions
# take tables and return tables with the column names the notebooks use:
#
#   correct        0/1 numeric from the exported TRUE/"true" booleans (NA kept)
#   group          game-qualified original group id ("<gameId> <A|B|C>")
#   blockNum_c     block number centered within the returned table
#   condition      factor with levels CONDITION_ORDER, or the subset asked for
#   speakerId, speakerGroup, inGroupSpeaker   from attach_speaker()
#
# `load_tables()` reads every data and derived table for the active dataset
# (see use_dataset() in config.R); missing derived files come back as empty
# tibbles so a notebook can test `has_rows(x)` instead of file paths.
#
# Tests: analysis/tests/test_prepare.R

# ── Loading ──────────────────────────────────────────────────────────────────

read_table <- function(name, dir = data_dir) {
  path <- file.path(dir, name)
  if (!file.exists(path)) {
    return(tibble())
  }
  read_csv(path, show_col_types = FALSE)
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
    # timeouts, late arrivals), written by combine_runs.py since September
    # 2026; empty for datasets processed before that
    dropouts = read_table("dropouts.csv"),
    adjacent_sim = read_table("adjacent_similarities.csv", derived_dir),
    pairwise_sim = read_table(pairwise_file("sbert"), derived_dir),
    block_pairwise_sim = read_table(block_pairwise_file("sbert"), derived_dir),
    # The content-word Jaccard counterparts (same pairs, `similarity` is the
    # Jaccard overlap, NA where a description has no content words), for the
    # preregistered robustness check; empty when compute_derived.py has not
    # written them
    pairwise_sim_jaccard = read_table(pairwise_file("jaccard"), derived_dir),
    block_pairwise_sim_jaccard = read_table(
      block_pairwise_file("jaccard"),
      derived_dir
    ),
    phase_change = read_table("phase_change_similarities.csv", derived_dir),
    desc_props = read_table("description_properties.csv", derived_dir),
    lex_uniq = read_table("lexical_uniqueness.csv", derived_dir)
  )
}

# ── Column recodes ───────────────────────────────────────────────────────────

as_correct <- function(x) as.numeric(x == TRUE | x == "true")

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

# Block number continuous across phases using each game's own Phase 1 length.
# One-indexed, like every block number in the manuscript: the exported blockNum
# counts from 0 within its phase, so a 6 + 6 game runs 1 to 12 here and Phase 2
# starts at 7. The only consumer is 04_exploratory.qmd, whose axes and reported
# block numbers therefore read the same way as the paper's.
add_global_block <- function(df, games) {
  df |>
    left_join(games |> select(gameId, phase1Blocks), by = "gameId") |>
    mutate(
      globalBlock = ifelse(phaseNum == 1, blockNum + 1, blockNum + 1 + phase1Blocks)
    )
}

# ── Accuracy outcomes: the response-opportunity denominator ──────────────────
#
# Both accuracy outcomes are proportions of *eligible listener response
# opportunities*, not of submitted answers. An opportunity is an active
# listener assigned to the task on a played trial with a speaker message
# available during the response period; `responseOpportunity` is computed once
# in the pipeline (analysis/preprocessing.py). A correct answer received by
# the server's scoring cutoff is 1; an incorrect answer, an ordinary timeout,
# and a late arrival are all 0. Trials with no response opportunity leave the
# denominator rather than counting as failures, and observations made
# unanswerable by a documented technical failure become NA.
#
# `denominator = "submitted"` reproduces the earlier coding, in which only
# scored answers counted, and exists so the pilot SI can keep reporting the
# numbers it was written with (see main.tex on the pilot retaining its earlier
# processing). It is not the preregistered rule and must not be used for the
# full sample. None of this touches the live Phase 1 accuracy screening in
# experiment/server/src/accuracy.js, which is unchanged.

DENOMINATOR_RULES <- c("opportunity", "submitted")

# A dataset processed before the rule landed has no responseOpportunity
# column; say so rather than silently reporting the old denominator.
require_opportunity_columns <- function(df, needed, table_name) {
  missing <- setdiff(needed, names(df))
  if (length(missing)) {
    stop(
      table_name,
      " is missing ",
      paste(missing, collapse = ", "),
      ". Re-run the pipeline (make process) so the response-opportunity ",
      "columns are written.",
      call. = FALSE
    )
  }
  df
}

# Documented technical failures, one row per affected observation, recorded in
# data/<dataset>/technical_exclusions.csv before the primary contrasts are
# examined. Columns: gameId, playerId, roundId, outcome
# ("referential", "social", or "both"), reason. Missing file means none.
technical_exclusions <- function(dir = data_dir) {
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
  require_opportunity_columns(
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

# Set `correct` to NA for the observations a documented technical failure made
# unanswerable or unrecoverable. Missing or late responses alone never qualify.
apply_technical_exclusions <- function(df, exclusions, outcome) {
  if (!has_rows(df) || !has_rows(exclusions)) {
    return(df)
  }
  affected <- exclusions |>
    filter(outcome %in% c(.env$outcome, "both")) |>
    select(gameId, playerId, roundId) |>
    distinct() |>
    mutate(technicalFailure = TRUE)
  df |>
    left_join(affected, by = c("gameId", "playerId", "roundId")) |>
    mutate(
      technicalFailure = !is.na(technicalFailure),
      correct = ifelse(technicalFailure, NA_real_, correct)
    )
}

# Post-hoc participant exclusions (preregistration, "Exclusion criteria").
# `data/<dataset>/participant_exclusions.csv` (playerId, reason) names the
# participants excluded after the fact; preprocessing.py drops their messages
# and flags `excluded` / `exclusionReason` on their own rows of trials.csv and
# social_guesses.csv and on the rows of the listeners they spoke to (reason
# "speaker excluded: <reason>"). Those observations are missing, not
# unsuccessful: code_accuracy() sets their outcome to NA, the same treatment a
# documented technical failure gets, and the reasons are reported beside the
# technical exclusions. The file is optional; an absent file means nobody was
# excluded.
participant_exclusions <- function(dir = data_dir) {
  ex <- read_table("participant_exclusions.csv", dir)
  if (!has_rows(ex)) {
    return(tibble(playerId = character(), reason = character()))
  }
  require_opportunity_columns(
    ex,
    c("playerId", "reason"),
    "participant_exclusions.csv"
  )
  ex |> mutate(playerId = as.character(playerId), reason = as.character(reason))
}

# A frame processed before the exclusion columns existed has no `excluded`
# column; treat it as "nobody excluded" and let the notebooks say so once
# (see exclusion_columns_present()).
exclusion_columns_present <- function(df) {
  all(c("excluded", "exclusionReason") %in% names(df))
}

# Set `correct` to NA on the rows a post-hoc participant exclusion flagged, and
# carry the flag as `participantExcluded` with its `exclusionReason`.
apply_participant_exclusions <- function(df) {
  if (!has_rows(df)) {
    return(df)
  }
  if (!"excluded" %in% names(df)) {
    return(
      df |>
        mutate(participantExcluded = FALSE, exclusionReason = NA_character_)
    )
  }
  if (!"exclusionReason" %in% names(df)) {
    df$exclusionReason <- NA_character_
  }
  df |>
    mutate(
      participantExcluded = excluded == TRUE | excluded == "true",
      participantExcluded = participantExcluded %in% TRUE,
      exclusionReason = ifelse(
        participantExcluded & !is.na(exclusionReason) & nzchar(exclusionReason),
        as.character(exclusionReason),
        ifelse(
          participantExcluded,
          "excluded (no reason recorded)",
          NA_character_
        )
      ),
      correct = ifelse(participantExcluded, NA_real_, correct)
    )
}

# Code one accuracy outcome from its three facts: whether an answer was
# submitted at all, whether it was flagged as arriving after the deadline, and
# how the server scored it.
#
# "On time" means received by the server's scoring cutoff, and the decisive
# evidence for that is a score: the server scores at the deadline, so a
# submitted answer with no score did not arrive in time. The explicit late
# flag says the same thing, and is what identifies these rows as late
# arrivals rather than anomalies; it is checked as well because it is the
# recorded reason, and because pilot exports predate it.
#
# Rows flagged by a post-hoc participant exclusion (`excluded == TRUE`) keep
# their place in the opportunity frame with an NA outcome, so they are counted
# and reported but never scored.
code_accuracy <- function(df, submitted, late, scored_correct) {
  df |>
    mutate(
      submitted = {{ submitted }},
      lateArrival = {{ late }} %in% TRUE,
      scoredCorrect = as_correct({{ scored_correct }}),
      onTime = submitted & !lateArrival & !is.na(scoredCorrect),
      correct = as.numeric(onTime & scoredCorrect == 1)
    ) |>
    apply_participant_exclusions()
}

# The pre-2026-09-16 coding, kept only so the pilot SI reports the numbers it
# was written with: whatever the server scored, with unscored answers dropped
# by the na.rm in each summary. Never use it for the full sample.
code_accuracy_historical <- function(df, scored_correct) {
  df |>
    mutate(
      scoredCorrect = as_correct({{ scored_correct }}),
      onTime = !is.na(scoredCorrect),
      lateArrival = FALSE,
      correct = scoredCorrect
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

phase1_listener_trials <- function(
  trials,
  denominator = "opportunity",
  exclusions = technical_exclusions()
) {
  denominator <- match.arg(denominator, DENOMINATOR_RULES)
  out <- trials |>
    filter(phaseNum == 1, role == "listener") |>
    mutate(tangram = target) |>
    add_group_id()
  if (denominator == "submitted") {
    return(code_accuracy_historical(out, clickedCorrect))
  }
  out |>
    require_opportunity_columns(
      c("responseOpportunity", "lateClick", "clicked"),
      "trials"
    ) |>
    filter(responseOpportunity) |>
    code_accuracy(!is.na(clicked), lateClick, clickedCorrect) |>
    apply_technical_exclusions(exclusions, "referential")
}

# Proportion of listeners correct per round (the unit of the accuracy model)
phase1_round_accuracy <- function(
  trials,
  denominator = "opportunity",
  exclusions = technical_exclusions()
) {
  phase1_listener_trials(trials, denominator, exclusions) |>
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
# determines eligibility here. Historical pilot preparation remains unchanged.
#
# `accuracy` is the round-level proportion correct (for the descriptive
# plots); `listener_trials` is the listener-trial frame with the 0/1 `correct`
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
# Phase 2 bars had previously gone unnoticed in a descriptive figure.
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

# Listener trials of one phase with correct, condition, and centered block.
# `conditions` restricts to a subset (e.g. SOCIAL_CONDITIONS) and sets the
# factor levels; block is centered after that restriction.
listener_trials <- function(
  trials,
  games,
  phase = 2,
  conditions = NULL,
  denominator = "opportunity",
  exclusions = technical_exclusions()
) {
  denominator <- match.arg(denominator, DENOMINATOR_RULES)
  levels <- if (is.null(conditions)) CONDITION_ORDER else conditions
  # `.env$phase`: the trials table has its own `phase` column ("refgame"), which
  # the data mask would otherwise pick over this argument
  out <- trials |> filter(phaseNum == .env$phase, role == "listener")
  out <- if (denominator == "submitted") {
    code_accuracy_historical(out, clickedCorrect)
  } else {
    out |>
      require_opportunity_columns(
        c("responseOpportunity", "lateClick", "clicked"),
        "trials"
      ) |>
      filter(responseOpportunity) |>
      code_accuracy(!is.na(clicked), lateClick, clickedCorrect) |>
      apply_technical_exclusions(exclusions, "referential")
  }
  out |>
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
  # technical failure (technicalFailure, from apply_technical_exclusions())
  # and a post-hoc participant exclusion (participantExcluded). Either column
  # is absent when there were none.
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

# Speaker trials with and without an analyzable description, by condition and
# phase. A description is analyzable when the speaker's trial has a row in the
# (filtered) speaker-utterance table: a speaker who said nothing is `silent`,
# an excluded participant's descriptions were dropped at preprocessing
# (`excluded`), and a speaker whose messages were all classified as
# non-referential has `non_referential_only`. The proportion is what the
# preregistration's coverage reporting refers to when it counts analyzable
# descriptions.
speaker_description_coverage <- function(
  trials,
  speaker_utts,
  games,
  by = c("condition", "phaseNum")
) {
  speakers <- trials |>
    filter(role == "speaker") |>
    add_condition(games)
  if (!has_rows(speakers)) {
    return(tibble())
  }
  keys <- c("gameId", "playerId", "phaseNum", "blockNum", "target")
  described <- speaker_utts |>
    select(all_of(keys)) |>
    distinct() |>
    mutate(has_description = TRUE)
  speakers <- speakers |>
    left_join(described, by = keys) |>
    mutate(
      has_description = has_description %in% TRUE,
      is_silent = if ("hasSpeakerMessage" %in% names(speakers)) {
        !(hasSpeakerMessage == TRUE | hasSpeakerMessage == "true") %in% TRUE
      } else {
        FALSE
      },
      is_excluded = if ("excluded" %in% names(speakers)) {
        (excluded == TRUE | excluded == "true") %in% TRUE
      } else {
        FALSE
      }
    )
  by <- intersect(by, names(speakers))
  # The flags keep their own names so the counts below can be named after
  # them without shadowing them mid-summarise
  speakers |>
    group_by(across(all_of(by))) |>
    summarise(
      speaker_trials = n(),
      with_description = sum(has_description),
      without_description = sum(!has_description),
      prop_without = without_description / speaker_trials,
      silent = sum(!has_description & is_silent),
      excluded = sum(!has_description & !is_silent & is_excluded),
      non_referential_only = sum(!has_description & !is_silent & !is_excluded),
      .groups = "drop"
    )
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

# Attach the speaker of each listener trial. A roundId is shared by all groups
# in a game, so the join needs the listener's current group as well; joining on
# (gameId, roundId) alone would match three speakers, and (gameId, blockNum,
# target) would also match Phase 1 speakers because blockNum resets per phase.
# trials.csv carries speakerId and inGroupSpeaker itself since September 2026
# (same definition, computed in preprocessing.py); any such columns are dropped
# first so this join stays the single definition the notebooks use, and the
# data integrity suite checks the exported copies against it.
attach_speaker <- function(listener_df, trials) {
  listener_df <- listener_df |>
    select(-any_of(c("speakerId", "speakerGroup", "inGroupSpeaker")))
  speakers <- trials |>
    filter(role == "speaker") |>
    select(
      gameId,
      roundId,
      currentGroup,
      speakerId = playerId,
      speakerGroup = originalGroup
    ) |>
    distinct()
  listener_df |>
    left_join(speakers, by = c("gameId", "roundId", "currentGroup")) |>
    mutate(
      inGroupSpeaker = factor(
        ifelse(originalGroup == speakerGroup, "in_group", "out_group"),
        levels = c("out_group", "in_group")
      )
    )
}

# Social guesses (Phase 2 of the social conditions) with correct, condition,
# and centered block
social_guess_trials <- function(
  social_guesses,
  games,
  conditions = SOCIAL_CONDITIONS,
  denominator = "opportunity",
  exclusions = technical_exclusions()
) {
  if (!has_rows(social_guesses)) {
    return(tibble())
  }
  denominator <- match.arg(denominator, DENOMINATOR_RULES)
  levels <- if (is.null(conditions)) CONDITION_ORDER else conditions
  out <- if (denominator == "submitted") {
    social_guesses |>
      filter(!is.na(socialGuess)) |>
      code_accuracy_historical(socialGuessCorrect)
  } else {
    social_guesses |>
      require_opportunity_columns(
        c("responseOpportunity", "socialTimeout", "lateSocialGuess"),
        "social_guesses"
      ) |>
      filter(responseOpportunity) |>
      code_accuracy(!socialTimeout, lateSocialGuess, socialGuessCorrect) |>
      apply_technical_exclusions(exclusions, "social")
  }
  out |>
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

# Within-group pairs of the block-by-block similarities for one phase, with a
# game-qualified group id (group1 == group2 for within-group pairs).
#
# The exported `blockNum` is 0-indexed, so block_pairwise_similarities.csv
# holds Phase 1 blockNum 1..5 (the first block in which two speakers per group
# have described a target is 0-indexed block 1). The paper counts blocks from
# 1 (H3b uses blocks 2-6 with the milestone at block 3), so this is the one
# place the 1-indexed `block` column (blockNum + 1) is created; H3b and its
# plots work on `block`, and `blockNum` is kept only for traceability.
within_group_block_pairs <- function(
  block_pairwise_sim,
  games,
  phase = 1,
  conditions = SOCIAL_CONDITIONS
) {
  if (!has_rows(block_pairwise_sim)) {
    return(tibble())
  }
  block_pairwise_sim |>
    filter(phaseNum == .env$phase, sameGroup == 1) |>
    add_condition(games, conditions) |>
    mutate(
      block = as.integer(blockNum) + 1L,
      group = paste0(gameId, "_", group1)
    )
}

# One mean per group, tangram, and 1-indexed block, rather than treating
# overlapping speaker pairs as independent observations. Missing means are
# omitted, never filled from another block.
within_group_block_means <- function(
  block_pairwise_sim,
  games,
  phase = 1,
  conditions = SOCIAL_CONDITIONS
) {
  pairs <- within_group_block_pairs(
    block_pairwise_sim,
    games,
    phase,
    conditions
  )
  if (!has_rows(pairs)) {
    return(tibble())
  }
  pairs |>
    filter(is.finite(similarity)) |>
    group_by(gameId, condition, group, target, block) |>
    summarise(similarity = mean(similarity), n_pairs = n(), .groups = "drop") |>
    mutate(
      blockNum = block - 1L,
      group_target = interaction(group, target, drop = TRUE)
    )
}

# The H3c measures (concreteness, word frequency, lexical uniqueness) for each
# speaker's final Phase 1 description of each tangram, with the game-qualified
# original group id the H3c models' group intercept uses
final_phase_properties <- function(
  desc_props,
  lex_uniq,
  games,
  phase = 1,
  conditions = CONDITION_ORDER
) {
  if (!has_rows(desc_props) || !has_rows(lex_uniq)) {
    return(tibble())
  }
  desc_props |>
    left_join(
      lex_uniq |>
        select(gameId, playerId, target, blockNum, phaseNum, uniqueness),
      by = c("gameId", "playerId", "target", "blockNum", "phaseNum")
    ) |>
    filter(phaseNum == .env$phase) |>
    add_condition(games, conditions) |>
    add_group_id() |>
    group_by(gameId, playerId, target) |>
    filter(blockNum == max(blockNum)) |>
    ungroup()
}

# The H3c comparison: final Phase 1 descriptions in the social conditions
final_phase1_properties <- function(
  desc_props,
  lex_uniq,
  games,
  conditions = SOCIAL_CONDITIONS
) {
  final_phase_properties(
    desc_props,
    lex_uniq,
    games,
    phase = 1,
    conditions = conditions
  )
}
