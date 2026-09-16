# Shared configuration for the Quarto analysis notebooks.
#
# Sourcing this file is the whole setup a notebook needs: it resolves the
# active dataset's paths, defines the constants and palettes, sets the ggplot
# theme, and sources every helper file in analysis/R/ (data preparation, model
# fitting, group specificity, contrasts, Bayes factors, stats-to-LaTeX,
# plotting).
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
# "pilots"); a notebook that is tied to one dataset, such as SI_pilot.qmd,
# calls use_dataset("pilots") after sourcing this file.

DEFAULT_DATASET <- "pilots"

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
  # Prefer filtered utterances when available
  utterances_file <<- if (
    file.exists(file.path(data_dir, "speaker_utterances_filtered.csv"))
  ) {
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
# mirrored to Overleaf through Dropbox). The SI notebooks write their stats
# macros and figures into the preregistration; the full-sample notebooks will
# write into the manuscript once it exists.
prereg_dir <- here("writing", "preregistration")
manuscript_dir <- here("writing", "manuscript")

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

# Blocks are 1-indexed in plots: Phase 1 = 1-6, Phase 2 = 7-12
PHASE_BOUNDARY <- 6.5
PHASE2_OFFSET <- 6

# Bayes factors for non-significant planned contrasts (see R/bayes_factors.R):
# "auto" computes them only when a contrast has p >= .05, "always" computes
# them for every planned contrast, "never" skips them (fast renders).
BAYES_FACTORS <- Sys.getenv("BAYES_FACTORS", unset = "auto")

# ── Color palettes (match analysis/plot_style.py) ────────────

CONDITION_COLORS <- c(
  refer_separated = "#016E4A",
  refer_mixed = "#029E73",
  social_mixed = "#DE8F05",
  social_first = "#A86B04"
)

CONDITION_LABELS <- c(
  refer_separated = "Refer separated",
  refer_mixed = "Refer mixed",
  social_mixed = "Social mixed",
  social_first = "Social-first"
)

GROUP_COLORS <- c(A = "#ce3045", B = "#27689e", C = "#edc35d")

# ── Global ggplot theme ───────────────────────────────────

theme_set(
  theme_classic(base_size = 18) +
    theme(
      strip.background = element_blank(),
      text = element_text(family = "Arial Nova"),
      panel.spacing = unit(1, "lines"),
      strip.text = element_text(size = 18),
      legend.key = element_blank()
    )
)

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
