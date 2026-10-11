# Tests for the notebook-facing dataset banner in analysis/config.R.

if (!exists("dataset_banner")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

banner_games <- tibble(condition = c("refer_mixed", NA, "social_first"))

full_txt <- paste(
  capture.output(dataset_banner("full", banner_games)),
  collapse = "\n"
)
check(
  "the full-sample banner is an informational callout that names the dataset and counts the games",
  grepl("::: {.callout-note}", full_txt, fixed = TRUE) &&
    grepl("Dataset: full", full_txt, fixed = TRUE) &&
    grepl("data/full/", full_txt, fixed = TRUE) &&
    grepl("2 games with a condition", full_txt, fixed = TRUE) &&
    !grepl("not results", full_txt, fixed = TRUE)
)
smoke_txt <- paste(
  capture.output(dataset_banner("smoke", banner_games)),
  collapse = "\n"
)
check(
  "any other dataset gets a warning callout saying its macros are not results",
  grepl("::: {.callout-warning}", smoke_txt, fixed = TRUE) &&
    grepl("data/smoke/", smoke_txt, fixed = TRUE) &&
    grepl("not results", smoke_txt, fixed = TRUE)
)
check(
  "the banner works without a games table",
  grepl(
    "callout-note",
    paste(capture.output(dataset_banner("full")), collapse = "")
  )
)
check(
  "the banner returns its text invisibly",
  identical(
    capture.output(x <- dataset_banner("full")),
    strsplit(x, "\n")[[1]][-1]
  ) ||
    grepl("callout-note", x)
)
