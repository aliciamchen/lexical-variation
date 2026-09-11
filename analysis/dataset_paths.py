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

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = "pilots"
RUNS_DIR = PROJECT_ROOT / "data" / "runs"


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

    def __repr__(self) -> str:
        return f"DatasetDirs({self.name!r})"


def dataset_dirs(explicit: str | None = None) -> DatasetDirs:
    return DatasetDirs(dataset_name(explicit))


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
