"""Stage the final Empirica export of each server period for an off-site backup.

    uv run python operations/final_exports.py                # stage into backups/final_exports/
    uv run python operations/final_exports.py --dry-run      # report only
    uv run python operations/final_exports.py --dest <dir>   # another destination

The backup loop (`operations/copy_tajriba.sh`) exported the production server
every five minutes during a session, so `experiment/data/` holds hundreds of
export folders of which most are earlier snapshots of a later one: an Empirica
export is a cumulative snapshot of one server, and a later export of the same
server holds every record of an earlier one, with newer versions. Only a
server reset (a crash, or clearing tajriba.json between sessions) starts a
new period. The last export of each period is therefore the one worth
keeping, and together those cover every record ever exported.

This script finds them from the data rather than from names or times: it
reads the record ids of every table straight from each zip and marks an
export redundant when some later export contains all of them, table by table.
It then copies the exports that are not redundant into `<dest>/exports/<ts>/`
(the zip and the server log saved beside it), copies every server log into
`<dest>/server-logs/` (each log is the twenty minutes before its export, so
the intermediate exports' logs are what makes the server's history
continuous), and writes `manifest.json` (which exports each kept one covers,
which registered run of a dataset each covers, record counts, and the check
that the kept exports hold every record) and a `README.md` for whoever finds
the backup. Nothing under `experiment/data/` is touched.

`data/<dataset>/runs.txt` is expected to name exactly these exports. The
manifest records which kept export each registered run falls under, and the
summary names any registered run that is not itself a period's final export,
since such a run would be missing the records written after it was taken.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))
from dataset_paths import RAW_CSV_FILES, TIMESTAMP_DIR_PATTERN, dataset_dirs  # noqa: E402

DEFAULT_SOURCE = PROJECT_ROOT / "experiment" / "data"
DEFAULT_DEST = PROJECT_ROOT / "backups" / "final_exports"


def export_folders(source: Path) -> list[Path]:
    """The timestamp-named export folders under `source`, oldest first."""
    return sorted(p for p in source.iterdir() if p.is_dir() and TIMESTAMP_DIR_PATTERN.match(p.name))


def record_ids(zip_path: Path) -> dict[str, frozenset]:
    """The set of record ids in each table of one export zip."""
    ids = {}
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        for table in RAW_CSV_FILES:
            if table not in names:
                ids[table] = frozenset()
                continue
            with zf.open(table) as fh:
                frame = pd.read_csv(io.BytesIO(fh.read()), usecols=["id"], dtype=str)
            ids[table] = frozenset(frame["id"].dropna())
    return ids


def contained_in(ids: dict[str, dict[str, frozenset]]) -> dict[str, str | None]:
    """For each export, the first later export that holds all of its records
    in every table, or None when no later export does."""
    order = sorted(ids)
    result: dict[str, str | None] = {}
    for i, ts in enumerate(order):
        result[ts] = None
        for later in order[i + 1:]:
            if all(ids[ts][t] <= ids[later][t] for t in RAW_CSV_FILES):
                result[ts] = later
                break
    return result


def final_export_of(ts: str, containment: dict[str, str | None]) -> str:
    """Follow the containment chain from an export to the kept export that covers it."""
    while containment[ts] is not None:
        ts = containment[ts]
    return ts


def registered_runs(dataset: str) -> list[str]:
    return dataset_dirs(dataset).read_runs()


def analyze(source: Path, dataset: str) -> dict:
    folders = export_folders(source)
    ids: dict[str, dict[str, frozenset]] = {}
    sizes: dict[str, int] = {}
    without_zip: list[str] = []
    unreadable: dict[str, str] = {}
    for folder in folders:
        zips = sorted(folder.glob("empirica-export-*.zip"))
        if len(zips) != 1:
            without_zip.append(folder.name)
            continue
        try:
            ids[folder.name] = record_ids(zips[0])
        except Exception as exc:  # noqa: BLE001 -- a corrupt zip is a finding, not a crash
            unreadable[folder.name] = str(exc)
            continue
        sizes[folder.name] = zips[0].stat().st_size

    containment = contained_in(ids)
    kept = [ts for ts in sorted(ids) if containment[ts] is None]
    coverage = {k: [ts for ts in sorted(ids) if final_export_of(ts, containment) == k] for k in kept}

    union_all = {t: set().union(*(ids[ts][t] for ts in ids)) for t in RAW_CSV_FILES}
    union_kept = {t: set().union(*(ids[ts][t] for ts in kept)) for t in RAW_CSV_FILES}
    complete = all(union_all[t] == union_kept[t] for t in RAW_CSV_FILES)

    runs = registered_runs(dataset)
    run_cover = {
        r: (final_export_of(r, containment) if r in ids else None) for r in runs
    }
    return {
        "source": str(source),
        "exports": len(ids),
        "folders_without_zip": without_zip,
        "unreadable_zips": unreadable,
        "kept": kept,
        "kept_zip_bytes": {k: sizes[k] for k in kept},
        "coverage": coverage,
        "every_record_covered": complete,
        "records_per_table": {t: len(union_all[t]) for t in RAW_CSV_FILES},
        "dataset": dataset,
        "registered_runs": runs,
        "registered_run_final_export": run_cover,
        "registered_runs_not_final": [r for r, c in run_cover.items() if c != r],
        "final_exports_not_registered": [k for k in kept if k not in runs],
    }


def stage(analysis: dict, source: Path, dest: Path) -> dict:
    """Copy the kept exports and every server log into `dest`; return what was copied."""
    exports_dir = dest / "exports"
    logs_dir = dest / "server-logs"
    exports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    copied_exports = []
    for ts in analysis["kept"]:
        target = exports_dir / ts
        target.mkdir(exist_ok=True)
        for f in sorted((source / ts).iterdir()):
            if f.is_file():
                shutil.copy2(f, target / f.name)
        copied_exports.append(ts)
    copied_logs = 0
    for folder in export_folders(source):
        for log in folder.glob("server-log-*.txt"):
            shutil.copy2(log, logs_dir / log.name)
            copied_logs += 1
    return {"exports": copied_exports, "server_logs": copied_logs}


def write_readme(analysis: dict, staged: dict, dest: Path) -> None:
    kept = analysis["kept"]
    lines = [
        f"# Final Empirica exports of the full sample (staged {date.today().isoformat()})",
        "",
        "This folder is the deduplicated backup of the raw data of the lexical-variation",
        "experiment's full sample (September 22 to October 8, 2026). The production",
        "server was exported every five minutes during a data-collection session, and an",
        "Empirica export is a cumulative snapshot of one server, so most of those exports",
        "are earlier states of a later one. `exports/` holds the last export of each",
        f"server period ({len(kept)} of {analysis['exports']} exports), chosen by checking that",
        "a later export holds every record of the earlier one in every table; together",
        f"they hold every record that was ever exported ({'verified' if analysis['every_record_covered'] else 'NOT verified'}).",
        "Each export folder has the zip of CSV tables that `empirica export` wrote and the",
        "server log saved beside it. `server-logs/` has the log saved with every export,",
        "including the dropped ones, because each log covers only the twenty minutes before",
        f"its export ({staged['server_logs']} files). `manifest.json` lists which exports each kept",
        "one covers and which registered run of the analysis dataset each corresponds to",
        f"(`data/{analysis['dataset']}/runs.txt` {'names exactly these exports' if not analysis['registered_runs_not_final'] and not analysis['final_exports_not_registered'] else 'differs from them; see the manifest'}).",
        "",
        "The zips hold identifiable participant data (Prolific ids, free text) and must",
        "stay private; the anonymized, analysis-ready data are produced from them by the",
        "pipeline in the project repository (`analysis/extract_run.py` and onward).",
        "",
        "Built by `operations/final_exports.py` in the repository.",
        "",
        "| Kept export | Covers | From |",
        "|---|---|---|",
    ]
    for k in kept:
        cov = analysis["coverage"][k]
        lines.append(f"| {k} | {len(cov)} exports | {cov[0]} |")
    if analysis["folders_without_zip"]:
        lines += ["", "Export folders with no zip (a backup that failed; only their logs are here): "
                  + ", ".join(analysis["folders_without_zip"])]
    (dest / "README.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="folder of export folders (default experiment/data)")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="where to stage (default backups/final_exports)")
    parser.add_argument("--dataset", default="full", help="dataset whose runs.txt to cross-reference (default full)")
    parser.add_argument("--dry-run", action="store_true", help="analyze and report; copy nothing")
    args = parser.parse_args()

    analysis = analyze(args.source, args.dataset)
    kept = analysis["kept"]
    print(f"{analysis['exports']} exports under {args.source}; {len(kept)} are the final export of a server period")
    print(f"every record covered by the kept exports: {analysis['every_record_covered']}")
    total_mb = sum(analysis["kept_zip_bytes"].values()) / 1e6
    print(f"kept zips: {total_mb:.1f} MB")
    if analysis["folders_without_zip"]:
        print(f"folders without a zip: {analysis['folders_without_zip']}")
    if analysis["unreadable_zips"]:
        print(f"unreadable zips: {analysis['unreadable_zips']}")
    not_final = analysis["registered_runs_not_final"]
    unregistered = analysis["final_exports_not_registered"]
    if not not_final and not unregistered:
        print(f"data/{args.dataset}/runs.txt names exactly the final export of every period")
    else:
        print(
            f"registered runs in data/{args.dataset}/runs.txt that are not a period's final export: "
            f"{', '.join(not_final) or 'none'}; final exports not registered: {', '.join(unregistered) or 'none'}"
        )
    if args.dry_run:
        return
    staged = stage(analysis, args.source, args.dest)
    analysis["staged"] = staged
    (args.dest / "manifest.json").write_text(json.dumps(analysis, indent=2) + "\n")
    write_readme(analysis, staged, args.dest)
    print(f"staged {len(staged['exports'])} exports and {staged['server_logs']} server logs in {args.dest}")


if __name__ == "__main__":
    main()
