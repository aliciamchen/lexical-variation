# The preregistered sensitivity analyses of the Phase 2 results (H1, H2 and
# H4), each refitting the primary models on a subset of games or with one
# covariate added and reporting the planned contrasts beside the primary ones:
#
#   complete_games      games that kept all nine players
#   three_groups        games that kept all three original groups throughout
#                       Phase 2
#   active_groups       the minimum number of active original groups during
#                       Phase 2 as a covariate
#   tangram_set         tangram set as a covariate (balanced within condition,
#                       so a sensitivity analysis rather than a primary term)
#   late_arrivals       H4 with late answers dropped instead of counted as
#                       unsuccessful (lateness is per outcome: lateClick for
#                       the selection, lateSocialGuess for the guess)
#   length_adjusted     H1/H2 on group-specificity estimates adjusted for the
#                       pair's length difference and mean length, after a
#                       diagnostic of whether Phase 2 length tracks
#                       group-specificity
#
# When a restriction excludes no games the results are the primary ones by
# construction and nothing is refit. The paper does not restrict analyses to
# games with significant Phase 1 group-specificity, so no such rerun appears.
# The H1/H2 reruns read the per-game estimates from group_specificity.R; the
# H4 reruns refit the models h4.R saved, on the same data.
#
# Writes results/<dataset>/estimates/primary/robustness.csv (every rerun
# contrast, with the restriction and the games it kept) and
# primary/robustness_restrictions.csv (per restriction, how many games it
# kept and whether that left the primary analyses unchanged).

source(here::here("models", "config.R"))
suppressPackageStartupMessages({
  library(lme4)
  library(emmeans)
})
list2env(load_tables(), envir = globalenv())

gs <- gs_wide(require_estimates("primary/group_specificity", "models/primary/group_specificity.R"))
h12 <- fit_h12(gs)
contrasts <- h12$contrasts
n_real <- sum(!is.na(games$condition))

social_h4 <- social_guess_trials(social_guesses, games, SOCIAL_CONDITIONS)
p2_listener_social <- listener_trials(trials, games, phase = 2, conditions = SOCIAL_CONDITIONS) |>
  attach_speaker()
h4_specs <- list(
  list(name = "H4a", analysis = "h4a", data = social_h4,
       model = load_fit("h4a", "models/primary/h4.R"), late = "lateSocialGuess",
       weights = list(H4a_socialfirst_gt_socialmixed = c(-1, 1))),
  list(name = "H4b", analysis = "h4b", data = p2_listener_social,
       model = load_fit("h4b", "models/primary/h4.R"), late = "lateClick",
       weights = list(H4b_socialmixed_gt_socialfirst = c(1, -1)))
)
h4_primary_table <- function(spec) {
  contrast_table(contrast(emmeans(spec$model, "condition", type = "response"), spec$weights), "primary")
}

rows <- tibble()
restrictions <- tibble()
add_rows <- function(...) rows <<- bind_rows(rows, ...)
note_restriction <- function(restriction, kept, identical) {
  restrictions <<- bind_rows(restrictions, tibble(
    restriction = restriction, games_kept = as.integer(kept),
    games_excluded = as.integer(n_real - kept), identical = identical
  ))
}
# The rows of one robustness_rerun() result (complete games, three groups).
rerun_rows <- function(rr, restriction) {
  if (is.null(rr) || isTRUE(rr$identical)) {
    return(tibble())
  }
  bind_rows(
    tidy_contrast_table(rr$h12, "h1_h2", restriction = restriction, n_games = rr$n_games_h12),
    tidy_contrast_table(rr$h4$H4a$table, "h4a", restriction = restriction, n_games = rr$h4$H4a$n_games),
    tidy_contrast_table(rr$h4$H4b$table, "h4b", restriction = restriction, n_games = rr$h4$H4b$n_games)
  )
}
# One H4 model refit with a covariate, its contrast beside the primary one.
h4_with_covariate <- function(spec, d, covariate, label, restriction) {
  m <- fit_progressively(update(H4_FORMULA, as.formula(sprintf(". ~ . + %s", covariate))), data = d, family = binomial)
  if (!inherits(m, "glmerMod")) {
    return(tibble())
  }
  cat(sprintf("\n%s with %s (%s):\n", spec$name, label, random_effects_structure(m)))
  ct <- tryCatch(
    contrast(emmeans(m, "condition", type = "response"), spec$weights),
    error = function(e) {
      cat("  not estimable in this dataset:", conditionMessage(e), "\n")
      NULL
    }
  )
  if (is.null(ct)) {
    return(tibble())
  }
  print(knitr::kable(bind_rows(h4_primary_table(spec), contrast_table(ct, label)), digits = 3))
  tidy_contrasts(ct, spec$analysis, restriction = restriction, n_games = n_distinct(d$gameId),
                 n_obs = nobs(m), random_effects = random_effects_structure(m))
}

# ── Description length as a covariate ─────────────────────────────────────
cat("=== Robustness check: description length ===\n")
gs_adjusted <- gs_wide(read_estimates("primary/group_specificity_length_adjusted"))
if (!has_rows(gs_adjusted)) {
  cat("No length-adjusted estimates (group_specificity.R writes them when the pairwise table has lengths); skipped.\n")
} else {
  length_by_game <- speaker_utts |>
    filter(phaseNum == 2) |>
    group_by(gameId) |>
    summarise(mean_length_p2 = mean(uttLength, na.rm = TRUE), .groups = "drop")
  diag <- gs |> filter(both_endpoints) |> left_join(length_by_game, by = "gameId")
  cat("Mean Phase 2 description length by condition (games with both endpoints):\n")
  print(knitr::kable(
    diag |> group_by(condition) |>
      summarise(games = n(), mean_length = mean(mean_length_p2, na.rm = TRUE), .groups = "drop"),
    digits = 2
  ))
  if (nrow(diag) >= 4) {
    cat(sprintf(
      "Game-level correlation between mean Phase 2 length and Phase 2 group specificity: r = %.2f\n",
      cor(diag$mean_length_p2, diag$gs_phase2, use = "complete.obs")
    ))
  }
  h12_adjusted <- fit_h12(gs_adjusted)
  if (!is.null(h12_adjusted$contrasts) && all(table(h12_adjusted$data$condition) >= 2)) {
    cat("\nH1/H2 with length-adjusted group specificity:\n")
    print(knitr::kable(bind_rows(
      contrast_table(contrasts, "primary"),
      contrast_table(h12_adjusted$contrasts, "length-adjusted")
    ), digits = 3))
    add_rows(tidy_contrasts(h12_adjusted$contrasts, "h1_h2", restriction = "length_adjusted",
                            n_games = nrow(h12_adjusted$data)))
  } else {
    cat("\nH1/H2 rerun needs at least two games per condition; skipped.\n")
  }
  note_restriction("length_adjusted", nrow(h12_adjusted$data), FALSE)
}

# ── Complete nine-player games ────────────────────────────────────────────
complete <- complete_games(players, games)
cat(sprintf("\n%d of %d games kept all nine players.\n", length(complete), n_real))
rr_complete <- robustness_rerun(complete, "complete nine-player games",
                                gs = gs, primary_contrasts = contrasts, h4 = h4_specs)
add_rows(rerun_rows(rr_complete, "complete_games"))
note_restriction("complete_games", length(complete), isTRUE(rr_complete$identical))

# ── Phase 2 roster size ───────────────────────────────────────────────────
roster <- games |>
  filter(!is.na(condition)) |>
  transmute(gameId, activeGroupsMin = as.integer(activeGroupsMin))
three_groups <- roster |> filter(activeGroupsMin == 3) |> pull(gameId)
cat(sprintf("\n%d of %d games kept all three original groups throughout Phase 2.\n",
            length(three_groups), nrow(roster)))
rr_three_groups <- robustness_rerun(three_groups, "games with three active groups throughout Phase 2",
                                    gs = gs, primary_contrasts = contrasts, h4 = h4_specs)
add_rows(rerun_rows(rr_three_groups, "three_groups"))
note_restriction("three_groups", length(three_groups), isTRUE(rr_three_groups$identical))

gs_roster <- gs |> left_join(roster, by = "gameId") |> mutate(activeGroupsMin = factor(activeGroupsMin))
if (n_distinct(gs_roster$activeGroupsMin) < 2) {
  cat("\nEvery game has the same minimum number of active groups; the covariate is not estimable.\n")
} else {
  cat("\nGames per condition and minimum number of active groups:\n")
  print(knitr::kable(gs_roster |> count(condition, activeGroupsMin)))
  # With few games the covariate can be nested in condition, which emmeans
  # refuses to contrast; report that rather than stop.
  h12_roster <- tryCatch(
    fit_h12(gs_roster, covariate = "gs_phase1 + activeGroupsMin"),
    error = function(e) list(model = NULL, contrasts = NULL, note = conditionMessage(e))
  )
  if (is.null(h12_roster$contrasts) || any(is.na(coef(h12_roster$model)))) {
    cat("\nH1/H2 with the minimum number of active groups as a covariate is not estimable in this dataset",
        if (!is.null(h12_roster$note)) paste0(" (", h12_roster$note, ")"), ".\n", sep = "")
  } else {
    cat("\nH1/H2 with the minimum number of active groups as a covariate:\n")
    print(knitr::kable(bind_rows(
      contrast_table(contrasts, "primary"),
      contrast_table(h12_roster$contrasts, "with active groups")
    ), digits = 3))
    add_rows(tidy_contrasts(h12_roster$contrasts, "h1_h2", restriction = "active_groups",
                            n_games = nrow(h12_roster$data)))
  }
  for (spec in h4_specs) {
    d <- spec$data |>
      select(-any_of(c("activeGroups", "activeGroupsMin"))) |>
      left_join(roster, by = "gameId") |>
      mutate(activeGroupsMin = factor(activeGroupsMin))
    if (n_distinct(d$activeGroupsMin) < 2) next
    add_rows(h4_with_covariate(spec, d, "activeGroupsMin", "the number of active groups as a covariate", "active_groups"))
  }
  note_restriction("active_groups", n_real, FALSE)
}

# ── Tangram set as a covariate ────────────────────────────────────────────
if (n_distinct(games$tangramSet[!is.na(games$condition)]) < 2) {
  cat("\nOnly one tangram set in this dataset; the covariate is not estimable.\n")
} else {
  gs_set <- gs |> left_join(games |> select(gameId, tangramSet), by = "gameId") |> mutate(tangramSet = factor(tangramSet))
  cat("\nGames per condition and tangram set:\n")
  print(knitr::kable(gs_set |> count(condition, tangramSet)))
  h12_set <- fit_h12(gs_set, covariate = "gs_phase1 + tangramSet")
  if (!is.null(h12_set$contrasts)) {
    cat("\nH1/H2 with tangram set as a covariate:\n")
    print(knitr::kable(bind_rows(
      contrast_table(contrasts, "primary"),
      contrast_table(h12_set$contrasts, "with tangram set")
    ), digits = 3))
    add_rows(tidy_contrasts(h12_set$contrasts, "h1_h2", restriction = "tangram_set", n_games = nrow(h12_set$data)))
  } else {
    cat("\nH1/H2 rerun not possible:", h12_set$note, "\n")
  }
  for (spec in h4_specs) {
    if (!"tangramSet" %in% names(spec$data)) next
    d <- spec$data |> mutate(tangramSet = factor(tangramSet))
    if (n_distinct(d$tangramSet) < 2) next
    add_rows(h4_with_covariate(spec, d, "tangramSet", "tangram set as a covariate", "tangram_set"))
  }
  note_restriction("tangram_set", n_real, FALSE)
}

# ── Late arrivals ─────────────────────────────────────────────────────────
for (spec in h4_specs) {
  if (!spec$late %in% names(spec$data)) next
  late_flag <- spec$data[[spec$late]] %in% TRUE
  cat(sprintf("\n%s late arrivals (%s):\n", spec$name, spec$late))
  print(knitr::kable(late_arrival_summary(spec$data, late = .data[[spec$late]]), digits = 4))
  if (!any(late_flag)) {
    cat("No late arrivals; the sensitivity analysis is not needed.\n")
    next
  }
  d_on_time <- spec$data |> filter(!late_flag)
  m_on_time <- fit_progressively(formula(spec$model), data = d_on_time, family = binomial)
  if (!inherits(m_on_time, "glmerMod")) {
    cat("Model did not converge with late arrivals excluded.\n")
    next
  }
  cat(sprintf("%s with late arrivals excluded (%s):\n", spec$name, random_effects_structure(m_on_time)))
  ct <- contrast(emmeans(m_on_time, "condition", type = "response"), spec$weights)
  print(knitr::kable(bind_rows(h4_primary_table(spec), contrast_table(ct, "late arrivals excluded")), digits = 3))
  add_rows(tidy_contrasts(ct, spec$analysis, restriction = "late_arrivals", n_games = n_distinct(d_on_time$gameId),
                          n_obs = nobs(m_on_time), random_effects = random_effects_structure(m_on_time)))
}
note_restriction("late_arrivals", n_real, FALSE)

write_estimates(rows, "primary/robustness", source = "models/primary/robustness.R")
write_estimates(restrictions, "primary/robustness_restrictions", source = "models/primary/robustness.R")
