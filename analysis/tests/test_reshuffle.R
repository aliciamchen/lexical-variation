# Tests for the reshuffle-health summary in analysis/R/reshuffle.R.

if (!exists("reshuffle_health")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

# ── Fixture: one mixed game with a reduced roster, one separated game ────────
#
# g1 (social_mixed) has three Phase 2 rounds after one player (C2) left.
#   r1: group X is a trio with exactly one in-group listener; group Y is a pair
#       with an out-group listener.
#   r2: group X is a trio with two in-group listeners (rule not met); group Y is
#       a pair with an in-group listener; C0 speaks in a block whose designated
#       index is 1, so that is a reassignment.
#   r3: like r1.
# g2 (refer_separated) has one Phase 2 round with the original trio.

games <- tibble(
  gameId = c("g1", "g2"),
  condition = c("social_mixed", "refer_separated"),
  activeGroups = c(3, 3)
)

players <- tribble(
  ~gameId , ~playerId , ~originalGroup , ~playerIndex ,
  "g1"    , "A0"      , "A"            ,            0 , "g1" , "A1" , "A" , 1 , "g1" , "A2" , "A" , 2 ,
  "g1"    , "B0"      , "B"            ,            0 , "g1" , "B1" , "B" , 1 , "g1" , "B2" , "B" , 2 ,
  "g1"    , "C0"      , "C"            ,            0 , "g1" , "C1" , "C" , 1 , "g1" , "C2" , "C" , 2 ,
  "g2"    , "D0"      , "A"            ,            0 , "g2" , "D1" , "A" , 1 , "g2" , "D2" , "A" , 2
)

row <- function(
  gameId,
  roundId,
  playerId,
  og,
  cg,
  role,
  phaseNum,
  blockNum,
  trialNum
) {
  tibble(
    gameId,
    roundId,
    playerId,
    originalGroup = og,
    currentGroup = cg,
    role,
    phaseNum,
    blockNum,
    trialNum,
    phase = "refgame"
  )
}
trials <- bind_rows(
  # Phase 1 round for g1 (fixed trio, designated speaker)
  row("g1", "p1", "A0", "A", "A", "speaker", 1, 0, 1),
  row("g1", "p1", "A1", "A", "A", "listener", 1, 0, 1),
  row("g1", "p1", "A2", "A", "A", "listener", 1, 0, 1),
  # r1, block 0 (designated index 0)
  row("g1", "r1", "A0", "A", "X", "speaker", 2, 0, 37),
  row("g1", "r1", "A1", "A", "X", "listener", 2, 0, 37),
  row("g1", "r1", "B2", "B", "X", "listener", 2, 0, 37),
  row("g1", "r1", "B0", "B", "Y", "speaker", 2, 0, 37),
  row("g1", "r1", "C1", "C", "Y", "listener", 2, 0, 37),
  # r2, block 1 (designated index 1)
  row("g1", "r2", "A1", "A", "X", "speaker", 2, 1, 43),
  row("g1", "r2", "A0", "A", "X", "listener", 2, 1, 43),
  row("g1", "r2", "A2", "A", "X", "listener", 2, 1, 43),
  row("g1", "r2", "C0", "C", "Y", "speaker", 2, 1, 43),
  row("g1", "r2", "C1", "C", "Y", "listener", 2, 1, 43),
  # r3, block 2 (designated index 2)
  row("g1", "r3", "B2", "B", "X", "speaker", 2, 2, 49),
  row("g1", "r3", "B1", "B", "X", "listener", 2, 2, 49),
  row("g1", "r3", "A0", "A", "X", "listener", 2, 2, 49),
  row("g1", "r3", "A2", "A", "Y", "speaker", 2, 2, 49),
  row("g1", "r3", "C1", "C", "Y", "listener", 2, 2, 49),
  # g2 Phase 2 round, block 0
  row("g2", "q1", "D0", "A", "A", "speaker", 2, 0, 37),
  row("g2", "q1", "D1", "A", "A", "listener", 2, 0, 37),
  row("g2", "q1", "D2", "A", "A", "listener", 2, 0, 37)
)

# ── group_trials ─────────────────────────────────────────────────────────────

gt <- group_trials(trials)
check("one row per game, round, and current group", nrow(gt) == 8)
check(
  "the in-group listener count follows the speaker's original group",
  gt$n_in_group[gt$roundId == "r1" & gt$currentGroup == "X"] == 1 &&
    gt$n_in_group[gt$roundId == "r2" & gt$currentGroup == "X"] == 2 &&
    gt$n_in_group[gt$roundId == "r1" & gt$currentGroup == "Y"] == 0 &&
    gt$n_in_group[gt$roundId == "r2" & gt$currentGroup == "Y"] == 1
)
check(
  "group sizes are counted per current group",
  all(gt$size[gt$currentGroup == "X"] == 3) &&
    all(gt$size[gt$currentGroup == "Y"] == 2)
)

# ── reshuffle_health ─────────────────────────────────────────────────────────

health <- reshuffle_health(trials, games, players)
g1 <- health[health$gameId == "g1", ]
g2 <- health[health$gameId == "g2", ]

check("one row per game", nrow(health) == 2)
check(
  "Phase 2 rounds are counted",
  g1$phase2_rounds == 3 && g2$phase2_rounds == 1
)
check(
  "the Phase 2 roster is the number of distinct players in the first and last round",
  g1$phase2_players_start == 5 &&
    g1$phase2_players_end == 5 &&
    g2$phase2_players_start == 3
)
check(
  "trios and pairs are split by size",
  g1$trios == 3 && g1$pairs == 3 && g2$trios == 1 && g2$pairs == 0
)
check("trios meeting the rule are counted", g1$trios_one_in_group == 2)
check(
  "the share of trios meeting the rule is reported for mixed games only",
  isTRUE(all.equal(g1$prop_trios_one_in_group, 2 / 3)) &&
    is.na(g2$prop_trios_one_in_group)
)
check(
  "speaker reassignments are derived from the rotation index when the flag is absent",
  g1$speaker_reassignments == 1 && g2$speaker_reassignments == 0
)

# The exported flag takes precedence when present
flagged <- trials |>
  mutate(speakerReassigned = role == "speaker" & playerId == "B2")
health_flag <- reshuffle_health(flagged, games, players)
check(
  "the exported speakerReassigned flag is used when present",
  health_flag$speaker_reassignments[health_flag$gameId == "g1"] == 1 &&
    health_flag$speaker_reassignments[health_flag$gameId == "g2"] == 0
)

# Without players or the flag the count is missing rather than wrong
health_none <- reshuffle_health(trials, games)
check(
  "the reassignment count is missing when neither source is available",
  all(is.na(health_none$speaker_reassignments))
)
