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

# ── Color palettes (match analysis/plot_style.py) ────────────

CONDITION_COLORS <- c(
  refer_separated = "#0173B2",
  refer_mixed     = "#029E73",
  social_mixed    = "#DE8F05",
  social_first    = "#CC78BC"
)

CONDITION_ORDER <- c("refer_separated", "refer_mixed", "social_mixed", "social_first")

GROUP_COLORS <- c(A = "#F8766D", B = "#00BA38", C = "#619CFF")
GROUP_ORDER  <- c("A", "B", "C")

# Single-metric accent colors (for outcome-neutral plots without condition facets)
ACCENT <- list(
  length     = "#0173B2",
  accuracy   = "#029E73",
  similarity = "#DE8F05",
  social     = "#9467BD"
)

# ── Phase boundary ──────────────────────────────────────────

PHASE_BOUNDARY <- 5.5
PHASE2_OFFSET  <- 6

# ── Global ggplot theme (seaborn-ticks style) ───────────────

theme_set(

  theme_minimal(base_size = 13) +
    theme(
      panel.grid.minor = element_blank(),
      axis.ticks = element_line(linewidth = 0.3),
      strip.text = element_text(face = "plain"),
      plot.title = element_text(face = "plain"),
      legend.title = element_text(face = "plain")
    )
)

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

add_phase_boundary <- function(p) {
  p + geom_vline(xintercept = PHASE_BOUNDARY, color = "gray",
                 linetype = "dotted", alpha = 0.6)
}

continuous_block <- function(df) {
  df %>% mutate(block = blockNum + (phaseNum == 2) * PHASE2_OFFSET)
}

format_condition <- function(x) str_replace_all(x, "_", " ")

save_fig <- function(p, filename, width = 8, height = 5, dpi = 150) {
  ggsave(file.path(figures_dir, filename), p,
         width = width, height = height, dpi = dpi)
}
