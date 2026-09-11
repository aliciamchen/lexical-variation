# Tests for the shared data preparation in analysis/R/prepare.R.

if (!exists("attach_speaker")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

# ── A two-game fixture: 9 players in 3 groups, one Phase 2 round per game ────

games <- tibble(
  gameId = c("g1", "g2"),
  condition = c("social_mixed", "refer_separated"),
  phase1Blocks = c(6, 6)
)

# Round r1 in g1: current groups X and Y, each with one speaker and two listeners.
# The `phase` column is the stage name, as in the real table; it must not be
# confused with the `phase` argument of listener_trials().
trials <- tribble(
  ~gameId , ~roundId , ~playerId , ~originalGroup , ~currentGroup , ~role      , ~phaseNum , ~blockNum , ~target , ~clickedCorrect , ~phase    ,
  "g1"    , "r1"     , "s1"      , "A"            , "X"           , "speaker"  ,         2 ,         0 , "t1"    , NA              , "refgame" ,
  "g1"    , "r1"     , "l1"      , "A"            , "X"           , "listener" ,         2 ,         0 , "t1"    , "true"          , "refgame" ,
  "g1"    , "r1"     , "l2"      , "B"            , "X"           , "listener" ,         2 ,         0 , "t1"    , "false"           , "refgame" ,
  "g1"    , "r1"     , "s2"      , "C"            , "Y"           , "speaker"  ,         2 ,         0 , "t1"    , NA              , "refgame" ,
  "g1"    , "r1"     , "l3"      , "C"            , "Y"           , "listener" ,         2 ,         0 , "t1"    , "true"            , "refgame" ,
  "g1"    , "r1"     , "l4"      , "A"            , "Y"           , "listener" ,         2 ,         0 , "t1"    , "false"         , "refgame" ,
  "g1"    , "p1"     , "l1"      , "A"            , "A"           , "listener" ,         1 ,         0 , "t2"    , "true"            , "refgame" ,
  "g1"    , "p1"     , "l4"      , "A"            , "A"           , "listener" ,         1 ,         0 , "t2"    , "false"           , "refgame" ,
  "g2"    , "r9"     , "s3"      , "B"            , "B"           , "speaker"  ,         2 ,         3 , "t1"    , NA              , "refgame" ,
  "g2"    , "r9"     , "l5"      , "B"            , "B"           , "listener" ,         2 ,         3 , "t1"    , "true", "refgame"
)

check(
  "as_correct handles logical and string booleans and keeps NA",
  identical(as_correct(c(TRUE, "true", FALSE, "false", NA)), c(1, 1, 0, 0, NA))
)

# ── attach_speaker ───────────────────────────────────────────────────────────

p2 <- listener_trials(trials, games, phase = 2) |> attach_speaker(trials)
check(
  "every Phase 2 listener trial gets exactly one speaker",
  nrow(p2) == 5 && all(!is.na(p2$speakerId))
)
check(
  "the speaker is the one from the listener's current group in that round",
  p2$speakerId[p2$playerId == "l1"] == "s1" &&
    p2$speakerId[p2$playerId == "l3"] == "s2"
)
check(
  "in-group status compares original groups, not current groups",
  p2$inGroupSpeaker[p2$playerId == "l1"] == "in_group" && # l1 is A, s1 is A
    p2$inGroupSpeaker[p2$playerId == "l2"] == "out_group" && # l2 is B, s1 is A
    p2$inGroupSpeaker[p2$playerId == "l4"] == "out_group"
) # l4 is A, s2 is C
check(
  "in-group is a factor with out_group as the reference level",
  identical(levels(p2$inGroupSpeaker), c("out_group", "in_group"))
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

sg <- tibble(
  gameId = c("g1", "g2"),
  blockNum = c(0, 1),
  socialGuessCorrect = c("true", FALSE)
)
sgt <- social_guess_trials(sg, games)
check(
  "social_guess_trials keeps the social conditions only and recodes correct",
  nrow(sgt) == 1 && sgt$correct == 1 && sgt$gameId == "g1"
)
check(
  "social_guess_trials returns an empty tibble for empty input",
  nrow(social_guess_trials(tibble(), games)) == 0
)
