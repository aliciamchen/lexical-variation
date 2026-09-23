"""Tests for operations/payments.py. No API calls and no real data needed.

Run with `make test-ops` or `uv run pytest operations/test_payments.py -q`.
Exports are built as small zips in a temporary directory; Prolific's submission
list is given as plain dicts in the shape its API returns.
"""
from __future__ import annotations

import csv
import io
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
        z.writestr("game.csv", table(games, ["id", "status", "batchID"]))
        z.writestr("player.csv", table(players, [
            "id", "gameID", "participantIdentifier", "studyId", "is_active",
            "bonus", "partialPay", "exitReason",
        ]))
    return path


def player(pid, game, study, active=True, bonus="", partial="", reason=""):
    return {"id": f"e-{pid}", "gameID": game, "participantIdentifier": pid, "studyId": study,
            "is_active": "true" if active else "false", "bonus": bonus,
            "partialPay": partial, "exitReason": reason}


def submission(pid, status="AWAITING REVIEW", paid_cents=(), code=None):
    sub = {"id": f"s-{pid}", "participant_id": pid, "status": status,
           "bonus_payments": list(paid_cents)}
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
        player("rehearsal", "G4", "S1", bonus="5.00"),
        player("", "G1", "S1", bonus="1.00"),
    ]
    return make_export(tmp_path / "empirica-export-20260922_150048.zip", games, players)


class TestPayeesFromExports:
    def test_finishers_get_bonus_and_removed_players_partial_pay(self, export):
        payees = payments.payees_from_exports([export])
        assert payees["finisher"].kind == "bonus"
        assert payees["finisher"].amount == 7.18
        assert payees["removed"].kind == "partial"
        assert payees["removed"].amount == 9.84
        assert payees["removed"].exit_reason == "group disbanded"

    def test_study_and_batch_come_from_the_export(self, export):
        payees = payments.payees_from_exports([export])
        assert payees["finisher"].study_id == "S1"
        assert payees["finisher"].batch == "B1"

    def test_players_in_failed_games_or_without_an_id_are_skipped(self, export):
        payees = payments.payees_from_exports([export])
        assert "lobbyfail" not in payees
        assert "" not in payees

    def test_a_running_game_is_flagged(self, export):
        assert payments.payees_from_exports([export])["playing"].game_running

    def test_excluded_games_are_left_out(self, export):
        assert "rehearsal" not in payments.payees_from_exports([export], {"G4"})

    def test_a_later_export_replaces_an_earlier_one(self, tmp_path, export):
        later = make_export(
            tmp_path / "empirica-export-20260923_011152.zip",
            [{"id": "G2", "status": "ended", "batchID": "B2"}],
            [player("playing", "G2", "S2", bonus="6.50")],
        )
        # Passed newest first on purpose: order comes from the timestamps.
        payees = payments.payees_from_exports([later, export])
        assert payees["playing"].amount == 6.5
        assert not payees["playing"].game_running


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
        ]
        return {study.study_id: study}

    def test_paste_files_hold_only_ready_rows_without_a_header(self, tmp_path):
        payments.write_outputs(self.studies(), tmp_path / "out", offline=False)
        folder = tmp_path / "out" / "2026-09-23_full-sample-batch-5_7d0805"
        assert (folder / "bonus.csv").read_text() == "ready1,7.18\n"
        assert (folder / "partial.csv").read_text() == "part1,9.80\n"
        assert not (folder / "lobby.csv").exists()

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
        assert not (folder / "bonus.csv").exists()

    def test_the_directory_is_rewritten(self, tmp_path):
        stale = tmp_path / "out" / "old-study" / "bonus.csv"
        stale.parent.mkdir(parents=True)
        stale.write_text("someone,1.00\n")
        payments.write_outputs(self.studies(), tmp_path / "out", offline=False)
        assert not stale.exists()
