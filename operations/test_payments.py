"""Tests for operations/payments.py. No API calls and no real data needed.

Run with `make test-ops` or `uv run pytest operations/test_payments.py -q`.
Exports are built as small zips in a temporary directory; Prolific's submission
list is given as plain dicts in the shape its API returns.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "operations"))

import payments  # noqa: E402
import prolific  # noqa: E402

LOBBY = prolific.LOBBY_TIMEOUT_CODE


def make_export(path: Path, games: list[dict], players: list[dict]) -> Path:
    def table(rows, columns):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("game.csv", table(games, ["id", "status", "batchID", "startLastChangedAt", "endedLastChangedAt"]))
        z.writestr("player.csv", table(players, [
            "id", "gameID", "participantIdentifier", "studyId", "is_active",
            "bonus", "partialPay", "exitReason", "ended", "introDone", "quiz_attempts",
            "participantIdentifierLastChangedAt", "treatment",
        ]))
    return path


def player(pid, game, study, active=True, bonus="", partial="", reason=""):
    return {"id": f"e-{pid}", "gameID": game, "participantIdentifier": pid, "studyId": study,
            "is_active": "true" if active else "false", "bonus": bonus,
            "partialPay": partial, "exitReason": reason}


def by_pid(payees):
    """payees_from_exports keys by (participant, game); most tests have one game per person."""
    return {pid: payee for (pid, _), payee in payees.items()}


def submission(pid, status="AWAITING REVIEW", paid_cents=(), code=None, minutes=None):
    sub = {"id": f"s-{pid}", "participant_id": pid, "status": status,
           "bonus_payments": list(paid_cents)}
    if minutes is not None:
        sub["time_taken"] = int(minutes * 60)
    if code:
        sub["study_code"] = code
    return sub


@pytest.fixture
def export(tmp_path):
    games = [
        {"id": "G1", "status": "ended", "batchID": "B1"},
        {"id": "G2", "status": "running", "batchID": "B2"},
        {"id": "G3", "status": "failed", "batchID": "B3"},
        {"id": "G4", "status": "ended", "batchID": "B1"},
    ]
    players = [
        player("finisher", "G1", "S1", bonus="7.183"),
        player("removed", "G1", "S1", active=False, partial="9.84", reason="group disbanded"),
        player("playing", "G2", "S2", bonus="3.00"),
        player("lobbyfail", "G3", "S2"),
        player("excluded", "G4", "S1", bonus="5.00"),
        player("", "G1", "S1", bonus="1.00"),
    ]
    return make_export(tmp_path / "empirica-export-20260922_150048.zip", games, players)


class TestPayeesFromExports:
    def test_finishers_get_bonus_and_removed_players_partial_pay(self, export):
        payees = by_pid(payments.payees_from_exports([export]))
        assert payees["finisher"].kind == "bonus"
        assert payees["finisher"].amount == 7.18
        assert payees["removed"].kind == "partial"
        assert payees["removed"].amount == 9.84
        assert payees["removed"].exit_reason == "group disbanded"

    def test_study_and_batch_come_from_the_export(self, export):
        payees = by_pid(payments.payees_from_exports([export]))
        assert payees["finisher"].study_id == "S1"
        assert payees["finisher"].batch == "B1"

    def test_players_in_failed_games_or_without_an_id_are_skipped(self, export):
        payees = by_pid(payments.payees_from_exports([export]))
        assert "lobbyfail" not in payees
        assert "" not in payees

    def test_a_running_game_is_flagged(self, export):
        assert by_pid(payments.payees_from_exports([export]))["playing"].game_running

    def test_players_in_a_game_excluded_from_the_analysis_are_still_paid(self, tmp_path, export, monkeypatch):
        # A game in exclude_games.txt, such as one with a repeat participant, is
        # dropped from the analysis, but its players did the task and are owed.
        (tmp_path / "data" / "t").mkdir(parents=True)
        (tmp_path / "data" / "t" / "exclude_games.txt").write_text("G4\n")
        monkeypatch.setattr(payments, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(payments, "PAYMENTS_DIR", tmp_path / "payments")
        payments.main([str(export), "--dataset", "t", "--offline"])
        listed = {r["participant"] for f in (tmp_path / "payments" / "t").glob("*/status.csv")
                  for r in csv.DictReader(open(f))}
        assert "excluded" in listed

    def test_a_later_export_replaces_an_earlier_one(self, tmp_path, export):
        later = make_export(
            tmp_path / "empirica-export-20260923_011152.zip",
            [{"id": "G2", "status": "ended", "batchID": "B2"}],
            [player("playing", "G2", "S2", bonus="6.50")],
        )
        # Passed newest first on purpose: order comes from the timestamps.
        payees = by_pid(payments.payees_from_exports([later, export]))
        assert payees["playing"].amount == 6.5
        assert not payees["playing"].game_running

    def test_game_length_comes_from_the_game_timestamps(self, tmp_path):
        path = make_export(
            tmp_path / "empirica-export-20260923_194233.zip",
            [{"id": "G5", "status": "ended", "batchID": "B5",
              "startLastChangedAt": "2026-09-23T22:11:19.704553412Z",
              "endedLastChangedAt": "2026-09-23T23:15:23.727121504Z"}],
            [player("slow", "G5", "S5", bonus="6.00")],
        )
        assert by_pid(payments.payees_from_exports([path]))["slow"].game_minutes == 64.1


class TestAssignStudies:
    """A payee's study comes from their Prolific id when the link did not record it."""

    def payee(self, pid="p", study="", joined="2026-09-25T22:22:00.000Z", game="G1"):
        return payments.Payee(participant=pid, study_id=study, kind="bonus", amount=5.67,
                              game=game, joined_at=joined)

    def sub(self, pid="p", start="2026-09-25T22:10:00Z", end="2026-09-25T23:20:00Z", code=None):
        s = submission(pid, code=code)
        s["started_at"], s["completed_at"] = start, end
        return s

    def test_the_links_study_is_kept_when_it_has_the_submission(self):
        payees = {("p", "G1"): self.payee(study="S14")}
        payments.assign_studies(payees, {"S14": [self.sub()], "S13": [self.sub()]})
        assert payees[("p", "G1")].study_id == "S14"
        assert payees[("p", "G1")].study_source == "link"

    def test_a_missing_study_id_is_found_by_the_prolific_id(self):
        payees = {("p", "G1"): self.payee()}
        payments.assign_studies(payees, {"S14": [self.sub()], "S13": [self.sub(pid="other")]})
        assert payees[("p", "G1")].study_id == "S14"
        assert payees[("p", "G1")].study_source == "identifier"

    def test_several_submissions_go_to_the_one_whose_window_holds_the_game(self):
        # A lobby wait in the earlier session, then a whole game in the later one
        # (2026-09-25: returned with the lobby code in batch 13, played in batch 14).
        payees = {("p", "G1"): self.payee(joined="2026-09-25T22:22:00Z")}
        lobby = self.sub(start="2026-09-25T21:05:00Z", end="2026-09-25T21:09:00Z", code=LOBBY)
        game = self.sub(start="2026-09-25T22:12:00Z", end="2026-09-25T23:15:00Z")
        payments.assign_studies(payees, {"S13": [lobby], "S14": [game]})
        assert payees[("p", "G1")].study_id == "S14"

    def test_the_finished_code_decides_before_the_time_window(self):
        # The real case: the batch 13 submission was returned (no end time) and
        # the batch 14 one was only opened after the game to enter the code.
        payees = {("p", "G1"): self.payee(joined="2026-09-25T22:22:00Z")}
        lobby = self.sub(start="2026-09-25T21:05:00Z", end=None, code=LOBBY)
        finished = self.sub(start="2026-09-25T23:10:00Z", end="2026-09-25T23:10:30Z",
                            code=prolific.FINISHED_CODE)
        payments.assign_studies(payees, {"S13": [lobby], "S14": [finished]})
        assert payees[("p", "G1")].study_id == "S14"

    def test_a_returned_submission_is_not_treated_as_open_ended(self):
        payees = {("p", "G1"): self.payee(joined="2026-09-26T03:00:00Z")}
        returned = self.sub(start="2026-09-25T21:05:00Z", end=None)
        later = self.sub(start="2026-09-26T02:50:00Z", end="2026-09-26T04:00:00Z")
        payments.assign_studies(payees, {"S13": [returned], "S15": [later]})
        assert payees[("p", "G1")].study_id == "S15"

    def test_a_submission_closed_before_the_game_is_not_where_it_was_claimed(self):
        # 2026-10-08: a player reached the last session through a bare link and
        # never opened its game study. Their only game-study submission was a
        # lobby wait returned two hours earlier, which still owes that wait; the
        # game is paid through the session's scheduling survey instead.
        payees = {("p", "G1"): self.payee(joined="2026-10-08T23:10:00Z")}
        lobby = self.sub(start="2026-10-08T21:26:00Z", end="2026-10-08T21:36:00Z", code=LOBBY)
        survey = self.sub(start="2026-10-08T22:35:00Z", end="2026-10-08T22:47:00Z")
        payments.assign_studies(payees, {"S35": [lobby]})
        assert payees[("p", "G1")].study_id == ""
        payments.place_unsubmitted(payees, {"S35": [lobby], "SURVEY36": [survey]})
        assert payees[("p", "G1")].study_id == "SURVEY36"
        assert payees[("p", "G1")].kind == "unsubmitted"

    def test_a_returned_submission_from_an_earlier_day_is_not_a_single_match(self):
        payees = {("p", "G1"): self.payee(joined="2026-10-08T23:10:00Z")}
        returned = self.sub(start="2026-10-07T19:55:00Z", end=None)
        payments.assign_studies(payees, {"S30": [returned]})
        assert payees[("p", "G1")].study_id == ""

    def test_two_unclaimed_submissions_still_leave_the_payee_to_the_survey(self):
        # 2026-10-07: an old lobby wait and a game-study submission opened after
        # the game and returned without a code. Neither claims the game, which
        # was paid through the scheduling survey; that placement must not move.
        payees = {("p", "G1"): self.payee(joined="2026-10-07T19:52:00Z")}
        lobby = self.sub(start="2026-09-24T03:30:00Z", end="2026-09-24T03:45:00Z", code=LOBBY)
        returned = self.sub(start="2026-10-07T20:45:00Z", end=None)
        payments.assign_studies(payees, {"S8": [lobby], "S30": [returned]})
        assert payees[("p", "G1")].study_id == ""

    def test_no_matching_submission_leaves_the_payee_unassigned(self):
        payees = {("typo", "G1"): self.payee(pid="typo")}
        payments.assign_studies(payees, {"S14": [self.sub()]})
        assert payees[("typo", "G1")].study_id == ""

    def test_a_lobby_wait_in_one_study_is_paid_though_they_played_in_another(self):
        study = payments.Study("S13")
        payments.settle(study, [submission("p", code=LOBBY, status="RETURNED")], set())
        assert [(p.kind, p.participant) for p in study.payees] == [("lobby", "p")]
        assert study.payees[0].ready

    def test_two_sessions_by_the_same_person_are_both_kept(self, tmp_path):
        path = make_export(
            tmp_path / "empirica-export-20260926_121514.zip",
            [{"id": "G1", "status": "ended", "batchID": "B1"}, {"id": "G2", "status": "ended", "batchID": "B2"}],
            [player("p", "G1", "S1", bonus="3.00"), {**player("p", "G2", "S2", bonus="4.00"), "id": "e-p2"}],
        )
        payees = payments.payees_from_exports([path])
        assert {k for k in payees} == {("p", "G1"), ("p", "G2")}


class TestUnsubmitted:
    """Players who never submitted the game study are paid through another study."""

    def test_a_finisher_is_owed_base_and_bonus_on_their_scheduling_survey(self):
        payees = {("p", "G1"): payments.Payee(participant="p", study_id="", kind="bonus", amount=6.45,
                                             game="G1", joined_at="2026-09-25T20:49:00Z")}
        survey = submission("p"); survey["started_at"] = "2026-09-25T20:10:00Z"
        payments.place_unsubmitted(payees, {"SURVEY13": [survey]})
        payee = payees[("p", "G1")]
        assert (payee.study_id, payee.kind, payee.study_source) == ("SURVEY13", "unsubmitted", "unsubmitted")
        assert payee.amount == round(prolific.BASE_PAY + 6.45, 2)

    def test_a_removed_players_partial_pay_already_includes_the_base(self):
        payees = {("r", "G1"): payments.Payee(participant="r", study_id="", kind="partial", amount=7.71,
                                             game="G1", joined_at="2026-09-25T20:49:00Z")}
        payments.place_unsubmitted(payees, {"SURVEY13": [submission("r")]})
        assert payees[("r", "G1")].amount == 7.71

    def test_it_is_ready_on_an_approved_survey_submission(self):
        study = payments.Study("SURVEY13", estimated_minutes=1, reward=0.30)
        study.payees.append(payments.Payee(participant="p", study_id="SURVEY13", kind="unsubmitted",
                                           amount=18.45, game="G1"))
        payments.settle(study, [submission("p", status="APPROVED")], {"p"})
        assert study.payees[0].ready and study.payees[0].still_owed == 18.45

    def test_overtime_uses_the_game_rate_not_the_surveys(self):
        study = payments.Study("SURVEY13", estimated_minutes=1, reward=0.30)
        study.payees.append(payments.Payee(participant="p", study_id="SURVEY13", kind="unsubmitted",
                                           amount=18.45, game="G1", game_minutes=71.0, site_minutes=75.0))
        payments.settle(study, [submission("p", minutes=1)], {"p"}, game_rate=12.0 / 50)
        [ot] = [x for x in study.payees if x.kind == "overtime"]
        assert ot.amount == round(15 * 12.0 / 50, 2)


class TestOvertime:
    """A finisher whose submission ran past 60 minutes is owed the minutes beyond it."""

    def study(self, *payees_):
        study = payments.Study("S1", estimated_minutes=50, reward=12.0)
        study.payees.extend(payees_)
        return study

    def finisher(self, pid="a", game_minutes=64.0, **kw):
        return payments.Payee(participant=pid, study_id="S1", kind="bonus", amount=7.18,
                              game="G1", game_minutes=game_minutes, **kw)

    def overtime(self, study):
        return [p for p in study.payees if p.kind == "overtime"]

    def test_the_minutes_past_the_threshold_are_paid_at_the_advertised_rate(self):
        study = self.study(self.finisher())
        payments.settle(study, [submission("a", minutes=71)], {"a"})
        [ot] = self.overtime(study)
        assert ot.amount == round(11 * 12.0 / 50, 2) and ot.ready
        assert ot.minutes_taken == 71.0

    def test_game_length_does_not_matter(self):
        study = self.study(self.finisher(game_minutes=47.0))
        payments.settle(study, [submission("a", minutes=71)], {"a"})
        assert len(self.overtime(study)) == 1

    def test_part_minutes_are_not_paid(self):
        study = self.study(self.finisher())
        payments.settle(study, [submission("a", minutes=60.5)], {"a"})
        assert self.overtime(study) == []

    def test_a_submission_within_the_threshold_owes_none(self):
        study = self.study(self.finisher())
        payments.settle(study, [submission("a", minutes=59)], {"a"})
        assert self.overtime(study) == []

    def test_removed_players_are_not_owed_overtime(self):
        removed = payments.Payee(participant="r", study_id="S1", kind="partial", amount=4.58,
                                 game="G1", game_minutes=64.0)
        study = self.study(removed)
        payments.settle(study, [submission("r", status="RETURNED", minutes=40)], {"r"})
        assert self.overtime(study) == []

    def test_a_running_game_owes_none_yet(self):
        study = self.study(self.finisher(game_running=True))
        payments.settle(study, [submission("a", minutes=71)], {"a"})
        assert self.overtime(study) == []

    def test_the_threshold_can_be_changed(self):
        study = self.study(self.finisher())
        payments.settle(study, [submission("a", minutes=71)], {"a"}, overtime_after=50)
        [ot] = self.overtime(study)
        assert ot.amount == round(21 * 12.0 / 50, 2)

    def test_a_paid_performance_bonus_does_not_count_as_overtime(self):
        study = self.study(self.finisher())
        payments.settle(study, [submission("a", minutes=71, paid_cents=[718])], {"a"})
        bonus = next(p for p in study.payees if p.kind == "bonus")
        [ot] = self.overtime(study)
        assert not bonus.ready and bonus.already_paid == 7.18
        assert ot.ready and ot.already_paid == 0 and ot.still_owed == 2.64

    def test_payments_beyond_the_bonus_settle_the_overtime(self):
        study = self.study(self.finisher())
        payments.settle(study, [submission("a", minutes=71, paid_cents=[718, 264])], {"a"})
        [ot] = self.overtime(study)
        assert not ot.ready and ot.note == "paid"

    def test_the_games_own_record_counts_when_prolific_saw_a_minute(self):
        # Played through a link sent by message, then opened the study only to enter the code.
        study = self.study(self.finisher(site_minutes=72.0))
        payments.settle(study, [submission("a", minutes=1)], {"a"})
        [ot] = self.overtime(study)
        assert ot.amount == round(12 * 12.0 / 50, 2)

    def test_no_estimate_on_the_study_means_no_overtime(self):
        study = payments.Study("S1")
        study.payees.append(self.finisher())
        payments.settle(study, [submission("a", minutes=71)], {"a"})
        assert self.overtime(study) == []


class TestSettle:
    def study(self, *payees_):
        study = payments.Study("S1")
        study.payees.extend(payees_)
        return study

    def payee(self, pid, kind="bonus", amount=5.0, **kw):
        return payments.Payee(participant=pid, study_id="S1", kind=kind, amount=amount, **kw)

    def test_unpaid_bonus_is_ready(self):
        study = self.study(self.payee("a"))
        payments.settle(study, [submission("a")], {"a"})
        assert study.payees[0].ready and study.payees[0].still_owed == 5.0

    def test_paid_bonuses_are_subtracted_in_cents(self):
        study = self.study(self.payee("a", amount=7.18))
        payments.settle(study, [submission("a", paid_cents=[500])], {"a"})
        assert study.payees[0].already_paid == 5.0
        assert study.payees[0].still_owed == 2.18
        assert study.payees[0].ready

    def test_fully_paid_is_not_ready(self):
        study = self.study(self.payee("a", amount=7.18))
        payments.settle(study, [submission("a", paid_cents=[718])], {"a"})
        assert not study.payees[0].ready and study.payees[0].note == "paid"

    def test_partial_pay_is_withheld_from_an_approved_submission(self):
        study = self.study(self.payee("a", kind="partial", amount=9.84))
        payments.settle(study, [submission("a", status="APPROVED")], {"a"})
        assert not study.payees[0].ready and study.payees[0].still_owed == 0

    def test_an_approved_partial_above_the_base_is_owed_the_rest(self):
        # Removed near the end of Phase 1 with bonuses earned: owed more than the base.
        study = self.study(self.payee("a", kind="partial", amount=14.22))
        payments.settle(study, [submission("a", status="APPROVED")], {"a"})
        assert study.payees[0].ready
        assert study.payees[0].still_owed == round(14.22 - prolific.BASE_PAY, 2)

    def test_an_approved_partial_above_the_base_subtracts_what_was_paid(self):
        study = self.study(self.payee("a", kind="partial", amount=14.22))
        payments.settle(study, [submission("a", status="APPROVED", paid_cents=[100])], {"a"})
        assert study.payees[0].still_owed == round(14.22 - prolific.BASE_PAY - 1.0, 2)

    def test_a_finisher_bonus_is_still_owed_after_approval(self):
        study = self.study(self.payee("a"))
        payments.settle(study, [submission("a", status="APPROVED")], {"a"})
        assert study.payees[0].ready

    def test_no_submission_is_owed_but_not_ready(self):
        study = self.study(self.payee("a"))
        payments.settle(study, [], {"a"})
        assert not study.payees[0].ready
        assert study.payees[0].still_owed == 5.0
        assert study.payees[0].status == "no submission"

    def test_a_running_game_is_not_ready(self):
        study = self.study(self.payee("a", game_running=True))
        payments.settle(study, [submission("a")], {"a"})
        assert not study.payees[0].ready

    def test_lobby_timeouts_come_from_the_submission_code(self):
        study = self.study()
        payments.settle(study, [submission("w", code=LOBBY), submission("x")], set())
        lobby = [p for p in study.payees if p.kind == "lobby"]
        assert [p.participant for p in lobby] == ["w"]
        assert lobby[0].amount == round(prolific.LOBBY_TIMEOUT_PAY, 2) and lobby[0].ready

    def test_someone_placed_in_a_game_is_never_also_a_lobby_timeout(self):
        study = self.study()
        payments.settle(study, [submission("g", code=LOBBY)], {"g"})
        assert study.payees == []

    def test_an_approved_lobby_submission_is_not_paid_again(self):
        study = self.study()
        payments.settle(study, [submission("w", status="APPROVED", code=LOBBY)], set())
        assert not study.payees[0].ready


class TestWriteOutputs:
    def studies(self):
        study = payments.Study("6ab347643dce11f5837d0805", name="Group communication game",
                               internal_name="full sample batch 5", created="2026-09-23T03:28:00")
        study.payees = [
            payments.Payee("ready1", study.study_id, "bonus", 7.18, still_owed=7.18, ready=True, game="G1"),
            payments.Payee("paid1", study.study_id, "bonus", 6.0, already_paid=6.0, note="paid", game="G1"),
            payments.Payee("part1", study.study_id, "partial", 9.8, still_owed=9.8, ready=True, game="G1"),
            payments.Payee("ready1", study.study_id, "overtime", 5.04, still_owed=5.04, ready=True, game="G1"),
        ]
        return {study.study_id: study}

    def test_paste_files_hold_only_ready_rows_without_a_header(self, tmp_path):
        payments.write_outputs(self.studies(), tmp_path / "out", offline=False)
        folder = tmp_path / "out" / "2026-09-23_full-sample-batch-5_7d0805"
        assert (folder / "1_main.csv").read_text() == "ready1,7.18\npart1,9.80\n"
        assert (folder / "2_overtime.csv").read_text() == "ready1,5.04\n"
        assert not (folder / "bonus.csv").exists()

    def test_the_main_file_has_one_line_per_person(self, tmp_path):
        studies = self.studies()
        study = next(iter(studies.values()))
        study.payees.append(payments.Payee("ready1", study.study_id, "lobby", 2.0, still_owed=2.0, ready=True))
        payments.write_outputs(studies, tmp_path / "out", offline=False)
        main = (tmp_path / "out" / "2026-09-23_full-sample-batch-5_7d0805" / "1_main.csv").read_text()
        assert main == "ready1,9.18\npart1,9.80\n"

    def test_no_overtime_file_when_nobody_is_owed_overtime(self, tmp_path):
        studies = self.studies()
        study = next(iter(studies.values()))
        study.payees = [p for p in study.payees if p.kind != "overtime"]
        payments.write_outputs(studies, tmp_path / "out", offline=False)
        assert not (tmp_path / "out" / "2026-09-23_full-sample-batch-5_7d0805" / "2_overtime.csv").exists()

    def test_status_lists_everyone(self, tmp_path):
        payments.write_outputs(self.studies(), tmp_path / "out", offline=False)
        rows = list(csv.DictReader(open(tmp_path / "out" / "2026-09-23_full-sample-batch-5_7d0805" / "status.csv")))
        assert {r["participant"] for r in rows} == {"ready1", "paid1", "part1"}

    def test_summary_totals_the_ready_amounts(self, tmp_path):
        summary = payments.write_outputs(self.studies(), tmp_path / "out", offline=False)
        assert summary[0]["bonus_ready"] == 1 and summary[0]["bonus_amount"] == 7.18
        assert summary[0]["partial_amount"] == 9.8

    def test_offline_writes_no_paste_files(self, tmp_path):
        payments.write_outputs(self.studies(), tmp_path / "out", offline=True)
        folder = tmp_path / "out" / "2026-09-23_full-sample-batch-5_7d0805"
        assert (folder / "status.csv").exists()
        assert not (folder / "1_main.csv").exists()

    def test_the_summary_counts_submissions_that_still_have_to_be_returned(self, tmp_path):
        studies = self.studies()
        study = next(iter(studies.values()))
        study.payees.append(payments.Payee("lob1", study.study_id, "lobby", 2.0, status="AWAITING REVIEW",
                                           submitted_at="2026-09-23T04:00:00"))
        study.payees.append(payments.Payee("lob2", study.study_id, "lobby", 2.0, status="RETURNED"))
        summary = payments.write_outputs(studies, tmp_path / "out", offline=False)
        assert summary[0]["awaiting_return"] == 1
        assert summary[0]["auto_approval"] == "2026-10-14"

    def test_the_directory_is_rewritten(self, tmp_path):
        stale = tmp_path / "out" / "old-study" / "bonus.csv"
        stale.parent.mkdir(parents=True)
        stale.write_text("someone,1.00\n")
        payments.write_outputs(self.studies(), tmp_path / "out", offline=False)
        assert not stale.exists()


def waiter_row(pid, game, study, ended, intro="true", attempts="1", entered="2026-09-25T21:04:00.0Z", rid=None):
    return {**player(pid, game, study), "id": rid or f"w-{pid}-{game}", "is_active": "", "ended": ended,
            "introDone": intro, "quiz_attempts": attempts, "participantIdentifierLastChangedAt": entered}


class TestLobbyWaiters:
    """Lobby timeouts who returned the study without entering the lobby code."""

    def export(self, tmp_path, rows, games=None):
        games = games or [{"id": "F1", "status": "failed", "batchID": "B13"},
                          {"id": "G9", "status": "ended", "batchID": "B14",
                           "startLastChangedAt": "2026-09-25T22:15:00Z"}]
        return make_export(tmp_path / "empirica-export-20260925_180641.zip", games, rows)

    def test_a_lobby_timeout_and_an_overflow_player_are_waiters(self, tmp_path):
        path = self.export(tmp_path, [waiter_row("lobby", "F1", "S13", "game failed"),
                                      waiter_row("overflow", "", "S13", "no more games", intro="", attempts="")])
        waiters = payments.lobby_waiters(payments.visits_without_a_game([path]))
        assert set(waiters) == {"lobby", "overflow"}
        assert waiters["lobby"][0].study_id == "S13"

    def test_quiz_failures_and_people_still_in_the_instructions_are_not(self, tmp_path):
        path = self.export(tmp_path, [
            waiter_row("quizfail", "F1", "S13", "game failed", intro="", attempts="3"),
            waiter_row("reading", "F1", "S13", "game failed", intro="", attempts=""),
            waiter_row("quizfail2", "", "S13", "no more games", intro="", attempts="3"),
        ])
        assert payments.lobby_waiters(payments.visits_without_a_game([path])) == {}

    def test_a_visit_keeps_the_condition_of_the_game_it_was_assigned(self, tmp_path):
        """Empirica copies the game's treatment onto the player, and an overflow player keeps it."""
        sf = '{"condition":"social_first","tangram_set":1,"playerCount":9}'
        path = self.export(tmp_path, [
            {**waiter_row("lobby", "F1", "S13", "game failed"), "treatment": sf},
            {**waiter_row("overflow", "", "S13", "no more games", intro="", attempts=""), "treatment": sf},
            {**waiter_row("other", "F1", "S13", "game failed"), "treatment": '{"condition":"refer_mixed"}'},
            {**waiter_row("broken", "F1", "S13", "game failed"), "treatment": "not json"},
        ])
        visits = payments.visits_without_a_game([path])
        assert {pid: vs[0].condition for pid, vs in visits.items()} == {
            "lobby": "social_first", "overflow": "social_first", "other": "refer_mixed", "broken": ""}

    def test_a_returned_submission_without_the_code_is_paid_lobby_pay(self, tmp_path):
        path = self.export(tmp_path, [waiter_row("w", "F1", "S13", "game failed")])
        waiters = payments.lobby_waiters(payments.visits_without_a_game([path]))
        study = payments.Study("S13")
        payments.settle(study, [submission("w", status="RETURNED"), submission("x", status="RETURNED")],
                        set(), waiters=waiters)
        [lobby] = study.payees
        assert (lobby.participant, lobby.kind, lobby.ready) == ("w", "lobby", True)
        assert lobby.amount == round(prolific.LOBBY_TIMEOUT_PAY, 2)
        assert "no code entered" in lobby.exit_reason

    def test_without_a_study_id_the_submission_window_decides(self, tmp_path):
        path = self.export(tmp_path, [waiter_row("w", "F1", "", "game failed", entered="2026-09-25T21:04:00Z")])
        waiters = payments.lobby_waiters(payments.visits_without_a_game([path]))
        during = submission("w", status="RETURNED")
        during["started_at"] = "2026-09-25T21:00:00Z"
        later = submission("w", status="RETURNED")
        later["started_at"], later["completed_at"] = "2026-09-26T21:00:00Z", "2026-09-26T21:05:00Z"
        first, second = payments.Study("S13"), payments.Study("S15")
        payments.settle(first, [during], set(), waiters=waiters)
        payments.settle(second, [later], set(), waiters=waiters)
        assert [p.kind for p in first.payees] == ["lobby"]
        assert second.payees == []

    def test_a_waiter_who_played_in_the_same_study_is_not_also_paid_lobby_pay(self, tmp_path):
        path = self.export(tmp_path, [waiter_row("w", "F1", "S13", "game failed")])
        study = payments.Study("S13")
        payments.settle(study, [submission("w", status="RETURNED")], {"w"},
                        waiters=payments.lobby_waiters(payments.visits_without_a_game([path])))
        assert study.payees == []

    def test_a_later_snapshot_where_the_game_started_is_not_a_waiter(self, tmp_path):
        early = make_export(tmp_path / "empirica-export-20260925_180000.zip",
                            [{"id": "G1", "status": "failed", "batchID": "B1"}],
                            [waiter_row("p", "G1", "S1", "game failed", rid="r1")])
        late = make_export(tmp_path / "empirica-export-20260925_190000.zip",
                           [{"id": "G1", "status": "ended", "batchID": "B1"}],
                           [{**player("p", "G1", "S1", bonus="5.00"), "id": "r1"}])
        assert payments.lobby_waiters(payments.visits_without_a_game([early, late])) == {}


def timed(pid, started, completed=None, **kw):
    sub = submission(pid, **kw)
    sub["started_at"] = started
    if completed:
        sub["completed_at"] = completed
    return sub


class TestAssignWaiters:
    """Each lobby wait is paid exactly once, including waits reached through a link sent by message."""

    def wait(self, study="", entered="2026-10-08T20:04:00Z", ended="game failed"):
        return {"w": [payments.Visit("w", study, entered, ended, waited=True)]}

    def survey(self, **kw):
        return timed("w", "2026-10-08T19:44:00Z", "2026-10-08T19:45:00Z", status="APPROVED", **kw)

    def settle_all(self, studies, subs, assigned, game_studies):
        for sid, study in studies.items():
            payments.settle(study, subs.get(sid, []), set(), waiters=assigned.get(sid, {}),
                            game_study=sid in game_studies)
        return sorted((sid, p.kind) for sid, study in studies.items() for p in study.payees)

    def test_a_wait_reached_through_a_link_is_paid_through_the_survey(self):
        studies = {"S34": payments.Study("S34")}
        subs = {"S34": [], "SURVEY34": [self.survey()]}
        assigned = payments.assign_waiters(studies, {}, subs, self.wait(), {"S34"})
        assert assigned == {}
        [lobby] = studies["SURVEY34"].payees
        assert (lobby.kind, lobby.study_source) == ("lobby", "unsubmitted")
        self.settle_all(studies, subs, assigned, {"S34"})
        # The survey's approval paid its own small reward, not the base, so the lobby pay is still owed.
        assert lobby.ready and lobby.still_owed == round(prolific.LOBBY_TIMEOUT_PAY, 2)

    def test_a_wait_the_lobby_code_accounts_for_is_left_to_settle(self):
        coded = timed("w", "2026-10-08T20:30:00Z", "2026-10-08T20:31:00Z", code=LOBBY)
        studies = {"S34": payments.Study("S34")}
        subs = {"S34": [coded], "SURVEY34": [self.survey()]}
        assigned = payments.assign_waiters(studies, {}, subs, self.wait(), {"S34"})
        assert self.settle_all(studies, subs, assigned, {"S34"}) == [("S34", "lobby")]

    def test_the_lobby_code_typed_into_the_survey_is_paid_there_in_full(self):
        studies = {"S34": payments.Study("S34")}
        subs = {"S34": [], "SURVEY34": [self.survey(code=LOBBY)]}
        assigned = payments.assign_waiters(studies, {}, subs, self.wait(), {"S34"})
        assert self.settle_all(studies, subs, assigned, {"S34"}) == [("SURVEY34", "lobby")]
        [lobby] = studies["SURVEY34"].payees
        assert lobby.ready and lobby.study_source == "unsubmitted"

    def test_a_wait_followed_by_a_game_in_the_same_session_is_not_paid(self):
        played = {("w", "G1"): payments.Payee("w", "", "bonus", 6.0, game="G1", joined_at="2026-10-08T20:10:00Z")}
        studies = {}
        assigned = payments.assign_waiters(studies, played, {"SURVEY34": [self.survey()]}, self.wait(), set())
        assert assigned == {} and studies == {}

    def test_a_game_in_a_later_session_does_not_cancel_the_wait(self):
        played = {("w", "G1"): payments.Payee("w", "", "bonus", 6.0, game="G1", joined_at="2026-10-08T23:08:00Z")}
        studies = {}
        payments.assign_waiters(studies, played, {"SURVEY34": [self.survey()]}, self.wait(), set())
        assert [p.kind for p in studies["SURVEY34"].payees] == ["lobby"]

    def test_two_records_in_one_session_are_one_wait(self):
        waits = {"w": [payments.Visit("w", "", "2026-10-08T23:04:00Z", "no more games", waited=True),
                       payments.Visit("w", "", "2026-10-08T23:08:00Z", "no more games", waited=True)]}
        studies = {}
        payments.assign_waiters(studies, {}, {"SURVEY36": [self.survey()]}, waits, set())
        assert [p.kind for p in studies["SURVEY36"].payees] == ["lobby"]

    def test_a_wait_two_game_studies_account_for_is_paid_in_one(self):
        returned_survey = timed("w", "2026-10-08T19:44:00Z", status="RETURNED")  # no end: open three hours
        first = timed("w", "2026-10-08T19:50:00Z", status="RETURNED")
        second = timed("w", "2026-10-08T20:00:00Z", status="RETURNED")
        studies = {"S33": payments.Study("S33"), "S34": payments.Study("S34")}
        subs = {"S33": [first], "S34": [second], "SURVEY34": [returned_survey]}
        assigned = payments.assign_waiters(studies, {}, subs, self.wait(study="S34"), {"S33", "S34"})
        assert self.settle_all(studies, subs, assigned, {"S33", "S34"}) == [("S34", "lobby")]

    def test_an_earlier_sessions_open_submission_does_not_pay_a_coded_wait_again(self):
        # Returned without an end, the earlier session's submission counts as open for three
        # hours, which reaches into the next session, where the wait was paid by its code.
        earlier = timed("w", "2026-10-08T15:40:00Z", status="RETURNED")
        coded = timed("w", "2026-10-08T18:45:00Z", "2026-10-08T18:50:00Z", status="RETURNED", code=LOBBY)
        studies = {"S32": payments.Study("S32"), "S33": payments.Study("S33")}
        subs = {"S32": [earlier], "S33": [coded]}
        assigned = payments.assign_waiters(studies, {}, subs, self.wait(study="S33", entered="2026-10-08T18:35:00Z"),
                                           {"S32", "S33"})
        assert self.settle_all(studies, subs, assigned, {"S32", "S33"}) == [("S33", "lobby")]

    def test_with_no_earlier_submission_the_wait_has_no_study(self):
        studies = {}
        later = timed("w", "2026-10-09T19:44:00Z", "2026-10-09T19:45:00Z")
        payments.assign_waiters(studies, {}, {"SURVEY35": [later]}, self.wait(), set())
        assert [p.kind for p in studies[payments.NO_STUDY].payees] == ["lobby"]

    def test_lobby_pay_beside_paid_game_pay_on_one_submission_is_still_owed(self):
        # Waited out a failed lobby, then played in a later session, both paid through one survey submission.
        study = payments.Study("SURVEY22")
        study.payees = [payments.Payee("w", "SURVEY22", "unsubmitted", 19.62, game="G1", study_source="unsubmitted"),
                        payments.Payee("w", "SURVEY22", "lobby", 2.0, study_source="unsubmitted")]
        payments.settle(study, [timed("w", "2026-10-04T23:25:00Z", "2026-10-04T23:26:00Z", status="APPROVED",
                                      paid_cents=[1962])], {"w"})
        game, lobby = study.payees[:2]
        assert not game.ready and game.already_paid == 19.62
        assert lobby.ready and lobby.already_paid == 0 and lobby.still_owed == 2.0

    def test_lobby_pay_through_a_survey_is_not_awaiting_return(self, tmp_path):
        study = payments.Study("SURVEY18", internal_name="survey 18", created="2026-09-27T01:00:00")
        study.payees = [payments.Payee("w", "SURVEY18", "lobby", 2.0, still_owed=2.0, ready=True,
                                       status="AWAITING REVIEW", submitted_at="2026-09-27T01:46:00",
                                       study_source="unsubmitted")]
        [row] = payments.write_outputs({"SURVEY18": study}, tmp_path / "out", offline=False)
        assert row["awaiting_return"] == 0 and row["lobby_ready"] == 1


class TestReconciliation:
    """Submissions and payments that no row would otherwise account for."""

    def test_a_game_study_submission_owed_nothing_must_be_returned(self, tmp_path):
        study = payments.Study("S8", internal_name="batch 8", created="2026-09-24T00:00:00")
        payments.settle(study, [timed("q", "2026-09-24T00:22:00Z", "2026-09-24T00:42:00Z", code="NOCODE")], set())
        [row] = study.payees
        assert (row.kind, row.ready, row.still_owed) == ("none", False, 0.0)
        [summary] = payments.write_outputs({"S8": study}, tmp_path / "out", offline=False)
        assert summary["awaiting_return"] == 1 and summary["auto_approval"] == "2026-10-15"

    def test_a_code_that_is_none_of_the_experiments_is_not_repeated(self):
        study = payments.Study("S29")
        payments.settle(study, [submission("q", code="a" * 24)], set())
        assert "a" * 24 not in study.payees[0].exit_reason

    def test_a_game_code_without_a_game_points_to_a_mistyped_identifier(self):
        study = payments.Study("S8")
        payments.settle(study, [submission("q", code=prolific.FINISHED_CODE)], set())
        assert "mistyped" in study.payees[0].note

    def test_a_survey_lists_nobody_owed_nothing(self):
        study = payments.Study("SURVEY8")
        payments.settle(study, [submission("q")], set(), game_study=False)
        assert study.payees == []

    def test_a_payment_no_row_explains_is_listed(self):
        studies = {"S21": payments.Study("S21")}
        rows = payments.reconcile(studies, {"SURVEY21": [submission("g", paid_cents=[200])]}, {"SURVEY21": "survey 21"})
        assert [(r["study"], r["unexplained"], r["held_back"]) for r in rows] == [("survey 21", 2.0, "")]

    def test_a_line_equal_to_a_payment_made_elsewhere_is_held_back(self):
        # The bonus went out through the scheduling survey and was still listed in the game study.
        owed = payments.Payee("d", "S17", "bonus", 18.16, still_owed=18.16, ready=True, game="G1")
        study = payments.Study("S17", payees=[owed])
        rows = payments.reconcile({"S17": study}, {"SURVEY17": [submission("d", paid_cents=[1816])], "S17": []},
                                  {"SURVEY17": "survey 17", "S17": "batch 17"})
        assert not owed.ready and "survey 17" in owed.note
        assert rows[0]["held_back"] == "batch 17"

    def test_paying_more_than_a_row_asked_for_holds_nothing_back(self):
        # $4 for a $2 lobby wait in one session; a wait two weeks later is owed in full.
        earlier = payments.Payee("w", "S10", "lobby", 2.0, already_paid=2.0)
        later = payments.Payee("w", "S31", "lobby", 2.0, still_owed=2.0, ready=True)
        studies = {"S10": payments.Study("S10", payees=[earlier]), "S31": payments.Study("S31", payees=[later])}
        rows = payments.reconcile(studies, {"S10": [submission("w", paid_cents=[200, 200])], "S31": []}, {})
        assert [r["unexplained"] for r in rows] == [2.0] and later.ready

    def test_paid_rows_are_not_listed(self):
        paid = payments.Payee("a", "S1", "bonus", 5.0, already_paid=5.0)
        rows = payments.reconcile({"S1": payments.Study("S1", payees=[paid])}, {"S1": [submission("a", paid_cents=[500])]}, {})
        assert rows == []


class TestReturnedFinisher:
    def test_a_returned_finisher_is_owed_the_base_as_a_bonus_too(self):
        study = payments.Study("S1")
        study.payees.append(payments.Payee(participant="a", study_id="S1", kind="bonus", amount=6.45, game="G1"))
        payments.settle(study, [submission("a", status="RETURNED")], {"a"})
        [payee] = study.payees
        assert payee.ready and payee.still_owed == round(prolific.BASE_PAY + 6.45, 2)
        assert "returned" in payee.exit_reason

    def test_an_approved_finisher_is_owed_only_the_bonus(self):
        study = payments.Study("S1")
        study.payees.append(payments.Payee(participant="a", study_id="S1", kind="bonus", amount=6.45, game="G1"))
        payments.settle(study, [submission("a", status="APPROVED")], {"a"})
        assert study.payees[0].still_owed == 6.45


class TestRepeatParticipants:
    def test_someone_in_two_started_games_played_twice(self):
        payees = {("p", "G1"): payments.Payee("p", "S1", "bonus", 3.0, game="00000G1"),
                  ("p", "G2"): payments.Payee("p", "S2", "bonus", 4.0, game="00000G2"),
                  ("q", "G1"): payments.Payee("q", "S1", "bonus", 3.0, game="00000G1")}
        [row] = payments.repeat_participants(payees, {})
        assert row["kind"] == "played twice" and row["games"] == "0000G1 0000G2"

    def test_an_earlier_lobby_wait_is_listed_but_allowed(self):
        payees = {("p", "G9"): payments.Payee("p", "S14", "bonus", 3.0, game="CSEVVD",
                                              joined_at="2026-09-25T22:15:00Z")}
        visits = {"p": [payments.Visit("p", "S13", "2026-09-25T21:04:00Z", "game failed", waited=True)]}
        [row] = payments.repeat_participants(payees, visits)
        assert row["kind"] == "earlier visit without a game, then played"

    def test_a_quiz_failure_who_came_back_is_named_as_such(self):
        payees = {("p", "G9"): payments.Payee("p", "S14", "bonus", 3.0, game="CSEVVD",
                                              joined_at="2026-09-26T22:15:00Z")}
        visits = {"p": [payments.Visit("p", "S13", "2026-09-25T21:04:00Z", "game failed", quiz_failed=True)]}
        [row] = payments.repeat_participants(payees, visits)
        assert row["kind"] == "quiz failed earlier, then played"

    def test_an_earlier_social_first_visit_is_named_as_such(self):
        payees = {("p", "G9"): payments.Payee("p", "S14", "bonus", 3.0, game="CSEVVD",
                                              joined_at="2026-09-26T22:15:00Z")}
        visits = {"p": [payments.Visit("p", "S13", "2026-09-25T21:04:00Z", "game failed", waited=True,
                                       condition="social_first")]}
        [row] = payments.repeat_participants(payees, visits)
        assert row["kind"] == "saw the social-first instructions earlier, then played"

    def test_a_pilot_participant_who_played_is_named_as_such(self):
        payees = {("p" * 24, "G9"): payments.Payee("p" * 24, "S14", "bonus", 3.0, game="6FK46P",
                                                   joined_at="2026-10-07T19:36:00Z")}
        visits = {"p" * 24: [payments.Visit("p" * 24, "S13", "2026-09-25T21:04:00Z", "game failed", waited=True)]}
        [row] = payments.repeat_participants(payees, visits, pilot={"p" * 24})
        assert row["kind"] == "took part in a pilot, then played" and row["games"] == "6FK46P"

    def test_a_record_from_the_same_session_is_not_a_return(self):
        payees = {("p", "G9"): payments.Payee("p", "S14", "bonus", 3.0, game="CSEVVD",
                                              joined_at="2026-09-25T22:15:00Z")}
        visits = {"p": [payments.Visit("p", "S14", "2026-09-25T22:05:00Z", "no more games", waited=True)]}
        assert payments.repeat_participants(payees, visits) == []


class TestAdjustments:
    def payee(self, kind="partial", amount=9.43, **kw):
        return payments.Payee(participant="p", study_id="S1", kind=kind, amount=amount, game="G1",
                              player_id="E1", earned_bonus=1.52, base_partial=9.43, **kw)

    def test_restore_bonus_adds_the_earned_bonus_to_the_prorated_base(self):
        payees = {("p", "G1"): self.payee(exit_reason="player timeout")}
        unmatched = payments.apply_adjustments(payees, {"E1": ("restore_bonus", "guess-only removal")})
        payee = payees[("p", "G1")]
        assert unmatched == [] and payee.amount == 10.95
        assert "bonus restored: guess-only removal" in payee.exit_reason

    def test_a_partial_pay_that_already_includes_the_bonus_is_not_doubled(self):
        payees = {("p", "G1"): self.payee(amount=10.95, exit_reason="group disbanded")}
        payments.apply_adjustments(payees, {"E1": ("restore_bonus", "x")})
        assert payees[("p", "G1")].amount == 10.95

    def test_a_finisher_is_unchanged(self):
        payees = {("p", "G1"): self.payee(kind="bonus", amount=6.0)}
        payments.apply_adjustments(payees, {"E1": ("restore_bonus", "x")})
        assert payees[("p", "G1")].amount == 6.0

    def test_an_adjustment_for_nobody_is_reported(self):
        assert payments.apply_adjustments({}, {"E9": ("restore_bonus", "x")}) == ["E9"]

    def test_the_file_needs_known_adjustments_and_reasons(self, tmp_path):
        (tmp_path / payments.ADJUSTMENTS_FILE).write_text("playerId,adjustment,reason\nE1,restore_bonus,lag\n")
        assert payments.read_adjustments(tmp_path) == {"E1": ("restore_bonus", "lag")}
        (tmp_path / payments.ADJUSTMENTS_FILE).write_text("playerId,adjustment,reason\nE1,double_it,lag\n")
        with pytest.raises(ValueError, match="unknown adjustment"):
            payments.read_adjustments(tmp_path)
        (tmp_path / payments.ADJUSTMENTS_FILE).write_text("playerId,adjustment,reason\nE1,restore_bonus,\n")
        with pytest.raises(ValueError, match="needs a reason"):
            payments.read_adjustments(tmp_path)
        assert payments.read_adjustments(tmp_path / "missing") == {}


class TestPlayedTwice:
    def test_a_later_sessions_submission_does_not_claim_an_earlier_game(self):
        # Played at noon through a messaged link (no study id, no game-study
        # submission), then signed up again and finished an afternoon game.
        noon = payments.Payee(participant="p", study_id="", kind="bonus", amount=7.17, game="G1",
                              joined_at="2026-10-05T16:06:00Z", game_minutes=70.0)
        later = submission("p", status="AWAITING REVIEW", code=prolific.FINISHED_CODE)
        later["started_at"], later["completed_at"] = "2026-10-05T19:40:00Z", "2026-10-05T20:50:00Z"
        payees = {("p", "G1"): noon}
        payments.assign_studies(payees, {"S26": [later]})
        assert payees[("p", "G1")].study_id == ""
        survey = submission("p", status="APPROVED"); survey["started_at"] = "2026-10-05T15:40:00Z"
        payments.place_unsubmitted(payees, {"SURVEY24": [survey], "S26": [later]})
        assert payees[("p", "G1")].study_id == "SURVEY24"
        assert payees[("p", "G1")].amount == round(prolific.BASE_PAY + 7.17, 2)

    def test_a_submission_opened_soon_after_the_game_still_claims_it(self):
        game = payments.Payee(participant="p", study_id="", kind="bonus", amount=5.0, game="G1",
                              joined_at="2026-09-25T22:22:00Z", game_minutes=50.0)
        sub = submission("p", code=prolific.FINISHED_CODE)
        sub["started_at"], sub["completed_at"] = "2026-09-25T23:20:00Z", "2026-09-25T23:20:30Z"
        payees = {("p", "G1"): game}
        payments.assign_studies(payees, {"S14": [sub]})
        assert payees[("p", "G1")].study_id == "S14"


def test_the_blocklist_holds_everyone_placed_in_a_started_game(tmp_path):
    payees = {
        ("a", "G1"): payments.Payee("a", "S1", "bonus", 3.0, game="G1"),           # finished and submitted
        ("b", "G1"): payments.Payee("b", "SURVEY", "unsubmitted", 18.0, game="G1"),  # played by link only
        ("c", "G1"): payments.Payee("c", "", "bonus", 3.0, game="G1"),             # no submission anywhere
        ("r", "G1"): payments.Payee("r", "S1", "partial", 4.0, game="G1"),         # removed, returned
        ("d", "G1"): payments.Payee("d", "SURVEY", "unsubmitted", 18.0, game="G1"),  # played twice
        ("d", "G2"): payments.Payee("d", "S2", "bonus", 7.0, game="G2"),
    }
    assert payments.write_blocklist(payees, tmp_path) == 5
    assert (tmp_path / "blocklist_ids.txt").read_text() == "a\nb\nc\nd\nr\n"


def test_quiz_failures_are_blocked_but_lobby_timeouts_and_overflow_players_are_not(tmp_path):
    """Outside social-first; these visits carry no condition."""
    payees = {("a", "G1"): payments.Payee("a", "S1", "bonus", 3.0, game="G1")}
    visits = {"q": [payments.Visit("q", "S1", "", "game failed", quiz_failed=True)],
              "w": [payments.Visit("w", "S1", "", "game failed", waited=True)],
              "n": [payments.Visit("n", "S1", "", "no more games")]}
    submissions = {"S1": [submission("w", status="RETURNED", code=prolific.LOBBY_TIMEOUT_CODE),
                          submission("n", status="RETURNED")]}
    assert payments.write_blocklist(payees, tmp_path, visits, submissions) == 2
    assert (tmp_path / "blocklist_ids.txt").read_text() == "a\nq\n"


def test_anyone_who_saw_the_social_first_instructions_is_blocked_without_a_game(tmp_path):
    """Its instructions describe Phase 2; the other conditions' visitors stay eligible."""
    visits = {"sl": [payments.Visit("sl", "S1", "", "game failed", waited=True, condition="social_first")],
              "so": [payments.Visit("so", "S1", "", "no more games", condition="social_first")],
              "sr": [payments.Visit("sr", "S1", "", "game failed", condition="social_first")],  # left mid-instructions
              "ml": [payments.Visit("ml", "S1", "", "game failed", waited=True, condition="refer_mixed")],
              "mo": [payments.Visit("mo", "S1", "", "no more games", condition="social_mixed")],
              "un": [payments.Visit("un", "S1", "", "")],  # never assigned to a game
              "tw": [payments.Visit("tw", "S1", "", "game failed", waited=True, condition="refer_separated"),
                     payments.Visit("tw", "S2", "", "no more games", condition="social_first")]}
    assert payments.write_blocklist({}, tmp_path, visits, {}) == 4
    assert (tmp_path / "blocklist_ids.txt").read_text() == "sl\nso\nsr\ntw\n"


def test_pilot_participants_are_blocked(tmp_path):
    payees = {("a", "G1"): payments.Payee("a", "S1", "bonus", 3.0, game="G1")}
    assert payments.write_blocklist(payees, tmp_path, {}, {}, pilot={"b" * 24}) == 2
    assert (tmp_path / "blocklist_ids.txt").read_text() == f"a\n{'b' * 24}\n"


def tajriba_file(path: Path, players: list[tuple[str, str]], started: set[str]) -> Path:
    """A minimal tajriba.json: one attribute record per line, as Empirica's event log writes them."""
    def attr(node, key, val):
        return json.dumps({"kind": "Attribute", "obj": {"key": key, "val": val, "nodeID": node}})
    lines = [json.dumps({"version": "v1.12.1"}), attr("G1", "start", "false"), attr("G2", "start", "false")]
    for i, (pid, game) in enumerate(players):
        lines += [json.dumps({"kind": "Participant", "obj": {"Identifier": pid}}),
                  attr(f"P{i}", "participantIdentifier", json.dumps(pid)), attr(f"P{i}", "gameID", json.dumps(game))]
    lines += [attr(game, "start", "true") for game in started]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def test_pilot_participants_come_from_the_zips_and_the_raw_tajriba_files(tmp_path):
    """Players of started games and quiz failures count; lobby timeouts and test logins do not."""
    played, quiz, lobby, early, early_lobby = ("a" * 24, "b" * 24, "c" * 24, "d" * 24, "e" * 24)
    (tmp_path / "20260228_170936").mkdir()
    make_export(tmp_path / "20260228_170936" / "empirica-export-20260228_170936.zip",
                [{"id": "G1", "status": "ended"}, {"id": "F1", "status": "failed"}],
                [player(played, "G1", ""), player("alice", "G1", ""),
                 waiter_row(quiz, "F1", "", "game failed", intro="", attempts="3"),
                 waiter_row(lobby, "F1", "", "game failed")])
    tajriba_file(tmp_path / "20250327_232127" / "tajriba.json",
                 [(early, "G1"), (early_lobby, "G2"), ("awerawer", "G1")], started={"G1"})
    assert payments.pilot_participants(tmp_path) == {played, quiz, early}


def test_a_finished_or_partial_code_blocks_a_player_the_exports_do_not_name(tmp_path):
    """A mistyped identifier leaves the player out of the payees; their code still blocks them."""
    submissions = {"S1": [submission("t", code=prolific.FINISHED_CODE),
                          submission("p", status="RETURNED", code=prolific.PARTIAL_CODE),
                          submission("l", status="RETURNED", code=prolific.LOBBY_TIMEOUT_CODE)]}
    assert payments.write_blocklist({}, tmp_path, {}, submissions) == 2
    assert (tmp_path / "blocklist_ids.txt").read_text() == "p\nt\n"
