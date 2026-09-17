# Tests for the notebook-facing pieces of analysis/config.R: the dataset
# banner and the stats file path.

if (!exists("dataset_banner")) {
  source(here::here("analysis", "config.R"))
}
if (!exists("check")) {
  source(here::here("analysis", "tests", "check.R"))
}

banner_games <- tibble(condition = c("refer_mixed", NA, "social_first"))

pilot_txt <- paste(
  capture.output(dataset_banner("pilots", banner_games)),
  collapse = "\n"
)
check(
  "the pilot banner is a warning callout that names the dataset and says the numbers are not results",
  grepl("::: {.callout-warning}", pilot_txt, fixed = TRUE) &&
    grepl("data/pilots/", pilot_txt, fixed = TRUE) &&
    grepl("2 games with a condition", pilot_txt, fixed = TRUE) &&
    grepl("not results", pilot_txt, fixed = TRUE)
)
full_txt <- paste(
  capture.output(dataset_banner("full", banner_games)),
  collapse = "\n"
)
check(
  "another dataset gets an informational callout without the pilot warning",
  grepl("::: {.callout-note}", full_txt, fixed = TRUE) &&
    grepl("Dataset: full", full_txt, fixed = TRUE) &&
    !grepl("not results", full_txt, fixed = TRUE)
)
check(
  "the banner works without a games table",
  grepl(
    "callout-warning",
    paste(capture.output(dataset_banner("pilots")), collapse = "")
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
