"""
Analysis pipeline: raw tables → processed tables → derived metrics → frames.

Operates on one dataset (see dataset_paths.py for the layout): the anonymized
raw tables in data/<dataset>/raw/ must already exist (written by extract_run.py
and combine_runs.py), and the outputs go to data/<dataset>/tables/, derived/
and frames/.

Usage:
    uv run python -m pipeline.process_data                          # run full pipeline on $DATASET (default full)
    uv run python -m pipeline.process_data --dataset full           # another dataset
    uv run python -m pipeline.process_data --skip-filter            # skip Vertex AI step
    uv run python -m pipeline.process_data --skip-derived           # skip SBERT step
    uv run python -m pipeline.process_data --skip-frames            # skip the model-input frames
"""

import argparse
import subprocess
import sys
from pathlib import Path

from pipeline.dataset_paths import (
    FILTERED_UTTERANCES_FILE,
    PROJECT_ROOT,
    add_dataset_argument,
    dataset_dirs,
    filtered_utterances_status,
    stale_filtered_message,
)


def run_step(module: str, *args: str) -> None:
    """Run one pipeline module from the repository root."""
    subprocess.run(
        [sys.executable, "-m", f"pipeline.{module}", *args],
        check=True,
        cwd=PROJECT_ROOT,
    )


def banner(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print(f"{'=' * 60}")


def step_preprocess(dataset: str) -> None:
    """Run preprocessing.py: raw tables → analysis-ready tables."""
    banner("Step 1: Preprocessing")
    run_step("preprocessing", "--dataset", dataset)


def step_filter_messages(dataset: str) -> None:
    """Run filter_nonreferential.py: classify and filter non-referential messages."""
    banner("Step 2: Filtering non-referential messages")
    run_step("filter_nonreferential", "classify", "--dataset", dataset)
    run_step("filter_nonreferential", "apply", "--dataset", dataset)


def step_compute_derived(dataset: str, utterances_file: str | None = None) -> None:
    """Run compute_derived.py: embeddings, similarity tables and description properties."""
    banner("Step 3: Computing derived metrics")
    args = ["--dataset", dataset]
    if utterances_file:
        args += ["--utterances-file", utterances_file]
    run_step("compute_derived", *args)


def step_build_frames(dataset: str) -> None:
    """Run build_frames.py: the model-input frames from the processed and derived tables."""
    banner("Step 4: Building the model-input frames")
    run_step("build_frames", "--dataset", dataset)


def choose_utterances_file(tables_dir: Path) -> str | None:
    """Which utterance file the derived step should read when the filter was skipped.

    Preprocessing has already deleted a filtered file that no longer matches
    messages.csv; what can remain is a current one (use it), none (the derived
    step falls back to the unfiltered file on its own), or one whose sidecar is
    missing. That last case is refused downstream, so the fallback is chosen
    here and announced: the derived metrics will include non-referential
    messages until the filter is rerun.
    """
    status, detail = filtered_utterances_status(tables_dir)
    if status == "current":
        print(f"  Using {FILTERED_UTTERANCES_FILE}: {detail}")
        return None
    if status == "absent":
        print("  No filtered utterances; the derived metrics use speaker_utterances.csv")
        return None
    warn = "!" * 60
    print(f"\n{warn}")
    print(f"WARNING: {stale_filtered_message(status, detail)}")
    print("Falling back to speaker_utterances.csv (unfiltered) because --skip-filter was given.")
    print("The derived metrics therefore include non-referential messages; run")
    print("  uv run python -m pipeline.filter_nonreferential classify --dataset <name>")
    print("  uv run python -m pipeline.filter_nonreferential apply    --dataset <name>")
    print("and recompute the derived metrics before analyzing them.")
    print(f"{warn}\n")
    return "speaker_utterances.csv"


def main():
    parser = argparse.ArgumentParser(
        description="Run the analysis pipeline on one dataset (data/<dataset>/)",
    )
    add_dataset_argument(parser)
    parser.add_argument("--skip-filter", action="store_true",
                        help="Skip non-referential message filtering (requires Vertex AI)")
    parser.add_argument("--skip-derived", action="store_true",
                        help="Skip computing derived metrics (SBERT embeddings, similarity tables, description properties)")
    parser.add_argument("--skip-frames", action="store_true",
                        help="Skip building the model-input frames (needs the derived tables)")
    args = parser.parse_args()

    dirs = dataset_dirs(args.dataset)
    print(f"Dataset: {dirs.name}")

    if not dirs.raw.is_dir():
        print(f"Error: {dirs.raw} does not exist.", file=sys.stderr)
        print("Either the raw data is not committed, or you need to run:", file=sys.stderr)
        print("  uv run python -m pipeline.extract_run <zip>", file=sys.stderr)
        print(f"  uv run python -m pipeline.combine_runs --dataset {dirs.name} <runs...>", file=sys.stderr)
        sys.exit(1)

    step_preprocess(dirs.name)

    utterances_file = None
    if args.skip_filter:
        banner("Skipping message filtering (--skip-filter)")
        utterances_file = choose_utterances_file(dirs.tables)
    else:
        step_filter_messages(dirs.name)

    if args.skip_derived:
        banner("Skipping derived metrics (--skip-derived)")
    else:
        step_compute_derived(dirs.name, utterances_file)

    if args.skip_frames:
        banner("Skipping the model-input frames (--skip-frames)")
    else:
        step_build_frames(dirs.name)

    banner("Pipeline complete!")
    print(f"  Tables:  {dirs.tables}")
    print(f"  Derived: {dirs.derived}")
    print(f"  Frames:  {dirs.frames}")


if __name__ == "__main__":
    main()
