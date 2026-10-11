# Tests for the estimates writer and reader in models/R/results.R.

if (!exists("write_estimates")) {
  source(here::here("models", "config.R"))
}
if (!exists("check")) {
  source(here::here("models", "tests", "check.R"))
}

res_dir <- file.path(tempdir(), "estimates_test")
dir.create(res_dir, showWarnings = FALSE)
res_df <- tibble(
  gameId = c("g1", "g2"),
  condition = factor(
    c("refer_mixed", "social_first"),
    levels = CONDITION_ORDER
  ),
  coefficient = c(0.5, NA),
  estimable = c(TRUE, FALSE)
)
res_path <- write_estimates(res_df, "primary/gs", source = "test", dir = res_dir)
check(
  "the table goes into the family's subdirectory",
  res_path == file.path(res_dir, "primary", "gs.csv") && file.exists(res_path)
)
back <- read_estimates("primary/gs", dir = res_dir)
check(
  "write_estimates writes the frame as CSV with empty cells for missing values, and read_estimates reads it back",
  nrow(back) == 2 &&
    back$gameId[2] == "g2" &&
    is.na(back$coefficient[2]) &&
    back$condition[1] == "refer_mixed" &&
    isTRUE(back$estimable[1])
)
manifest <- jsonlite::read_json(file.path(res_dir, "manifest.json"))
check(
  "the manifest records the source, the rows, the columns and the commit",
  manifest[["primary/gs"]]$source == "test" &&
    manifest[["primary/gs"]]$rows == 2 &&
    identical(unlist(manifest[["primary/gs"]]$columns), names(res_df)) &&
    is.character(manifest[["primary/gs"]]$commit) &&
    nzchar(manifest[["primary/gs"]]$commit)
)
write_estimates(res_df[1, ], "primary/gs", source = "test2", dir = res_dir)
manifest <- jsonlite::read_json(file.path(res_dir, "manifest.json"))
check(
  "writing a table again replaces its manifest entry",
  manifest[["primary/gs"]]$rows == 1 && manifest[["primary/gs"]]$source == "test2"
)
check(
  "a name that is not an identifier or family/identifier is refused",
  inherits(try(write_estimates(res_df, "gs by game", dir = res_dir), silent = TRUE), "try-error") &&
    inherits(try(write_estimates(res_df, "a/b/c", dir = res_dir), silent = TRUE), "try-error")
)
check(
  "a missing table reads as an empty tibble and require_estimates names the script to run",
  nrow(read_estimates("primary/missing", dir = res_dir)) == 0 &&
    grepl(
      "models/primary/missing.R",
      conditionMessage(tryCatch(
        require_estimates("primary/missing", "models/primary/missing.R", dir = res_dir),
        error = function(e) e
      )),
      fixed = TRUE
    )
)
check(
  "git_commit is a short hash, optionally marked dirty, or unknown",
  grepl("^([0-9a-f]{7,}(-dirty)?|unknown)$", git_commit())
)
unlink(res_dir, recursive = TRUE)
