"""
Analysis pipeline: raw CSVs → preprocessed data → derived metrics.

Operates on data/pilots/. The raw CSVs in data/pilots/raw_anonymized/ must already exist
(either committed, or produced by extract_run.py + combine_runs.py).

Usage:
    uv run python analysis/process_data.py                          # run full pipeline
    uv run python analysis/process_data.py --skip-filter            # skip Vertex AI step
    uv run python analysis/process_data.py --skip-derived           # skip SBERT step
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
PILOTS_DIR = PROJECT_ROOT / "data" / "pilots"


def step_preprocess(raw_dir: Path, data_dir: Path) -> None:
    """Run preprocessing.py: raw CSVs → analysis-ready CSVs."""
    print(f"\n{'=' * 60}")
    print("Step 1: Preprocessing")
    print(f"{'=' * 60}")
    script = ANALYSIS_DIR / "preprocessing.py"
    subprocess.run(
        [sys.executable, str(script), str(raw_dir), "--output", str(data_dir)],
        check=True,
    )


def step_filter_messages(data_dir: Path) -> None:
    """Run filter_nonreferential.py: classify and filter non-referential messages."""
    print(f"\n{'=' * 60}")
    print("Step 2: Filtering non-referential messages")
    print(f"{'=' * 60}")
    script = ANALYSIS_DIR / "filter_nonreferential.py"
    subprocess.run(
        [sys.executable, str(script), "classify", "--data-dir", str(data_dir)],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(script), "apply", "--data-dir", str(data_dir)],
        check=True,
    )


def step_compute_derived(data_dir: Path, output_dir: Path) -> None:
    """Run compute_derived.py: embeddings, similarities, UMAP, etc."""
    print(f"\n{'=' * 60}")
    print("Step 3: Computing derived metrics")
    print(f"{'=' * 60}")
    output_dir.mkdir(parents=True, exist_ok=True)
    script = ANALYSIS_DIR / "compute_derived.py"
    subprocess.run(
        [sys.executable, str(script), str(data_dir), "--output", str(output_dir)],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run the analysis pipeline on data/pilots/",
    )
    parser.add_argument("--skip-filter", action="store_true",
                        help="Skip non-referential message filtering (requires Vertex AI)")
    parser.add_argument("--skip-derived", action="store_true",
                        help="Skip computing derived metrics (SBERT, similarities, UMAP)")
    args = parser.parse_args()

    raw_dir = PILOTS_DIR / "raw_anonymized"
    data_dir = PILOTS_DIR
    derived_dir = ANALYSIS_DIR / "pilot_derived"

    if not raw_dir.is_dir():
        print(f"Error: {raw_dir} does not exist.", file=sys.stderr)
        print("Either the raw data is not committed, or you need to run:", file=sys.stderr)
        print("  uv run python analysis/extract_run.py <zip>", file=sys.stderr)
        print("  uv run python analysis/combine_runs.py <runs...>", file=sys.stderr)
        sys.exit(1)

    step_preprocess(raw_dir, data_dir)

    if args.skip_filter:
        print(f"\n{'=' * 60}")
        print("Skipping message filtering (--skip-filter)")
        print(f"{'=' * 60}")
    else:
        step_filter_messages(data_dir)

    if args.skip_derived:
        print(f"\n{'=' * 60}")
        print("Skipping derived metrics (--skip-derived)")
        print(f"{'=' * 60}")
    else:
        step_compute_derived(data_dir, derived_dir)

    print(f"\n{'=' * 60}")
    print("Pipeline complete!")
    print(f"{'=' * 60}")
    print(f"  Data:    {data_dir}")
    print(f"  Derived: {derived_dir}")


if __name__ == "__main__":
    main()
