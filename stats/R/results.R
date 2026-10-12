# The estimates tables the model scripts write, and how the scripts read each
# other's.
#
# Every model script ends by writing what it estimated as a tidy CSV in
# results/estimates/<family>/<name>.csv, where the family is checks,
# primary or secondary and the name matches the script's own
# (stats/primary/h1_h2.R writes primary/h1_h2.csv; a script with several
# tables adds a suffix, primary/h4_social_components.csv). The manifest.json
# beside them records, per table, the script that wrote it, its rows and
# columns and the git commit of the working tree at the time, so a number in
# the manuscript can be traced to the code that produced it. The Python
# formatter (report/inferential.py) turns these tables into the LaTeX macros,
# the figure scripts draw from them, and a later script reads an earlier one's
# estimates with read_estimates() instead of refitting (the game-level
# regressions read the per-game group-specificity estimates this way).
#
# Usage:
#   write_estimates(contrasts, "primary/h1_h2", source = "stats/primary/h1_h2.R")
#   gs <- read_estimates("primary/group_specificity")
#
# Tests: stats/tests/test_results.R

# The short hash of HEAD, suffixed -dirty when tracked files have uncommitted
# changes, or "unknown" without git. The same string preprocessing/provenance.py
# writes on the Python side.
git_commit <- function() {
  run <- function(...) {
    out <- tryCatch(
      suppressWarnings(system2("git", c(...), stdout = TRUE, stderr = FALSE)),
      error = function(e) NULL
    )
    if (is.null(out) || !is.null(attr(out, "status"))) NULL else out
  }
  head <- run("-C", shQuote(here::here()), "rev-parse", "--short", "HEAD")
  if (is.null(head) || length(head) == 0) {
    return("unknown")
  }
  dirty <- run("-C", shQuote(here::here()), "status", "--porcelain", "--untracked-files=no")
  if (length(dirty) > 0 && any(nzchar(dirty))) paste0(head[1], "-dirty") else head[1]
}

check_estimates_name <- function(name) {
  stopifnot(
    is.character(name),
    length(name) == 1,
    grepl("^[A-Za-z][A-Za-z0-9_]*(/[A-Za-z][A-Za-z0-9_]*)?$", name)
  )
  invisible(name)
}

write_estimates <- function(
  df,
  name,
  source = "a model script",
  dir = estimates_dir
) {
  stopifnot(is.data.frame(df))
  check_estimates_name(name)
  path <- file.path(dir, paste0(name, ".csv"))
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  readr::write_csv(df, path, na = "")
  update_manifest(dir, name, list(
    file = paste0(name, ".csv"),
    source = source,
    rows = nrow(df),
    columns = as.list(names(df)),
    commit = git_commit()
  ))
  cat("Wrote", nrow(df), "rows to", path, "\n")
  invisible(path)
}

# Add or replace one table's entry in the manifest. Scripts run in parallel
# (make -j) would otherwise read, change and write the file over each other,
# so the update holds a lock: dir.create() is atomic, so the first script to
# create the lock directory owns the manifest until it removes it.
update_manifest <- function(dir, name, entry, timeout = 30) {
  manifest_path <- file.path(dir, "manifest.json")
  lock <- file.path(dir, ".manifest.lock")
  deadline <- Sys.time() + timeout
  while (!dir.create(lock, showWarnings = FALSE)) {
    if (Sys.time() > deadline) {
      stop(sprintf("could not lock %s within %d seconds (remove %s if no script is running)",
                   manifest_path, timeout, lock), call. = FALSE)
    }
    Sys.sleep(0.1)
  }
  on.exit(unlink(lock, recursive = TRUE), add = TRUE)
  manifest <- if (file.exists(manifest_path)) {
    jsonlite::read_json(manifest_path)
  } else {
    list()
  }
  manifest[[name]] <- entry
  manifest <- manifest[order(names(manifest))]
  jsonlite::write_json(manifest, manifest_path, auto_unbox = TRUE, pretty = TRUE)
  invisible(manifest_path)
}

# An estimates table another script wrote, with every column's type guessed
# from all of its rows; an empty tibble when the file does not exist, so a
# script can say which earlier script to run.
read_estimates <- function(name, dir = estimates_dir) {
  check_estimates_name(name)
  path <- file.path(dir, paste0(name, ".csv"))
  if (!file.exists(path)) {
    return(tibble())
  }
  readr::read_csv(path, show_col_types = FALSE, guess_max = Inf)
}

# Stop with the script to run first when an estimates table a script depends
# on is missing.
require_estimates <- function(name, written_by, dir = estimates_dir) {
  est <- read_estimates(name, dir)
  if (!has_rows(est)) {
    stop(
      sprintf(
        "%s/%s.csv is missing or empty; run `Rscript %s` first (or `make estimates`).",
        dir, name, written_by
      ),
      call. = FALSE
    )
  }
  est
}
