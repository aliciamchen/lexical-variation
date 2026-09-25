"""What each Prolific study still owes, built from a dataset's exports.

    uv run python operations/payments.py --dataset full <zip> [<zip> ...]
    make payments DATASET=full          # the same, fed the zips in runs.txt

A session can span several Prolific studies and several Empirica batches, and
an export is a cumulative snapshot of the server, so no single export or batch
lines up with "the people one study owes". This step reads every export of the
dataset, takes each player placed in a game, and groups them by the Prolific
study recorded from their study link (`studyId`). It then asks Prolific, with
read-only requests, for each study's name and submissions, which carry each
submission's status and the bonuses already paid on it, and adds the
lobby-timeout participants. They do have player records in the exports, but no
game that started, so they are identified the way they were paid for: by the
lobby-timeout completion code on their Prolific submission. That also covers
overflow players Empirica turned away with "no more games", whose exit screen
shows the same code. A study whose players never reached a started game is not
found through the exports, so pass it with --study.

The output is one folder per study under data/payments/<dataset>/, named by the
study's creation date and internal name, with paste-ready files for Prolific's
bulk bonus box (`participant_id,amount`, no header) and a status.csv listing
everyone with what they were owed, what is already paid, and why a row is not
ready. The whole directory is rewritten on every run, so re-running after
paying on the website shows those people as settled. It pays nobody: payments
are made on the Prolific website, or with `prolific.py pay`.

Rules, the same as `prolific.py pay`: a finisher is owed their bonus; a removed
player their partial pay; a lobby-timeout participant LOBBY_TIMEOUT_PAY.
A partial or lobby amount is paid as a bonus on a RETURNED or AWAITING REVIEW
submission. An APPROVED one already received the full base reward, so only the
part of the amount above BASE_PAY is still owed (removed players who played
most of the game can be owed more than the base). What Prolific
records as paid in `bonus_payments` is subtracted, so a partly paid person is
owed only the rest. Players in games listed in data/<dataset>/exclude_games.txt
are left out. The files contain Prolific ids, which is why data/payments/ is
gitignored.

Overtime: when many games run at once the server slows down, and a game that
should take about 45 minutes can run 60 to 75, so the study takes well over the
"45 to 60 minutes" the instructions promise. A finisher whose submission took
longer than OVERTIME_AFTER_MINUTES is owed the minutes beyond it, paid at the
study's own advertised rate (reward / estimated minutes, $12 / 50 = $0.24 a
minute), counted in whole minutes. Counting from the threshold rather than from the study's estimate
avoids a cliff between just under and just over it. Prolific's `time_taken`
covers the whole submission, instructions and lobby included. Overtime goes out as a separate bonus file, overtime.csv; pay
bonus.csv first, because what Prolific records as paid is counted against the
performance bonus before the overtime.
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import prolific  # noqa: E402
from combine_runs import read_excluded_games  # noqa: E402

PROJECT_ROOT = prolific.PROJECT_ROOT
PAYMENTS_DIR = PROJECT_ROOT / "data" / "payments"
KINDS = ("bonus", "partial", "lobby", "overtime")
# Finishers are paid for the minutes their submission took beyond this, the top of
# the "45 to 60 minutes" the instructions promise.
OVERTIME_AFTER_MINUTES = 60
NO_STUDY = ""


@dataclass
class Payee:
    participant: str
    study_id: str
    kind: str  # bonus | partial | lobby
    amount: float
    game: str = ""
    batch: str = ""
    exit_reason: str = ""
    game_running: bool = False
    game_minutes: float = 0.0
    minutes_taken: float = 0.0
    status: str = ""
    already_paid: float = 0.0
    still_owed: float = 0.0
    ready: bool = False
    note: str = ""


@dataclass
class Study:
    study_id: str
    name: str = ""
    internal_name: str = ""
    created: str = ""
    estimated_minutes: int = 0
    reward: float = 0.0
    payees: list[Payee] = field(default_factory=list)

    @property
    def folder(self) -> str:
        if not self.study_id:
            return "no-study-id"
        label = re.sub(r"[^A-Za-z0-9]+", "-", self.internal_name or self.name or "study").strip("-").lower()
        return f"{self.created[:10] or 'undated'}_{label[:40]}_{self.study_id[-6:]}"


def _csv(z: zipfile.ZipFile, name: str) -> list[dict]:
    return list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8")))


def _float(value) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _minutes_between(start: str | None, end: str | None) -> float:
    """Minutes between two Empirica timestamps (ISO 8601, nanoseconds, trailing Z)."""
    try:
        t0 = datetime.fromisoformat((start or "")[:19])
        t1 = datetime.fromisoformat((end or "")[:19])
    except ValueError:
        return 0.0
    return round(max(0.0, (t1 - t0).total_seconds() / 60.0), 1)


def _export_stamp(path: Path) -> str:
    match = re.search(r"(\d{8}_\d{6})", path.name)
    return match.group(1) if match else path.name


def payees_from_exports(zips: list[Path], excluded_games: set[str] = frozenset()) -> dict[str, Payee]:
    """Everyone placed in a game, keyed by Prolific id.

    Exports are read oldest first and a later export replaces a person's row,
    because each export is a cumulative snapshot and the newest has their final
    state. Games that never started (lobby failures, stopped before start) have
    no players and contribute nothing.
    """
    payees: dict[str, Payee] = {}
    for path in sorted(zips, key=_export_stamp):
        with zipfile.ZipFile(path) as z:
            games = {g["id"]: g for g in _csv(z, "game.csv")}
            for p in _csv(z, "player.csv"):
                game_id = p.get("gameID") or ""
                game = games.get(game_id)
                if not game or game_id in excluded_games:
                    continue
                status = (game.get("status") or "").lower()
                if status not in ("ended", "running"):
                    continue
                pid = (p.get("participantIdentifier") or p.get("prolificPid") or "").strip()
                if not pid:
                    continue
                active = str(p.get("is_active")).strip().lower() == "true"
                payees[pid] = Payee(
                    participant=pid,
                    study_id=(p.get("studyId") or "").strip(),
                    kind="bonus" if active else "partial",
                    amount=_float(p.get("bonus")) if active else _float(p.get("partialPay")),
                    game=game_id,
                    batch=game.get("batchID") or "",
                    exit_reason=p.get("exitReason") or "",
                    game_running=status == "running",
                    game_minutes=_minutes_between(game.get("startLastChangedAt"), game.get("endedLastChangedAt"))
                    if status == "ended" else 0.0,
                )
    return payees


def group_by_study(payees: dict[str, Payee]) -> dict[str, Study]:
    studies: dict[str, Study] = {}
    for payee in payees.values():
        studies.setdefault(payee.study_id, Study(payee.study_id)).payees.append(payee)
    return studies


def overtime_payee(study: Study, payee: Payee, submission: dict | None,
                   overtime_after: float = OVERTIME_AFTER_MINUTES) -> Payee | None:
    """The overtime owed to a finisher, or None (see the module docstring)."""
    if payee.kind != "bonus" or payee.game_running:
        return None
    if not submission or not submission.get("time_taken") or not study.estimated_minutes or not study.reward:
        return None
    minutes = submission["time_taken"] / 60.0
    # Whole minutes, so someone a few seconds over is not sent a one-cent bonus.
    over = math.floor(minutes - overtime_after)
    if over <= 0:
        return None
    rate = study.reward / study.estimated_minutes
    return Payee(participant=payee.participant, study_id=study.study_id, kind="overtime",
                 amount=round(over * rate, 2), game=payee.game, batch=payee.batch,
                 game_minutes=payee.game_minutes, minutes_taken=round(minutes, 1))


def settle(study: Study, submissions: list[dict], game_payees: set[str],
           overtime_after: float = OVERTIME_AFTER_MINUTES) -> None:
    """Add the study's lobby timeouts and decide what each payee is still owed.

    `submissions` is the study's submission list from Prolific, which carries
    `status` and `bonus_payments` (paid bonuses, in cents); `game_payees` is
    everyone placed in a game, in any study, so that nobody is also counted as
    a lobby timeout.
    """
    by_participant = {s.get("participant_id"): s for s in submissions if s.get("participant_id")}
    for pid, sub in by_participant.items():
        if pid in game_payees or prolific.submission_code(sub) != prolific.LOBBY_TIMEOUT_CODE:
            continue
        study.payees.append(Payee(
            participant=pid, study_id=study.study_id, kind="lobby",
            amount=round(prolific.LOBBY_TIMEOUT_PAY, 2), exit_reason="lobby timeout",
        ))
    for payee in list(study.payees):
        overtime = overtime_payee(study, payee, by_participant.get(payee.participant), overtime_after)
        if overtime:
            study.payees.append(overtime)
    earned = {p.participant: p.amount for p in study.payees if p.kind == "bonus"}
    for payee in study.payees:
        sub = by_participant.get(payee.participant)
        if sub is None:
            payee.status, payee.note = "no submission", "no submission from this participant in this study"
            payee.still_owed = payee.amount
            continue
        payee.status = prolific.norm_status(sub.get("status"))
        paid = round(sum(sub.get("bonus_payments") or []) / 100.0, 2)
        if payee.kind == "bonus":
            # Bonuses already paid count against the performance bonus first,
            # and anything beyond it against the overtime.
            payee.already_paid = min(paid, payee.amount)
        elif payee.kind == "overtime":
            payee.already_paid = round(max(0.0, paid - earned.get(payee.participant, 0.0)), 2)
        else:
            payee.already_paid = paid
        payee.still_owed = round(max(0.0, payee.amount - payee.already_paid), 2)
        if payee.kind in ("partial", "lobby") and payee.status == "APPROVED":
            # Approval paid the full base reward, which covers a partial or lobby
            # amount up to BASE_PAY; only the part above it is still owed.
            payee.still_owed = round(max(0.0, payee.amount - prolific.BASE_PAY - payee.already_paid), 2)
            if payee.still_owed > 0:
                payee.ready = True
                payee.note = f"submission approved: the ${prolific.BASE_PAY:.2f} base was paid, so only the rest is owed"
            else:
                payee.note = f"submission approved: the ${prolific.BASE_PAY:.2f} base reward covers it"
        elif payee.game_running:
            payee.note = "game still running; the amount is not final"
        elif payee.still_owed <= 0:
            payee.note = "paid" if payee.amount > 0 else "nothing owed"
        else:
            payee.ready = True


def mark_unverified(study: Study) -> None:
    for payee in study.payees:
        payee.status = "not checked (--offline)"
        payee.still_owed = payee.amount
        payee.note = "not checked against Prolific; no paste files written"


def write_outputs(studies: dict[str, Study], out_dir: Path, offline: bool) -> list[dict]:
    """Rewrite out_dir with one folder per study and a summary; return the summary rows."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    generated = datetime.now().isoformat(timespec="seconds")
    summary = []
    for study in sorted(studies.values(), key=lambda s: (s.created, s.study_id)):
        folder = out_dir / study.folder
        folder.mkdir()
        with open(folder / "status.csv", "w", newline="") as f:
            columns = ["participant", "kind", "game", "batch", "exit_reason", "game_minutes",
                       "minutes_taken", "status", "amount", "already_paid", "still_owed", "ready", "note"]
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for p in sorted(study.payees, key=lambda p: (KINDS.index(p.kind), p.game, p.participant)):
                writer.writerow({c: getattr(p, c) for c in columns})
        row = {"study_id": study.study_id, "internal_name": study.internal_name, "name": study.name,
               "created": study.created, "folder": study.folder, "generated": generated,
               "games": " ".join(sorted({p.game[-6:] for p in study.payees if p.game}))}
        for kind in KINDS:
            ready = [p for p in study.payees if p.kind == kind and p.ready]
            row[f"{kind}_ready"] = len(ready)
            row[f"{kind}_amount"] = round(sum(p.still_owed for p in ready), 2)
            if ready and not offline:
                with open(folder / f"{kind}.csv", "w", newline="") as f:
                    for p in ready:
                        f.write(f"{p.participant},{p.still_owed:.2f}\n")
        row["not_ready"] = sum(1 for p in study.payees if not p.ready and p.still_owed > 0)
        summary.append(row)
    with open(out_dir / "summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()) if summary else ["study_id"])
        writer.writeheader()
        writer.writerows(summary)
    return summary


def print_summary(summary: list[dict], out_dir: Path, offline: bool) -> None:
    print(f"\nWrote {out_dir}/ (rewritten on every run)\n")
    for row in summary:
        title = row["internal_name"] or row["name"] or "(no study id recorded on these players)"
        print(f"{title}  [{row['study_id'] or '-'}]  games: {row['games'] or '-'}")
        owed = ", ".join(f"{k} {row[f'{k}_ready']} (${row[f'{k}_amount']:.2f})" for k in KINDS if row[f"{k}_ready"])
        print(f"    ready to pay: {owed or 'nothing'}" + (f"; {row['not_ready']} more owed but not ready (see status.csv)" if row["not_ready"] else ""))
        print(f"    folder: {row['folder']}/")
    if offline:
        print("\n--offline: nothing was checked against Prolific, so no paste files were written.")
    else:
        print("\nPaste each <kind>.csv into that study's bulk bonus on Prolific, then re-run to confirm.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("zips", nargs="+", type=Path, help="Empirica export zips (make payments passes runs.txt)")
    parser.add_argument("--dataset", required=True, help="Dataset name; output goes to data/payments/<dataset>/")
    parser.add_argument("--study", action="append", default=[], metavar="STUDY_ID",
                        help="Also check this Prolific study, for one where nobody reached a game "
                             "(no started game to find it through); repeatable")
    parser.add_argument("--overtime-after", type=float, default=OVERTIME_AFTER_MINUTES, metavar="MINUTES",
                        help=f"Finishers are paid for the minutes their submission took beyond this "
                             f"(default {OVERTIME_AFTER_MINUTES:g})")
    parser.add_argument("--offline", action="store_true",
                        help="Do not contact Prolific: list payees by study only, write no paste files")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    excluded = set(read_excluded_games(PROJECT_ROOT / "data" / args.dataset))
    payees = payees_from_exports(args.zips, excluded)
    if excluded:
        print(f"Leaving out players in {len(excluded)} excluded game(s) (data/{args.dataset}/exclude_games.txt).")
    studies = group_by_study(payees)
    for study_id in args.study:
        studies.setdefault(study_id, Study(study_id))
    if not args.offline:
        token = prolific.load_token()
        game_payees = set(payees)
        for study in studies.values():
            if study.study_id == NO_STUDY:
                for payee in study.payees:
                    payee.status, payee.note = "no study id", "no Prolific study recorded (local or test player?)"
                    payee.still_owed = payee.amount
                continue
            info = prolific.api("GET", f"/studies/{study.study_id}/", token) or {}
            study.name = info.get("name") or ""
            study.internal_name = info.get("internal_name") or ""
            study.created = (info.get("date_created") or "")[:19]
            study.estimated_minutes = int(info.get("estimated_completion_time") or 0)
            study.reward = round((info.get("reward") or 0) / 100.0, 2)
            settle(study, list(prolific.paged(f"/studies/{study.study_id}/submissions/", token)), game_payees,
                   args.overtime_after)
    else:
        for study in studies.values():
            mark_unverified(study)
    out_dir = PAYMENTS_DIR / args.dataset
    summary = write_outputs(studies, out_dir, args.offline)
    print_summary(summary, out_dir, args.offline)


if __name__ == "__main__":
    main()
