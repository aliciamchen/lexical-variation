# Shared configuration for the R model scripts.
#
# Sourcing this file is the whole setup a script needs: it resolves the
# active dataset's paths, defines the design constants, and sources every
# helper file in models/R/ (data preparation, model fitting, group
# specificity, contrasts, Bayes factors, the estimates writer). The scripts
# draw nothing and format no statistics: each fits its models and writes
# tidy estimates tables with write_estimates(); report/inferential.py turns
# those into the manuscript's macros and report/figures/ draws from them.
#
# Usage (at the top of each models/<family>/<name>.R):
#   source(here::here("models", "config.R"))
#   tables <- load_tables()

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
})

# ── Paths ────────────────────────────────────────────────────
# Every dataset follows the same layout (defined in preprocessing/dataset_paths.py):
# the hand-written inputs at the top of data/<name>/ and the generated files
# one level down, in a directory per stage. The scripts read
#   data/<name>/tables/         the analysis-ready tables
#   data/<name>/measures/       similarity tables and description properties
#   data/<name>/model_inputs/   the aggregated tables the models are fit to
# and write
#   results/<name>/estimates/   the estimates tables, one per script
#   data/<name>/cache/          fitted objects kept between runs
# The active dataset comes from the DATASET environment variable (default
# "full").

DEFAULT_DATASET <- "full"


DEFAULT_DATASET <- "full"

# Refuse a speaker_utterances_filtered.csv that was not built from the current
# messages.csv. The filtered file is derived from messages.csv through the
# classifier's labels, and nothing in it says which messages.csv it came from,
# so `filter_nonreferential.py apply` writes a sidecar with that file's sha256
# and row count. The Python steps check it (dataset_paths.py); this is the same
# check for the model scripts, which would otherwise analyze a stale file silently
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
  dataset_dir <<- here("data", name)
  tables_dir <<- file.path(dataset_dir, "tables")
  measures_dir <<- file.path(dataset_dir, "measures")
  model_inputs_dir <<- file.path(dataset_dir, "model_inputs")
  cache_dir <<- file.path(dataset_dir, "cache")
  results_dir <<- here("results", name)
  estimates_dir <<- file.path(results_dir, "estimates")
  dir.create(estimates_dir, showWarnings = FALSE, recursive = TRUE)
  dir.create(cache_dir, showWarnings = FALSE, recursive = TRUE)
  # Prefer filtered utterances when available, but only when their sidecar
  # shows they were built from the messages.csv beside them.
  utterances_file <<- if (
    file.exists(file.path(tables_dir, "speaker_utterances_filtered.csv"))
  ) {
    check_filtered_utterances(tables_dir)
    "speaker_utterances_filtered.csv"
  } else {
    "speaker_utterances.csv"
  }
  if (!file.exists(file.path(tables_dir, "games.csv"))) {
    warning(
      sprintf("No processed data for dataset '%s' at %s", name, tables_dir),
      call. = FALSE
    )
  }
  if (name != DEFAULT_DATASET) {
    message(sprintf(
      "Dataset '%s' is not the full sample: the estimates written to %s are not results.",
      name, estimates_dir
    ))
  }
  invisible(name)
}

use_dataset()

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

# The analysis windows compute_measures.py writes on the pairwise similarities.
# The primary H1/H2 comparison uses the two final windows; phase2_early is
# descriptive. Named here so a consumer cannot quietly fold one window into
# another (see label_window() in R/prepare.R).
WINDOW_LABELS <- c(
  phase1_final = "Phase 1 final",
  phase2_early = "Phase 2 early",
  phase2_final = "Phase 2 final"
)

# Blocks are 1-indexed in the paper: Phase 1 = 1-6, Phase 2 = 7-12
PHASE_BOUNDARY <- 6.5
PHASE2_OFFSET <- 6

# Bayes factors for non-significant planned contrasts (see R/bayes_factors.R
# and models/primary/bayes_factors.R): "auto" computes them only when a
# contrast has p >= .05, "always" computes them for every planned contrast,
# "never" skips the script without touching its earlier estimates.
BAYES_FACTORS <- Sys.getenv("BAYES_FACTORS", unset = "auto")

set.seed(67)

# emmeans on lmer fits: use Satterthwaite degrees of freedom explicitly (the
# default tries Kenward-Roger first and prints a note when pbkrtest is absent)
if (requireNamespace("emmeans", quietly = TRUE)) {
  emmeans::emm_options(lmer.df = "satterthwaite")
}

# ── Helpers ─────────────────────────────────────────────────
# Every file in models/R/ defines functions only (plus its package loads), so
# the order does not matter. See the header of each file for what it provides.

for (helper in sort(list.files(
  here("models", "R"),
  pattern = "\\.R$",
  full.names = TRUE
))) {
  source(helper)
}
rm(helper)

# ── Fitted objects kept between scripts ──────────────────────
# A script that fits a model other scripts reuse (the H4 logistic models,
# which the robustness and Bayes-factor scripts refit on subsets or in brms)
# saves it here; the readers stop with the script to run when it is absent.
fits_dir <- function() {
  d <- file.path(cache_dir, "fits")
  dir.create(d, showWarnings = FALSE, recursive = TRUE)
  d
}
save_fit <- function(object, name) {
  path <- file.path(fits_dir(), paste0(name, ".rds"))
  saveRDS(object, path)
  invisible(path)
}
load_fit <- function(name, written_by) {
  path <- file.path(fits_dir(), paste0(name, ".rds"))
  if (!file.exists(path)) {
    stop(
      sprintf("%s is missing; run `Rscript %s` first (or `make models`).", path, written_by),
      call. = FALSE
    )
  }
  readRDS(path)
}
