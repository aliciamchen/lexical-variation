# Tests for the response-opportunity denominator shared by both accuracy
# outcomes (analysis/R/prepare.R).

if (!exists("listener_trials")) source(here::here("analysis", "config.R"))
if (!exists("check")) source(here::here("analysis", "tests", "check.R"))

acc_games <- tibble(
  gameId = c("g1", "g2"),
  condition = c("social_mixed", "social_first")
)

# One listener of each kind: correct, incorrect, timeout, late arrival, and a
# trial whose speaker never spoke. Plus a speaker row, which is never an
# opportunity.
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
  # r2's speaker said nothing, so p5 had no response opportunity
  responseOpportunity = c(TRUE, TRUE, TRUE, TRUE, FALSE, FALSE),
  hasSpeakerMessage = c(TRUE, TRUE, TRUE, TRUE, FALSE, TRUE)
)

no_exclusions <- technical_exclusions(tempdir())
lt <- listener_trials(acc_trials, acc_games, phase = 2, exclusions = no_exclusions)

check(
  "only eligible listener opportunities enter the denominator",
  nrow(lt) == 4 && setequal(lt$playerId, c("p1", "p2", "p3", "p4"))
)
check(
  "a correct on-time answer is 1; incorrect, timeout, and late are all 0",
  lt$correct[lt$playerId == "p1"] == 1 &&
    all(lt$correct[lt$playerId %in% c("p2", "p3", "p4")] == 0)
)
check(
  "a timeout and a late arrival are not counted as on-time responses",
  lt$onTime[lt$playerId == "p1"] &&
    !any(lt$onTime[lt$playerId %in% c("p3", "p4")])
)
check(
  "the trial with no speaker message is excluded, not scored zero",
  !("p5" %in% lt$playerId)
)

# The rule must not be reachable on a dataset processed before it landed.
check(
  "trials without the opportunity columns are an error, not a silent fallback",
  inherits(
    try(listener_trials(acc_trials |> select(-responseOpportunity), acc_games,
                        phase = 2, exclusions = no_exclusions), silent = TRUE),
    "try-error"
  )
)

# Historical coding: every scored answer counts, nothing is excluded.
hist_lt <- listener_trials(acc_trials, acc_games, phase = 2,
                           denominator = "submitted", exclusions = no_exclusions)
check(
  "the historical coding keeps all listener rows and drops only unscored ones",
  nrow(hist_lt) == 5 &&
    sum(!is.na(hist_lt$correct)) == 4 &&
    is.na(hist_lt$correct[hist_lt$playerId == "p4"])
)
check(
  "the historical coding counts a timeout the server scored false as incorrect",
  hist_lt$correct[hist_lt$playerId == "p3"] == 0
)

# ── Technical exclusions ────────────────────────────────────────────────────

excl_dir <- file.path(tempdir(), "excl")
dir.create(excl_dir, showWarnings = FALSE)
readr::write_csv(
  tibble(gameId = "g1", playerId = "p2", roundId = "r1",
         outcome = "referential", reason = "listener browser crashed mid-trial"),
  file.path(excl_dir, "technical_exclusions.csv")
)
lt_excl <- listener_trials(acc_trials, acc_games, phase = 2,
                           exclusions = technical_exclusions(excl_dir))
check(
  "a documented technical failure is missing, not unsuccessful",
  is.na(lt_excl$correct[lt_excl$playerId == "p2"]) &&
    lt_excl$correct[lt_excl$playerId == "p3"] == 0
)
check(
  "a technical exclusion for the other outcome leaves this one alone",
  {
    readr::write_csv(
      tibble(gameId = "g1", playerId = "p2", roundId = "r1",
             outcome = "social", reason = "social widget failed to render"),
      file.path(excl_dir, "technical_exclusions.csv")
    )
    other <- listener_trials(acc_trials, acc_games, phase = 2,
                             exclusions = technical_exclusions(excl_dir))
    other$correct[other$playerId == "p2"] == 0
  }
)
check(
  "an exclusion with no recorded reason is rejected",
  {
    readr::write_csv(
      tibble(gameId = "g1", playerId = "p2", roundId = "r1",
             outcome = "social", reason = "  "),
      file.path(excl_dir, "technical_exclusions.csv")
    )
    inherits(try(technical_exclusions(excl_dir), silent = TRUE), "try-error")
  }
)
unlink(excl_dir, recursive = TRUE)

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
  socialGuess = c("same_group", "different_group", NA, "same_group", "same_group"),
  socialGuessCorrect = c(TRUE, FALSE, NA, NA, TRUE),
  socialTimeout = c(FALSE, FALSE, TRUE, FALSE, FALSE),
  lateSocialGuess = c(FALSE, FALSE, FALSE, TRUE, FALSE),
  responseOpportunity = c(TRUE, TRUE, TRUE, TRUE, FALSE)
)
sg <- social_guess_trials(acc_guesses, acc_games, exclusions = no_exclusions)
check(
  "an unanswered social guess counts as unsuccessful rather than vanishing",
  nrow(sg) == 4 && sg$correct[sg$playerId == "p3"] == 0 &&
    sg$socialTimeout[sg$playerId == "p3"]
)
check(
  "a late social guess is unsuccessful and not on time",
  sg$correct[sg$playerId == "p4"] == 0 && !sg$onTime[sg$playerId == "p4"]
)
check(
  "a social opportunity with no speaker message is excluded",
  !("p5" %in% sg$playerId)
)
hist_sg <- social_guess_trials(acc_guesses, acc_games, denominator = "submitted",
                               exclusions = no_exclusions)
check(
  "the historical social coding keeps only submitted guesses",
  nrow(hist_sg) == 4 && !("p3" %in% hist_sg$playerId) &&
    abs(mean(hist_sg$correct, na.rm = TRUE) - 2 / 3) < 1e-12
)

# ── Reporting ───────────────────────────────────────────────────────────────

summ <- response_opportunity_summary(lt, by = "phaseNum")
check(
  "the summary separates nonresponse from incorrect answers",
  summ$opportunities == 4 && summ$on_time == 2 &&
    abs(summ$on_time_rate - 0.5) < 1e-12 &&
    abs(summ$accuracy - 0.25) < 1e-12 &&
    abs(summ$accuracy_on_time - 0.5) < 1e-12
)
check(
  "technically excluded observations are reported and left out of the rates",
  {
    dir.create(excl_dir, showWarnings = FALSE)
    readr::write_csv(
      tibble(gameId = "g1", playerId = "p2", roundId = "r1",
             outcome = "both", reason = "server dropped the round"),
      file.path(excl_dir, "technical_exclusions.csv")
    )
    s <- response_opportunity_summary(
      listener_trials(acc_trials, acc_games, phase = 2,
                      exclusions = technical_exclusions(excl_dir)),
      by = "phaseNum"
    )
    unlink(excl_dir, recursive = TRUE)
    s$opportunities == 4 && s$excluded_technical == 1 && s$scored == 3
  }
)

late_summ <- late_arrival_summary(lt, by = NULL)
check(
  "late arrivals are counted and rated over opportunities",
  late_summ$late_arrivals == 1 && abs(late_summ$late_rate - 0.25) < 1e-12
)
check(
  "the sensitivity analysis drops late arrivals instead of scoring them zero",
  {
    kept <- drop_late_arrivals(lt)
    nrow(kept) == 3 && !("p4" %in% kept$playerId)
  }
)
check(
  "social lateness is assessed with its own flag, not the tangram one",
  {
    kept <- drop_late_arrivals(sg, late = lateSocialGuess)
    nrow(kept) == 3 && !("p4" %in% kept$playerId)
  }
)
