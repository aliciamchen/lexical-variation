# Tests for write_result() in analysis/R/results.R.

if (!exists("write_result")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

res_dir <- file.path(tempdir(), "results_test")
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
res_path <- write_result(res_df, "gs_by_game", source = "test", dir = res_dir)
back <- readr::read_csv(res_path, show_col_types = FALSE)
check(
  "write_result writes the frame as CSV with empty cells for missing values",
  nrow(back) == 2 &&
    back$gameId[2] == "g2" &&
    is.na(back$coefficient[2]) &&
    back$condition[1] == "refer_mixed" &&
    isTRUE(back$estimable[1])
)
manifest <- jsonlite::read_json(file.path(res_dir, "manifest.json"))
check(
  "the manifest records the source, the rows and the columns",
  manifest$gs_by_game$source == "test" &&
    manifest$gs_by_game$rows == 2 &&
    identical(unlist(manifest$gs_by_game$columns), names(res_df))
)
write_result(res_df[1, ], "gs_by_game", source = "test2", dir = res_dir)
manifest <- jsonlite::read_json(file.path(res_dir, "manifest.json"))
check(
  "writing a result again replaces its manifest entry",
  manifest$gs_by_game$rows == 1 && manifest$gs_by_game$source == "test2"
)
check(
  "a name that is not an identifier is refused",
  inherits(
    try(write_result(res_df, "gs by game", dir = res_dir), silent = TRUE),
    "try-error"
  )
)
unlink(res_dir, recursive = TRUE)
