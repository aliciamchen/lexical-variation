# Plotting helpers shared by the notebooks: condition and group scales, the
# Phase 2 background layers, legend extraction, and figure saving into the
# active dataset's figures directory. Palettes and the ggplot theme are set in
# config.R (they match analysis/plot_style.py).

format_condition <- function(x) {
  ifelse(
    x %in% names(CONDITION_LABELS),
    CONDITION_LABELS[x],
    str_to_sentence(str_replace_all(x, "_", " "))
  )
}

scale_color_condition <- function(
  labels = function(x) format_condition(x),
  ...
) {
  scale_color_manual(values = CONDITION_COLORS, labels = labels, ...)
}

scale_fill_condition <- function(
  labels = function(x) format_condition(x),
  ...
) {
  scale_fill_manual(values = CONDITION_COLORS, labels = labels, ...)
}

scale_color_group <- function(...) {
  scale_color_manual(values = GROUP_COLORS, ...)
}

scale_fill_group <- function(...) {
  scale_fill_manual(values = GROUP_COLORS, ...)
}

# Block number continuous across phases on the 1-12 axis used in figures
continuous_block <- function(df) {
  df |> mutate(block = blockNum + (phaseNum == 2) * PHASE2_OFFSET)
}

# Phase 2 background shading, vline, and 1-12 x-axis breaks
phase2_layers <- function() {
  list(
    annotate(
      "rect",
      xmin = PHASE_BOUNDARY,
      xmax = Inf,
      ymin = -Inf,
      ymax = Inf,
      fill = "gray90",
      alpha = 0.5
    ),
    geom_vline(
      xintercept = PHASE_BOUNDARY,
      color = "gray70",
      linetype = "dotted"
    ),
    scale_x_continuous(
      breaks = 1:12,
      limits = c(0.8, 12.2),
      labels = as.integer
    )
  )
}

# Bold tag theme for patchwork plot_annotation
TAG_THEME <- theme(plot.tag = element_text(face = "bold", size = 20))

# Extract a standalone legend grob from a ggplot
extract_legend <- function(p) {
  g <- ggplotGrob(p)
  g$grobs[[which(g$layout$name == "guide-box-bottom")]]
}

# Save into figures_dir (PDFs through cairo so fonts embed)
save_fig <- function(p, filename, width = 8, height = 5, dpi = 150) {
  dir.create(figures_dir, showWarnings = FALSE, recursive = TRUE)
  path <- file.path(figures_dir, filename)
  if (grepl("\\.pdf$", filename)) {
    ggsave(path, p, width = width, height = height, device = cairo_pdf)
  } else {
    ggsave(path, p, width = width, height = height, dpi = dpi)
  }
  invisible(path)
}
