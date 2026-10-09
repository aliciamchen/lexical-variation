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
are identified mainly the way they were told to claim their pay: by the
lobby-timeout completion code on their Prolific submission, which also covers
overflow players Empirica turned away with "no more games", whose exit screen
shows the same code. Someone who returned the study without entering that code
is found from the export instead (visits_without_a_game), and someone who
reached the lobby through a link sent by message, with no submission in the
session's study at all, is paid through their latest earlier submission,
normally the scheduling survey (assign_waiters). A study in
which nobody reached a started game is found through those lobby records when
the study link recorded it, or through a submission bearing the lobby code
among the recent studies; otherwise pass it with --study.

The output is one folder per study under data/payments/<dataset>/, named by the
study's creation date and internal name, with paste-ready files for Prolific's
bulk bonus box (`participant_id,amount`, no header, one line per person):
1_main.csv (performance bonuses, partial pay, lobby pay, and players paid
through this study because they never submitted the game study) and
2_overtime.csv, to be pasted in that order. status.csv lists everyone with
what they were owed, what is already paid, and why a row is not ready, and
repeats.csv lists anyone who took part in more than one session. The whole
directory is rewritten on every run, so re-running after paying on the website
shows those people as settled. It pays nobody: payments are made by hand on
the Prolific website.

Rules: a finisher is owed their bonus, plus the BASE_PAY reward when they
returned their submission (a returned submission cannot be approved); a
removed player their partial pay; a lobby-timeout participant
LOBBY_TIMEOUT_PAY. A partial or lobby amount is paid as a bonus on a RETURNED
or AWAITING REVIEW submission. An APPROVED game-study submission already received the full base
reward, so only the part of the amount above BASE_PAY is still owed (removed players who played
most of the game can be owed more than the base). What Prolific
records as paid in `bonus_payments` is subtracted, so a partly paid person is
owed only the rest; when one submission carries several of a person's rows, the
payment counts against their game pay first, then partial or lobby pay, then
overtime. Players in games listed in data/<dataset>/exclude_games.txt
are paid like everyone else: excluding a game from the analysis, as for a
game with a repeat participant, changes nothing about what its players are
owed, and they stay on the blocklist and in the repeat check. The files
contain Prolific ids, which is why data/payments/ is gitignored.

Overtime: when many games run at once the server slows down, and a game that
should take about 45 minutes can run 60 to 75, so the study takes well over the
"45 to 60 minutes" the instructions promise. A finisher whose submission took
longer than OVERTIME_AFTER_MINUTES is owed the minutes beyond it, paid at the
study's own advertised rate (reward / estimated minutes, $12 / 50 = $0.24 a
minute), counted in whole minutes. Counting from the threshold rather than from the study's estimate
avoids a cliff between just under and just over it. Prolific's `time_taken`
covers the whole submission, instructions and lobby included. Overtime goes out as a separate paste file, 2_overtime.csv;
paste 1_main.csv first, because what Prolific records as paid is counted
against the performance bonus before the overtime.

Repeat participants: one Prolific id placed in two started games means
someone played twice, which eligibility should have prevented, and is printed
as a warning. Someone who took part in a pilot session (experiment/pilot_data/)
and then played is listed as well; pilot participants are blocklisted, so a new
one means the list had not reached the survey. Someone who waited out a lobby
in one session and played in a later one is allowed (lobby timeouts stay
eligible) and is listed for information.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prolific  # noqa: E402

PROJECT_ROOT = prolific.PROJECT_ROOT
PAYMENTS_DIR = PROJECT_ROOT / "data" / "payments"
KINDS = ("bonus", "partial", "lobby", "overtime", "unsubmitted")
# Finishers are paid for the minutes their submission took beyond this, the top of
# the "45 to 60 minutes" the instructions promise.
OVERTIME_AFTER_MINUTES = 60
NO_STUDY = ""
MAX_QUIZ_ATTEMPTS = prolific.GAME["max_quiz_attempts"]
# The condition whose instructions and quiz describe Phase 2 (the social guessing
# task and its reward) before the game starts. Anyone assigned to one of its games
# has seen them, so they are blocked even without a started game; the other three
# conditions share instructions that social-first only adds to.
SOCIAL_FIRST = "social_first"
assert SOCIAL_FIRST in prolific.CONDITIONS, "SOCIAL_FIRST must name a condition in experiment/shared/constants.js"
# The raw exports of the pilot sessions (March 2025 to September 2026), which ran
# before the full sample on servers of their own. Everyone who took part in one is
# blocked too (pilot_participants).
PILOT_EXPORTS = PROJECT_ROOT / "experiment" / "pilot_data"
PROLIFIC_ID = re.compile(r"[0-9a-f]{24}")
# The paste files, in the order they are pasted, and the kinds each one holds.
PASTE_FILES = (("1_main.csv", ("bonus", "partial", "lobby", "unsubmitted")), ("2_overtime.csv", ("overtime",)))
# The order in which what Prolific records as paid on a submission is counted
# against one person's rows: their game pay first, then partial or lobby pay, then
# overtime, which is pasted last.
PAID_ORDER = {"bonus": 0, "unsubmitted": 0, "partial": 1, "lobby": 1, "overtime": 2}
# Prolific approves a submission left awaiting review this long after it was
# submitted, which pays a removed player or lobby timeout the full base reward.
AUTO_APPROVAL = timedelta(days=21)
# A lobby wait counts as an earlier session when it began at least this long
# before the game the same person played; a reload in the same session is closer.
RETURN_GAP = timedelta(minutes=30)
# A submission started this long after a game ended is not where that game was claimed.
LATE_SUBMISSION = timedelta(hours=1)
# Per-player corrections the author decides on, in data/<dataset>/. Keyed by
# the Empirica player id (as in players.csv), never a Prolific id.
ADJUSTMENTS_FILE = "payment_adjustments.csv"
ADJUSTMENTS = ("restore_bonus",)


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
    submitted_at: str = ""  # when the Prolific submission was completed
    player_id: str = ""  # the Empirica player id, which payment_adjustments.csv names
    earned_bonus: float = 0.0  # the performance bonus the player had earned, forfeited or not
    base_partial: float = 0.0  # the prorated base pay of a removed player
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


@dataclass
class Visit:
    """A player record that never reached a started game."""
    participant: str
    study_id: str
    entered_at: str  # when they entered their identifier
    ended: str
    waited: bool = False  # waited in the lobby for a game that never started; owed lobby pay
    quiz_failed: bool = False
    condition: str = ""  # of the game they were assigned to, which set the instructions and quiz they saw


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


def payees_from_exports(zips: list[Path]) -> dict[tuple[str, str], Payee]:
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
                if not game:
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
                    player_id=p.get("id") or "",
                    earned_bonus=_float(p.get("bonus")),
                    base_partial=_float(p.get("partialBasePay")),
                )
    return payees


def read_adjustments(data_dir: Path) -> dict[str, tuple[str, str]]:
    """{player id: (adjustment, reason)} from data/<dataset>/payment_adjustments.csv.

    The file is optional and holds the author's per-player decisions, one row
    each with columns playerId, adjustment, reason. `restore_bonus` pays a
    removed player their prorated base plus the bonus they had earned, for a
    removal that was not really theirs to answer for (a removal for inactivity
    forfeits the bonus otherwise). An unknown adjustment is an error rather
    than a silent no-op, and every row needs a reason.
    """
    path = data_dir / ADJUSTMENTS_FILE
    if not path.exists():
        return {}
    adjustments = {}
    with open(path, newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            player = (row.get("playerId") or "").strip()
            kind = (row.get("adjustment") or "").strip()
            reason = (row.get("reason") or "").strip()
            if not player:
                continue
            if kind not in ADJUSTMENTS:
                raise ValueError(f"{path.name} line {i}: unknown adjustment {kind!r} (expected one of {ADJUSTMENTS})")
            if not reason:
                raise ValueError(f"{path.name} line {i}: every adjustment needs a reason")
            adjustments[player] = (kind, reason)
    return adjustments


def apply_adjustments(payees: dict[tuple[str, str], Payee], adjustments: dict[str, tuple[str, str]]) -> list[str]:
    """Apply the author's adjustments to the payees; return the player ids that matched nobody."""
    by_player = {p.player_id: p for p in payees.values() if p.player_id}
    unmatched = []
    for player, (kind, reason) in adjustments.items():
        payee = by_player.get(player)
        if payee is None:
            unmatched.append(player)
            continue
        if kind == "restore_bonus" and payee.kind == "partial":
            restored = round(payee.base_partial + payee.earned_bonus, 2)
            if restored > payee.amount:
                payee.amount = restored
                payee.exit_reason = "; ".join(filter(None, [payee.exit_reason, f"bonus restored: {reason}"]))
    return unmatched


def _true(value) -> bool:
    return str(value or "").strip().lower() in ("true", "1", "yes")


def _condition(treatment: str | None) -> str:
    """The condition in a player's `treatment`, which Empirica copies from the game it assigns them to."""
    try:
        value = json.loads(treatment or "{}")
    except json.JSONDecodeError:
        return ""
    return str(value.get("condition") or "") if isinstance(value, dict) else ""


def visits_without_a_game(zips: list[Path]) -> dict[str, list[Visit]]:
    """Every player record that never reached a started game, by Prolific id.

    `waited` marks the ones owed lobby pay: a player whose game failed while
    they were in the lobby (intro and quiz done, then the lobby timer ran out),
    or whom Empirica turned away with "no more games" after the game they were
    assigned to filled. Both see the lobby-timeout screen. Quiz failures and
    people still in the instructions when the game failed never reached the
    lobby. Records are keyed by player id, so a later export replaces an
    earlier snapshot of the same record.

    `condition` is that of the game the player was assigned to. Empirica
    assigns a game as soon as a participant arrives and shows the
    instructions and quiz of its treatment, and it keeps the player's
    `treatment` when it later turns them away with "no more games", so an
    overflow player has seen those instructions too, often only in part.
    """
    records: dict[str, Visit] = {}
    for path in sorted(zips, key=_export_stamp):
        with zipfile.ZipFile(path) as z:
            games = {g["id"]: g for g in _csv(z, "game.csv")}
            for p in _csv(z, "player.csv"):
                pid = (p.get("participantIdentifier") or p.get("prolificPid") or "").strip()
                game_id = p.get("gameID") or ""
                key = p.get("id") or f"{pid}:{game_id}"
                if not pid:
                    continue
                if ((games.get(game_id) or {}).get("status") or "").lower() in ("ended", "running"):
                    records.pop(key, None)
                    continue
                ended = (p.get("ended") or "").strip()
                intro_done = _true(p.get("introDone"))
                try:
                    attempts = int(float(p.get("quiz_attempts") or 0))
                except ValueError:
                    attempts = 0
                quiz_failed = not intro_done and attempts >= MAX_QUIZ_ATTEMPTS
                waited = (ended == "game failed" and intro_done) or (ended == "no more games" and not quiz_failed)
                records[key] = Visit(pid, (p.get("studyId") or "").strip(),
                                     p.get("participantIdentifierLastChangedAt") or "", ended, waited, quiz_failed,
                                     _condition(p.get("treatment")))
    visits: dict[str, list[Visit]] = {}
    for visit in records.values():
        visits.setdefault(visit.participant, []).append(visit)
    return visits


def pilot_participants(root: Path = PILOT_EXPORTS) -> set[str]:
    """Everyone who took part in a pilot session, by Prolific id: placed in a started game or failed the quiz.

    The pilot exports under `root` are read like the dataset's: export zips,
    and for the March 2025 pilot, of which only the server's tajriba.json was
    kept, that file. As in the full sample, pilot lobby timeouts stay
    eligible. Identifiers that are not Prolific ids, the test logins of the
    early pilots, are left out.
    """
    zips = sorted(root.rglob("*.zip"))
    found = {p.participant for p in payees_from_exports(zips).values()}
    found |= {pid for pid, vs in visits_without_a_game(zips).items() if any(v.quiz_failed for v in vs)}
    for path in sorted(root.rglob("tajriba.json")):
        found |= _tajriba_players(path)
    return {pid.lower() for pid in found if PROLIFIC_ID.fullmatch(pid.lower())}


def _tajriba_players(path: Path) -> set[str]:
    """The identifiers of the players placed in a started game, from a raw tajriba.json.

    The file is Empirica's event log, one JSON record per line, in the order
    the events happened. An attribute record names the scope it belongs to
    (`nodeID`): a player's scope carries `participantIdentifier` and
    `gameID`, and a game's scope gets `start` = true when the game starts.
    """
    identifier, game_of, started = {}, {}, set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if record.get("kind") != "Attribute":
                continue
            attr = record.get("obj") or {}
            key, node, value = attr.get("key"), attr.get("nodeID"), attr.get("val") or ""
            if key == "participantIdentifier":
                identifier[node] = str(json.loads(value) or "").strip()
            elif key == "gameID":
                game_of[node] = json.loads(value) if value else ""
            elif key == "start" and value == "true":
                started.add(node)
    return {pid for node, pid in identifier.items() if pid and game_of.get(node) in started}


def lobby_waiters(visits: dict[str, list[Visit]]) -> dict[str, list[Visit]]:
    """The visits that are owed lobby pay, by Prolific id."""
    waiters = {pid: [v for v in vs if v.waited] for pid, vs in visits.items()}
    return {pid: vs for pid, vs in waiters.items() if vs}


def repeat_participants(payees: dict[tuple[str, str], Payee], visits: dict[str, list[Visit]],
                        pilot: set[str] = frozenset()) -> list[dict]:
    """People who took part in more than one session.

    "played twice": one Prolific id placed in two started games, which
    eligibility should have prevented. "took part in a pilot, then played":
    someone in `pilot` (pilot_participants) who played in this dataset;
    pilot participants are blocklisted, so this too means the list had not
    reached the survey. Otherwise a visit without a game at
    least RETURN_GAP before the game the person played means they came back:
    "quiz failed earlier, then played" (quiz failures are blocklisted, so this
    means one came back before the list reached the survey), "saw the
    social-first instructions earlier, then played" (blocklisted for the same
    reason) or "earlier visit without a game, then played" (a lobby timeout or
    overflow player outside social-first, who stays eligible on purpose).
    """
    games_by: dict[str, list[Payee]] = {}
    for (pid, _), payee in payees.items():
        games_by.setdefault(pid, []).append(payee)
    rows = []
    for pid, played in sorted(games_by.items()):
        if len(played) > 1:
            rows.append({"participant": pid, "kind": "played twice",
                         "games": " ".join(sorted(p.game[-6:] for p in played))})
            continue
        if pid.lower() in pilot:
            rows.append({"participant": pid, "kind": "took part in a pilot, then played", "games": played[0].game[-6:]})
            continue
        start = _when(played[0].joined_at)
        earlier = [v for v in visits.get(pid, []) if start and _when(v.entered_at)
                   and _when(v.entered_at) <= start - RETURN_GAP]
        if earlier:
            if any(v.quiz_failed for v in earlier):
                kind = "quiz failed earlier, then played"
            elif any(v.condition == SOCIAL_FIRST for v in earlier):
                kind = "saw the social-first instructions earlier, then played"
            else:
                kind = "earlier visit without a game, then played"
            rows.append({"participant": pid, "kind": kind, "games": played[0].game[-6:]})
    return rows


def _when(value: str | None) -> datetime | None:
    """An ISO 8601 timestamp (Empirica's or Prolific's) as a naive UTC datetime."""
    try:
        return datetime.fromisoformat((value or "")[:19])
    except ValueError:
        return None


def _submission_window(sub: dict) -> tuple[datetime | None, datetime | None]:
    """When a submission was open; a returned one with no end is given three hours rather than left open."""
    start, end = _when(sub.get("started_at")), _when(sub.get("completed_at"))
    if start and end is None:
        end = start + timedelta(hours=3)
    return start, end


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
    4. otherwise a single match, unless that submission closed before the
       game started (with the same three hours for a returned one without
       an end): a game cannot be claimed on a submission that was already
       over. On 2026-10-08 five players reached the last session through a
       bare link and never opened its game study, and the only game-study
       submission each had was a lobby wait returned in an earlier session,
       which must keep paying that wait. Such a player falls to
       place_unsubmitted, which pays them through the session's scheduling
       survey.

    Submissions that started more than LATE_SUBMISSION after the game ended
    are left out first: they belong to a later game by the same person.

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
        # A submission opened long after this game ended belongs to a later
        # session (someone who played twice), so it cannot be where this game
        # was claimed; the game then falls to place_unsubmitted.
        joined = _when(payee.joined_at)
        game_end = joined + timedelta(minutes=payee.game_minutes) if joined and payee.game_minutes else None
        matches = [(sid, sub) for sid, sub in by_participant.get(payee.participant, [])
                   if not (game_end and _when(sub.get("started_at"))
                           and _when(sub.get("started_at")) > game_end + LATE_SUBMISSION)]
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
                start, end = _submission_window(sub)
                if joined and start and start <= joined <= end:
                    covering.append((start, sid))
            if covering:
                chosen = max(covering)[1]
            elif len(matches) == 1:
                end = _submission_window(matches[0][1])[1]
                if not (joined and end and end < joined):
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


def _waited_in(waiter: Visit, study_id: str, submission: dict) -> bool:
    """Whether a lobby record belongs to this study's submission: the link recorded
    the study, or the identifier was entered while the submission was open."""
    if waiter.study_id and waiter.study_id == study_id:
        return True
    entered, start = _when(waiter.entered_at), _when(submission.get("started_at"))
    if not entered or not start:
        return False
    end = _when(submission.get("completed_at")) or start + timedelta(hours=3)
    return start - timedelta(minutes=10) <= entered <= end


def assign_waiters(studies: dict[str, Study], payees: dict[tuple[str, str], Payee],
                   submissions: dict[str, list[dict]], waiters: dict[str, list[Visit]],
                   game_studies: set[str]) -> dict[str, dict[str, list[Visit]]]:
    """Decide where each lobby wait is paid; return the waits settle is to pay, by study.

    One person's records within RETURN_GAP of each other are one wait (a
    reload), and a wait followed within RETURN_GAP by a game the same person
    played is paid with that game. settle pays one wait for every submission
    that bears the lobby code, wherever the person typed it, so each such
    submission accounts for the person's wait nearest to it in time, and its
    study is added to `studies` when missing, since settle sees only those. A
    remaining wait belongs to the game study the link recorded or whose
    submission was open when they entered the lobby (_waited_in), the latest
    of these when there are several, so that it is paid once. Someone who
    reached the lobby through a link sent by message, because Prolific showed
    them the session's study late, has no such submission: their
    scheduling-survey submission closed hours before. Their wait is paid
    here, through the latest submission that started before it, as
    place_unsubmitted does for players, or listed under NO_STUDY when there is
    none.
    """
    joined: dict[str, list[datetime]] = {}
    for (pid, _), payee in payees.items():
        if _when(payee.joined_at):
            joined.setdefault(pid, []).append(_when(payee.joined_at))
    own: dict[str, list[tuple[str, dict]]] = {}
    for sid, subs in submissions.items():
        for sub in subs:
            if sub.get("participant_id"):
                own.setdefault(sub["participant_id"], []).append((sid, sub))
    assigned: dict[str, dict[str, list[Visit]]] = {}
    for pid, visits in waiters.items():
        waits: list[Visit] = []
        for visit in sorted(visits, key=lambda v: v.entered_at):
            entered = _when(visit.entered_at)
            previous = _when(waits[-1].entered_at) if waits else None
            if entered and previous and entered - previous < RETURN_GAP:
                continue
            if entered and any(timedelta(0) <= start - entered < RETURN_GAP for start in joined.get(pid, [])):
                continue
            waits.append(visit)
        for sid, sub in own.get(pid, []):
            played_there = any(p.participant == pid and p.kind != "lobby" for p in studies.get(sid, Study(sid)).payees)
            if prolific.submission_code(sub) != prolific.LOBBY_TIMEOUT_CODE or played_there:
                continue
            studies.setdefault(sid, Study(sid))
            at = _when(sub.get("completed_at")) or _when(sub.get("started_at"))
            if waits:
                waits.remove(min(waits, key=lambda v: abs((_when(v.entered_at) - at).total_seconds())
                                 if at and _when(v.entered_at) else 0))
        for visit in waits:
            claiming = [(sid, sub) for sid, sub in own.get(pid, [])
                        if sid in game_studies and _waited_in(visit, sid, sub)]
            if claiming:
                sid = max(claiming, key=lambda c: (c[0] == visit.study_id, _when(c[1].get("started_at")) or datetime.min))[0]
                studies.setdefault(sid, Study(sid))
                assigned.setdefault(sid, {}).setdefault(pid, []).append(visit)
                continue
            entered = _when(visit.entered_at)
            if entered is None:
                continue
            earlier = [(_when(sub.get("started_at")), sid) for sid, sub in own.get(pid, [])
                       if _when(sub.get("started_at")) and _when(sub.get("started_at")) <= entered]
            sid = max(earlier)[1] if earlier else NO_STUDY
            reason = "lobby timeout" if visit.ended == "game failed" else "no more games"
            studies.setdefault(sid, Study(sid)).payees.append(Payee(
                participant=pid, study_id=sid, kind="lobby", amount=round(prolific.LOBBY_TIMEOUT_PAY, 2),
                exit_reason=f"{reason} (no submission in the session's study)", study_source="unsubmitted",
            ))
    return assigned


def settle(study: Study, submissions: list[dict], game_payees: set[str],
           overtime_after: float = OVERTIME_AFTER_MINUTES, game_rate: float | None = None,
           waiters: dict[str, list[Visit]] | None = None, game_study: bool = True) -> None:
    """Add the study's lobby timeouts and decide what each payee is still owed.

    `submissions` is the study's submission list from Prolific, which carries
    `status` and `bonus_payments` (paid bonuses, in cents); `game_payees` is
    everyone who played a game in this study, so that nobody is also counted as
    one of its lobby timeouts. It is per study because the same person can wait
    out a lobby in one session and play in the next. `waiters` (the waits
    assign_waiters gave this study) finds lobby timeouts who returned the study
    without entering the lobby code. `game_study` is false for a study that is
    not a session's game study, such as a scheduling survey someone typed the
    lobby code into, whose approval paid only its own reward.
    """
    by_participant = {s.get("participant_id"): s for s in submissions if s.get("participant_id")}
    for pid, sub in by_participant.items():
        if pid in game_payees:
            continue
        if prolific.submission_code(sub) == prolific.LOBBY_TIMEOUT_CODE:
            reason = "lobby timeout"
        else:
            waited = [w for w in (waiters or {}).get(pid, []) if _waited_in(w, study.study_id, sub)]
            if not waited:
                continue
            reason = f"{'lobby timeout' if waited[0].ended == 'game failed' else 'no more games'} (no code entered)"
        study.payees.append(Payee(
            participant=pid, study_id=study.study_id, kind="lobby",
            amount=round(prolific.LOBBY_TIMEOUT_PAY, 2), exit_reason=reason,
            study_source="" if game_study else "unsubmitted",
        ))
    for payee in study.payees:
        sub = by_participant.get(payee.participant)
        if payee.kind == "bonus" and sub and prolific.norm_status(sub.get("status")) == "RETURNED":
            # A returned submission cannot be approved, so the base reward goes out
            # as a bonus alongside the performance bonus.
            payee.amount = round(prolific.BASE_PAY + payee.amount, 2)
            payee.exit_reason = "; ".join(filter(None, [payee.exit_reason, "submission returned: base paid as bonus"]))
    for payee in list(study.payees):
        rate = game_rate if payee.kind == "unsubmitted" else None
        overtime = overtime_payee(study, payee, by_participant.get(payee.participant), overtime_after, rate)
        if overtime:
            study.payees.append(overtime)
    # Bonuses already paid on the submission are counted against the person's
    # rows in PAID_ORDER, so a lobby payment beside game pay on one survey
    # submission is not taken as paid when only the game pay was.
    unclaimed: dict[str, float] = {}
    for payee in sorted(study.payees, key=lambda p: PAID_ORDER[p.kind]):
        sub = by_participant.get(payee.participant)
        if sub is None:
            payee.status, payee.note = "no submission", "no submission from this participant in this study"
            payee.still_owed = payee.amount
            continue
        payee.status = prolific.norm_status(sub.get("status"))
        payee.submitted_at = (sub.get("completed_at") or "")[:19]
        paid = unclaimed.setdefault(payee.participant, round(sum(sub.get("bonus_payments") or []) / 100.0, 2))
        payee.already_paid = round(min(paid, payee.amount), 2)
        unclaimed[payee.participant] = round(paid - payee.already_paid, 2)
        payee.still_owed = round(max(0.0, payee.amount - payee.already_paid), 2)
        if payee.kind in ("partial", "lobby") and payee.status == "APPROVED" and payee.study_source != "unsubmitted":
            # Approval paid the full base reward, which covers a partial or lobby
            # amount up to BASE_PAY; only the part above it is still owed. A wait
            # paid through another study (a scheduling survey) got only that
            # study's reward.
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
                       "minutes_taken", "status", "submitted_at", "amount", "already_paid", "still_owed", "ready", "note"]
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
        for filename, kinds in PASTE_FILES:
            # One line per person: Prolific's bulk bonus takes each participant once.
            owed: dict[str, float] = {}
            for p in study.payees:
                if p.kind in kinds and p.ready:
                    owed[p.participant] = round(owed.get(p.participant, 0.0) + p.still_owed, 2)
            if owed and not offline:
                with open(folder / filename, "w", newline="") as f:
                    for participant, amount in owed.items():
                        f.write(f"{participant},{amount:.2f}\n")
        row["not_ready"] = sum(1 for p in study.payees if not p.ready and p.still_owed > 0)
        # Removed players and lobby timeouts must return their submission; one
        # still awaiting review is approved by Prolific at AUTO_APPROVAL.
        waiting = [p for p in study.payees if p.kind in ("partial", "lobby") and p.status == "AWAITING REVIEW"
                   and p.study_source != "unsubmitted"]
        row["awaiting_return"] = len(waiting)
        dates = [_when(p.submitted_at) for p in waiting if _when(p.submitted_at)]
        row["auto_approval"] = (min(dates) + AUTO_APPROVAL).date().isoformat() if dates else ""
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
        if row["awaiting_return"]:
            print(f"    {row['awaiting_return']} partial or lobby submission(s) still awaiting review: ask them to return it; "
                  f"Prolific approves them" + (f" from {row['auto_approval']}" if row["auto_approval"] else " after 21 days"))
        print(f"    folder: {row['folder']}/")
    if offline:
        print("\n--offline: nothing was checked against Prolific, so no paste files were written.")
    else:
        print("\nIn each study's bulk bonus on Prolific, paste 1_main.csv, then 2_overtime.csv; re-run to confirm.")


def write_blocklist(payees: dict[tuple[str, str], Payee], out_dir: Path,
                    visits: dict[str, list[Visit]] | None = None,
                    submissions: dict[str, list[dict]] | None = None, pilot: set[str] = frozenset()) -> int:
    """blocklist_ids.txt: everyone the scheduling surveys must keep out, for the participant group they block.

    Nobody who has started the task may sign up again. Lobby timeouts and
    overflow players ("no more games") never started it and stay eligible,
    except in social-first: its instructions and quiz explain Phase 2 before
    the game, so someone who has seen them must not be shown another
    condition's instructions later, while someone who saw another condition's
    may be assigned to social-first and simply read more. Prolific's "exclude
    participants from other studies" filter cannot draw that line: it
    excludes every submission in the listed studies, returned ones included.
    The survey therefore blocks the participant group that sync_blocklist.py
    fills from this list instead, and the list has to be complete on its own:
    every Prolific id placed in a started game, every quiz failure, everyone
    assigned to a social-first game that never started for them (lobby
    timeouts, overflow players, people who left during the instructions),
    every submission in a fetched study that carries the finished or
    partial code, which catches a player whose identifier was mistyped and so
    matches no export record, and everyone in `pilot`, who took part in a
    pilot session (pilot_participants).
    """
    played = {p.participant for p in payees.values()}
    quiz_failed = {pid for pid, vs in (visits or {}).items() if any(v.quiz_failed for v in vs)}
    saw_social_first = {pid for pid, vs in (visits or {}).items() if any(v.condition == SOCIAL_FIRST for v in vs)}
    by_code = {sub.get("participant_id") for subs in (submissions or {}).values() for sub in subs
               if prolific.submission_code(sub) in (prolific.FINISHED_CODE, prolific.PARTIAL_CODE)}
    blocked = sorted((played | quiz_failed | saw_social_first | by_code | set(pilot)) - {None, ""})
    (out_dir / "blocklist_ids.txt").write_text("".join(f"{pid}\n" for pid in blocked))
    return len(blocked)


def write_repeats(rows: list[dict], out_dir: Path) -> None:
    """repeats.csv (with Prolific ids, so only on disk) and a summary without them."""
    with open(out_dir / "repeats.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["participant", "kind", "games"])
        writer.writeheader()
        writer.writerows(rows)
    twice = [r for r in rows if r["kind"] == "played twice"]
    if twice:
        print(f"\nWARNING: {len(twice)} participant(s) placed in more than one started game "
              f"(games {'; '.join(r['games'] for r in twice)}); see repeats.csv.")
    else:
        print("\nRepeat participants: nobody was placed in more than one started game.")
    for kind in ("took part in a pilot, then played", "quiz failed earlier, then played",
                 "saw the social-first instructions earlier, then played", "earlier visit without a game, then played"):
        games = [r["games"] for r in rows if r["kind"] == kind]
        if games:
            print(f"  {len(games)} {kind} (games {' '.join(games)}); see repeats.csv.")


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
    payees = payees_from_exports(args.zips)
    visits = visits_without_a_game(args.zips)
    waiters = lobby_waiters(visits)
    adjustments = read_adjustments(PROJECT_ROOT / "data" / args.dataset)
    unmatched = apply_adjustments(payees, adjustments)
    if adjustments:
        print(f"Applied {len(adjustments) - len(unmatched)} adjustment(s) from data/{args.dataset}/{ADJUSTMENTS_FILE}.")
    for player in unmatched:
        print(f"  WARNING: {ADJUSTMENTS_FILE} names player {player}, who is in no game of these exports.")
    studies = group_by_study(payees)
    for study_id in args.study:
        studies.setdefault(study_id, Study(study_id))
    if not args.offline:
        token = prolific.load_token()
        # Every study seen on a player, or passed with --study, is a candidate;
        # its submissions let a player without a study id be placed by their
        # Prolific id (assign_studies).
        # A study recorded only on lobby records (no game in it started) is a
        # candidate too, so its lobby timeouts are not missed.
        candidates = sorted({p.study_id for p in payees.values() if p.study_id} | set(args.study)
                            | {w.study_id for ws in waiters.values() for w in ws if w.study_id})
        submissions = {sid: list(prolific.paged(f"/studies/{sid}/submissions/", token)) for sid in candidates}
        # The session studies, which pay the game's base reward on approval; a
        # scheduling survey pays a few cents. Found by reward below, so that a
        # session study no player record names (no game in it started) counts.
        game_studies = set(candidates)
        assign_studies(payees, submissions)
        game_rate = next((round(s["reward"] / 100.0 / s["estimated_completion_time"], 4) for s in
                          (prolific.api("GET", f"/studies/{sid}/", token) or {} for sid in candidates[-1:])
                          if s.get("reward") and s.get("estimated_completion_time")), None)
        if waiters or any(not p.study_id for p in payees.values()):
            # Players with no game-study submission, and lobby waiters who may
            # have none: look through the other recent studies (the scheduling
            # surveys) for somewhere to pay them.
            first = min([_when(p.joined_at) for p in payees.values() if _when(p.joined_at)]
                        + [_when(w.entered_at) for ws in waiters.values() for w in ws if _when(w.entered_at)],
                        default=None)
            others = [s for s in prolific.paged("/studies/", token)
                      if s["id"] not in submissions and first and _when(s.get("date_created"))
                      and _when(s.get("date_created")) >= first - timedelta(days=2)]
            game_studies |= {s["id"] for s in others if (s.get("reward") or 0) / 100.0 >= prolific.BASE_PAY}
            for sid in dict.fromkeys(s["id"] for s in others):
                submissions[sid] = list(prolific.paged(f"/studies/{sid}/submissions/", token))
            place_unsubmitted(payees, submissions)
            candidates = sorted(set(candidates) | {p.study_id for p in payees.values() if p.study_id})
        studies = group_by_study(payees)
        for study_id in candidates:
            studies.setdefault(study_id, Study(study_id))
        assigned = assign_waiters(studies, payees, submissions, waiters, game_studies)
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
            in_study = {p.participant for p in study.payees if p.kind != "lobby"}
            settle(study, submissions[study.study_id], in_study, args.overtime_after, game_rate,
                   assigned.get(study.study_id, {}), study.study_id in game_studies)
    else:
        for study in studies.values():
            mark_unverified(study)
    out_dir = PAYMENTS_DIR / args.dataset
    summary = write_outputs(studies, out_dir, args.offline)
    print_summary(summary, out_dir, args.offline)
    pilot = pilot_participants() if PILOT_EXPORTS.is_dir() else set()
    if not pilot:
        print(f"\nWARNING: no pilot participants found in {PILOT_EXPORTS.relative_to(PROJECT_ROOT)}/, so they are "
              "neither repeat-checked nor blocklisted.")
    write_repeats(repeat_participants(payees, visits, pilot), out_dir)
    if not args.offline:
        n = write_blocklist(payees, out_dir, visits, submissions, pilot)
        print(f"  blocklist_ids.txt lists {n} people who started a game, failed the quiz, saw the social-first "
              f"instructions or took part in a pilot ({len(pilot)}); "
              "`make sync-blocklist` adds any new ones to the participant group the scheduling surveys block.")


if __name__ == "__main__":
    main()
