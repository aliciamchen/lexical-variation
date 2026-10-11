# Makefile for the data pipeline.
#
# The pipeline is keyed by a dataset name; every dataset follows the same
# layout (see analysis/dataset_paths.py and analysis/config.R):
#   data/<name>/              preprocessed CSVs, raw_anonymized/, runs.txt
#   analysis/derived/<name>/  derived metrics and model caches
#   figures/<name>/           figures
# The default is the full sample; pass DATASET=<name> for another one.
#
# From scratch with raw Empirica export zips listed in data/<name>/runs.txt:
#   make all                      # the full sample
#   make all DATASET=smoke        # another dataset
#
# Individual targets:
#   make extract        # extract the dataset's zips → data/runs/<timestamp>/
#   make combine        # stack runs → data/<name>/raw_anonymized/
#   make process        # preprocess → filter → derived metrics → model-input frames
#   make frames         # only the model-input frames (fast; needs processed and derived tables)
#   make test           # validate processed data (pytest integrity suite)
#   make payments       # what each Prolific study still owes → data/payments/<name>/
#   make tally          # games per condition and tangram set; stopping-rule progress
#   make notebooks      # render the analysis notebooks 00-05
#   BAYES_FACTORS=never make notebooks   # render without the brms refits (a fast check)
#
# Smoke-testing one export before it joins a dataset:
#   make smoke ZIP=experiment/data/<run>/empirica-export-<run>.zip
# runs extract → combine → process (no Vertex AI) → integrity suite in a
# throwaway dataset named `smoke` (data/smoke/, analysis/derived/smoke/), which
# is never committed. The block-count checks are expected to fail for games
# played in TEST_MODE, whose phases are shorter than production.
#
# Each run's zip is looked up as experiment/data/<run>/empirica-export-<run>.zip
# or, failing that, as experiment/data/*/empirica-export-<run>.zip, because the
# old backup loop wrote every zip of a session into the directory of the first.

DATASET ?= full
export DATASET

# Directories
DATA_DIR = data/$(DATASET)
DERIVED_DIR = analysis/derived/$(DATASET)
FIGURES_DIR = figures/$(DATASET)
RUNS_FILE = $(DATA_DIR)/runs.txt
# Run timestamps from runs.txt (comments and blank lines dropped)
RUNS := $(shell [ -f $(RUNS_FILE) ] && sed -e 's/\#.*//' $(RUNS_FILE) | tr -s '[:space:]' '\n' | grep -v '^$$' | tr '\n' ' ')
# The export zip of one run: in its own directory, or in any other export
# directory (old backup loops put many zips in one). Make aborts with the run's
# name when neither exists, so a typo in runs.txt cannot start a partial extract.
zip_for_run = $(or $(firstword $(wildcard experiment/data/$(1)/empirica-export-$(1).zip experiment/data/*/empirica-export-$(1).zip)),$(error No export zip for run $(1): expected experiment/data/$(1)/empirica-export-$(1).zip or experiment/data/*/empirica-export-$(1).zip))
ZIPS = $(foreach run,$(RUNS),$(call zip_for_run,$(run)))

# The preregistered analysis notebooks, rendered on the active dataset
NOTEBOOKS = $(wildcard analysis/0[0-9]_*.qmd)

.PHONY: all extract combine process process-no-filter frames payments sync-blocklist tally final-exports notebooks test test-ops smoke runs help

# ── Main targets ────────────────────────────────────────────

all: extract combine process test notebooks  ## Full pipeline from zips to rendered notebooks

# ── Pipeline steps ──────────────────────────────────────────

runs: ## Show the dataset and the runs registered in data/<name>/runs.txt
	@echo "DATASET=$(DATASET)  data=$(DATA_DIR)  derived=$(DERIVED_DIR)  figures=$(FIGURES_DIR)"
	@echo "runs: $(RUNS)"

extract: ## Extract each Empirica export zip listed in runs.txt
	@if [ -z "$(RUNS)" ]; then echo "Error: no runs listed in $(RUNS_FILE)"; exit 1; fi
	@for zip in $(ZIPS); do \
		echo "=== Extracting $$zip ==="; \
		uv run python analysis/extract_run.py "$$zip"; \
	done

combine: ## Stack the registered runs into data/<name>/raw_anonymized/
	uv run python analysis/combine_runs.py --dataset $(DATASET)

process: ## Run full pipeline (preprocess → filter → derived → frames)
	uv run python analysis/process_data.py --dataset $(DATASET)

process-no-filter: ## Run pipeline skipping filter (no Vertex AI needed)
	uv run python analysis/process_data.py --dataset $(DATASET) --skip-filter

frames: ## Build the model-input frames from the processed and derived tables → analysis/derived/<name>/
	uv run python analysis/build_frames.py --dataset $(DATASET)

payments: ## What each Prolific study still owes, from every zip in runs.txt → data/payments/<name>/ (read-only Prolific calls)
	@if [ -z "$(RUNS)" ]; then echo "Error: no runs listed in $(RUNS_FILE)"; exit 1; fi
	uv run python operations/payments.py --dataset $(DATASET) $(ZIPS)

sync-blocklist: ## Add everyone on data/payments/<name>/blocklist_ids.txt to the Prolific group the surveys block (asks first; the only Prolific write)
	uv run python operations/sync_blocklist.py --dataset $(DATASET) $(SYNC_ARGS)

tally: ## Games per (condition, tangram set) cell and progress against the stopping rule (reads data/<name>/)
	uv run python operations/tally.py --dataset $(DATASET)

final-exports: ## Stage the final export of each server period, plus every server log, in backups/final_exports/ for the off-site backup
	uv run python operations/final_exports.py --dataset $(DATASET)

test: ## Validate processed data against the integrity suite and run the Python and R helper tests
	uv run pytest analysis/test_data_integrity.py analysis/test_compute_derived.py analysis/test_preprocessing.py analysis/test_build_frames.py analysis/test_stats_tex.py operations/test_payments.py operations/test_tally.py operations/test_prolific.py operations/test_sync_blocklist.py -q
	Rscript analysis/tests/run_all.R

test-ops: ## Run only the operations tests: payments, blocklist sync, tally, Prolific client (no API calls, no data needed)
	uv run pytest operations/test_payments.py operations/test_tally.py operations/test_prolific.py operations/test_sync_blocklist.py -q

# The zip is extracted into data/runs/<run>/ like any other and registered in
# data/smoke/runs.txt, so the combine step reads the same file it always does.
# Nothing under data/smoke/ or analysis/derived/smoke/ is meant to be committed.
smoke: ## Smoke-test one export end to end in a throwaway dataset: make smoke ZIP=<path to zip>
	@if [ -z "$(ZIP)" ]; then \
		echo "Usage: make smoke ZIP=experiment/data/<run>/empirica-export-<run>.zip"; exit 1; \
	fi
	@if [ ! -f "$(ZIP)" ]; then echo "Error: $(ZIP) does not exist"; exit 1; fi
	rm -rf data/smoke analysis/derived/smoke
	uv run python analysis/extract_run.py "$(ZIP)" --dataset smoke
	uv run python analysis/combine_runs.py --dataset smoke
	uv run python analysis/process_data.py --dataset smoke --skip-filter
	@echo
	@echo "=== Integrity suite on the smoke dataset ==="
	@echo "The block-count checks (blocks per phase, trials per block, speaker rotation)"
	@echo "are expected to fail for games played in TEST_MODE, which shortens the phases"
	@echo "to 3 + 2 blocks. The bonus checks apply the production pay rate, so an export"
	@echo "from before it was set fails them too. Anything else"
	@echo "that fails is a real problem with the export."
	-DATASET=smoke uv run pytest analysis/test_data_integrity.py -q
	@echo
	@echo "Smoke test finished. Outputs: data/smoke/ and analysis/derived/smoke/ (throwaway;"
	@echo "remove with: rm -rf data/smoke analysis/derived/smoke)"

# ── Notebooks ───────────────────────────────────────────────

notebooks: ## Render the analysis notebooks 00–05 on the active dataset
	@for nb in $(NOTEBOOKS); do \
		echo "=== Rendering $$nb (DATASET=$(DATASET)) ==="; \
		quarto render "$$nb" || exit 1; \
	done

# ── Utilities ───────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
