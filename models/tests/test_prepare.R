# Tests for the shared data preparation in models/R/prepare.R.

if (!exists("attach_speaker")) {
  source(here::here("models", "config.R"))
}
if (!exists("check")) {
  source(here::here("models", "tests", "check.R"))
}

# ── A two-game fixture: 9 players in 3 groups, one Phase 2 round per game ────

games <- tibble(
  gameId = c("g1", "g2"),
  condition = c("social_mixed", "refer_separated"),
  phase1Blocks = c(6, 6)
)

# Round r1 in g1: current groups X and Y, each with one speaker and two
# listeners. The `phase` column is the stage name, as in the real table; it
# must not be confused with the `phase` argument of listener_trials(). The
# coded outcome, the speaker and the in-group flag are on the rows, as the
# pipeline writes them; the denominator rule itself is tested in
# test_accuracy_denominator.R.
trials <- tribble(
  ~gameId , ~roundId , ~playerId , ~originalGroup , ~currentGroup , ~role      , ~phaseNum , ~blockNum , ~target , ~clicked , ~clickedCorrect , ~phase    , ~correct , ~onTime , ~speakerId , ~inGroupSpeaker ,
  "g1"    , "r1"     , "s1"      , "A"            , "X"           , "speaker"  ,         2 ,         0 , "t1"    , NA       , NA              , "refgame" , NA       , NA      , "s1"       , NA              ,
  "g1"    , "r1"     , "l1"      , "A"            , "X"           , "listener" ,         2 ,         0 , "t1"    , "t1"     , "true"          , "refgame" ,        1 , TRUE    , "s1"       , TRUE            ,
  "g1"    , "r1"     , "l2"      , "B"            , "X"           , "listener" ,         2 ,         0 , "t1"    , "t2"     , "false"         , "refgame" ,        0 , TRUE    , "s1"       , FALSE           ,
  "g1"    , "r1"     , "s2"      , "C"            , "Y"           , "speaker"  ,         2 ,         0 , "t1"    , NA       , NA              , "refgame" , NA       , NA      , "s2"       , NA              ,
  "g1"    , "r1"     , "l3"      , "C"            , "Y"           , "listener" ,         2 ,         0 , "t1"    , "t1"     , "true"          , "refgame" ,        1 , TRUE    , "s2"       , TRUE            ,
  "g1"    , "r1"     , "l4"      , "A"            , "Y"           , "listener" ,         2 ,         0 , "t1"    , "t2"     , "false"         , "refgame" ,        0 , TRUE    , "s2"       , FALSE           ,
  "g1"    , "p1"     , "l1"      , "A"            , "A"           , "listener" ,         1 ,         0 , "t2"    , "t2"     , "true"          , "refgame" ,        1 , TRUE    , "s9"       , TRUE            ,
  "g1"    , "p1"     , "l4"      , "A"            , "A"           , "listener" ,         1 ,         0 , "t2"    , "t1"     , "false"         , "refgame" ,        0 , TRUE    , "s9"       , TRUE            ,
  "g2"    , "r9"     , "s3"      , "B"            , "B"           , "speaker"  ,         2 ,         3 , "t1"    , NA       , NA              , "refgame" , NA       , NA      , "s3"       , NA              ,
  "g2"    , "r9"     , "l5"      , "B"            , "B"           , "listener" ,         2 ,         3 , "t1"    , "t1"     , "true"          , "refgame" ,        1 , TRUE    , "s3"       , TRUE
) |>
  mutate(
    lateClick = FALSE,
    hasSpeakerMessage = TRUE,
    responseOpportunity = role == "listener"
  )

# ── attach_speaker ───────────────────────────────────────────────────────────

p2 <- listener_trials(trials, games, phase = 2) |> attach_speaker()
check(
  "every Phase 2 listener trial carries its speaker",
  nrow(p2) == 5 && all(!is.na(p2$speakerId))
)
check(
  "the speaker is the one on the listener's row",
  p2$speakerId[p2$playerId == "l1"] == "s1" &&
    p2$speakerId[p2$playerId == "l3"] == "s2"
)
check(
  "the in-group flag becomes the factor the models use",
  p2$inGroupSpeaker[p2$playerId == "l1"] == "in_group" &&
    p2$inGroupSpeaker[p2$playerId == "l2"] == "out_group" &&
    p2$inGroupSpeaker[p2$playerId == "l4"] == "out_group"
)
check(
  "in-group is a factor with out_group as the reference level",
  identical(levels(p2$inGroupSpeaker), c("out_group", "in_group"))
)
check("the flag written as text by a CSV round trip is read too", {
  txt <- attach_speaker(
    p2 |> mutate(inGroupSpeaker = c("True", "False", "True", "False", "True"))
  )
  identical(
    as.character(txt$inGroupSpeaker),
    c("in_group", "out_group", "in_group", "out_group", "in_group")
  )
})
check(
  "a table without the speaker columns is an error, not a silent result",
  inherits(
    try(attach_speaker(p2 |> select(-speakerId)), silent = TRUE),
    "try-error"
  )
)

# ── listener_trials ──────────────────────────────────────────────────────────

check(
  "listener_trials keeps only listeners of the requested phase",
  all(p2$role == "listener") && all(p2$phaseNum == 2)
)
check(
  "condition is a factor with the full order when no subset is given",
  identical(levels(p2$condition), CONDITION_ORDER)
)
soc <- listener_trials(trials, games, phase = 2, conditions = SOCIAL_CONDITIONS)
check(
  "a condition subset filters the rows and sets the factor levels",
  all(soc$gameId == "g1") && identical(levels(soc$condition), SOCIAL_CONDITIONS)
)
check(
  "block is centered after the restriction",
  abs(mean(soc$blockNum_c)) < 1e-12
)

# ── Phase 1 helpers ──────────────────────────────────────────────────────────

acc <- phase1_round_accuracy(trials)
check(
  "round accuracy is the proportion of listeners correct",
  nrow(acc) == 1 && acc$ref_accuracy == 0.5
)
check("group ids are game-qualified", acc$group == "g1 A")

utts <- tibble(
  gameId = "g1",
  playerId = c("s1", "s1"),
  originalGroup = "A",
  phaseNum = c(1, 2),
  blockNum = c(2, 0),
  target = "t1",
  utterance = c("a b", "a"),
  uttLength = c(2, 1)
)
p1u <- phase1_utterances(utts)
check(
  "phase1_utterances keeps Phase 1 and adds participant, group, tangram",
  nrow(p1u) == 1 &&
    all(c("participant", "group", "tangram", "blockNum_c") %in% names(p1u))
)

# ── Convention-formation checks ─────────────────────────────────────────────

check_games <- tibble(
  gameId = paste0("check", seq_along(CONDITION_ORDER)),
  condition = CONDITION_ORDER
)
check_utts <- tibble(
  gameId = rep(check_games$gameId, each = 3),
  playerId = rep(paste0("speaker", seq_along(CONDITION_ORDER)), each = 3),
  originalGroup = "A",
  phaseNum = rep(c(1, 1, 2), length(CONDITION_ORDER)),
  blockNum = c(rep(c(0, 5, 0), 3), 4, 5, 0),
  target = "t1",
  # Lengthening descriptions are retained, not screened for a favorable trend.
  uttLength = rep(c(1, 20, 10), length(CONDITION_ORDER))
)
check_trials <- check_utts |>
  mutate(
    roundId = paste0("r", row_number()),
    role = "listener",
    clicked = "t1",
    clickedCorrect = FALSE,
    lateClick = FALSE,
    hasSpeakerMessage = TRUE,
    responseOpportunity = TRUE,
    correct = 0,
    onTime = TRUE
  )
check_adjacent <- check_utts |> mutate(simAdjacent = 0.1)
convention_data <- convention_check_data(
  check_utts,
  check_trials,
  check_adjacent,
  check_games
)

check(
  "convention checks retain all conditions for descriptive reporting",
  all(vapply(
    convention_data$all_conditions,
    function(d) {
      nrow(d) == 8 && setequal(as.character(d$condition), CONDITION_ORDER)
    },
    logical(1)
  ))
)
check(
  "pooled convention checks contain exactly the three shared-Phase-1 conditions",
  all(vapply(
    convention_data$shared_phase1,
    function(d) {
      nrow(d) == 6 &&
        setequal(as.character(d$condition), H12_CONDITIONS) &&
        identical(levels(d$condition), H12_CONDITIONS)
    },
    logical(1)
  ))
)
check(
  "shared Phase 1 blocks are recentered after excluding social-first",
  all(vapply(
    convention_data$shared_phase1,
    function(d) abs(mean(d$blockNum_c)) < 1e-12,
    logical(1)
  ))
)
check(
  "poor accuracy and lengthening descriptions do not exclude games from checks",
  all(convention_data$shared_phase1$accuracy$ref_accuracy == 0) &&
    all(c(1, 20) %in% convention_data$shared_phase1$utterances$uttLength) &&
    all(convention_data$shared_phase1$utterances$phaseNum == 1)
)
check(
  "groups in pooled convention checks remain game-qualified",
  length(unique(convention_data$shared_phase1$accuracy$group)) == 3
)
check(
  "the listener-trial frame for the logistic accuracy check carries a 0/1 outcome, group, tangram, and game",
  all(
    c("correct", "group", "tangram", "gameId", "blockNum_c", "condition") %in%
      names(convention_data$shared_phase1$listener_trials)
  ) &&
    all(convention_data$shared_phase1$listener_trials$correct %in% c(0, 1))
)
no_adjacent <- convention_check_data(
  check_utts,
  check_trials,
  tibble(),
  check_games
)
check(
  "missing adjacent similarities do not remove length or accuracy observations",
  nrow(no_adjacent$shared_phase1$adjacent) == 0 &&
    nrow(no_adjacent$shared_phase1$utterances) == 6 &&
    nrow(no_adjacent$shared_phase1$accuracy) == 6
)

# ── label_window ────────────────────────────────────────────────────────────

win_df <- tibble(
  window = c("phase1_final", "phase2_early", "phase2_final"),
  similarity = c(0.1, 0.2, 0.3)
)
labelled <- label_window(win_df)
check(
  "each window keeps its own label rather than collapsing into two phases",
  nrow(labelled) == 3 &&
    identical(
      as.character(labelled$window_label),
      c("Phase 1 final", "Phase 2 early", "Phase 2 final")
    ) &&
    identical(levels(labelled$window_label), unname(WINDOW_LABELS))
)
two_windows <- label_window(win_df, windows = c("phase1_final", "phase2_final"))
check(
  "restricting to the H1/H2 windows drops phase2_early instead of relabelling it",
  nrow(two_windows) == 2 &&
    !("Phase 2 early" %in% levels(two_windows$window_label))
)
check(
  "an unrecognized window is an error, not a silent relabel",
  inherits(
    try(label_window(tibble(window = "phase3_final")), silent = TRUE),
    "try-error"
  )
)
check(
  "an empty similarity table passes through label_window",
  nrow(label_window(tibble())) == 0
)

# ── add_condition on a table that already has condition ──────────────────────

pc <- tibble(
  gameId = c("g1", "g2"),
  condition = c("social_mixed", "refer_separated"),
  x = 1:2
)
out <- add_condition(pc, games)
check(
  "add_condition reuses an existing condition column instead of duplicating it",
  !"condition.x" %in% names(out) && is.factor(out$condition) && nrow(out) == 2
)

# ── social guesses ───────────────────────────────────────────────────────────

# Both listeners answered on time; the nonresponse and lateness cases are in
# test_accuracy_denominator.R.
sg <- tibble(
  gameId = c("g1", "g2"),
  blockNum = c(0, 1),
  socialGuess = "same_group",
  socialGuessCorrect = c("true", FALSE),
  socialTimeout = FALSE,
  lateSocialGuess = FALSE,
  responseOpportunity = TRUE,
  correct = c(1, 0),
  onTime = TRUE
)
sgt <- social_guess_trials(sg, games)
check(
  "social_guess_trials keeps the social conditions only and carries the outcome",
  nrow(sgt) == 1 && sgt$correct == 1 && sgt$gameId == "g1"
)
check(
  "social_guess_trials returns an empty tibble for empty input",
  nrow(social_guess_trials(tibble(), games)) == 0
)

# ── final_phase_properties: the frame, restricted to a phase and conditions ──

props <- tibble(
  gameId = c("g1", "g1", "g2"),
  playerId = c("s1", "s1", "s3"),
  originalGroup = c("A", "A", "B"),
  target = "t1",
  phaseNum = c(1, 2, 2),
  blockNum = c(4, 5, 3),
  block = blockNum + 1,
  condition = c("social_mixed", "social_mixed", "refer_separated"),
  group = c("g1 A", "g1 A", "g2 B"),
  n_content_words = c(4, 3, 5),
  n_concrete = c(1, 0, 3),
  concreteness = c(0.25, 0, 0.6),
  mean_zipf_freq = c(4, 3, 4.5),
  uniqueness = c(0.2, 0.9, 0.4),
  n_unique_words = c(1, 3, 2)
)
p1 <- final_phase_properties(props, phase = 1)
check(
  "final_phase_properties keeps the requested phase with the frame's group id",
  nrow(p1) == 1 &&
    p1$blockNum == 4 &&
    p1$uniqueness == 0.2 &&
    p1$group == "g1 A"
)
check(
  "phase2_utterances carries the game-qualified group id",
  "group" %in%
    names(phase2_utterances(utts, games)) &&
    phase2_utterances(utts, games)$group == "g1 A"
)
p2props <- final_phase_properties(props, phase = 2)
check(
  "phase 2 covers every condition by default",
  nrow(p2props) == 2 && identical(levels(p2props$condition), CONDITION_ORDER)
)
check(
  "final_phase1_properties is the social-conditions Phase 1 case",
  nrow(final_phase1_properties(props)) == 1 &&
    identical(
      levels(final_phase1_properties(props)$condition),
      SOCIAL_CONDITIONS
    )
)
check(
  "a frame missing a column is an error, and no rows in gives no rows out",
  inherits(
    try(final_phase_properties(props |> select(-group)), silent = TRUE),
    "try-error"
  ) &&
    nrow(final_phase_properties(tibble())) == 0
)

# ── within_group_block_means: the frame, restricted to a phase and conditions ─

means <- tibble(
  gameId = c("g1", "g1", "g1", "g2", "g3"),
  condition = c(
    "social_mixed",
    "social_mixed",
    "social_mixed",
    "social_first",
    "refer_mixed"
  ),
  group = c("g1_A", "g1_A", "g1_A", "g2_A", "g3_A"),
  target = "t1",
  phaseNum = c(1, 1, 2, 1, 1),
  blockNum = c(1, 2, 2, 2, 2),
  block = blockNum + 1,
  similarity = c(0.3, 0.6, 0.7, 0.9, 0.6),
  n_pairs = c(1, 2, 1, 1, 1)
)
wg <- within_group_block_means(means)
check(
  "within_group_block_means keeps Phase 1 rows of the social conditions with integer blocks",
  nrow(wg) == 3 &&
    all(wg$gameId %in% c("g1", "g2")) &&
    is.integer(wg$block) &&
    identical(levels(wg$condition), SOCIAL_CONDITIONS) &&
    "group_target" %in% names(wg)
)
check(
  "another phase or condition set can be asked for",
  nrow(within_group_block_means(means, phase = 2)) == 1 &&
    nrow(within_group_block_means(means, conditions = CONDITION_ORDER)) == 4
)
check(
  "a frame missing a column is an error, and no rows in gives no rows out",
  inherits(
    try(within_group_block_means(means |> select(-n_pairs)), silent = TRUE),
    "try-error"
  ) &&
    nrow(within_group_block_means(tibble())) == 0
)

# ── binomial_measure ─────────────────────────────────────────────────────────
# H3c fits concreteness and lexical uniqueness as binomial counts rather than
# as Gaussian proportions, so the reshaping from a stored ratio plus its
# counts into cbind(k, n - k) has to be exact, and a description with no
# content words has to drop out rather than become a zero-out-of-zero row.
local({
  props <- tibble(
    gameId = c("g1", "g1", "g1"),
    playerId = c("p1", "p2", "p3"),
    target = c("t1", "t1", "t1"),
    n_content_words = c(4L, 2L, 0L),
    n_concrete = c(3L, 0L, 0L),
    concreteness = c(0.75, 0, NA_real_)
  )
  out <- binomial_measure(props, "n_concrete")
  check(
    "binomial_measure splits the counts into successes and failures",
    identical(out$k, c(3L, 0L)) && identical(out$n_minus_k, c(1L, 2L))
  )
  check(
    "a description with no content words is dropped, not counted as 0 of 0",
    nrow(out) == 2L && !"p3" %in% out$playerId
  )
  check(
    "the reshaped counts reproduce the stored proportion",
    isTRUE(all.equal(out$k / (out$k + out$n_minus_k), out$concreteness))
  )
  check(
    "each description gets its own identifier for the observation-level term",
    length(unique(out$descriptionId)) == nrow(out)
  )
  check(
    "missing counts are an error, not a silently empty model frame",
    inherits(
      try(
        binomial_measure(props |> select(-n_concrete), "n_concrete"),
        silent = TRUE
      ),
      "try-error"
    )
  )
  check(
    "no rows in gives no rows out rather than an error",
    nrow(binomial_measure(tibble(), "n_concrete")) == 0L
  )
})

# ── add_group_id: the invariant every (1 | game) + (1 | group) model rests on ─
#
# Groups are nested within games. That nesting is expressed in the DATA, by
# giving each group a game-unique identifier, rather than in the formulas,
# which use `(1 | gameId) + (1 | group)` instead of `(1 | gameId/group)`. The
# two are the same model only while the identifiers really are game-unique.
# If `group` ever became a bare "A"/"B"/"C", every one of those models would
# silently start treating game 1's group A and game 7's group A as the same
# group -- a crossed structure, with no error and no warning. This is the
# check that makes that failure loud.
local({
  df <- tibble(
    gameId = c("gameX", "gameX", "gameY", "gameY"),
    originalGroup = c("A", "B", "A", "B")
  )
  out <- add_group_id(df)
  check(
    "add_group_id gives every group a game-unique identifier",
    n_distinct(out$group) == 4L
  )
  check(
    "the same original-group letter in two games gets two identifiers",
    out$group[out$gameId == "gameX" & out$originalGroup == "A"] !=
      out$group[out$gameId == "gameY" & out$originalGroup == "A"]
  )
  check(
    "each group identifier belongs to exactly one game",
    all(
      out |>
        distinct(group, gameId) |>
        count(group) |>
        pull(n) ==
        1L
    )
  )
  check(
    "the identifier still names the game and the original group it came from",
    all(mapply(grepl, out$gameId, out$group)) &&
      all(mapply(grepl, out$originalGroup, out$group))
  )
})

# ── ingroup_advantage: the frame, restricted to conditions and cell sizes ───
# The paired form of the in-group contrast: one difference score per listener,
# computed by preprocessing/build_model_inputs.py; here the frame is restricted.
local({
  adv <- tibble(
    gameId = c("g1", "g1", "g3"),
    condition = c("social_mixed", "social_mixed", "refer_mixed"),
    playerId = c("p1", "p2", "p9"),
    acc_in = c(1, 0.5, 0.8),
    acc_out = c(0.5, 0.5, 0.2),
    n_in = c(2L, 2L, 5L),
    n_out = c(2L, 1L, 5L),
    advantage = c(0.5, 0, 0.6)
  )
  out <- ingroup_advantage(adv)
  check(
    "one row per listener of the social conditions, with the factor levels set",
    nrow(out) == 2L &&
      setequal(out$playerId, c("p1", "p2")) &&
      identical(levels(out$condition), SOCIAL_CONDITIONS)
  )
  check(
    "advantage and the cell sizes come through for coverage and precision",
    out$advantage[out$playerId == "p1"] == 0.5 && all(out$n_in == 2)
  )
  check(
    "min_trials drops thin cells for the sensitivity check",
    identical(ingroup_advantage(adv, min_trials = 2L)$playerId, "p1")
  )
  check(
    "another condition set can be asked for",
    nrow(ingroup_advantage(
      adv,
      conditions = c("refer_mixed", SOCIAL_CONDITIONS)
    )) ==
      3L
  )
  check(
    "a frame without the advantage columns is an error, not an empty result",
    inherits(
      try(ingroup_advantage(adv |> select(-advantage)), silent = TRUE),
      "try-error"
    )
  )
  check(
    "no rows in gives no rows out",
    nrow(ingroup_advantage(tibble())) == 0L
  )
})

# ── word_level_measure ───────────────────────────────────────────────────────
# The H3c models predict a per-word binary outcome. Expanding the counts is
# exactly equivalent to a binomial on (k, n-k) with a per-description
# intercept, so the two must give identical fits; if they ever diverge, the
# expansion is wrong.
local({
  props <- tibble(
    gameId = "g1",
    playerId = c("p1", "p2"),
    target = c("t1", "t1"),
    n_content_words = c(4L, 3L),
    n_concrete = c(3L, 0L),
    concreteness = c(0.75, 0)
  )
  out <- word_level_measure(props, "n_concrete", "is_concrete")
  check(
    "one row per content word",
    nrow(out) == 7L
  )
  check(
    "the right number of ones and zeros per description",
    sum(out$is_concrete[out$playerId == "p1"]) == 3L &&
      sum(out$playerId == "p1") == 4L &&
      sum(out$is_concrete[out$playerId == "p2"]) == 0L &&
      sum(out$playerId == "p2") == 3L
  )
  check(
    "the count columns do not ride along and get mistaken for the outcome",
    !any(c("k", "n_minus_k") %in% names(out))
  )
  check(
    "no rows in gives no rows out",
    nrow(word_level_measure(tibble(), "n_concrete")) == 0L
  )
})

# The equivalence itself, on a frame big enough to fit both forms.
local({
  set.seed(4)
  props <- tidyr::expand_grid(g = 1:8, p = 1:6, target = paste0("t", 1:4)) |>
    mutate(
      gameId = paste0("g", g),
      group = paste(gameId, (p - 1) %/% 3, sep = ":"),
      playerId = paste(gameId, p, sep = ":"),
      condition = factor(ifelse(g <= 4, "a", "b")),
      n_content_words = 6L,
      n_concrete = rbinom(n(), 6, 0.4)
    )
  agg <- binomial_measure(props, "n_concrete")
  wide <- word_level_measure(props, "n_concrete", "is_concrete")
  f_agg <- cbind(k, n_minus_k) ~ condition + (1 | group) + (1 | descriptionId)
  f_wl <- is_concrete ~ condition + (1 | group) + (1 | descriptionId)
  m_agg <- suppressWarnings(lme4::glmer(f_agg, agg, family = binomial))
  m_wl <- suppressWarnings(lme4::glmer(f_wl, wide, family = binomial))
  check(
    "word-level and aggregated binomial give the same fixed effects",
    isTRUE(all.equal(
      unname(lme4::fixef(m_agg)),
      unname(lme4::fixef(m_wl)),
      tolerance = 1e-4
    ))
  )
  check(
    "and the same standard errors",
    isTRUE(all.equal(
      unname(sqrt(diag(as.matrix(vcov(m_agg))))),
      unname(sqrt(diag(as.matrix(vcov(m_wl))))),
      tolerance = 1e-3
    ))
  )
})
