# Group specificity block by block: the trajectory the preregistration
# describes beside the two endpoints. For each game, the per-game model of the
# endpoints
#
#   similarity ~ sameGroup + (1 | target) + (1 | speakerPair)
#
# is fit to the pairs of each speaker's most recent description of a tangram
# at each block, resetting at the phase boundary. A tangram enters from the
# block in which every original group with a description of it has two
# describers, so the first block of each phase has no estimate. It describes
# how group specificity emerges and changes and gates nothing; the hypotheses
# are tested on the endpoints in primary/group_specificity.R.
#
# Writes results/estimates/checks/specificity_trajectory.csv: one row per
# game, phase and block with eligible pairs, with the coefficient, its
# standard error, whether the fit was singular, the pairs and tangrams it
# rests on, the condition and the paper's block numbers (`block` within the
# phase, `gameBlock` across the game, as trials.csv carries them).

source(here::here("stats", "config.R"))
list2env(load_tables(), envir = globalenv())

if (!has_rows(block_pairwise_sim)) {
  stop(
    "No block-by-block pairwise similarities; run the measures step first.",
    call. = FALSE
  )
}

blocks <- trials |>
  transmute(
    gameId = as.character(gameId),
    phaseNum = as.integer(phaseNum),
    blockNum = as.integer(blockNum),
    block,
    gameBlock
  ) |>
  distinct()
trajectory <- block_specificity_table(block_pairwise_sim) |>
  left_join(
    games |>
      filter(!is.na(condition)) |>
      transmute(gameId = as.character(gameId), condition),
    by = "gameId"
  ) |>
  filter(!is.na(condition)) |>
  left_join(blocks, by = c("gameId", "phaseNum", "blockNum")) |>
  mutate(condition = factor(condition, levels = CONDITION_ORDER)) |>
  select(
    gameId,
    condition,
    phaseNum,
    blockNum,
    block,
    gameBlock,
    coefficient,
    std_error,
    t_value,
    singular,
    n_pairs,
    n_targets,
    estimable,
    note
  ) |>
  arrange(condition, gameId, gameBlock)

cat(sprintf(
  "%d game-blocks from the start rule on, %d with an estimate, %d of them singular.\n",
  nrow(trajectory),
  sum(trajectory$estimable),
  sum(trajectory$singular %in% TRUE & trajectory$estimable)
))
not_estimable <- trajectory |> filter(!estimable)
if (nrow(not_estimable) > 0) {
  cat("\nGame-blocks without an estimate, by reason:\n")
  print(knitr::kable(not_estimable |> count(note)))
}
cat(
  "\nMean group specificity by condition and block (games with an estimate):\n"
)
print(knitr::kable(
  trajectory |>
    filter(estimable) |>
    group_by(condition, gameBlock) |>
    summarise(
      games = n(),
      mean_specificity = mean(coefficient),
      .groups = "drop"
    ) |>
    pivot_wider(
      names_from = condition,
      values_from = c(mean_specificity, games)
    ),
  digits = 3
))

write_estimates(
  trajectory,
  "checks/specificity_trajectory",
  source = "stats/checks/specificity_trajectory.R"
)
