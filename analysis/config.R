# Shared configuration for the Quarto analysis notebooks.
#
# Sourcing this file is the whole setup a notebook needs: it resolves the
# active dataset's paths, defines the constants, and sources every helper
# file in analysis/R/ (data preparation, model fitting, group specificity,
# contrasts, Bayes factors, stats-to-LaTeX). The notebooks draw nothing;
# the article's figures are made in Python (analysis/plot_style.py).
#
# Usage (in each .qmd setup chunk):
#   source(here::here("analysis", "config.R"))
#   list2env(load_tables(), envir = globalenv())   # games, trials, ... as variables

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
})

# ── Paths ────────────────────────────────────────────────────
# Every dataset follows the same layout (mirrored in analysis/dataset_paths.py):
#   data/<name>/               preprocessed CSVs (+ raw_anonymized/, runs.txt)
#   analysis/derived/<name>/   derived metrics and model caches
#   figures/<name>/            notebook figures
# The active dataset comes from the DATASET environment variable (default
# "full").

DEFAULT_DATASET <- "full"

# Refuse a speaker_utterances_filtered.csv that was not built from the current
# messages.csv. The filtered file is derived from messages.csv through the
# classifier's labels, and nothing in it says which messages.csv it came from,
# so `filter_nonreferential.py apply` writes a sidecar with that file's sha256
# and row count. The Python steps check it (dataset_paths.py); this is the same
# check for the notebooks, which would otherwise analyze a stale file silently
# after a reprocessing that rewrote messages.csv. A missing or unreadable
# sidecar is refused as well, since the file's provenance is then unknown.
check_filtered_utterances <- function(dir) {
  sidecar <- file.path(dir, "speaker_utterances_filtered.source.json")
  messages <- file.path(dir, "messages.csv")
  refuse <- function(detail) {
    stop(
      "speaker_utterances_filtered.csv in ", dir, " cannot be used: ", detail,
      ". Rerun the filter (`filter_nonreferential.py classify` and `apply`, or ",
      "`make process`) to rebuild it from the current messages.csv.",
      call. = FALSE
    )
  }
  if (!file.exists(sidecar)) {
    refuse(
      "it has no speaker_utterances_filtered.source.json beside it, so which messages.csv it was built from is unknown"
    )
  }
  record <- tryCatch(jsonlite::fromJSON(sidecar), error = function(e) NULL)
  if (!is.list(record) || !is.character(record$sha256) || !nzchar(record$sha256)) {
    refuse("its sidecar does not record the sha256 of the messages.csv it was built from")
  }
  if (!file.exists(messages)) {
    refuse("messages.csv is missing, so it cannot be checked")
  }
  current <- digest::digest(file = messages, algo = "sha256")
  if (!identical(record$sha256, current)) {
    refuse(sprintf(
      "it was built from a messages.csv with %s rows (sha256 %s...), but the current messages.csv differs (sha256 %s...)",
      if (is.null(record$rows)) "?" else record$rows,
      substr(record$sha256, 1, 12),
      substr(current, 1, 12)
    ))
  }
  invisible(TRUE)
}

use_dataset <- function(name = Sys.getenv("DATASET", unset = DEFAULT_DATASET)) {
  stopifnot(
    is.character(name),
    length(name) == 1,
    nzchar(name),
    !grepl("/", name)
  )
  DATASET <<- name
  data_dir <<- here("data", name)
  derived_dir <<- here("analysis", "derived", name)
  figures_dir <<- here("figures", name)
  dir.create(derived_dir, showWarnings = FALSE, recursive = TRUE)
  dir.create(figures_dir, showWarnings = FALSE, recursive = TRUE)
  # Prefer filtered utterances when available, but only when their sidecar
  # shows they were built from the messages.csv beside them.
  utterances_file <<- if (
    file.exists(file.path(data_dir, "speaker_utterances_filtered.csv"))
  ) {
    check_filtered_utterances(data_dir)
    "speaker_utterances_filtered.csv"
  } else {
    "speaker_utterances.csv"
  }
  if (!file.exists(file.path(data_dir, "games.csv"))) {
    warning(
      sprintf("No processed data for dataset '%s' at %s", name, data_dir),
      call. = FALSE
    )
  }
  invisible(name)
}

use_dataset()

# ── Writing projects ─────────────────────────────────────────
# Each manuscript is its own Overleaf project under writing/ (gitignored,
# mirrored to Overleaf through Dropbox). Notebooks 00-05 write their stats
# macros into writing/manuscript/stats/, the article's project, of which only
# that directory exists until the author creates the Overleaf clone;
# writing/preregistration/ is frozen with the preregistration.
manuscript_dir <- here("writing", "manuscript")

# Where a full-sample notebook writes its statistics macros
# (writing/manuscript/stats/<notebook>.tex, \input by the manuscript). The
# stem is the notebook's macro prefix, letters only, so the file name and the
# macro names agree.
stats_file <- function(notebook) {
  stopifnot(
    is.character(notebook),
    length(notebook) == 1,
    grepl("^[A-Za-z]+$", notebook)
  )
  file.path(manuscript_dir, "stats", paste0(notebook, ".tex"))
}

# ── Dataset banner ───────────────────────────────────────────
# Every notebook prints this right after its setup chunk, in a chunk with
# results = "asis", so the rendered page says which dataset it was built from.
# A render on any dataset other than the full sample gets a warning callout,
# because the statistics macros it writes to `writing/manuscript/stats/` are
# then not results. `games` (the loaded games table) adds the game count.
dataset_banner <- function(name = DATASET, games = NULL) {
  n_games <- if (is.data.frame(games) && "condition" %in% names(games)) {
    sum(!is.na(games$condition))
  } else {
    NA_integer_
  }
  where <- sprintf(
    "This render uses `data/%s/` and `analysis/derived/%s/`%s.",
    name,
    name,
    if (is.na(n_games)) "" else sprintf(" (%d games with a condition)", n_games)
  )
  if (name == "full") {
    kind <- "note"
    title <- "Dataset: full"
    body <- where
  } else {
    kind <- "warning"
    title <- sprintf("Dataset: %s, not the full sample", name)
    body <- paste(
      where,
      "The statistics macros this render writes to `writing/manuscript/stats/`",
      "are not results; render with `DATASET=full` for the full sample."
    )
  }
  txt <- sprintf("\n::: {.callout-%s}\n## %s\n%s\n:::\n\n", kind, title, body)
  cat(txt)
  invisible(txt)
}

# ── Design constants ─────────────────────────────────────────

CONDITION_ORDER <- c(
  "refer_separated",
  "refer_mixed",
  "social_mixed",
  "social_first"
)

# The two conditions with a social-identification task (H3, H4)
SOCIAL_CONDITIONS <- c("social_mixed", "social_first")

# The conditions that share the same Phase 1 procedure; the H1/H2 model is
# restricted to them because in social_first the manipulation precedes Phase 1
H12_CONDITIONS <- c("refer_separated", "refer_mixed", "social_mixed")

GROUP_ORDER <- c("A", "B", "C")

# The analysis windows compute_derived.py writes on the pairwise similarities.
# The primary H1/H2 comparison uses the two final windows; phase2_early is
# descriptive. Named here so a plot cannot quietly fold one window into
# another (see label_window() in R/prepare.R).
WINDOW_LABELS <- c(
  phase1_final = "Phase 1 final",
  phase2_early = "Phase 2 early",
  phase2_final = "Phase 2 final"
)

# Blocks are 1-indexed in the paper: Phase 1 = 1-6, Phase 2 = 7-12
PHASE_BOUNDARY <- 6.5
PHASE2_OFFSET <- 6

# Bayes factors for non-significant planned contrasts (see R/bayes_factors.R):
# "auto" computes them only when a contrast has p >= .05, "always" computes
# them for every planned contrast, "never" skips them (fast renders).
BAYES_FACTORS <- Sys.getenv("BAYES_FACTORS", unset = "auto")

set.seed(67)

# emmeans on lmer fits: use Satterthwaite degrees of freedom explicitly (the
# default tries Kenward-Roger first and prints a note when pbkrtest is absent)
if (requireNamespace("emmeans", quietly = TRUE)) {
  emmeans::emm_options(lmer.df = "satterthwaite")
}

# ── Helpers ─────────────────────────────────────────────────
# Every file in analysis/R/ defines functions only (plus its package loads), so
# the order does not matter. See the header of each file for what it provides.

for (helper in sort(list.files(
  here("analysis", "R"),
  pattern = "\\.R$",
  full.names = TRUE
))) {
  source(helper)
}
rm(helper)
