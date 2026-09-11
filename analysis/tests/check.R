# Minimal assertion helper for the R tests (no test framework needed).
check <- function(label, cond) {
  if (!isTRUE(cond)) {
    stop(sprintf("FAILED: %s", label), call. = FALSE)
  }
  cat(sprintf("ok: %s\n", label))
}
