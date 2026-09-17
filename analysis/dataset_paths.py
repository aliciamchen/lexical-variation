"""
Dataset layout shared by the pipeline scripts.

(The module is named dataset_paths rather than datasets so it cannot shadow the
Hugging Face `datasets` package that sentence-transformers imports.)

The pipeline is keyed by a dataset name (`pilots` for the pilot sessions; the
full sample gets its own name, e.g. `full`). Every dataset follows the same
layout, so switching datasets is a single environment variable or flag rather
than a set of edited paths:

    data/<name>/raw_anonymized/   anonymized raw Empirica CSVs (combine_runs.py)
    data/<name>/*.csv             preprocessed analysis-ready CSVs (preprocessing.py)
    data/<name>/runs.txt          the export timestamps combined into the dataset
    analysis/derived/<name>/      derived metrics and model caches (compute_derived.py)
    figures/<name>/               notebook figures

Per-run extracts are dataset-agnostic and go to data/runs/<timestamp>/.
`analysis/config.R` mirrors this layout for the Quarto notebooks; keep the two
in sync.

The active dataset is, in order of precedence, an explicit `--dataset`
argument, the `DATASET` environment variable, or `pilots`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = "pilots"
# The pilot is complete and committed. extract_run.py and combine_runs.py refuse
# to add exports to it or rebuild it from other exports without an explicit
# override, so a full-sample session can never be folded into it by accident.
FROZEN_DATASET = "pilots"
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
        self.raw = self.data / "raw_anonymized"
        self.runs_file = self.data / "runs.txt"
        self.derived = PROJECT_ROOT / "analysis" / "derived" / name
        self.figures = PROJECT_ROOT / "figures" / name

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


def write_filtered_sidecar(data_dir: Path) -> Path:
    """Record which messages.csv the filtered utterances in data_dir came from."""
    record = {"source": MESSAGES_FILE, **messages_fingerprint(data_dir / MESSAGES_FILE)}
    path = data_dir / FILTERED_UTTERANCES_SIDECAR
    path.write_text(json.dumps(record, indent=2) + "\n")
    return path


def read_filtered_sidecar(data_dir: Path) -> dict | None:
    path = data_dir / FILTERED_UTTERANCES_SIDECAR
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


def filtered_utterances_status(data_dir: Path) -> tuple[str, str]:
    """Whether speaker_utterances_filtered.csv in data_dir may be used.

    Returns (status, detail), where status is one of
      "absent"      no filtered file;
      "current"     the sidecar matches the messages.csv beside it;
      "unverified"  a filtered file with no (readable) sidecar;
      "stale"       the sidecar names a different messages.csv.
    The detail is a one-line explanation suitable for a warning or error.
    """
    data_dir = Path(data_dir)
    filtered = data_dir / FILTERED_UTTERANCES_FILE
    if not filtered.exists():
        return "absent", f"{FILTERED_UTTERANCES_FILE} not present"
    record = read_filtered_sidecar(data_dir)
    if record is None:
        return (
            "unverified",
            f"{FILTERED_UTTERANCES_FILE} has no {FILTERED_UTTERANCES_SIDECAR} beside it, "
            "so which messages.csv it was built from is unknown",
        )
    messages = data_dir / MESSAGES_FILE
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
            "Dataset name (data/<name>/, analysis/derived/<name>/); "
            f"default: $DATASET or '{DEFAULT_DATASET}'"
        ),
    )
