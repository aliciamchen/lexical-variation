# Makefile: from the Empirica exports to the article's macros and figures.
#
# Everything is keyed by a dataset name (DATASET, default full). The data
# tree holds what the pipeline makes from the exports and the results tree
# what the models and the paper layer make from the data (the layout is
# defined in pipeline/dataset_paths.py and mirrored in models/config.R):
#   data/<name>/                 the hand-written inputs: runs.txt and the exclusion files
#   data/<name>/raw/             the anonymized raw Empirica tables (combine)
#   data/<name>/tables/          the analysis-ready tables (process)
#   data/<name>/classifier/      the message filter's label cache (process)
#   data/<name>/measures/        embeddings, similarity tables, description properties (measures)
#   data/<name>/model_inputs/    the aggregated tables the models are fit to (model-inputs)
#   data/<name>/cache/           fitted objects kept between model runs (never committed)
#   results/<name>/estimates/    one tidy estimates table per model script (models)
#   results/<name>/stats/        the LaTeX macro files (stats)
#   results/<name>/figures/      the figures, each with the table it plots (figures)
#
# The verbs, in the order the work runs:
#   make data           # extract, combine and process the exports into data/<name>/ (private
#                       # inputs: the raw exports and Vertex AI credit for the message filter)
#   make test           # the integrity suite on the dataset, the Python unit tests and the R tests
#   make models         # fit every model script in models/ whose estimates are out of date
#   make paper          # the macros (inferential and descriptive) and the figures from the estimates
#   make sync           # copy results/<name>/stats and figures into writing/manuscript/
# `make all` runs data, test, models and paper in that order.
#
# Reproducing from the processed tables alone (no raw exports): with a
# dataset's tables/, classifier/ and measures/ under data/full/,
#   make model-inputs models paper
# rebuilds everything downstream; `make measures` regenerates the measures first.
#
# The model scripts are real Make targets: results/<name>/estimates/<family>/<name>.csv
# is built by models/<family>/<name>.R and depends on the data it reads, the
# shared R code and the estimates of earlier scripts, so `make models` reruns
# only what changed. The Bayes factors (minutes to tens of minutes, cached by
# brms) honor BAYES_FACTORS: auto (default; only for non-significant planned
# contrasts), always, or never (skip, keeping the previous estimates).
#
# The finer steps:
#   make extract        # extract the dataset's zips → data/runs/<timestamp>/
#   make combine        # stack runs → data/<name>/raw/
#   make process        # preprocess → filter → measures → model inputs
#   make measures       # only the measures (SBERT embeddings, similarities, description properties)
#   make model-inputs   # only the model inputs (fast; needs the tables and the measures)
#   make bayes-factors  # only the Bayes factor script
#   make inferential    # only the inferential macros (checks, primary, secondary)
#   make descriptives   # only the descriptive macros (overview, exploratory, survey)
#   make figures        # only the figures
#   make test-unit      # the Python unit tests alone (no data needed)
#   make payments       # what each Prolific study still owes → data/payments/<name>/
#   make tally          # games per condition and tangram set; stopping-rule progress
#
# Smoke-testing one export before it joins a dataset:
#   make smoke ZIP=experiment/data/<run>/empirica-export-<run>.zip
# runs extract → combine → process (no Vertex AI) → integrity suite in a
# throwaway dataset named `smoke` (data/smoke/, results/smoke/), which is never
# committed. The block-count checks are expected to fail for games played in
# TEST_MODE, whose phases are shorter than production.
#
# Each run's zip is looked up as experiment/data/<run>/empirica-export-<run>.zip
# or, failing that, as experiment/data/*/empirica-export-<run>.zip, because the
# old backup loop wrote every zip of a session into the directory of the first.

DATASET ?= full
export DATASET

# ── Directories ────────────────────────────────────────────
DATA_DIR = data/$(DATASET)
TABLES_DIR = $(DATA_DIR)/tables
MEASURES_DIR = $(DATA_DIR)/measures
MODEL_INPUTS_DIR = $(DATA_DIR)/model_inputs
RESULTS_DIR = results/$(DATASET)
ESTIMATES_DIR = $(RESULTS_DIR)/estimates
STATS_DIR = $(RESULTS_DIR)/stats
FIGURES_DIR = $(RESULTS_DIR)/figures
MANUSCRIPT_DIR = writing/manuscript
RUNS_FILE = $(DATA_DIR)/runs.txt
# Run timestamps from runs.txt (comments and blank lines dropped)
RUNS := $(shell [ -f $(RUNS_FILE) ] && sed -e 's/\#.*//' $(RUNS_FILE) | tr -s '[:space:]' '\n' | grep -v '^$$' | tr '\n' ' ')
# The export zip of one run: in its own directory, or in any other export
# directory (old backup loops put many zips in one). Make aborts with the run's
# name when neither exists, so a typo in runs.txt cannot start a partial extract.
zip_for_run = $(or $(firstword $(wildcard experiment/data/$(1)/empirica-export-$(1).zip experiment/data/*/empirica-export-$(1).zip)),$(error No export zip for run $(1): expected experiment/data/$(1)/empirica-export-$(1).zip or experiment/data/*/empirica-export-$(1).zip))
ZIPS = $(foreach run,$(RUNS),$(call zip_for_run,$(run)))

PY = uv run python
R_COMMON = models/config.R $(wildcard models/R/*.R)

.PHONY: all data models paper sync extract combine process process-no-filter measures model-inputs bayes-factors stats inferential descriptives figures payments sync-blocklist tally final-exports test test-unit test-ops smoke runs help

# ── The verbs ───────────────────────────────────────────────

all: data test models paper  ## Everything from the export zips to the article's macros and figures

data: extract combine process  ## Build data/<name>/ from the exports listed in runs.txt (extract, combine, process)

paper: stats figures  ## Write the macros and the figures from the estimates and the tables

sync: ## Copy results/<name>/stats/*.tex and figures/*.pdf into writing/manuscript/, where Overleaf reads them
	@mkdir -p $(MANUSCRIPT_DIR)/stats $(MANUSCRIPT_DIR)/figures
	cp $(STATS_DIR)/*.tex $(MANUSCRIPT_DIR)/stats/
	@n=0; for f in $(FIGURES_DIR)/*.pdf; do [ -e "$$f" ] && cp "$$f" $(MANUSCRIPT_DIR)/figures/ && n=$$((n+1)); done; echo "Synced $$(ls $(STATS_DIR)/*.tex | wc -l | tr -d ' ') stats files and $$n figures from $(RESULTS_DIR)/ to $(MANUSCRIPT_DIR)/"

# ── Pipeline steps ──────────────────────────────────────────

runs: ## Show the dataset and the runs registered in data/<name>/runs.txt
	@echo "DATASET=$(DATASET)  data=$(DATA_DIR)  results=$(RESULTS_DIR)"
	@echo "runs: $(RUNS)"

extract: ## Extract each Empirica export zip listed in runs.txt
	@if [ -z "$(RUNS)" ]; then echo "Error: no runs listed in $(RUNS_FILE)"; exit 1; fi
	@for zip in $(ZIPS); do \
		echo "=== Extracting $$zip ==="; \
		$(PY) -m pipeline.extract_run "$$zip"; \
	done

combine: ## Stack the registered runs into data/<name>/raw/
	$(PY) -m pipeline.combine_runs --dataset $(DATASET)

process: ## Run the processing steps (preprocess → filter → measures → model inputs)
	$(PY) -m pipeline.process_data --dataset $(DATASET)

process-no-filter: ## The processing steps without the message filter (no Vertex AI needed)
	$(PY) -m pipeline.process_data --dataset $(DATASET) --skip-filter

measures: ## Compute the measures from the utterances → data/<name>/measures/ (SBERT; minutes)
	$(PY) -m pipeline.compute_measures --dataset $(DATASET)

model-inputs: ## Build the model inputs from the tables and the measures → data/<name>/model_inputs/
	$(PY) -m pipeline.build_model_inputs --dataset $(DATASET)

payments: ## What each Prolific study still owes, from every zip in runs.txt → data/payments/<name>/ (read-only Prolific calls)
	@if [ -z "$(RUNS)" ]; then echo "Error: no runs listed in $(RUNS_FILE)"; exit 1; fi
	$(PY) operations/payments.py --dataset $(DATASET) $(ZIPS)

sync-blocklist: ## Add everyone on data/payments/<name>/blocklist_ids.txt to the Prolific group the surveys block (asks first; the only Prolific write)
	$(PY) operations/sync_blocklist.py --dataset $(DATASET) $(SYNC_ARGS)

tally: ## Games per (condition, tangram set) cell and progress against the stopping rule (reads data/<name>/)
	$(PY) operations/tally.py --dataset $(DATASET)

final-exports: ## Stage the final export of each server period, plus every server log, in backups/final_exports/ for the off-site backup
	$(PY) operations/final_exports.py --dataset $(DATASET)

# ── The models ──────────────────────────────────────────────
# One rule per script: the estimates table it writes, the data it reads and
# the estimates it builds on. The pattern rule below supplies the recipe.

ESTIMATES = \
  $(ESTIMATES_DIR)/checks/convention_trends.csv \
  $(ESTIMATES_DIR)/checks/phase1_group_specificity.csv \
  $(ESTIMATES_DIR)/checks/dropout_and_survey.csv \
  $(ESTIMATES_DIR)/primary/group_specificity.csv \
  $(ESTIMATES_DIR)/primary/h1_h2.csv \
  $(ESTIMATES_DIR)/primary/h3a.csv \
  $(ESTIMATES_DIR)/primary/h3b.csv \
  $(ESTIMATES_DIR)/primary/h3c.csv \
  $(ESTIMATES_DIR)/primary/h4.csv \
  $(ESTIMATES_DIR)/primary/robustness.csv \
  $(ESTIMATES_DIR)/primary/bayes_factors.csv \
  $(ESTIMATES_DIR)/secondary/semantic_change.csv \
  $(ESTIMATES_DIR)/secondary/phase2_accuracy.csv \
  $(ESTIMATES_DIR)/secondary/ingroup_advantage.csv \
  $(ESTIMATES_DIR)/secondary/specificity_vs_social_accuracy.csv \
  $(ESTIMATES_DIR)/secondary/social_accuracy_trend.csv \
  $(ESTIMATES_DIR)/secondary/phase2_length.csv \
  $(ESTIMATES_DIR)/secondary/utterance_properties.csv

GAMES = $(TABLES_DIR)/games.csv
PLAYERS = $(TABLES_DIR)/players.csv
TRIALS = $(TABLES_DIR)/trials.csv
UTTERANCES = $(TABLES_DIR)/speaker_utterances.csv
SOCIAL_GUESSES = $(TABLES_DIR)/social_guesses.csv
PAIRWISE = $(MEASURES_DIR)/pairwise_similarities.csv $(MEASURES_DIR)/pairwise_similarities_jaccard.csv
WITHIN_GROUP_MEANS = $(MODEL_INPUTS_DIR)/within_group_block_means.csv $(MODEL_INPUTS_DIR)/within_group_block_means_jaccard.csv
FINAL_PROPERTIES = $(MODEL_INPUTS_DIR)/final_phase_properties.csv

$(ESTIMATES_DIR)/checks/convention_trends.csv: $(UTTERANCES) $(TRIALS) $(GAMES) $(MEASURES_DIR)/adjacent_similarities.csv
$(ESTIMATES_DIR)/checks/phase1_group_specificity.csv: $(MEASURES_DIR)/pairwise_similarities.csv $(GAMES)
$(ESTIMATES_DIR)/checks/dropout_and_survey.csv: $(PLAYERS) $(GAMES)
$(ESTIMATES_DIR)/primary/group_specificity.csv: $(PAIRWISE) $(GAMES)
$(ESTIMATES_DIR)/primary/h1_h2.csv: $(ESTIMATES_DIR)/primary/group_specificity.csv
$(ESTIMATES_DIR)/primary/h3a.csv: $(ESTIMATES_DIR)/primary/group_specificity.csv
$(ESTIMATES_DIR)/primary/h3b.csv: $(WITHIN_GROUP_MEANS)
$(ESTIMATES_DIR)/primary/h3c.csv: $(FINAL_PROPERTIES)
$(ESTIMATES_DIR)/primary/h4.csv: $(TRIALS) $(SOCIAL_GUESSES) $(GAMES)
$(ESTIMATES_DIR)/primary/robustness.csv: $(ESTIMATES_DIR)/primary/group_specificity.csv $(ESTIMATES_DIR)/primary/h4.csv $(UTTERANCES) $(PLAYERS)
$(ESTIMATES_DIR)/primary/bayes_factors.csv: $(ESTIMATES_DIR)/primary/group_specificity.csv $(ESTIMATES_DIR)/primary/h4.csv
$(ESTIMATES_DIR)/secondary/semantic_change.csv: $(MEASURES_DIR)/phase_change_similarities.csv $(GAMES)
$(ESTIMATES_DIR)/secondary/phase2_accuracy.csv: $(TRIALS) $(GAMES)
$(ESTIMATES_DIR)/secondary/ingroup_advantage.csv: $(MODEL_INPUTS_DIR)/ingroup_advantage.csv
$(ESTIMATES_DIR)/secondary/specificity_vs_social_accuracy.csv: $(ESTIMATES_DIR)/primary/group_specificity.csv $(SOCIAL_GUESSES) $(GAMES)
$(ESTIMATES_DIR)/secondary/social_accuracy_trend.csv: $(SOCIAL_GUESSES) $(GAMES)
$(ESTIMATES_DIR)/secondary/phase2_length.csv: $(UTTERANCES) $(GAMES)
$(ESTIMATES_DIR)/secondary/utterance_properties.csv: $(FINAL_PROPERTIES)

$(ESTIMATES_DIR)/%.csv: models/%.R $(R_COMMON)
	Rscript $<

models: $(ESTIMATES)  ## Fit the model scripts whose estimates are out of date (results/<name>/estimates/)

# A data file a model needs but the dataset does not have yet
$(TABLES_DIR)/%.csv $(MEASURES_DIR)/%.csv $(MODEL_INPUTS_DIR)/%.csv:
	$(error $@ is missing: build the dataset first (make data; or make measures model-inputs from the processed tables))

bayes-factors: $(ESTIMATES_DIR)/primary/bayes_factors.csv  ## Only the Bayes factor script (BAYES_FACTORS=auto|always|never)

# ── The paper layer ─────────────────────────────────────────

stats: inferential descriptives  ## Both macro writers

inferential: ## The inferential macros (checks, primary, secondary) from results/<name>/estimates/
	$(PY) -m paper.inferential --dataset $(DATASET)

descriptives: ## The descriptive macros (overview, exploratory, survey) from the tables, the measures and the estimates
	$(PY) -m paper.descriptives --dataset $(DATASET)

figures: ## The article's figures, each with its plotted table → results/<name>/figures/
	$(PY) -m paper.figures --dataset $(DATASET)

# ── Tests ───────────────────────────────────────────────────

test: ## Every test: the integrity suite on the active dataset, the Python unit tests and the R tests
	uv run pytest -q
	Rscript models/tests/run_all.R

test-unit: ## The Python unit tests only (no processed data needed)
	uv run pytest -q --ignore=pipeline/test_data_integrity.py

test-ops: ## Only the operations tests: payments, blocklist sync, tally, Prolific client (no API calls, no data needed)
	uv run pytest operations -q

# The zip is extracted into data/runs/<run>/ like any other and registered in
# data/smoke/runs.txt, so the combine step reads the same file it always does.
# Nothing under data/smoke/ or results/smoke/ is meant to be committed.
smoke: ## Smoke-test one export end to end in a throwaway dataset: make smoke ZIP=<path to zip>
	@if [ -z "$(ZIP)" ]; then \
		echo "Usage: make smoke ZIP=experiment/data/<run>/empirica-export-<run>.zip"; exit 1; \
	fi
	@if [ ! -f "$(ZIP)" ]; then echo "Error: $(ZIP) does not exist"; exit 1; fi
	rm -rf data/smoke results/smoke
	$(PY) -m pipeline.extract_run "$(ZIP)" --dataset smoke
	$(PY) -m pipeline.combine_runs --dataset smoke
	$(PY) -m pipeline.process_data --dataset smoke --skip-filter
	@echo
	@echo "=== Integrity suite on the smoke dataset ==="
	@echo "The block-count checks (blocks per phase, trials per block, speaker rotation)"
	@echo "are expected to fail for games played in TEST_MODE, which shortens the phases"
	@echo "to 3 + 2 blocks. The bonus checks apply the production pay rate, so an export"
	@echo "from before it was set fails them too. Anything else"
	@echo "that fails is a real problem with the export."
	-DATASET=smoke uv run pytest pipeline/test_data_integrity.py -q
	@echo
	@echo "Smoke test finished. Output: data/smoke/ and results/smoke/ (throwaway)"

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
