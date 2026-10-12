"""
Dataset and results layout shared by the preprocessing, the models and the report layer.

(The module is named dataset_paths rather than datasets so it cannot shadow the
Hugging Face `datasets` package that sentence-transformers imports.)

Everything is keyed by a dataset name (`full` for the full sample, `smoke`
for the throwaway dataset `make smoke` writes). Every dataset follows the same
layout, so switching datasets is a single environment variable or flag rather
than a set of edited paths. The data tree holds what the preprocessing makes from
the exports, the results tree what the models and the report layer make from
the data:

    data/<name>/                 the hand-written inputs: runs.txt (the export
                                 timestamps combined into the dataset) and the
                                 exclusion and exception files
    data/<name>/raw/             the anonymized raw Empirica tables and their
                                 manifest.json (combine_runs.py)
    data/<name>/tables/          the analysis-ready tables (preprocessing.py;
                                 dropouts.csv from combine_runs.py; the filtered
                                 utterances and their sidecar from the filter)
    data/<name>/classifier/      the message filter's label cache, model record
                                 and the author's annotation check
    data/<name>/measures/        the measures computed from the descriptions:
                                 embeddings, similarity tables and description
                                 properties (compute_measures.py)
    data/<name>/model_inputs/    the aggregated tables the models are fit to
                                 (build_model_inputs.py)
    data/<name>/cache/           fitted objects the model scripts keep between
                                 runs (permutation results, brms fits, the H4
                                 fits the robustness and Bayes-factor scripts
                                 reuse); never committed
    results/estimates/           the tidy estimates tables each model script
                                 writes, with a manifest.json (stats/)
    results/macros/               the LaTeX macro files the manuscript reads
                                 (report/inferential.py, report/descriptives.py)
    results/figures/             the article's figures, each with the table it
                                 plots beside it (report/figures/), and in
                                 manual/ the hand-made ones

Everything generated sits one level down in the data tree, so a file at the
top of the dataset directory is one somebody wrote by hand. The results tree
is the full sample's and is committed; any other dataset keeps its results
inside its own data directory, data/<name>/results/, so a trial run never
touches it. `make sync` copies the stats and figures into the manuscript's
Overleaf project.

Per-run extracts are dataset-agnostic and go to data/runs/<timestamp>/.
`stats/config.R` mirrors this layout for the R model scripts; keep the two
in sync.

The active dataset is, in order of precedence, an explicit `--dataset`
argument, the `DATASET` environment variable, or `full`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = "full"
RUNS_DIR = PROJECT_ROOT / "data" / "runs"

# Per-run extract directories under data/runs/ are named by export timestamp.
TIMESTAMP_DIR_PATTERN = re.compile(r"^\d{8}_\d{6}$")

# The tables `empirica export` writes; extract_run.py copies them into a run's
# raw/ directory and combine_runs.py stacks them across runs.
RAW_CSV_FILES = [
    "batch.csv",
    "game.csv",
    "global.csv",
    "player.csv",
    "playerGame.csv",
    "playerRound.csv",
    "playerStage.csv",
    "round.csv",
    "stage.csv",
]

# The filtered utterances and the sidecar that ties them to the messages.csv
# they were built from (see filtered_utterances_status).
MESSAGES_FILE = "messages.csv"
FILTERED_UTTERANCES_FILE = "speaker_utterances_filtered.csv"
FILTERED_UTTERANCES_SIDECAR = "speaker_utterances_filtered.source.json"


def dataset_name(explicit: str | None = None) -> str:
    """Resolve the active dataset name."""
    name = explicit or os.environ.get("DATASET") or DEFAULT_DATASET
    if "/" in name or name in {"", ".", ".."}:
        raise ValueError(f"Invalid dataset name: {name!r}")
    return name


class DatasetDirs:
    """Paths for one dataset (see the module docstring for the layout)."""

    def __init__(self, name: str):
        self.name = name
        self.data = PROJECT_ROOT / "data" / name
        self.runs_file = self.data / "runs.txt"
        self.raw = self.data / "raw"
        self.tables = self.data / "tables"
        self.classifier = self.data / "classifier"
        self.measures = self.data / "measures"
        self.model_inputs = self.data / "model_inputs"
        self.cache = self.data / "cache"
        # The full sample's results are results/; any other dataset keeps its results inside its own data directory.
        self.results = PROJECT_ROOT / "results" if name == DEFAULT_DATASET else self.data / "results"
        self.estimates = self.results / "estimates"
        self.macros = self.results / "macros"
        self.figures = self.results / "figures"

    def read_runs(self) -> list[str]:
        """Export timestamps listed in runs.txt (blank lines and # comments ignored)."""
        if not self.runs_file.exists():
            return []
        runs = []
        for line in self.runs_file.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                runs.append(line)
        return runs

    def register_run(self, run_id: str) -> bool:
        """Add an export timestamp to runs.txt, returning whether it was new.

        Safe to call for every export: `combine_runs.py` unions the registered
        runs on record id and keeps the newest version of each record, so
        listing several cumulative exports from one server is correct rather
        than double-counting.
        """
        if run_id in self.read_runs():
            return False
        self.data.mkdir(parents=True, exist_ok=True)
        if not self.runs_file.exists():
            self.runs_file.write_text(
                f"# Empirica export timestamps combined into data/{self.name}/ "
                "(one per line).\n"
            )
        existing = self.runs_file.read_text()
        separator = "" if existing.endswith("\n") or not existing else "\n"
        with open(self.runs_file, "a") as handle:
            handle.write(f"{separator}{run_id}\n")
        return True

    def __repr__(self) -> str:
        return f"DatasetDirs({self.name!r})"


def dataset_dirs(explicit: str | None = None) -> DatasetDirs:
    return DatasetDirs(dataset_name(explicit))


# ── Filtered utterances and their provenance ────────────────────────────────
#
# speaker_utterances_filtered.csv is derived from messages.csv through the LLM
# labels in messages_classified.csv, but nothing in the file itself says which
# messages.csv it came from. Reprocessing rewrites messages.csv (a new run, an
# exclusion, a preprocessing fix) without touching the filtered file, and every
# downstream step prefers the filtered file when it exists -- so a stale one
# would be used silently. The `apply` step therefore writes a sidecar with the
# fingerprint of the messages.csv it read, and the consumers check it.


def messages_fingerprint(messages_path: Path) -> dict:
    """The identity of a messages.csv: its sha256 and its row count.

    The hash is what decides staleness; the row count is the readable half of
    the record, so a mismatch message can say how the two files differ.
    """
    import pandas as pd

    return {
        "sha256": hashlib.sha256(messages_path.read_bytes()).hexdigest(),
        "rows": int(len(pd.read_csv(messages_path))),
    }


def write_filtered_sidecar(tables_dir: Path) -> Path:
    """Record which messages.csv the filtered utterances in tables_dir came from."""
    record = {"source": MESSAGES_FILE, **messages_fingerprint(tables_dir / MESSAGES_FILE)}
    path = tables_dir / FILTERED_UTTERANCES_SIDECAR
    path.write_text(json.dumps(record, indent=2) + "\n")
    return path


def read_filtered_sidecar(tables_dir: Path) -> dict | None:
    path = tables_dir / FILTERED_UTTERANCES_SIDECAR
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


def filtered_utterances_status(tables_dir: Path) -> tuple[str, str]:
    """Whether speaker_utterances_filtered.csv in tables_dir may be used.

    Returns (status, detail), where status is one of
      "absent"      no filtered file;
      "current"     the sidecar matches the messages.csv beside it;
      "unverified"  a filtered file with no (readable) sidecar;
      "stale"       the sidecar names a different messages.csv.
    The detail is a one-line explanation suitable for a warning or error.
    """
    tables_dir = Path(tables_dir)
    filtered = tables_dir / FILTERED_UTTERANCES_FILE
    if not filtered.exists():
        return "absent", f"{FILTERED_UTTERANCES_FILE} not present"
    record = read_filtered_sidecar(tables_dir)
    if record is None:
        return (
            "unverified",
            f"{FILTERED_UTTERANCES_FILE} has no {FILTERED_UTTERANCES_SIDECAR} beside it, "
            "so which messages.csv it was built from is unknown",
        )
    messages = tables_dir / MESSAGES_FILE
    if not messages.exists():
        return "stale", f"{MESSAGES_FILE} is missing, so the filtered file cannot be checked"
    current = messages_fingerprint(messages)
    if record.get("sha256") == current["sha256"]:
        return "current", f"{FILTERED_UTTERANCES_FILE} matches {MESSAGES_FILE} ({current['rows']} messages)"
    return (
        "stale",
        f"{FILTERED_UTTERANCES_FILE} was built from a {MESSAGES_FILE} with "
        f"{record.get('rows', '?')} rows (sha256 {str(record.get('sha256', '?'))[:12]}...), "
        f"but the current one has {current['rows']} rows (sha256 {current['sha256'][:12]}...)",
    )


def stale_filtered_message(status: str, detail: str) -> str:
    """The refusal every consumer prints for a filtered file it will not use."""
    return (
        f"filtered utterances are stale; rerun the filter or pass "
        f"--utterances-file speaker_utterances.csv ({detail})"
        if status == "stale"
        else f"filtered utterances are stale or unverifiable; rerun the filter or pass "
        f"--utterances-file speaker_utterances.csv ({detail})"
    )


def add_dataset_argument(parser) -> None:
    """Add the shared --dataset option to an argparse parser."""
    parser.add_argument(
        "--dataset",
        default=None,
        help=(
            "Dataset name (data/<name>/); "
            f"default: $DATASET or '{DEFAULT_DATASET}'"
        ),
    )
