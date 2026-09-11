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
    adjacent_sim = read_table("adjacent_similarities.csv", derived_dir),
    pairwise_sim = read_table("pairwise_similarities.csv", derived_dir),
    block_pairwise_sim = read_table(
      "block_pairwise_similarities.csv",
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

# Block number continuous across phases using each game's own Phase 1 length
add_global_block <- function(df, games) {
  df |>
    left_join(games |> select(gameId, phase1Blocks), by = "gameId") |>
    mutate(
      globalBlock = ifelse(phaseNum == 1, blockNum, blockNum + phase1Blocks)
    )
}

# ── Phase 1 tables for the outcome-neutral models ────────────────────────────

phase1_utterances <- function(speaker_utts) {
  speaker_utts |>
    filter(phaseNum == 1) |>
    center_block() |>
    add_group_id() |>
    mutate(participant = playerId, tangram = target)
}

phase1_listener_trials <- function(trials) {
  trials |>
    filter(phaseNum == 1, role == "listener") |>
    mutate(correct = as_correct(clickedCorrect), tangram = target) |>
    add_group_id()
}

# Proportion of listeners correct per round (the unit of the accuracy model)
phase1_round_accuracy <- function(trials) {
  phase1_listener_trials(trials) |>
    group_by(gameId, roundId, blockNum, tangram, group) |>
    summarise(ref_accuracy = mean(correct, na.rm = TRUE), .groups = "drop") |>
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

# ── Trial-level tables with condition ────────────────────────────────────────

# Listener trials of one phase with correct, condition, and centered block.
# `conditions` restricts to a subset (e.g. SOCIAL_CONDITIONS) and sets the
# factor levels; block is centered after that restriction.
listener_trials <- function(trials, games, phase = 2, conditions = NULL) {
  levels <- if (is.null(conditions)) CONDITION_ORDER else conditions
  # `.env$phase`: the trials table has its own `phase` column ("refgame"), which
  # the data mask would otherwise pick over this argument
  trials |>
    filter(phaseNum == .env$phase, role == "listener") |>
    mutate(correct = as_correct(clickedCorrect)) |>
    add_condition(games, levels) |>
    center_block()
}

# Attach the speaker of each listener trial. A roundId is shared by all groups
# in a game, so the join needs the listener's current group as well; joining on
# (gameId, roundId) alone would match three speakers, and (gameId, blockNum,
# target) would also match Phase 1 speakers because blockNum resets per phase.
attach_speaker <- function(listener_df, trials) {
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
  conditions = SOCIAL_CONDITIONS
) {
  if (!has_rows(social_guesses)) {
    return(tibble())
  }
  levels <- if (is.null(conditions)) CONDITION_ORDER else conditions
  social_guesses |>
    mutate(correct = as_correct(socialGuessCorrect)) |>
    add_condition(games, levels) |>
    center_block()
}

phase2_utterances <- function(speaker_utts, games, conditions = NULL) {
  levels <- if (is.null(conditions)) CONDITION_ORDER else conditions
  speaker_utts |>
    filter(phaseNum == 2) |>
    add_condition(games, levels) |>
    center_block()
}

# ── Derived-metric tables ────────────────────────────────────────────────────

# Within-group pairs of the block-by-block similarities for one phase, with a
# game-qualified group id (group1 == group2 for within-group pairs)
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
    center_block() |>
    mutate(group = paste0(gameId, "_", group1))
}

# The H3c measures (concreteness, word frequency, lexical uniqueness) for each
# speaker's final Phase 1 description of each tangram
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
  final_phase_properties(desc_props, lex_uniq, games, phase = 1, conditions = conditions)
}
