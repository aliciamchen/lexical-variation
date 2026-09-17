"""
Analysis pipeline: raw CSVs → preprocessed data → derived metrics.

Operates on one dataset (see dataset_paths.py for the layout): the raw CSVs in
data/<dataset>/raw_anonymized/ must already exist (either committed, or
produced by extract_run.py + combine_runs.py), and the outputs go to
data/<dataset>/ and analysis/derived/<dataset>/.

Usage:
    uv run python analysis/process_data.py                          # run full pipeline on $DATASET (default pilots)
    uv run python analysis/process_data.py --dataset full           # another dataset
    uv run python analysis/process_data.py --skip-filter            # skip Vertex AI step
    uv run python analysis/process_data.py --skip-derived           # skip SBERT step
"""

import argparse
import subprocess
import sys
from pathlib import Path

from dataset_paths import (
    FILTERED_UTTERANCES_FILE,
    PROJECT_ROOT,
    add_dataset_argument,
    dataset_dirs,
    filtered_utterances_status,
    stale_filtered_message,
)

ANALYSIS_DIR = PROJECT_ROOT / "analysis"


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


def step_compute_derived(
    data_dir: Path, output_dir: Path, utterances_file: str | None = None
) -> None:
    """Run compute_derived.py: embeddings, similarities, UMAP, etc."""
    print(f"\n{'=' * 60}")
    print("Step 3: Computing derived metrics")
    print(f"{'=' * 60}")
    output_dir.mkdir(parents=True, exist_ok=True)
    script = ANALYSIS_DIR / "compute_derived.py"
    command = [sys.executable, str(script), str(data_dir), "--output", str(output_dir)]
    if utterances_file:
        command += ["--utterances-file", utterances_file]
    subprocess.run(command, check=True)


def choose_utterances_file(data_dir: Path) -> str | None:
    """Which utterance file the derived step should read when the filter was skipped.

    Preprocessing has already deleted a filtered file that no longer matches
    messages.csv; what can remain is a current one (use it), none (the derived
    step falls back to the unfiltered file on its own), or one whose sidecar is
    missing. That last case is refused downstream, so the fallback is chosen
    here and announced: the derived metrics will include non-referential
    messages until the filter is rerun.
    """
    status, detail = filtered_utterances_status(data_dir)
    if status == "current":
        print(f"  Using {FILTERED_UTTERANCES_FILE}: {detail}")
        return None
    if status == "absent":
        print("  No filtered utterances; the derived metrics use speaker_utterances.csv")
        return None
    banner = "!" * 60
    print(f"\n{banner}")
    print(f"WARNING: {stale_filtered_message(status, detail)}")
    print("Falling back to speaker_utterances.csv (unfiltered) because --skip-filter was given.")
    print("The derived metrics therefore include non-referential messages; run")
    print("  uv run python analysis/filter_nonreferential.py classify --data-dir <data_dir>")
    print("  uv run python analysis/filter_nonreferential.py apply    --data-dir <data_dir>")
    print("and recompute the derived metrics before analyzing them.")
    print(f"{banner}\n")
    return "speaker_utterances.csv"


def main():
    parser = argparse.ArgumentParser(
        description="Run the analysis pipeline on one dataset (data/<dataset>/)",
    )
    add_dataset_argument(parser)
    parser.add_argument("--skip-filter", action="store_true",
                        help="Skip non-referential message filtering (requires Vertex AI)")
    parser.add_argument("--skip-derived", action="store_true",
                        help="Skip computing derived metrics (SBERT, similarities, UMAP)")
    args = parser.parse_args()

    dirs = dataset_dirs(args.dataset)
    raw_dir = dirs.raw
    data_dir = dirs.data
    derived_dir = dirs.derived
    print(f"Dataset: {dirs.name}")

    if not raw_dir.is_dir():
        print(f"Error: {raw_dir} does not exist.", file=sys.stderr)
        print("Either the raw data is not committed, or you need to run:", file=sys.stderr)
        print("  uv run python analysis/extract_run.py <zip>", file=sys.stderr)
        print(f"  uv run python analysis/combine_runs.py --dataset {dirs.name} <runs...>", file=sys.stderr)
        sys.exit(1)

    step_preprocess(raw_dir, data_dir)

    utterances_file = None
    if args.skip_filter:
        print(f"\n{'=' * 60}")
        print("Skipping message filtering (--skip-filter)")
        print(f"{'=' * 60}")
        utterances_file = choose_utterances_file(data_dir)
    else:
        step_filter_messages(data_dir)

    if args.skip_derived:
        print(f"\n{'=' * 60}")
        print("Skipping derived metrics (--skip-derived)")
        print(f"{'=' * 60}")
    else:
        step_compute_derived(data_dir, derived_dir, utterances_file)

    print(f"\n{'=' * 60}")
    print("Pipeline complete!")
    print(f"{'=' * 60}")
    print(f"  Data:    {data_dir}")
    print(f"  Derived: {derived_dir}")


if __name__ == "__main__":
    main()
