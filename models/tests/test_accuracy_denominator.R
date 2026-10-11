# Tests for the response-opportunity frames shared by both accuracy outcomes
# (models/R/prepare.R). The rule itself is applied in
# preprocessing/preprocessing.py and tested there; these tests check that the R
# side keeps the opportunity rows, carries the coded outcome through, and
# reports the two kinds of missing outcome apart.

if (!exists("listener_trials")) {
  source(here::here("models", "config.R"))
}
if (!exists("check")) {
  source(here::here("models", "tests", "check.R"))
}

acc_games <- tibble(
  gameId = c("g1", "g2"),
  condition = c("social_mixed", "social_first")
)

# One listener of each kind, coded as the pipeline codes them: correct (1),
# incorrect (0), timeout (0), late arrival (0), a trial whose speaker never
# spoke (no opportunity, no outcome), and a speaker row (never an opportunity).
acc_trials <- tibble(
  gameId = "g1",
  playerId = c("p1", "p2", "p3", "p4", "p5", "p6"),
  roundId = c("r1", "r1", "r1", "r1", "r2", "r1"),
  originalGroup = "A",
  currentGroup = "A",
  role = c(rep("listener", 5), "speaker"),
  phaseNum = 2,
  blockNum = 1,
  target = "t1",
  clicked = c("t1", "t2", NA, "t1", "t1", NA),
  clickedCorrect = c(TRUE, FALSE, FALSE, NA, TRUE, NA),
  lateClick = c(FALSE, FALSE, FALSE, TRUE, FALSE, FALSE),
  responseOpportunity = c(TRUE, TRUE, TRUE, TRUE, FALSE, FALSE),
  hasSpeakerMessage = c(TRUE, TRUE, TRUE, TRUE, FALSE, TRUE),
  correct = c(1, 0, 0, 0, NA, NA),
  onTime = c(TRUE, TRUE, FALSE, FALSE, NA, NA),
  excluded = FALSE,
  exclusionReason = NA_character_
)

lt <- listener_trials(acc_trials, acc_games, phase = 2)
check(
  "only eligible listener opportunities enter the frame",
  nrow(lt) == 4 && setequal(lt$playerId, c("p1", "p2", "p3", "p4"))
)
check(
  "the coded outcome is carried through: a correct on-time answer is 1; incorrect, timeout and late are 0",
  lt$correct[lt$playerId == "p1"] == 1 &&
    all(lt$correct[lt$playerId %in% c("p2", "p3", "p4")] == 0)
)
check(
  "a timeout and a late arrival are not on-time responses, and the late one is flagged",
  lt$onTime[lt$playerId == "p1"] &&
    !any(lt$onTime[lt$playerId %in% c("p3", "p4")]) &&
    lt$lateArrival[lt$playerId == "p4"] &&
    !lt$lateArrival[lt$playerId == "p3"] &&
    !lt$submitted[lt$playerId == "p3"]
)
check(
  "the trial with no speaker message is excluded, not scored zero",
  !("p5" %in% lt$playerId)
)
check(
  "a table without the coded outcome is an error, not a silent fallback",
  inherits(
    try(
      listener_trials(acc_trials |> select(-correct), acc_games, phase = 2),
      silent = TRUE
    ),
    "try-error"
  )
)

# ── Missing outcomes: technical failures and participant exclusions ──────────
# The pipeline leaves `correct` empty for an observation a documented technical
# failure or a post-hoc participant exclusion made unanswerable, and flags the
# latter with `excluded` and its reason.

tech_trials <- acc_trials |>
  mutate(correct = ifelse(playerId == "p2", NA, correct))
lt_tech <- listener_trials(tech_trials, acc_games, phase = 2)
check(
  "an opportunity with no outcome and no exclusion flag is a technical failure",
  is.na(lt_tech$correct[lt_tech$playerId == "p2"]) &&
    lt_tech$technicalFailure[lt_tech$playerId == "p2"] &&
    !lt_tech$participantExcluded[lt_tech$playerId == "p2"] &&
    lt_tech$correct[lt_tech$playerId == "p3"] == 0
)

excl_trials <- acc_trials |>
  mutate(
    excluded = playerId == "p2",
    exclusionReason = ifelse(
      playerId == "p2",
      "speaker excluded: adversarial messages",
      ""
    ),
    correct = ifelse(playerId == "p2", NA, correct)
  )
lt_part <- listener_trials(excl_trials, acc_games, phase = 2)
check(
  "a post-hoc participant exclusion is missing, not unsuccessful, and keeps its row and reason",
  nrow(lt_part) == 4 &&
    is.na(lt_part$correct[lt_part$playerId == "p2"]) &&
    lt_part$participantExcluded[lt_part$playerId == "p2"] &&
    !lt_part$technicalFailure[lt_part$playerId == "p2"] &&
    lt_part$exclusionReason[lt_part$playerId == "p2"] ==
      "speaker excluded: adversarial messages" &&
    lt_part$correct[lt_part$playerId == "p1"] == 1
)
check(
  "a frame without exclusions is coded as nobody excluded",
  all(!lt$participantExcluded) && all(is.na(lt$exclusionReason))
)
check("an excluded row with a blank reason is still excluded and says so", {
  blank <- listener_trials(
    excl_trials |> mutate(exclusionReason = ""),
    acc_games,
    phase = 2
  )
  blank$exclusionReason[blank$playerId == "p2"] ==
    "excluded (no reason recorded)"
})

# ── Reporting ───────────────────────────────────────────────────────────────

summ <- response_opportunity_summary(lt, by = "phaseNum")
check(
  "the summary separates nonresponse from incorrect answers",
  summ$opportunities == 4 &&
    summ$on_time == 2 &&
    abs(summ$on_time_rate - 0.5) < 1e-12 &&
    abs(summ$accuracy - 0.25) < 1e-12 &&
    abs(summ$accuracy_on_time - 0.5) < 1e-12
)
s_tech <- response_opportunity_summary(lt_tech, by = "phaseNum")
check(
  "technically excluded observations are reported and left out of the rates",
  s_tech$opportunities == 4 &&
    s_tech$excluded_technical == 1 &&
    s_tech$excluded_participant == 0 &&
    s_tech$scored == 3
)
s_part <- response_opportunity_summary(lt_part, by = "phaseNum")
check(
  "participant exclusions are reported apart from technical ones and left out of the rates",
  s_part$opportunities == 4 &&
    s_part$excluded_participant == 1 &&
    s_part$excluded_technical == 0 &&
    s_part$scored == 3 &&
    abs(s_part$accuracy - 1 / 3) < 1e-12
)
pes <- participant_exclusion_summary(lt_part)
check(
  "participant_exclusion_summary lists the excluded rows by reason and kind",
  nrow(pes) == 1 &&
    pes$observations == 1 &&
    pes$kind == "listener of an excluded speaker" &&
    pes$exclusionReason == "speaker excluded: adversarial messages"
)
check(
  "participant_exclusion_summary is empty when nothing was excluded",
  nrow(participant_exclusion_summary(lt)) == 0
)
late_summ <- late_arrival_summary(lt, by = NULL)
check(
  "late arrivals are counted and rated over opportunities",
  late_summ$late_arrivals == 1 && abs(late_summ$late_rate - 0.25) < 1e-12
)
check("the sensitivity analysis drops late arrivals instead of scoring them zero", {
  kept <- drop_late_arrivals(lt)
  nrow(kept) == 3 && !("p4" %in% kept$playerId)
})

# ── Social guesses ──────────────────────────────────────────────────────────

acc_guesses <- tibble(
  gameId = "g1",
  playerId = c("p1", "p2", "p3", "p4", "p5"),
  roundId = "r1",
  originalGroup = "A",
  currentGroup = "A",
  phaseNum = 2,
  blockNum = 1,
  target = "t1",
  speakerId = "p6",
  socialGuess = c(
    "same_group",
    "different_group",
    NA,
    "same_group",
    "same_group"
  ),
  socialGuessCorrect = c(TRUE, FALSE, NA, NA, TRUE),
  socialTimeout = c(FALSE, FALSE, TRUE, FALSE, FALSE),
  lateSocialGuess = c(FALSE, FALSE, FALSE, TRUE, FALSE),
  responseOpportunity = c(TRUE, TRUE, TRUE, TRUE, FALSE),
  correct = c(1, 0, 0, 0, NA),
  onTime = c(TRUE, TRUE, FALSE, FALSE, NA),
  excluded = FALSE,
  exclusionReason = NA_character_
)
sg <- social_guess_trials(acc_guesses, acc_games)
check(
  "an unanswered social guess counts as unsuccessful rather than vanishing",
  nrow(sg) == 4 &&
    sg$correct[sg$playerId == "p3"] == 0 &&
    !sg$submitted[sg$playerId == "p3"]
)
check(
  "a late social guess is unsuccessful and not on time",
  sg$correct[sg$playerId == "p4"] == 0 &&
    !sg$onTime[sg$playerId == "p4"] &&
    sg$lateArrival[sg$playerId == "p4"]
)
check(
  "a social opportunity with no speaker message is excluded",
  !("p5" %in% sg$playerId)
)
check("social lateness is assessed with its own flag, not the tangram one", {
  kept <- drop_late_arrivals(sg, late = lateSocialGuess)
  nrow(kept) == 3 && !("p4" %in% kept$playerId)
})
sg_part <- social_guess_trials(
  acc_guesses |>
    mutate(
      excluded = playerId == "p1",
      exclusionReason = ifelse(playerId == "p1", "bot-like responses", ""),
      correct = ifelse(playerId == "p1", NA, correct)
    ),
  acc_games
)
check(
  "an excluded participant's own social guess is missing with its reason",
  is.na(sg_part$correct[sg_part$playerId == "p1"]) &&
    sg_part$exclusionReason[sg_part$playerId == "p1"] == "bot-like responses" &&
    participant_exclusion_summary(sg_part)$kind ==
      "excluded participant's own" &&
    sg_part$correct[sg_part$playerId == "p2"] == 0
)

# ── The technical-exclusions file, read to report it ────────────────────────

excl_dir <- file.path(tempdir(), "excl")
dir.create(excl_dir, showWarnings = FALSE)
check(
  "technical_exclusions is empty without the file",
  nrow(technical_exclusions(excl_dir)) == 0
)
readr::write_csv(
  tibble(
    gameId = "g1",
    playerId = "p2",
    roundId = "r1",
    outcome = "referential",
    reason = "listener browser crashed mid-trial"
  ),
  file.path(excl_dir, "technical_exclusions.csv")
)
check(
  "technical_exclusions reads the documented failures",
  nrow(technical_exclusions(excl_dir)) == 1
)
readr::write_csv(
  tibble(
    gameId = "g1",
    playerId = "p2",
    roundId = "r1",
    outcome = "social",
    reason = "  "
  ),
  file.path(excl_dir, "technical_exclusions.csv")
)
check(
  "an exclusion with no recorded reason is rejected",
  inherits(try(technical_exclusions(excl_dir), silent = TRUE), "try-error")
)
readr::write_csv(
  tibble(
    gameId = "g1",
    playerId = "p2",
    roundId = "r1",
    outcome = "other",
    reason = "x"
  ),
  file.path(excl_dir, "technical_exclusions.csv")
)
check(
  "an unknown outcome is rejected",
  inherits(try(technical_exclusions(excl_dir), silent = TRUE), "try-error")
)
unlink(excl_dir, recursive = TRUE)
