# Tests for check_filtered_utterances() (config.R): the notebooks must refuse a
# speaker_utterances_filtered.csv whose sidecar is missing or names another
# messages.csv, the same rule the Python steps apply through dataset_paths.py.

if (!exists("check_filtered_utterances")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

make_dataset <- function(sidecar = TRUE, matching = TRUE) {
  dir <- tempfile("sidecar-")
  dir.create(dir)
  writeLines(c("gameId,text", "g,a bunny"), file.path(dir, "messages.csv"))
  writeLines("gameId,utterance", file.path(dir, "speaker_utterances_filtered.csv"))
  if (sidecar) {
    sha <- if (matching) {
      digest::digest(file = file.path(dir, "messages.csv"), algo = "sha256")
    } else {
      strrep("0", 64)
    }
    jsonlite::write_json(
      list(source = "messages.csv", sha256 = sha, rows = 1L),
      file.path(dir, "speaker_utterances_filtered.source.json"),
      auto_unbox = TRUE
    )
  }
  dir
}

refuses <- function(dir) {
  inherits(try(check_filtered_utterances(dir), silent = TRUE), "try-error")
}

check(
  "a filtered file whose sidecar matches messages.csv is accepted",
  isTRUE(check_filtered_utterances(make_dataset()))
)
check(
  "a filtered file without a sidecar is refused",
  refuses(make_dataset(sidecar = FALSE))
)
check(
  "a filtered file built from a different messages.csv is refused",
  refuses(make_dataset(matching = FALSE))
)
check(
  "the refusal says how to rebuild the file",
  grepl("make process", conditionMessage(tryCatch(
    check_filtered_utterances(make_dataset(matching = FALSE)),
    error = function(e) e
  )), fixed = TRUE)
)
