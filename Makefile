# Makefile for the data pipeline.
#
# The pipeline is keyed by a dataset name; every dataset follows the same
# layout (see analysis/dataset_paths.py and analysis/config.R):
#   data/<name>/              preprocessed CSVs, raw_anonymized/, runs.txt
#   analysis/derived/<name>/  derived metrics and model caches
#   figures/<name>/           notebook figures
# The default is the pilot sessions; pass DATASET=<name> for another one.
#
# For reviewers (raw data + filtered utterances already committed):
#   make pilot
#
# From scratch with raw Empirica export zips listed in data/<name>/runs.txt:
#   make all                      # pilot sessions
#   make all DATASET=full         # the full sample
#
# Individual targets:
#   make extract        # extract the dataset's zips → data/runs/<timestamp>/
#   make combine        # stack runs → data/<name>/raw_anonymized/
#   make process        # preprocess → filter → derived metrics
#   make test           # validate processed data (pytest integrity suite)
#   make notebooks      # render the dataset's notebooks
#   make llm-process    # process LLM simulation JSONs → CSVs

DATASET ?= pilots
export DATASET

# Directories
DATA_DIR = data/$(DATASET)
DERIVED_DIR = analysis/derived/$(DATASET)
FIGURES_DIR = figures/$(DATASET)
RUNS_FILE = $(DATA_DIR)/runs.txt
# Run timestamps from runs.txt (comments and blank lines dropped)
RUNS := $(shell [ -f $(RUNS_FILE) ] && sed -e 's/\#.*//' $(RUNS_FILE) | tr -s '[:space:]' '\n' | grep -v '^$$' | tr '\n' ' ')
ZIPS = $(foreach run,$(RUNS),experiment/data/$(run)/empirica-export-$(run).zip)
LLM_SIM_DIR = analysis/llm_simulation
LLM_RESULTS = $(shell ls -d $(LLM_SIM_DIR)/llm_results_*/ 2>/dev/null | sort | tail -1)

# Notebooks per dataset: the pilot sessions feed the SI of the preregistration;
# every other dataset runs the preregistered analysis notebooks.
ifeq ($(DATASET),pilots)
NOTEBOOKS = analysis/SI_pilot.qmd $(LLM_SIM_DIR)/SI_llm_simulation.qmd
else
NOTEBOOKS = $(wildcard analysis/0[0-9]_*.qmd)
endif

.PHONY: all pilot extract combine process process-no-filter notebooks llm-process test runs help

# ── Main targets ────────────────────────────────────────────

all: extract combine process test notebooks  ## Full pipeline from zips to rendered notebooks

pilot: ## For reviewers: derive pilot metrics + render the SI notebooks (data already committed)
	$(MAKE) process-no-filter notebooks DATASET=pilots

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

process: ## Run full pipeline (preprocess → filter → derived)
	uv run python analysis/process_data.py --dataset $(DATASET)

process-no-filter: ## Run pipeline skipping filter (no Vertex AI needed)
	uv run python analysis/process_data.py --dataset $(DATASET) --skip-filter

test: ## Validate processed data against the integrity suite and run the R model tests
	uv run pytest analysis/test_data_integrity.py analysis/test_compute_derived.py analysis/test_preprocessing.py -q
	Rscript analysis/test_mixed_models.R

# ── LLM simulation ─────────────────────────────────────────

llm-process: ## Process LLM simulation JSONs → CSVs
	@if [ -z "$(LLM_RESULTS)" ]; then \
		echo "Error: no llm_results_*/ directory found in $(LLM_SIM_DIR)/"; \
		echo "Run the simulation first: bash $(LLM_SIM_DIR)/run_llm_simulation.sh"; \
		exit 1; \
	fi
	uv run python $(LLM_SIM_DIR)/process_llm_results.py "$(LLM_RESULTS)"

# ── Notebooks ───────────────────────────────────────────────

ifeq ($(DATASET),pilots)
notebooks: llm-process ## Render the dataset's notebooks (pilots: SI notebooks; otherwise 00–05)
else
notebooks: ## Render the dataset's notebooks (pilots: SI notebooks; otherwise 00–05)
endif
	@for nb in $(NOTEBOOKS); do \
		echo "=== Rendering $$nb (DATASET=$(DATASET)) ==="; \
		quarto render "$$nb" || exit 1; \
	done

# ── Utilities ───────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
