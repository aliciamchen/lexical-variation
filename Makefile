# Makefile for the pilot analysis pipeline.
#
# For reviewers (raw data + filtered utterances already committed):
#   make pilot
#
# From scratch with raw Empirica export zips:
#   make all
#
# Individual targets:
#   make extract        # extract zips → data/pilot_runs/
#   make combine        # stack runs → data/pilots/raw/
#   make process        # preprocess → filter → derived metrics
#   make notebooks      # render SI_pilot.qmd + SI_llm_simulation.qmd
#   make llm-process    # process LLM simulation JSONs → CSVs

PILOT_RUNS = 20260301_132907 20260301_214147
ZIPS = $(foreach run,$(PILOT_RUNS),experiment/data/$(run)/empirica-export-$(run).zip)

# Directories
PILOTS_DIR = data/pilots
DERIVED_DIR = analysis/pilot_derived
LLM_SIM_DIR = analysis/llm_simulation
LLM_RESULTS = $(shell ls -d $(LLM_SIM_DIR)/llm_results_*/ 2>/dev/null | sort | tail -1)

.PHONY: all pilot extract combine process process-no-filter notebooks llm-process clean help

# ── Main targets ────────────────────────────────────────────

all: extract combine process notebooks  ## Full pipeline from zips to rendered notebooks

pilot: process-no-filter notebooks  ## For reviewers: derive metrics + render (data already committed)

# ── Pipeline steps ──────────────────────────────────────────

extract: $(ZIPS)  ## Extract each Empirica export zip
	@for zip in $^; do \
		echo "=== Extracting $$zip ==="; \
		uv run python analysis/extract_run.py "$$zip"; \
	done

combine: ## Stack extracted runs into data/pilots/raw/
	uv run python analysis/combine_runs.py $(PILOT_RUNS)

process: ## Run full pipeline (preprocess → filter → derived)
	uv run python analysis/process_data.py

process-no-filter: ## Run pipeline skipping filter (no Vertex AI needed)
	uv run python analysis/process_data.py --skip-filter

# ── LLM simulation ─────────────────────────────────────────

llm-process: ## Process LLM simulation JSONs → CSVs
	@if [ -z "$(LLM_RESULTS)" ]; then \
		echo "Error: no llm_results_*/ directory found in $(LLM_SIM_DIR)/"; \
		echo "Run the simulation first: bash $(LLM_SIM_DIR)/run_llm_simulation.sh"; \
		exit 1; \
	fi
	uv run python $(LLM_SIM_DIR)/process_llm_results.py "$(LLM_RESULTS)"

# ── Notebooks ───────────────────────────────────────────────

notebooks: llm-process ## Render SI notebooks (pilot + LLM simulation)
	quarto render analysis/SI_pilot.qmd
	quarto render $(LLM_SIM_DIR)/SI_llm_simulation.qmd

# ── Utilities ───────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
