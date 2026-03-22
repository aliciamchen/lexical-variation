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

data_dir <- here("analysis", "processed_data")
figures_dir <- here("analysis", "figures")
dir.create(figures_dir, showWarnings = FALSE, recursive = TRUE)

# Prefer filtered utterances when available
utterances_file <- if (file.exists(file.path(data_dir, "speaker_utterances_filtered.csv"))) {
  "speaker_utterances_filtered.csv"
} else {
  "speaker_utterances.csv"
}

# ── Color palettes (match analysis/plot_style.py) ────────────

CONDITION_COLORS <- c(
  refer_separated = "#027A5E",
  refer_mixed     = "#5EC2A0",
  social_mixed    = "#F5B74A",
  social_first    = "#C47A00"
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

scale_color_condition <- function(...) {
  scale_color_manual(values = CONDITION_COLORS, ...)
}

scale_fill_condition <- function(...) {
  scale_fill_manual(values = CONDITION_COLORS, ...)
}

scale_color_group <- function(...) {
  scale_color_manual(values = GROUP_COLORS, ...)
}

scale_fill_group <- function(...) {
  scale_fill_manual(values = GROUP_COLORS, ...)
}

# ── Helper functions ────────────────────────────────────────

continuous_block <- function(df) {
  df %>% mutate(block = blockNum + (phaseNum == 2) * PHASE2_OFFSET)
}

format_condition <- function(x) {
  ifelse(x %in% names(CONDITION_LABELS), CONDITION_LABELS[x],
         str_to_sentence(str_replace_all(x, "_", " ")))
}

save_fig <- function(p, filename, width = 8, height = 5, dpi = 150) {
  path <- file.path(figures_dir, filename)
  if (grepl("\\.pdf$", filename)) {
    ggsave(path, p, width = width, height = height, device = cairo_pdf)
  } else {
    ggsave(path, p, width = width, height = height, dpi = dpi)
  }
}
