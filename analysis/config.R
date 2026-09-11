# Shared configuration for Quarto analysis notebooks.
#
# Defines data/output paths, color palettes (matching Python plot_style.py),
# and a global ggplot theme.
#
# Usage (in each .qmd setup chunk):
#   source(here("analysis", "config.R"))

library(tidyverse)
library(here)

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
  stopifnot(is.character(name), length(name) == 1, nzchar(name), !grepl("/", name))
  DATASET <<- name
  data_dir <<- here("data", name)
  derived_dir <<- here("analysis", "derived", name)
  figures_dir <<- here("figures", name)
  dir.create(derived_dir, showWarnings = FALSE, recursive = TRUE)
  dir.create(figures_dir, showWarnings = FALSE, recursive = TRUE)
  # Prefer filtered utterances when available
  utterances_file <<- if (file.exists(file.path(data_dir, "speaker_utterances_filtered.csv"))) {
    "speaker_utterances_filtered.csv"
  } else {
    "speaker_utterances.csv"
  }
  if (!file.exists(file.path(data_dir, "games.csv"))) {
    warning(sprintf("No processed data for dataset '%s' at %s", name, data_dir), call. = FALSE)
  }
  invisible(name)
}

use_dataset()

# ── Color palettes (match analysis/plot_style.py) ────────────

CONDITION_COLORS <- c(
  refer_separated = "#016E4A",
  refer_mixed     = "#029E73",
  social_mixed    = "#DE8F05",
  social_first    = "#A86B04"
)

CONDITION_ORDER <- c("refer_separated", "refer_mixed", "social_mixed", "social_first")

CONDITION_LABELS <- c(
  refer_separated = "Refer separated",
  refer_mixed     = "Refer mixed",
  social_mixed    = "Social mixed",
  social_first    = "Social-first"
)

GROUP_COLORS <- c(A = "#ce3045", B = "#27689e", C = "#edc35d")
GROUP_ORDER  <- c("A", "B", "C")

# ── Phase boundary ──────────────────────────────────────────
# Blocks are 1-indexed in plots: Phase 1 = 1–6, Phase 2 = 7–12
PHASE_BOUNDARY <- 6.5
PHASE2_OFFSET  <- 6

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

# ── Helper scales ───────────────────────────────────────────

scale_color_condition <- function(labels = function(x) format_condition(x), ...) {
  scale_color_manual(values = CONDITION_COLORS, labels = labels, ...)
}

scale_fill_condition <- function(labels = function(x) format_condition(x), ...) {
  scale_fill_manual(values = CONDITION_COLORS, labels = labels, ...)
}

scale_color_group <- function(...) {
  scale_color_manual(values = GROUP_COLORS, ...)
}

scale_fill_group <- function(...) {
  scale_fill_manual(values = GROUP_COLORS, ...)
}

# ── Plot layers ───────────────────────────────────────────

# Phase 2 background shading, vline, and 1–12 x-axis breaks
phase2_layers <- function() {
  list(
    annotate("rect", xmin = PHASE_BOUNDARY, xmax = Inf,
             ymin = -Inf, ymax = Inf, fill = "gray90", alpha = 0.5),
    geom_vline(xintercept = PHASE_BOUNDARY, color = "gray70", linetype = "dotted"),
    scale_x_continuous(breaks = 1:12, limits = c(0.8, 12.2), labels = as.integer)
  )
}

# Bold tag theme for patchwork plot_annotation
TAG_THEME <- theme(plot.tag = element_text(face = "bold", size = 20))

# Extract a standalone legend grob from a ggplot
extract_legend <- function(p) {
  g <- ggplotGrob(p)
  g$grobs[[which(g$layout$name == "guide-box-bottom")]]
}

# ── Helper functions ────────────────────────────────────────

continuous_block <- function(df) {
  df |> mutate(block = blockNum + (phaseNum == 2) * PHASE2_OFFSET)
}

format_condition <- function(x) {
  ifelse(x %in% names(CONDITION_LABELS), CONDITION_LABELS[x],
         str_to_sentence(str_replace_all(x, "_", " ")))
}

# ── P-value formatting ───────────────────────────────────

fmt_pval <- function(p) {
  if (p < .001) return("< .001")
  sub("^0", "", sprintf("%.3f", p))
}

# ── Effect sizes ──────────────────────────────────────────

library(effectsize)

report_effect_sizes <- function(model) {
  cat("\nStandardized parameters (effect sizes):\n")
  std_params <- standardize_parameters(model, method = "basic")
  print(std_params)
  invisible(std_params)
}

# Cohen's d between two conditions on game-level estimates (the unit of the
# weighted regressions for H1, H2, and H3a), with a pooled SD and 95% CI.
# This is the unadjusted between-condition difference that the power analysis
# was based on; the WLS contrast remains the inferential test. Returns NA when
# either condition has fewer than two games (e.g. the pilot).
cohens_d_games <- function(df, value, condition, a, b) {
  x <- df[[value]][df[[condition]] == a]
  y <- df[[value]][df[[condition]] == b]
  if (length(x) < 2 || length(y) < 2) {
    return(data.frame(contrast = paste(a, "-", b), d = NA_real_, CI_low = NA_real_, CI_high = NA_real_,
                      note = "not estimable with fewer than two games per condition"))
  }
  es <- effectsize::cohens_d(x, y, pooled_sd = TRUE)
  data.frame(contrast = paste(a, "-", b), d = es$Cohens_d, CI_low = es$CI_low, CI_high = es$CI_high, note = "")
}

# Bayes factors for non-significant planned contrasts (see bayes_factors.R):
# "auto" computes them only when a contrast has p >= .05, "always" computes
# them for every planned contrast, "never" skips them (fast renders).
BAYES_FACTORS <- Sys.getenv("BAYES_FACTORS", unset = "auto")

# ── Model fitting with the preregistered simplification ────
#
# fit_progressively(formula, data, family) fits the maximal random-effects
# structure and simplifies it the way the preregistration states (drop
# correlations, then slopes from the smallest variance component). It is
# defined in mixed_models.R together with simplification_log() and
# random_effects_structure(), which notebooks use to report what was fit.

source(here("analysis", "mixed_models.R"))

save_fig <- function(p, filename, width = 8, height = 5, dpi = 150) {
  dir.create(figures_dir, showWarnings = FALSE, recursive = TRUE)
  path <- file.path(figures_dir, filename)
  if (grepl("\\.pdf$", filename)) {
    ggsave(path, p, width = width, height = height, device = cairo_pdf)
  } else {
    ggsave(path, p, width = width, height = height, dpi = dpi)
  }
}
