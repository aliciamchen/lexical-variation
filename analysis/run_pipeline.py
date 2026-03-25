"""
Analysis pipeline: raw CSVs → preprocessed data → derived metrics.

Operates on data/pilots/. The raw CSVs in data/pilots/raw/ must already exist
(either committed, or produced by extract_run.py + combine).

Usage:
    uv run python analysis/run_pipeline.py                          # run full pipeline
    uv run python analysis/run_pipeline.py --skip-filter            # skip Vertex AI step

    uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147
    uv run python analysis/run_pipeline.py list
    uv run python analysis/run_pipeline.py bonuses
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
DATA_DIR = PROJECT_ROOT / "data"
RUNS_DIR = DATA_DIR / "pilot_runs"
PILOTS_DIR = DATA_DIR / "pilots"

TIMESTAMP_DIR_PATTERN = re.compile(r"^\d{8}_\d{6}$")

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

SUBCOMMANDS = {"list", "bonuses", "early-ended", "combine"}


# ── Pipeline steps ──────────────────────────────────────────

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


# ── Combine helpers ─────────────────────────────────────────

def validate_runs(run_ids: list[str]) -> list[Path]:
    """Check that each run's raw/ directory exists, return paths."""
    raw_dirs = []
    for run_id in run_ids:
        raw_dir = RUNS_DIR / run_id / "raw"
        if not raw_dir.is_dir():
            print(f"Error: {raw_dir} does not exist", file=sys.stderr)
            print(f"Run extract_run.py first to process the zip.", file=sys.stderr)
            sys.exit(1)
        raw_dirs.append(raw_dir)
    return raw_dirs


def stack_raw_csvs(raw_dirs: list[Path], run_ids: list[str]) -> dict[str, pd.DataFrame]:
    """Concatenate each raw CSV across runs, adding _sourceRun column."""
    combined = {}
    for csv_name in RAW_CSV_FILES:
        frames = []
        for raw_dir, run_id in zip(raw_dirs, run_ids):
            csv_path = raw_dir / csv_name
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                df["_sourceRun"] = run_id
                frames.append(df)
        if frames:
            combined[csv_name] = pd.concat(frames, ignore_index=True, join="outer")
        else:
            print(f"  Warning: {csv_name} not found in any run")
    return combined


def filter_failed_games(combined: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Remove games with no condition (lobby timeouts) and cascade to related tables."""
    game_df = combined["game.csv"]
    failed_mask = game_df["condition"].isna() | (game_df["condition"] == "")
    failed_ids = set(game_df.loc[failed_mask, "id"])

    if failed_ids:
        print(f"  Filtering out {len(failed_ids)} failed game(s): {failed_ids}")

    game_df = game_df[~game_df["id"].isin(failed_ids)].copy()
    combined["game.csv"] = game_df

    valid_game_ids = set(game_df["id"])
    for csv_name in ["player.csv", "playerGame.csv", "playerRound.csv",
                     "playerStage.csv", "round.csv", "stage.csv"]:
        if csv_name not in combined:
            continue
        df = combined[csv_name]
        if "gameID" in df.columns:
            combined[csv_name] = df[df["gameID"].isin(valid_game_ids)].copy()

    return combined


def write_combined_raw(combined: dict[str, pd.DataFrame], output_raw: Path):
    """Write combined raw CSVs to output directory."""
    output_raw.mkdir(parents=True, exist_ok=True)
    for csv_name, df in combined.items():
        df.to_csv(output_raw / csv_name, index=False)
        print(f"  {csv_name}: {len(df)} rows")


def write_manifest(output_dir: Path, run_ids: list[str], combined: dict[str, pd.DataFrame]):
    """Write manifest.json with provenance info."""
    game_df = combined["game.csv"]
    manifest = {
        "source_runs": run_ids,
        "created": datetime.now().isoformat(),
        "games": len(game_df),
        "conditions": game_df["condition"].value_counts().to_dict(),
        "row_counts": {name: len(df) for name, df in combined.items()},
    }
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest written to {manifest_path}")


# ── Subcommands ─────────────────────────────────────────────

def find_timestamped_dirs() -> list[Path]:
    """Find all timestamped run directories under data/pilot_runs/."""
    if not RUNS_DIR.is_dir():
        return []
    dirs = []
    for d in sorted(RUNS_DIR.iterdir(), reverse=True):
        if d.is_dir() and TIMESTAMP_DIR_PATTERN.match(d.name):
            dirs.append(d)
    return dirs


def cmd_list():
    """List all extracted runs."""
    dirs = find_timestamped_dirs()
    if not dirs:
        print("No runs found in data/pilot_runs/.")
        return

    print(f"\nExtracted runs (data/pilot_runs/):")
    print(f"{'─' * 90}")

    for d in dirs:
        dt = d.name
        games_path = d / "data" / "games.csv"
        game_info = ""
        player_info = ""
        if games_path.exists():
            try:
                games = pd.read_csv(games_path)
                n_games = len(games)
                conditions = ", ".join(sorted(games["condition"].dropna().unique()))
                game_info = f"{n_games} game{'s' if n_games != 1 else ''} ({conditions})"
                players_path = d / "data" / "players.csv"
                if players_path.exists():
                    players = pd.read_csv(players_path)
                    player_info = f"{len(players)} players"
            except Exception:
                game_info = "(error reading metadata)"
        has_bonuses = "yes" if (d / "bonuses.csv").exists() else "no"
        n_outputs = sum(1 for _ in d.rglob("*") if _.is_file())
        parts = [f"  {dt}"]
        if game_info:
            parts.append(game_info)
        if player_info:
            parts.append(player_info)
        parts.append(f"bonuses: {has_bonuses}")
        parts.append(f"{n_outputs} files")
        print("  ".join(parts))
    print()


def cmd_bonuses(run_name: str | None = None):
    """Print bonus CSV for a specific or latest run."""
    if run_name:
        bonus_dir = RUNS_DIR / run_name
    else:
        dirs = find_timestamped_dirs()
        if not dirs:
            print("No runs found.", file=sys.stderr)
            sys.exit(1)
        bonus_dir = dirs[0]

    bonus_path = bonus_dir / "bonuses.csv"
    if not bonus_path.exists():
        print(f"No bonuses.csv in {bonus_dir.name}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(bonus_path)
    print(f"\nBonuses for run {bonus_dir.name}:")
    print(f"{'─' * 50}")
    print(df.to_string(index=False))
    print(f"{'─' * 50}")
    print(f"  Total: ${df['bonus'].sum():.2f} across {len(df)} players")
    print(f"  Mean:  ${df['bonus'].mean():.2f}")
    print()


def cmd_early_ended(run_name: str | None = None):
    """Print early-ended players CSV for a specific or latest run."""
    if run_name:
        run_dir = RUNS_DIR / run_name
    else:
        dirs = find_timestamped_dirs()
        if not dirs:
            print("No runs found.", file=sys.stderr)
            sys.exit(1)
        run_dir = dirs[0]

    early_path = run_dir / "early_ended.csv"
    if not early_path.exists():
        print(f"No early_ended.csv in {run_dir.name}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(early_path)
    print(f"\nEarly-ended players for run {run_dir.name}:")
    print(f"{'─' * 80}")
    print(df.to_string(index=False))
    print(f"{'─' * 80}")
    print(f"  {len(df)} players, total partial pay: ${df['partial_pay'].sum():.2f}")
    print()


def cmd_combine(argv: list[str]):
    """Stack raw CSVs from multiple extracted runs into data/pilots/raw/."""
    parser = argparse.ArgumentParser(
        description="Stack raw CSVs from multiple runs into data/pilots/raw/"
    )
    parser.add_argument(
        "runs", nargs="+",
        help="Run timestamps (e.g. 20260301_132907 20260301_214147)"
    )
    args = parser.parse_args(argv)

    output_raw = PILOTS_DIR / "raw"

    print("Validating runs...")
    raw_dirs = validate_runs(args.runs)

    print("\nStacking raw CSVs...")
    combined = stack_raw_csvs(raw_dirs, args.runs)

    print("\nFiltering failed games...")
    combined = filter_failed_games(combined)

    print("\nWriting combined raw CSVs...")
    write_combined_raw(combined, output_raw)

    write_manifest(PILOTS_DIR, args.runs, combined)

    game_df = combined["game.csv"]
    print(f"\nCombine complete: {len(game_df)} games from {len(args.runs)} runs")
    print(f"  Output: {output_raw}")


# ── Main: run the pipeline ──────────────────────────────────

def run_pipeline(args):
    """Run the analysis pipeline on data/pilots/."""
    raw_dir = PILOTS_DIR / "raw"
    data_dir = PILOTS_DIR
    derived_dir = ANALYSIS_DIR / "pilot_derived"

    if not raw_dir.is_dir():
        print(f"Error: {raw_dir} does not exist.", file=sys.stderr)
        print("Either the raw data is not committed, or you need to run:", file=sys.stderr)
        print("  uv run python analysis/extract_run.py <zip>", file=sys.stderr)
        print("  uv run python analysis/run_pipeline.py combine <runs...>", file=sys.stderr)
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


def main():
    if len(sys.argv) > 1 and sys.argv[1] in SUBCOMMANDS:
        subcmd = sys.argv[1]
        if subcmd == "list":
            cmd_list()
            return
        elif subcmd == "bonuses":
            run_name = None
            if "--run" in sys.argv:
                idx = sys.argv.index("--run")
                if idx + 1 < len(sys.argv):
                    run_name = sys.argv[idx + 1]
                else:
                    print("--run requires a value", file=sys.stderr)
                    sys.exit(1)
            cmd_bonuses(run_name)
            return
        elif subcmd == "early-ended":
            run_name = None
            if "--run" in sys.argv:
                idx = sys.argv.index("--run")
                if idx + 1 < len(sys.argv):
                    run_name = sys.argv[idx + 1]
                else:
                    print("--run requires a value", file=sys.stderr)
                    sys.exit(1)
            cmd_early_ended(run_name)
            return
        elif subcmd == "combine":
            cmd_combine(sys.argv[2:])
            return

    parser = argparse.ArgumentParser(
        description="Run the analysis pipeline on data/pilots/",
    )
    parser.add_argument("--skip-filter", action="store_true",
                        help="Skip non-referential message filtering (requires Vertex AI)")
    parser.add_argument("--skip-derived", action="store_true",
                        help="Skip computing derived metrics (SBERT, similarities, UMAP)")
    args = parser.parse_args()

    run_pipeline(args)


if __name__ == "__main__":
    main()
