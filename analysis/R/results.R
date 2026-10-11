# Model estimates for the figures and the descriptive macros.
#
# The notebooks fit the models; the article's figures and descriptive
# statistics are made in Python. What they need from a model -- per-game
# estimates, contrasts, fitted values -- is written here as a tidy CSV in
# analysis/results/<dataset>/ with an entry in that directory's manifest.json
# (source notebook, rows, columns, time), so the Python side reads the
# estimates the notebook reported rather than refitting anything.
#
# Usage:
#   write_result(gs_table, "gs_by_game", source = "analysis/primary.qmd")
#
# Tests: analysis/tests/test_results.R

write_result <- function(
  df,
  name,
  source = "an analysis notebook",
  dir = results_dir
) {
  stopifnot(
    is.data.frame(df),
    is.character(name),
    length(name) == 1,
    grepl("^[A-Za-z][A-Za-z0-9_]*$", name)
  )
  dir.create(dir, showWarnings = FALSE, recursive = TRUE)
  path <- file.path(dir, paste0(name, ".csv"))
  readr::write_csv(df, path, na = "")
  manifest_path <- file.path(dir, "manifest.json")
  manifest <- if (file.exists(manifest_path)) {
    jsonlite::read_json(manifest_path)
  } else {
    list()
  }
  manifest[[name]] <- list(
    file = basename(path),
    source = source,
    rows = nrow(df),
    columns = as.list(names(df)),
    written = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z")
  )
  jsonlite::write_json(
    manifest,
    manifest_path,
    auto_unbox = TRUE,
    pretty = TRUE
  )
  cat("Wrote", nrow(df), "rows to", path, "\n")
  invisible(path)
}
