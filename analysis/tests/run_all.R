# Run every R test file in this directory.
#
#   Rscript analysis/tests/run_all.R
#
# Each test_*.R file is sourced in its own environment after config.R (which
# sources the helpers in analysis/R/). A failing check stops that file; the
# runner reports every file and exits non-zero if any failed.

suppressPackageStartupMessages(source(here::here("analysis", "config.R")))
source(here::here("analysis", "tests", "check.R"))

files <- sort(list.files(
  here::here("analysis", "tests"),
  pattern = "^test_.*\\.R$",
  full.names = TRUE
))
failed <- character(0)
for (f in files) {
  cat(sprintf("\n── %s ──\n", basename(f)))
  ok <- tryCatch(
    {
      source(f, local = new.env(parent = globalenv()))
      TRUE
    },
    error = function(e) {
      cat(conditionMessage(e), "\n")
      FALSE
    }
  )
  if (!ok) failed <- c(failed, basename(f))
}
cat("\n")
if (length(failed)) {
  cat("FAILED:", paste(failed, collapse = ", "), "\n")
  quit(status = 1)
}
cat(sprintf("All %d R test files passed.\n", length(files)))
