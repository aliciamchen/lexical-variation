"""What each Prolific study still owes, built from a dataset's exports.

    uv run python operations/payments.py --dataset full <zip> [<zip> ...]
    make payments DATASET=full          # the same, fed the zips in runs.txt

A session can span several Prolific studies and several Empirica batches, and
an export is a cumulative snapshot of the server, so no single export or batch
lines up with "the people one study owes". This step reads every export of the
dataset and takes each player placed in a game, identified by the Prolific id
they entered on the identifier screen (filled in from the study link's
PROLIFIC_PID when it has one). It asks Prolific, with read-only requests, for
the submissions of every study recorded on any player, and places each player
in the study where their Prolific id has a submission (assign_studies), which
also covers someone who reached the game without the study link's parameters
and so has no study id recorded. The submissions carry each one's status and
the bonuses already paid on it, and they add the lobby-timeout participants.
Those do have player records in the exports, but no game that started, so they
are identified the way they were paid for: by the lobby-timeout completion
code on their Prolific submission. That also covers overflow players Empirica
turned away with "no more games", whose exit screen shows the same code. A
study whose players never reached a started game is not found through the
exports, so pass it with --study.

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
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import prolific  # noqa: E402
from combine_runs import read_excluded_games  # noqa: E402

PROJECT_ROOT = prolific.PROJECT_ROOT
PAYMENTS_DIR = PROJECT_ROOT / "data" / "payments"
KINDS = ("bonus", "partial", "lobby", "overtime", "unsubmitted")
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
    joined_at: str = ""  # the game's start time, for matching a submission's time window
    site_minutes: float = 0.0  # identifier entered to exit survey submitted, from the game's own records
    study_source: str = ""  # "link" (studyId on the player) or "identifier" (found by Prolific id)
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


def payees_from_exports(zips: list[Path], excluded_games: set[str] = frozenset()) -> dict[tuple[str, str], Payee]:
    """Everyone placed in a game, keyed by (Prolific id, game id).

    The Prolific id is the identifier the participant entered, which the study
    link fills in when it carries PROLIFIC_PID. Keying by game as well keeps a
    person who took part in two sessions from overwriting one with the other.
    Exports are read oldest first and a later export replaces a row, because
    each export is a cumulative snapshot and the newest has the final state.
    Games that never started (lobby failures, stopped before start) have no
    players and contribute nothing.
    """
    payees: dict[tuple[str, str], Payee] = {}
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
                payees[(pid, game_id)] = Payee(
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
                    joined_at=game.get("startLastChangedAt") or "",
                    site_minutes=_minutes_between(p.get("participantIdentifierLastChangedAt"),
                                                  p.get("exitSurveyLastChangedAt"))
                    if p.get("exitSurvey") else 0.0,
                )
    return payees


def _when(value: str | None) -> datetime | None:
    """An ISO 8601 timestamp (Empirica's or Prolific's) as a naive UTC datetime."""
    try:
        return datetime.fromisoformat((value or "")[:19])
    except ValueError:
        return None


def assign_studies(payees: dict[tuple[str, str], Payee], submissions: dict[str, list[dict]]) -> None:
    """Decide which Prolific study pays each payee, using their Prolific id.

    The study id comes from the study link, and a participant who reaches the
    game without it (a bookmark, the browser history, a typed address) has
    none, although the identifier they entered is still their Prolific id. So
    each payee is matched to the studies where that id has a submission:

    1. the link's study, when it has a submission for them;
    2. otherwise the submission whose completion code fits the payee (the
       finished code for someone who finished, the partial code for someone
       removed), since that is where they claimed this game;
    3. otherwise the submission whose time window holds the game's start, a
       returned submission with no end being given three hours rather than
       treated as still open;
    4. otherwise a single match.

    Order matters: on 2026-09-25 a participant returned a batch 13 submission
    with the lobby code, then reached a batch 14 game through a bare link and
    only opened their batch 14 submission to enter the finished code, so the
    time window alone pointed at the wrong study. A payee with no match keeps
    whatever the link said and is reported as having no submission, so a
    mistyped id is shown rather than guessed.
    """
    by_participant: dict[str, list[tuple[str, dict]]] = {}
    for study_id, subs in submissions.items():
        for sub in subs:
            if sub.get("participant_id"):
                by_participant.setdefault(sub["participant_id"], []).append((study_id, sub))
    wanted = {"bonus": prolific.FINISHED_CODE, "partial": prolific.PARTIAL_CODE}
    for payee in payees.values():
        matches = by_participant.get(payee.participant, [])
        if payee.study_id and any(sid == payee.study_id for sid, _ in matches):
            payee.study_source = "link"
            continue
        chosen = None
        by_code = [sid for sid, sub in matches if prolific.submission_code(sub) == wanted.get(payee.kind)]
        if len(by_code) == 1:
            chosen = by_code[0]
        elif matches:
            joined = _when(payee.joined_at)
            covering = []
            for sid, sub in matches:
                start, end = _when(sub.get("started_at")), _when(sub.get("completed_at"))
                if start and end is None:
                    end = start + timedelta(hours=3)
                if joined and start and start <= joined <= end:
                    covering.append((start, sid))
            if covering:
                chosen = max(covering)[1]
            elif len(matches) == 1:
                chosen = matches[0][0]
        if chosen:
            payee.study_id, payee.study_source = chosen, "identifier"
        elif payee.study_id:
            payee.study_source = "link"


def group_by_study(payees: dict[tuple[str, str], Payee]) -> dict[str, Study]:
    studies: dict[str, Study] = {}
    for payee in payees.values():
        studies.setdefault(payee.study_id, Study(payee.study_id)).payees.append(payee)
    return studies


def overtime_payee(study: Study, payee: Payee, submission: dict | None,
                   overtime_after: float = OVERTIME_AFTER_MINUTES, rate: float | None = None) -> Payee | None:
    """The overtime owed to a finisher, or None (see the module docstring).

    Time on the study is the longer of Prolific's `time_taken` and the game's
    own record (identifier entered to exit survey submitted). The second is
    what counts for someone who played through a link sent by message and
    opened the study only to enter the code, whose `time_taken` is a minute.
    `rate` overrides the study's own reward per minute, for a payee paid
    through another study (a scheduling survey pays $0.30 for one minute).
    """
    if payee.kind not in ("bonus", "unsubmitted") or payee.game_running:
        return None
    if rate is None:
        if not study.estimated_minutes or not study.reward:
            return None
        rate = study.reward / study.estimated_minutes
    taken = (submission or {}).get("time_taken") or 0
    minutes = max(taken / 60.0, payee.site_minutes)
    if minutes <= 0:
        return None
    # Whole minutes, so someone a few seconds over is not sent a one-cent bonus.
    over = math.floor(minutes - overtime_after)
    if over <= 0:
        return None
    return Payee(participant=payee.participant, study_id=study.study_id, kind="overtime",
                 amount=round(over * rate, 2), game=payee.game, batch=payee.batch,
                 game_minutes=payee.game_minutes, minutes_taken=round(minutes, 1))


def place_unsubmitted(payees: dict[tuple[str, str], Payee], submissions: dict[str, list[dict]]) -> None:
    """Pay a player who never submitted the game study through another study.

    Some participants play through a link sent by message (Prolific shows a
    study to some people late) and never open the study to enter the code, so
    they have no game-study submission to approve. Their only submission is
    in another study, usually the session's scheduling survey, so the base pay
    and bonus go out as a bonus there. A finisher is owed BASE_PAY plus the
    bonus; a removed player their partial pay, which already includes the
    prorated base. The latest submission that started before the game is used.
    """
    for payee in payees.values():
        if payee.study_id:
            continue
        joined = _when(payee.joined_at)
        found = []
        for sid, subs in submissions.items():
            for sub in subs:
                if sub.get("participant_id") != payee.participant:
                    continue
                start = _when(sub.get("started_at"))
                if joined is None or start is None or start <= joined:
                    found.append((start or datetime.min, sid))
        if not found:
            continue
        payee.study_id, payee.study_source = max(found)[1], "unsubmitted"
        if payee.kind == "bonus":
            payee.amount = round(prolific.BASE_PAY + payee.amount, 2)
        payee.kind = "unsubmitted"


def settle(study: Study, submissions: list[dict], game_payees: set[str],
           overtime_after: float = OVERTIME_AFTER_MINUTES, game_rate: float | None = None) -> None:
    """Add the study's lobby timeouts and decide what each payee is still owed.

    `submissions` is the study's submission list from Prolific, which carries
    `status` and `bonus_payments` (paid bonuses, in cents); `game_payees` is
    everyone who played a game in this study, so that nobody is also counted as
    one of its lobby timeouts. It is per study because the same person can wait
    out a lobby in one session and play in the next.
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
        rate = game_rate if payee.kind == "unsubmitted" else None
        overtime = overtime_payee(study, payee, by_participant.get(payee.participant), overtime_after, rate)
        if overtime:
            study.payees.append(overtime)
    earned = {p.participant: p.amount for p in study.payees if p.kind in ("bonus", "unsubmitted")}
    for payee in study.payees:
        sub = by_participant.get(payee.participant)
        if sub is None:
            payee.status, payee.note = "no submission", "no submission from this participant in this study"
            payee.still_owed = payee.amount
            continue
        payee.status = prolific.norm_status(sub.get("status"))
        paid = round(sum(sub.get("bonus_payments") or []) / 100.0, 2)
        if payee.kind in ("bonus", "unsubmitted"):
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
            columns = ["participant", "kind", "game", "batch", "exit_reason", "study_source", "game_minutes",
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
        # Every study seen on a player, or passed with --study, is a candidate;
        # its submissions let a player without a study id be placed by their
        # Prolific id (assign_studies).
        candidates = sorted({p.study_id for p in payees.values() if p.study_id} | set(args.study))
        submissions = {sid: list(prolific.paged(f"/studies/{sid}/submissions/", token)) for sid in candidates}
        assign_studies(payees, submissions)
        game_rate = next((round(s["reward"] / 100.0 / s["estimated_completion_time"], 4) for s in
                          (prolific.api("GET", f"/studies/{sid}/", token) or {} for sid in candidates[-1:])
                          if s.get("reward") and s.get("estimated_completion_time")), None)
        if any(not p.study_id for p in payees.values()):
            # Players with no game-study submission: look through the other
            # recent studies (the scheduling surveys) for somewhere to pay them.
            first = min((_when(p.joined_at) for p in payees.values() if _when(p.joined_at)), default=None)
            others = [s["id"] for s in prolific.paged("/studies/", token)
                      if s["id"] not in submissions and first and _when(s.get("date_created"))
                      and _when(s.get("date_created")) >= first - timedelta(days=2)]
            for sid in dict.fromkeys(others):
                submissions[sid] = list(prolific.paged(f"/studies/{sid}/submissions/", token))
            place_unsubmitted(payees, submissions)
            candidates = sorted(set(candidates) | {p.study_id for p in payees.values() if p.study_id})
        studies = group_by_study(payees)
        for study_id in candidates:
            studies.setdefault(study_id, Study(study_id))
        for study in studies.values():
            if study.study_id == NO_STUDY:
                for payee in study.payees:
                    payee.status = "no study id"
                    payee.note = ("no submission with this Prolific id in any candidate study "
                                  "(a mistyped identifier, or a local or test player?)")
                    payee.still_owed = payee.amount
                continue
            info = prolific.api("GET", f"/studies/{study.study_id}/", token) or {}
            study.name = info.get("name") or ""
            study.internal_name = info.get("internal_name") or ""
            study.created = (info.get("date_created") or "")[:19]
            study.estimated_minutes = int(info.get("estimated_completion_time") or 0)
            study.reward = round((info.get("reward") or 0) / 100.0, 2)
            in_study = {p.participant for p in study.payees}
            settle(study, submissions[study.study_id], in_study, args.overtime_after, game_rate)
    else:
        for study in studies.values():
            mark_unverified(study)
    out_dir = PAYMENTS_DIR / args.dataset
    summary = write_outputs(studies, out_dir, args.offline)
    print_summary(summary, out_dir, args.offline)


if __name__ == "__main__":
    main()
