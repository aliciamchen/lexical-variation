"""
Tests for the Prolific session tooling.

`operations/session.py` publishes studies and moves money, and until these
existed it was the only substantial part of the repository with no tests at
all. The cases here cover the pure functions -- the ones that decide who is
eligible, who gets paid, what each person is told, and when a study goes live --
so that the parts with irreversible consequences are exercised without touching
the API.
"""

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "operations"))
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))

import game_constants  # noqa: E402
import session  # noqa: E402
from extract_run import extract_bonuses, resolve_batch  # noqa: E402


def args(**fields):
    fields.setdefault("reason", None)
    fields.setdefault("note_file", None)
    return SimpleNamespace(**fields)


# ---------------------------------------------------------------- constants


def test_constants_come_from_the_experiment():
    loaded = game_constants.load()
    source = (PROJECT_ROOT / "experiment" / "shared" / "constants.js").read_text()
    for code in loaded["codes"].values():
        assert f'"{code}"' in source
    assert f"BASE_PAY = {int(loaded['base_pay'])}" in source
    assert loaded["players_per_game"] == 9


def test_missing_constant_is_an_error_not_a_guess(tmp_path, monkeypatch):
    stub = tmp_path / "constants.js"
    stub.write_text('export const BASE_PAY = 12;\n')
    monkeypatch.setattr(game_constants, "CONSTANTS_JS", stub)
    with pytest.raises(game_constants.ConstantsError, match="PROLIFIC_CODES"):
        game_constants.load()


def test_a_computed_constant_is_refused(tmp_path, monkeypatch):
    stub = tmp_path / "constants.js"
    stub.write_text("export const BASE_PAY = TEST_MODE ? 1 : 12;\n")
    monkeypatch.setattr(game_constants, "CONSTANTS_JS", stub)
    with pytest.raises(game_constants.ConstantsError, match="not a plain number"):
        game_constants._number(stub.read_text(), "BASE_PAY")


def test_every_server_exit_reason_has_wording():
    """The guard that stops a reworded removal reason sending the wrong message."""
    assert session.SERVER_EXIT_REASONS <= session.KNOWN_EXIT_REASONS
    session.check_exit_reasons()


def test_exit_reasons_come_from_the_shared_constants():
    found = game_constants.exit_reasons()
    assert {"quiz failed", "player timeout", "group disbanded", "insufficient groups",
            "low accuracy", "insufficient groups after accuracy check",
            "game terminated"} <= found
    source = (PROJECT_ROOT / "experiment" / "shared" / "constants.js").read_text()
    for reason in found:
        assert f'"{reason}"' in source


COMMENTED_CONSTANTS = '''
export const GROUP_SIZE = 3; // players: 3
export const GROUP_NAMES = ["A", "B", "C"]; // was ["A", "B"]
export const conditions = [
  "refer_separated", "refer_mixed", // "old_name": retired
];
export const BASE_PAY = 12; // dollars; was 10
export const LOBBY_TIMEOUT_PAY = 2;
export const MAX_BONUS = 8;
export const getAvatarUrl = (seed) => `https://api.dicebear.com/9.x/identicon/svg?seed=${seed}`;
export const PROLIFIC_CODES = {
  completion: "AAAA1111", // finished: "not this"
  lobbyTimeout: "BBBB2222", // no game formed { in the lobby }
  partial: "CCCC3333", // removed early
};
export const EXIT_REASONS = {
  quizFailed: "quiz failed", // three failed attempts; url "http://x" ]
  playerTimeout: "player timeout",
  gameTerminated: "game terminated", // stopped: "the researcher"
};
'''


def test_comments_beside_declarations_do_not_leak_into_the_values(tmp_path, monkeypatch):
    stub = tmp_path / "constants.js"
    stub.write_text(COMMENTED_CONSTANTS)
    monkeypatch.setattr(game_constants, "CONSTANTS_JS", stub)
    loaded = game_constants.load()
    assert loaded["codes"] == {"completion": "AAAA1111", "lobbyTimeout": "BBBB2222", "partial": "CCCC3333"}
    assert loaded["conditions"] == ["refer_separated", "refer_mixed"]
    assert loaded["players_per_game"] == 9
    assert loaded["base_pay"] == 12
    assert game_constants.exit_reasons() == {"quiz failed", "player timeout", "game terminated"}


def test_a_missing_or_empty_exit_reasons_object_is_an_error(tmp_path, monkeypatch):
    stub = tmp_path / "constants.js"
    stub.write_text("export const BASE_PAY = 12;\n")
    monkeypatch.setattr(game_constants, "CONSTANTS_JS", stub)
    with pytest.raises(game_constants.ConstantsError, match="EXIT_REASONS"):
        game_constants.exit_reasons()
    stub.write_text("export const EXIT_REASONS = {\n  // nothing yet\n};\n")
    with pytest.raises(game_constants.ConstantsError, match="EXIT_REASONS"):
        game_constants.exit_reasons()


def test_a_url_in_a_string_is_not_a_comment():
    stripped = game_constants._without_comments('const u = "https://x.test/a"; // real comment')
    assert stripped == 'const u = "https://x.test/a"; '


# ------------------------------------------------------------ screening


def response(participant, answers, when="2026-09-16T20:00:00"):
    return {
        "participant_id": participant,
        "date_submitted": when,
        "questions": [
            {"question_title": title, "answers": [{"value": value}]}
            for title, value in answers
        ],
    }


YES3 = [("available?", "Yes"), ("desktop?", "Yes"), ("commit?", "Yes")]


def test_all_yes_is_eligible():
    out = session.screen_responses([response("p1", YES3)], 3)
    assert out["eligible"] == ["p1"]


def test_a_no_is_excluded_and_counted():
    answers = [("available?", "Yes"), ("desktop?", "No"), ("commit?", "Yes")]
    out = session.screen_responses([response("p1", answers)], 3)
    assert out["eligible"] == []
    assert out["rejected_by_question"] == {"desktop?": 1}


def test_a_response_with_no_questions_is_not_eligible():
    """The hole this replaced: no questions meant no failures meant eligible."""
    out = session.screen_responses([response("p1", [])], 3)
    assert out["eligible"] == []
    assert out["malformed"] == [("p1", 0)]


def test_a_short_response_is_set_aside_rather_than_guessed_at():
    out = session.screen_responses([response("p1", YES3[:2])], 3)
    assert out["eligible"] == []
    assert out["malformed"] == [("p1", 2)]


def test_duplicate_questions_are_not_merged():
    """Two questions sharing a title must still count as two."""
    answers = [("same?", "Yes"), ("same?", "No"), ("other?", "Yes")]
    out = session.screen_responses([response("p1", answers)], 3)
    assert out["eligible"] == []
    assert out["rejected_by_question"] == {"same?": 1}


def test_the_newest_response_per_participant_wins():
    early = response("p1", [("a", "No"), ("b", "No"), ("c", "No")], when="2026-09-16T19:00:00")
    late = response("p1", YES3, when="2026-09-16T20:30:00")
    out = session.screen_responses([early, late], 3)
    assert out["eligible"] == ["p1"]
    assert out["seen"] == 1


# --------------------------------------------------------------- payments


def test_read_payment_csv_drops_non_positive_rows(tmp_path):
    path = tmp_path / "early_ended.csv"
    path.write_text(
        "prolific_id,partial_pay,exit_reason\n"
        "alice,4.50,low accuracy\n"
        "bob,0.00,player timeout\n"
        "carol,-1.00,group disbanded\n"
    )
    rows, skipped = session.read_payment_csv(path, "partial_pay")
    assert [r["id"] for r in rows] == ["alice"]
    assert rows[0]["exit_reason"] == "low accuracy"
    assert skipped == 2


def test_per_person_ceiling_scales_the_total_guard():
    assert session.per_person_ceiling("lobby") == session.LOBBY_TIMEOUT_PAY
    assert session.per_person_ceiling("bonuses") == session.MAX_BONUS * 2
    assert session.per_person_ceiling("early") > session.per_person_ceiling("bonuses")


def test_an_inflated_total_is_refused_before_anything_is_sent(tmp_path, monkeypatch):
    """No single amount trips --max-each, but together they are impossible."""
    called = []
    monkeypatch.setattr(session, "api", lambda *a, **k: called.append(a))
    rows = [{"id": f"p{i}", "amount": 20.0} for i in range(10)]
    with pytest.raises(SystemExit, match="derived ceiling"):
        session.setup_payment(
            "token", tmp_path, "bonuses", "study", rows, {}, max_each=30.0, max_total=None
        )
    assert called == []


def test_a_plausible_total_passes_the_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session, "api", lambda *a, **k: {"id": "bulk1", "amount": 6000, "total_amount": 8000}
    )
    rows = [{"id": f"p{i}", "amount": 6.0} for i in range(10)]
    ledger = {}
    session.setup_payment(
        "token", tmp_path, "bonuses", "study", rows, ledger, max_each=30.0, max_total=None
    )
    assert ledger["bonuses"]["bulk_id"] == "bulk1"
    assert ledger["bonuses"]["participants_paid"] == [f"p{i}" for i in range(10)]
    assert ledger["bonuses"]["amounts"] == {f"p{i}": 6.0 for i in range(10)}
    assert ledger["bonuses"]["paid_at"] is None


def test_a_bulk_payment_for_the_wrong_amount_stops_before_paying(tmp_path, monkeypatch):
    """Prolific pays what the bulk payment holds, so it must hold what was asked."""
    monkeypatch.setattr(
        session, "api", lambda *a, **k: {"id": "bulk1", "amount": 5999, "total_amount": 8000}
    )
    rows = [{"id": f"p{i}", "amount": 6.0} for i in range(10)]
    ledger = {}
    with pytest.raises(SystemExit, match="5999 cents, but 6000 cents"):
        session.setup_payment(
            "token", tmp_path, "bonuses", "study", rows, ledger, max_each=30.0, max_total=None
        )
    # The bulk payment exists at Prolific, so the ledger must say so.
    saved = json.loads(session.ledger_path(tmp_path).read_text())
    assert saved["bonuses"]["bulk_id"] == "bulk1"
    assert saved["bonuses"]["paid_at"] is None


def test_a_response_without_an_amount_is_refused():
    entry = {"bulk_id": "b", "requested_total": 6.0, "response": {"total_amount": 800}}
    with pytest.raises(SystemExit, match="no readable amount"):
        session.check_setup_amount("bonuses", entry)


def test_max_each_defaults_to_a_whole_games_pay():
    assert session.MAX_EACH_DEFAULT == session.BASE_PAY + session.MAX_BONUS


def test_an_unfinished_pay_attempt_stops_everything():
    entry = {"bulk_id": "bulk1", "attempted_at": "2026-09-16T21:00:00", "paid_at": None}
    with pytest.raises(SystemExit, match="never"):
        session.check_unfinished_attempt("bonuses", entry)


def test_a_finished_payment_does_not_stop_anything():
    entry = {"bulk_id": "b", "attempted_at": "2026-09-16T21:00:00", "paid_at": "2026-09-16T21:00:02"}
    session.check_unfinished_attempt("bonuses", entry)


def test_the_attempt_is_recorded_before_the_call(tmp_path, monkeypatch):
    """A timeout after Prolific processed the payment must not look unpaid."""
    seen = {}

    def fake_request(method, path, token, *a, **k):
        seen["ledger_at_call_time"] = json.loads(session.ledger_path(tmp_path).read_text())
        return True, None, None

    monkeypatch.setattr(session, "request_api", fake_request)
    entry = {"bulk_id": "bulk1", "attempted_at": None, "paid_at": None}
    ledger = {"bonuses": entry}
    session.pay_bulk("token", tmp_path, "bonuses", entry, ledger)
    assert seen["ledger_at_call_time"]["bonuses"]["attempted_at"] is not None
    assert entry["paid_at"] is not None


def test_a_failed_pay_call_refuses_to_be_retried_blindly(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "request_api", lambda *a, **k: (False, None, "504: gateway"))
    entry = {"bulk_id": "bulk1", "attempted_at": None, "paid_at": None}
    with pytest.raises(SystemExit, match="DO NOT simply re-run"):
        session.pay_bulk("token", tmp_path, "bonuses", entry, {"bonuses": entry})
    saved = json.loads(session.ledger_path(tmp_path).read_text())
    assert saved["bonuses"]["attempted_at"] is not None
    assert saved["bonuses"]["paid_at"] is None


def test_already_paid_elsewhere_finds_an_earlier_runs_payment(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    runs = tmp_path / "data" / "runs"
    (runs / "run1").mkdir(parents=True)
    (runs / "run2").mkdir(parents=True)
    (runs / "run1" / "prolific_payments.json").write_text(json.dumps({
        "bonuses": {"paid_at": "2026-09-15T22:00:00", "participants_paid": ["alice", "bob"]}
    }))
    paid = session.already_paid_elsewhere("run2")
    assert paid == {"alice": "run1/bonuses", "bob": "run1/bonuses"}


def test_a_payment_only_set_up_does_not_count_as_paid(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    runs = tmp_path / "data" / "runs"
    (runs / "run1").mkdir(parents=True)
    (runs / "run1" / "prolific_payments.json").write_text(json.dumps({
        "bonuses": {"paid_at": None, "participants_paid": ["alice"]}
    }))
    assert session.already_paid_elsewhere("run2") == {}


# ------------------------------------------- pay: submission status filter


def submission(participant, status, code=None, **extra):
    return {
        "id": f"sub-{participant}",
        "participant_id": participant,
        "status": status,
        "study_code": code or session.PARTIAL_CODE,
        **extra,
    }


def test_statuses_are_normalized_across_spellings():
    assert session.norm_status("awaiting_review") == "AWAITING REVIEW"
    assert session.norm_status(" Returned ") == "RETURNED"
    assert session.norm_status(None) == ""


def test_only_returned_or_awaiting_review_submissions_are_paid():
    rows = [{"id": p, "amount": 3.0, "exit_reason": "group disbanded"}
            for p in ("ret", "wait", "appr", "rej", "active", "nobody")]
    by_participant = {
        "ret": submission("ret", "RETURNED"),
        "wait": submission("wait", "awaiting_review"),
        "appr": submission("appr", "APPROVED"),
        "rej": submission("rej", "REJECTED"),
        "active": submission("active", "ACTIVE"),
    }
    payable, skipped = session.payable_rows(rows, by_participant)
    assert [r["id"] for r in payable] == ["ret", "wait"]
    reasons = {row["id"]: why for row, why in skipped}
    assert reasons["appr"].startswith("APPROVED")
    assert "twice" in reasons["appr"]
    assert reasons["rej"].startswith("REJECTED")
    assert reasons["active"].startswith("ACTIVE")
    assert reasons["nobody"] == "no submission on this study"


def test_a_quiz_failure_row_is_never_paid():
    rows = [{"id": "q", "amount": 1.0, "exit_reason": "quiz failed"}]
    payable, skipped = session.payable_rows(rows, {"q": submission("q", "RETURNED")})
    assert payable == []
    assert "paid nothing by design" in skipped[0][1]


# ------------------------------------------ pay: ledger versus current rows


def ledger_entry(rows, **over):
    entry = {
        "bulk_id": "bulk1",
        "participants_paid": [r["id"] for r in rows],
        "amounts": {r["id"]: r["amount"] for r in rows},
        "requested_total": round(sum(r["amount"] for r in rows), 2),
        "response": {"amount": round(sum(r["amount"] for r in rows) * 100), "total_amount": 1000},
        "attempted_at": None,
        "paid_at": None,
    }
    entry.update(over)
    return entry


ROWS = [{"id": "alice", "amount": 4.5}, {"id": "bob", "amount": 3.0}]


def test_unchanged_rows_match_their_ledger_entry():
    session.check_rows_match_ledger("early", ledger_entry(ROWS), ROWS)


def test_a_row_that_appeared_since_set_up_is_refused():
    with pytest.raises(SystemExit, match="not in the bulk payment: carol"):
        session.check_rows_match_ledger(
            "early", ledger_entry(ROWS), ROWS + [{"id": "carol", "amount": 1.0}]
        )


def test_a_row_that_disappeared_since_set_up_is_refused():
    """Someone approved between set-up and pay drops out of the payable rows."""
    with pytest.raises(SystemExit, match="no longer to be paid: bob"):
        session.check_rows_match_ledger("early", ledger_entry(ROWS), ROWS[:1])


def test_a_changed_amount_is_refused():
    changed = [{"id": "alice", "amount": 4.5}, {"id": "bob", "amount": 3.5}]
    with pytest.raises(SystemExit, match=r"bob: \$3.00 set up, \$3.50 now"):
        session.check_rows_match_ledger("early", ledger_entry(ROWS), changed)


def test_a_ledger_without_per_person_amounts_compares_the_total():
    entry = ledger_entry(ROWS)
    del entry["amounts"]
    session.check_rows_match_ledger("early", entry, ROWS)
    changed = [{"id": "alice", "amount": 4.5}, {"id": "bob", "amount": 3.5}]
    with pytest.raises(SystemExit, match=r"total \$7.50 set up, \$8.00 now"):
        session.check_rows_match_ledger("early", entry, changed)


# ------------------------------------------------------------ pay: budget


def test_no_budget_means_no_check():
    assert session.check_session_budget(None, 500.0, 500.0, args()) is True


def test_a_payment_within_budget_proceeds():
    assert session.check_session_budget(800.0, 500.0, 250.0, args()) is True


def test_a_payment_over_budget_is_refused():
    with pytest.raises(SystemExit, match=r"over its budget of \$800.00"):
        session.check_session_budget(800.0, 500.0, 350.0, args(force_budget=False))


def test_force_budget_asks_again_and_then_proceeds():
    assert session.check_session_budget(800.0, 500.0, 350.0, args(force_budget=True, yes=True))


def test_spend_so_far_counts_only_paid_populations():
    ledgers = [{
        "bonuses": {"bulk_id": "a", "paid_at": "t", "requested_total": 10.0,
                    "response": {"total_amount": 1330}},
        "early": {"bulk_id": "b", "paid_at": None, "requested_total": 5.0,
                  "response": {"total_amount": 665}},
        "lobby": {"bulk_id": "c", "paid_at": "t", "requested_total": 4.0, "response": {}},
        "notes_sent": {"alice": "t"},
    }]
    assert session.paid_so_far(ledgers) == 13.30 + 4.0


# ------------------------------------------------- pay: end to end, mocked


def pay_args(**over):
    fields = dict(
        session=None, study="study1", run="run1", skip_lobby=True,
        max_each=session.MAX_EACH_DEFAULT, max_total=None, force_budget=False,
        reason=None, note_file=None, yes=True,
    )
    fields.update(over)
    return SimpleNamespace(**fields)


class FakeProlific:
    """Enough of the API for `pay`: bulk payments echo the amount they were asked for."""

    def __init__(self, submissions, fail_message_for=None):
        self.submissions = submissions
        self.calls = []
        self.fail_message_for = fail_message_for

    def paged(self, path, token, params=None):
        return iter(self.submissions)

    def api(self, method, path, token, payload=None, params=None, retries=0):
        self.calls.append((method, path, payload))
        if path == "/submissions/bonus-payments/":
            cents = round(sum(float(line.split(",")[1]) for line in payload["csv_bonuses"].splitlines()) * 100)
            return {"id": f"bulk{len(self.calls)}", "amount": cents, "total_amount": round(cents * 1.33)}
        if path == "/messages/" and payload["participant_id"] == self.fail_message_for:
            sys.exit("simulated failure")
        return {}

    def request_api(self, method, path, token, payload=None, params=None, retries=0):
        self.calls.append((method, path, payload))
        return True, None, None

    def messaged(self):
        return [c[2]["participant_id"] for c in self.calls if c[1] == "/messages/"]

    def return_requests(self):
        return [c[1] for c in self.calls if c[1].endswith("/request-return/")]


def install(monkeypatch, tmp_path, prolific):
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / ".sessions")
    monkeypatch.setattr(session, "paged", prolific.paged)
    monkeypatch.setattr(session, "api", prolific.api)
    monkeypatch.setattr(session, "request_api", prolific.request_api)
    run = tmp_path / "data" / "runs" / "run1"
    run.mkdir(parents=True)
    (run / "early_ended.csv").write_text(
        "prolific_id,partial_pay,exit_reason\n"
        "alice,4.50,group disbanded\n"
        "bob,3.00,low accuracy\n"
        "carol,2.00,player timeout\n"
    )
    return run


THREE_REMOVED = [
    submission("alice", "RETURNED"),
    submission("bob", "APPROVED"),
    submission("carol", "awaiting_review"),
]


def test_pay_skips_the_approved_and_notes_each_person_once(tmp_path, monkeypatch):
    prolific = FakeProlific(THREE_REMOVED)
    run = install(monkeypatch, tmp_path, prolific)

    session.cmd_pay(pay_args(), "token")

    ledger = json.loads((run / "prolific_payments.json").read_text())
    assert ledger["early"]["participants_paid"] == ["alice", "carol"]
    assert ledger["early"]["paid_at"]
    assert set(ledger["notes_sent"]) == {"alice", "carol"}
    assert sorted(prolific.messaged()) == ["alice", "carol"]
    # alice had already returned; carol is asked to.
    assert prolific.return_requests() == ["/submissions/sub-carol/request-return/"]

    prolific.calls.clear()
    session.cmd_pay(pay_args(), "token")
    assert prolific.messaged() == []
    assert not [c for c in prolific.calls if c[1] == "/submissions/bonus-payments/"]
    assert not [c for c in prolific.calls if c[1].endswith("/pay/")]


def test_a_note_that_failed_part_way_is_the_only_one_resent(tmp_path, monkeypatch):
    prolific = FakeProlific(THREE_REMOVED, fail_message_for="carol")
    run = install(monkeypatch, tmp_path, prolific)
    with pytest.raises(SystemExit, match="simulated failure"):
        session.cmd_pay(pay_args(), "token")
    ledger = json.loads((run / "prolific_payments.json").read_text())
    assert set(ledger["notes_sent"]) == {"alice"}

    prolific.fail_message_for = None
    prolific.calls.clear()
    session.cmd_pay(pay_args(), "token")
    assert prolific.messaged() == ["carol"]


def test_rows_that_changed_after_set_up_stop_the_payment(tmp_path, monkeypatch):
    prolific = FakeProlific(THREE_REMOVED)
    run = install(monkeypatch, tmp_path, prolific)
    answers = iter([True, False])  # set up, then decline to pay
    monkeypatch.setattr(session, "confirm", lambda question, args: next(answers))
    session.cmd_pay(pay_args(), "token")
    ledger = json.loads((run / "prolific_payments.json").read_text())
    assert ledger["early"]["paid_at"] is None

    (run / "early_ended.csv").write_text(
        "prolific_id,partial_pay,exit_reason\nalice,4.50,group disbanded\ncarol,2.50,player timeout\n"
    )
    monkeypatch.setattr(session, "confirm", lambda question, args: True)
    with pytest.raises(SystemExit, match=r"carol: \$2.00 set up, \$2.50 now"):
        session.cmd_pay(pay_args(), "token")
    assert not [c for c in prolific.calls if c[1].endswith("/pay/")]


def test_a_session_budget_stops_a_payment_that_exceeds_it(tmp_path, monkeypatch):
    prolific = FakeProlific(THREE_REMOVED)
    install(monkeypatch, tmp_path, prolific)
    session.write_session("s1", condition="refer_mixed", tangram_set="0", budget_usd=5.0)
    with pytest.raises(SystemExit, match="over its budget"):
        session.cmd_pay(pay_args(session="s1"), "token")
    assert not [c for c in prolific.calls if c[1].endswith("/pay/")]


def test_force_budget_lets_a_confirmed_overrun_through(tmp_path, monkeypatch):
    prolific = FakeProlific(THREE_REMOVED)
    run = install(monkeypatch, tmp_path, prolific)
    session.write_session("s1", condition="refer_mixed", tangram_set="0", budget_usd=5.0)
    session.cmd_pay(pay_args(session="s1", force_budget=True), "token")
    ledger = json.loads((run / "prolific_payments.json").read_text())
    assert ledger["early"]["paid_at"]


# --------------------------------------------------------------------- tally


GAMES_CSV = (
    "gameId,condition,tangramSet,numPlayers,ended,endedReason\n"
    "g1,refer_mixed,0.0,9,True,end of game\n"
    "g2,refer_separated,0.0,9,True,end of game\n"
    "g3,refer_separated,1.0,9,True,end of game\n"
    "g4,social_first,1.0,9,True,all players removed\n"
)


def test_tally_counts_complete_games_per_cell_and_marks_the_emptiest(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / ".sessions")
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    session.write_session("s1", condition="social_mixed", tangram_set="1")
    counts, emptiest = session.print_tally("full")
    assert counts[("refer_separated", "0")]["games"] == 1
    assert counts[("refer_separated", "1")]["games"] == 1
    assert counts[("social_first", "1")] == {"games": 0, "incomplete": 1, "sessions": 0, "pending": 0}
    assert counts[("social_mixed", "1")]["sessions"] == 1
    assert counts[("social_mixed", "1")]["pending"] == 1
    assert len(counts) == 8
    # No complete games in refer_mixed set 1, social_mixed set 0/1, social_first
    # set 0/1; the pending session breaks the tie against social_mixed set 1,
    # and conditions order breaks the rest.
    assert emptiest == ("refer_mixed", "1")


def test_tally_lines_mark_exactly_one_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / ".sessions")
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    counts, emptiest = session.cell_counts(
        session.read_games_table(tmp_path / "data" / "full" / "games.csv"), {}
    )
    lines = session.tally_lines(counts, emptiest)
    assert len(lines) == 9
    assert sum("<- emptiest" in line for line in lines) == 1
    assert any(line.startswith("  refer_mixed") and "1" in line and "<- emptiest" in line
               for line in lines)


def test_tally_without_games_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / ".sessions")
    assert session.print_tally("full") is None
    assert "no games yet" in capsys.readouterr().out


def test_tally_without_games_still_shows_saved_sessions(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / ".sessions")
    session.write_session("s1", condition="refer_mixed", tangram_set="0")
    counts, emptiest = session.print_tally("full")
    assert counts[("refer_mixed", "0")]["sessions"] == 1
    assert emptiest != ("refer_mixed", "0")
    assert "no games yet" in capsys.readouterr().out


def test_tangram_set_labels_agree_across_spellings():
    assert session.tangram_set_label("0.0") == session.tangram_set_label(0) == "0"
    assert session.tangram_set_label("1") == "1"
    assert session.tangram_set_label("") == "?"


# ------------------------------------------------ pay: run versus session


def write_run_games(run, games, meta_games=None):
    (run / "raw").mkdir(parents=True, exist_ok=True)
    (run / "raw" / "game.csv").write_text(
        "id,condition,tangram_set\n" + "".join(f"{g},{c},{s}\n" for g, c, s in games)
    )
    meta = {"batch": "b1", "games": meta_games or [g for g, _, _ in games]}
    (run / "run_meta.json").write_text(json.dumps(meta))
    return meta


def test_a_run_matching_the_session_treatment_is_quiet(tmp_path, capsys):
    run = tmp_path / "run1"
    meta = write_run_games(run, [("g1", "refer_mixed", "0"), ("g2", "refer_mixed", "0.0")])
    session.check_run_treatment(run, meta, {"condition": "refer_mixed", "tangram_set": "0"})
    assert "WARNING" not in capsys.readouterr().out


def test_a_run_with_another_treatment_is_flagged(tmp_path, capsys):
    run = tmp_path / "run1"
    meta = write_run_games(run, [("g1", "social_mixed", "1")])
    session.check_run_treatment(run, meta, {"condition": "refer_mixed", "tangram_set": "0"})
    out = capsys.readouterr().out
    assert "condition social_mixed, but the session was set up for refer_mixed" in out
    assert "tangram set 1, but the session was set up for 0" in out


def test_only_the_batchs_games_are_compared(tmp_path, capsys):
    """A cumulative export carries earlier sessions' games; run_meta.json scopes them out."""
    run = tmp_path / "run1"
    meta = write_run_games(
        run, [("old", "social_mixed", "1"), ("g1", "refer_mixed", "0")], meta_games=["g1"]
    )
    session.check_run_treatment(run, meta, {"condition": "refer_mixed", "tangram_set": "0"})
    assert "WARNING" not in capsys.readouterr().out


# ------------------------------------------------------- wording and notes


def test_others_left_reasons_get_the_blameless_note():
    for reason in session.OTHERS_LEFT_REASONS:
        out = session.wording_for(reason, args())
        assert out["name"] == "others-left"
        assert "Nothing went wrong on your end" in out["note"]


def test_neutral_reasons_do_not_spell_out_why():
    out = session.wording_for("low accuracy", args())
    assert out["name"] == "neutral"
    assert "accuracy" not in out["note"].lower()


def test_the_new_server_reasons_get_the_blameless_note():
    for reason in ("insufficient groups", "game terminated"):
        assert reason in session.SERVER_EXIT_REASONS
        assert "Nothing went wrong on your end" in session.wording_for(reason, args())["note"]
    assert session.wording_for("insufficient groups", args())["name"] == "others-left"


def test_a_stopped_batch_gets_its_own_note_not_the_others_left_one():
    out = session.wording_for("Game Terminated", args())
    assert out["name"] == "stopped"
    assert "stop this session early" in out["note"]
    assert "other players" not in out["note"].lower()
    assert "{amount}" in out["note"]


def test_idle_removals_get_their_own_plain_note():
    out = session.wording_for("Player Timeout", args())
    assert out["name"] == "inactive"
    note = out["note"]
    assert "without a response" in note
    assert "not included" in note
    assert "{amount}" in note
    assert "return the submission" in note
    for blame in ("your fault", "you failed", "inactive", "idle"):
        assert blame not in note.lower()
    assert "without a response" in out["reason"]


def test_a_quiz_failure_would_fall_back_to_neutral_wording():
    assert session.wording_for("quiz failed", args())["name"] == "neutral"


def test_lobby_timeouts_get_their_own_note():
    out = session.wording_for(session.LOBBY_TIMEOUT_REASON, args())
    assert out["name"] == "lobby"
    assert "{amount}" in out["note"]
    assert "still eligible" in out["note"]


def test_every_note_template_takes_an_amount():
    for reason in list(session.KNOWN_EXIT_REASONS) + [session.LOBBY_TIMEOUT_REASON]:
        assert "{amount}" in session.wording_for(reason, args())["note"]


# ---------------------------------------------------------------- retiming


def survey_sections(title):
    return [{"id": "s", "questions": [{"id": "q", "title": title, "answers": [{"id": "a"}]}]}]


def test_retiming_returns_the_time_it_replaced():
    sections = survey_sections("Are you available at 8:30pm ET to participate in a study?")
    _, changed, old_time = session.retime_sections(sections, "9pm ET")
    assert old_time == "8:30pm ET"
    assert "9pm ET" in changed[0]


def test_retiming_without_an_availability_question_stops():
    with pytest.raises(SystemExit, match="Could not find an availability question"):
        session.retime_sections(survey_sections("Do you have a desktop computer?"), "9pm ET")


def test_retiming_gives_every_copied_element_a_fresh_id():
    sections = survey_sections("Are you available at 8:30pm ET to participate in a study?")
    new, _, _ = session.retime_sections(sections, "9pm ET")
    assert new[0]["id"] != "s"
    assert new[0]["questions"][0]["id"] != "q"
    assert new[0]["questions"][0]["answers"][0]["id"] != "a"


def test_leftover_times_catches_a_stale_mention():
    assert session.leftover_times("Starts at 8:30pm sharp", "9pm ET") == ["8:30pm"]


def test_leftover_times_ignores_the_new_time():
    assert session.leftover_times("Starts at 9 pm, that is 9pm ET", "9pm ET") == []


def test_retime_text_replaces_every_mention():
    text, count = session.retime_text("At 8:30pm ET. Again: 8:30pm ET.", "8:30pm ET", "9pm ET")
    assert count == 2
    assert "8:30pm" not in text


# ------------------------------------------------------- completion codes


def test_only_the_codes_that_saw_the_task_join_the_blocklist():
    codes = [{"code": c} for c in session.PROLIFIC_CODES.values()]
    updated = session.with_group_action(codes, "group1")
    joined = {
        c["code"] for c in updated
        if any(a.get("action") == "ADD_TO_PARTICIPANT_GROUP" for a in c.get("actions", []))
    }
    assert joined == session.PLAYED_CODES
    assert session.LOBBY_TIMEOUT_CODE not in joined


def test_reapplying_the_group_action_does_not_duplicate_it():
    codes = [{"code": session.FINISHED_CODE}]
    once = session.with_group_action(codes, "group1")
    twice = session.with_group_action(once, "group2")
    actions = twice[0]["actions"]
    assert len(actions) == 1
    assert actions[0]["participant_group"] == "group2"


def good_codes(**actions_by_key):
    """Completion codes carrying the actions the experiment needs, with overrides per key."""
    defaults = {
        "completion": ["MANUALLY_REVIEW", "ADD_TO_PARTICIPANT_GROUP"],
        "partial": ["REQUEST_RETURN", "ADD_TO_PARTICIPANT_GROUP"],
        "lobbyTimeout": ["REQUEST_RETURN"],
    }
    defaults.update(actions_by_key)
    return [
        {"code": session.PROLIFIC_CODES[key], "actions": [{"action": a} for a in actions]}
        for key, actions in defaults.items()
    ]


def good_template(**over):
    payload = {"reward": int(session.BASE_PAY * 100), "completion_codes": good_codes()}
    payload.update(over)
    return payload


def test_template_drift_in_the_reward_is_refused():
    with pytest.raises(SystemExit, match="reward is 1500"):
        session.check_game_template(good_template(reward=1500), allow_mismatch=False)


def test_template_drift_in_the_codes_is_refused():
    payload = good_template(completion_codes=[{"code": "XXXX"}])
    with pytest.raises(SystemExit, match="completion codes"):
        session.check_game_template(payload, allow_mismatch=False)


def test_a_matching_template_passes():
    session.check_game_template(good_template(), allow_mismatch=False)


def test_a_finished_code_that_approves_itself_is_refused():
    codes = good_codes(completion=["AUTOMATICALLY_APPROVE", "ADD_TO_PARTICIPANT_GROUP"])
    with pytest.raises(SystemExit, match=f"code {session.FINISHED_CODE} .*carries AUTOMATICALLY_APPROVE"):
        session.check_game_template(good_template(completion_codes=codes), allow_mismatch=False)


def test_a_partial_code_without_a_return_request_is_refused():
    codes = good_codes(partial=["ADD_TO_PARTICIPANT_GROUP"])
    with pytest.raises(SystemExit, match=f"code {session.PARTIAL_CODE} .*lacks REQUEST_RETURN"):
        session.check_game_template(good_template(completion_codes=codes), allow_mismatch=False)


def test_a_lobby_code_without_a_return_request_is_refused():
    codes = good_codes(lobbyTimeout=[])
    with pytest.raises(SystemExit, match=f"code {session.LOBBY_TIMEOUT_CODE} .*lacks REQUEST_RETURN"):
        session.check_game_template(good_template(completion_codes=codes), allow_mismatch=False)


def test_played_codes_must_join_the_blocklist_group():
    codes = good_codes(completion=["MANUALLY_REVIEW"], partial=["REQUEST_RETURN"])
    with pytest.raises(SystemExit) as caught:
        session.check_game_template(good_template(completion_codes=codes), allow_mismatch=False)
    message = str(caught.value)
    assert f"code {session.FINISHED_CODE} (completion) lacks ADD_TO_PARTICIPANT_GROUP" in message
    assert f"code {session.PARTIAL_CODE} (partial) lacks ADD_TO_PARTICIPANT_GROUP" in message


def test_a_lobby_code_need_not_join_the_blocklist():
    """Lobby timeouts stay eligible, so their code carrying no group action is correct."""
    session.check_game_template(good_template(), allow_mismatch=False)


def test_the_setup_pipeline_produces_codes_the_check_accepts():
    """with_group_action on a template with the return actions satisfies check_game_template."""
    codes = good_codes(completion=["MANUALLY_REVIEW"], partial=["REQUEST_RETURN"])
    payload = good_template(completion_codes=session.with_group_action(codes, "group1"))
    session.check_game_template(payload, allow_mismatch=False)


# ------------------------------------------------- study transitions and allowlist


class StudyApi:
    """A fake Prolific for one study: records calls, serves the study on GET."""

    def __init__(self, study, post_result=(False, None, "400: already active")):
        self.study = study
        self.post_result = post_result
        self.calls = []

    def request_api(self, method, path, token, payload=None, params=None, retries=0):
        self.calls.append((method, path, payload))
        return self.post_result

    def api(self, method, path, token, payload=None, params=None, retries=0):
        self.calls.append((method, path, payload))
        return self.study if method == "GET" else {}


def test_a_refused_publish_counts_when_the_study_is_already_active(monkeypatch):
    fake = StudyApi({"status": "ACTIVE"})
    monkeypatch.setattr(session, "request_api", fake.request_api)
    monkeypatch.setattr(session, "api", fake.api)
    ok, error = session.transition_study("token", "s1", "PUBLISH", retries=2)
    assert ok and error is None
    assert [c[0] for c in fake.calls] == ["POST", "GET"]


def test_a_refused_publish_is_a_failure_when_the_study_is_still_unpublished(monkeypatch):
    fake = StudyApi({"status": "UNPUBLISHED"})
    monkeypatch.setattr(session, "request_api", fake.request_api)
    monkeypatch.setattr(session, "api", fake.api)
    ok, error = session.transition_study("token", "s1", "PUBLISH")
    assert not ok
    assert "400" in error


def test_a_successful_transition_does_not_fetch_the_study(monkeypatch):
    fake = StudyApi({"status": "UNPUBLISHED"}, post_result=(True, {}, None))
    monkeypatch.setattr(session, "request_api", fake.request_api)
    monkeypatch.setattr(session, "api", fake.api)
    assert session.transition_study("token", "s1", "PUBLISH") == (True, None)
    assert [c[0] for c in fake.calls] == ["POST"]


def test_an_already_allowlisted_study_is_not_patched(monkeypatch, capsys):
    fake = StudyApi({
        "status": "ACTIVE",
        "filters": [{"filter_id": "participant_group_allowlist", "selected_values": ["g1"]}],
    })
    monkeypatch.setattr(session, "api", fake.api)
    session.set_study_allowlist("token", "s1", "g1")
    assert [c[0] for c in fake.calls] == ["GET"]
    assert "already allowlisted" in capsys.readouterr().out


def test_a_different_allowlist_on_a_draft_is_replaced(monkeypatch):
    fake = StudyApi({
        "status": "UNPUBLISHED",
        "filters": [{"filter_id": "participant_group_allowlist", "selected_values": ["old"]}],
    })
    monkeypatch.setattr(session, "api", fake.api)
    session.set_study_allowlist("token", "s1", "g1")
    patch = next(c for c in fake.calls if c[0] == "PATCH")
    assert patch[2]["filters"] == [
        {"filter_id": "participant_group_allowlist", "selected_values": ["g1"]}
    ]


# ------------------------------------------------------- approve and close


def test_approve_says_when_there_is_no_run_to_cross_check(monkeypatch, capsys):
    monkeypatch.setattr(session, "newest_run", lambda: None)
    monkeypatch.setattr(session, "paged", lambda *a, **k: iter([]))
    monkeypatch.delenv("DATASET", raising=False)
    session.cmd_approve(SimpleNamespace(study_id="s1", session=None, run=None, yes=True), "token")
    out = capsys.readouterr().out
    assert "no run to cross-check against (no data/full/runs.txt yet)" in out


def test_close_approves_only_the_screening_submissions_awaiting_review(monkeypatch):
    fake = StudyApi({"status": "ACTIVE", "reward": 30, "name": "Screening"},
                    post_result=(True, {}, None))
    monkeypatch.setattr(session, "request_api", fake.request_api)
    monkeypatch.setattr(session, "api", fake.api)
    monkeypatch.setattr(session, "paged", lambda *a, **k: iter([
        {"id": "a", "status": "AWAITING REVIEW"},
        {"id": "b", "status": "awaiting_review"},
        {"id": "c", "status": "APPROVED"},
        {"id": "d", "status": "RETURNED"},
    ]))
    session.cmd_close(SimpleNamespace(study_id="s1", session=None, yes=True), "token")
    transitions = [(c[1], c[2]) for c in fake.calls if c[0] == "POST"]
    assert transitions == [
        ("/studies/s1/transition/", {"action": "STOP"}),
        ("/submissions/a/transition/", {"action": "APPROVE"}),
        ("/submissions/b/transition/", {"action": "APPROVE"}),
    ]


def test_close_on_a_stopped_study_still_approves(monkeypatch, capsys):
    fake = StudyApi({"status": "AWAITING REVIEW", "reward": 30, "name": "Screening"})
    monkeypatch.setattr(session, "request_api", fake.request_api)
    monkeypatch.setattr(session, "api", fake.api)
    monkeypatch.setattr(session, "paged", lambda *a, **k: iter([{"id": "a", "status": "AWAITING REVIEW"}]))
    session.cmd_close(SimpleNamespace(study_id="s1", session=None, yes=True), "token")
    posts = [(c[1], c[2]) for c in fake.calls if c[0] == "POST"]
    assert posts == [("/submissions/a/transition/", {"action": "APPROVE"})]
    assert "nothing to stop" in capsys.readouterr().out


# -------------------------------------------------------- publish timing


ANNOUNCED = "6pm PT / 9pm ET"


def at_noon_pacific():
    import datetime
    from zoneinfo import ZoneInfo

    return datetime.datetime(2026, 9, 16, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


def test_either_half_of_the_announced_time_resolves_to_the_same_instant():
    eastern, _ = session.resolve_publish_time("21:00", ANNOUNCED, now=at_noon_pacific())
    pacific, _ = session.resolve_publish_time("18:00", ANNOUNCED, now=at_noon_pacific())
    assert eastern == pacific


def test_a_time_that_contradicts_the_announcement_is_refused():
    """The bug: --at was naive local time while participants were told PT/ET."""
    with pytest.raises(SystemExit, match="gap of"):
        session.resolve_publish_time("20:00", ANNOUNCED, now=at_noon_pacific())


def test_force_time_allows_a_deliberate_gap():
    target, lines = session.resolve_publish_time(
        "20:00", ANNOUNCED, force=True, now=at_noon_pacific()
    )
    assert target is not None
    assert any("WARNING" in line for line in lines)


def test_an_explicit_timezone_is_honored():
    target, _ = session.resolve_publish_time("21:00 ET", ANNOUNCED, now=at_noon_pacific())
    assert target.hour == 21


def test_a_time_already_past_is_refused():
    import datetime
    from zoneinfo import ZoneInfo

    after_the_session = datetime.datetime(
        2026, 9, 16, 22, 0, tzinfo=ZoneInfo("America/New_York")
    )
    with pytest.raises(SystemExit, match="already past"):
        session.resolve_publish_time("21:00", ANNOUNCED, now=after_the_session)


def test_no_at_warns_that_publishing_now_is_early():
    target, lines = session.resolve_publish_time(None, ANNOUNCED, now=at_noon_pacific())
    assert target is None
    assert any("before the announced" in line for line in lines)


def test_an_unparseable_clock_is_refused():
    with pytest.raises(SystemExit, match="24-hour clock"):
        session.parse_clock("9pm")


def test_an_unknown_timezone_is_refused():
    with pytest.raises(SystemExit, match="neither an IANA zone"):
        session.parse_clock("21:00 XYZ")


def test_announced_times_are_parsed_out_of_the_wording():
    found = session.parse_announced_times(ANNOUNCED)
    assert [(h, z) for h, _, z, _ in found] == [
        (18, "America/Los_Angeles"),
        (21, "America/New_York"),
    ]


# ------------------------------------------------------------ batch scoping


def write_export(tmp_path, games, players):
    """A minimal Empirica export: several batches, as a cumulative one has."""
    pd.DataFrame(games).to_csv(tmp_path / "game.csv", index=False)
    pd.DataFrame(players).to_csv(tmp_path / "player.csv", index=False)
    pd.DataFrame(
        [{"id": b, "configLastChangedAt": f"2026-09-{10 + i:02d}T20:00:00"}
         for i, b in enumerate(sorted({g["batchID"] for g in games}))]
    ).to_csv(tmp_path / "batch.csv", index=False)


TWO_SESSIONS = dict(
    games=[
        {"id": "g1", "condition": "refer_mixed", "batchID": "batchA"},
        {"id": "g2", "condition": "social_mixed", "batchID": "batchB"},
    ],
    players=[
        {"gameID": "g1", "is_active": True, "participantIdentifier": "old1", "bonus": 5.0,
         "partialPay": 0, "exitReason": ""},
        {"gameID": "g2", "is_active": True, "participantIdentifier": "new1", "bonus": 6.0,
         "partialPay": 0, "exitReason": ""},
        {"gameID": "g2", "is_active": False, "participantIdentifier": "new2", "bonus": 0,
         "partialPay": 4.0, "exitReason": "group disbanded"},
    ],
)


def test_the_newest_batch_is_chosen_from_a_cumulative_export(tmp_path):
    write_export(tmp_path, **TWO_SESSIONS)
    games = pd.read_csv(tmp_path / "game.csv")
    batches = pd.read_csv(tmp_path / "batch.csv")
    assert resolve_batch(games, batches, None)[0] == "batchB"


def test_an_earlier_sessions_players_are_not_written_for_payment(tmp_path):
    """The bug: exports are cumulative, so run 2 paid run 1's finishers again."""
    write_export(tmp_path, **TWO_SESSIONS)
    out = tmp_path / "out"
    scope = extract_bonuses(tmp_path, out)
    paid = set(pd.read_csv(out / "bonuses.csv")["prolific_id"])
    assert paid == {"new1"}
    assert "old1" not in paid
    assert scope["batch"] == "batchB"
    early = pd.read_csv(out / "early_ended.csv")
    assert list(early["prolific_id"]) == ["new2"]
    assert list(early["exit_reason"]) == ["group disbanded"]


def test_an_explicit_batch_can_be_paid(tmp_path):
    write_export(tmp_path, **TWO_SESSIONS)
    out = tmp_path / "out"
    extract_bonuses(tmp_path, out, batch="batchA")
    assert set(pd.read_csv(out / "bonuses.csv")["prolific_id"]) == {"old1"}


def test_all_batches_is_available_when_it_is_really_wanted(tmp_path):
    write_export(tmp_path, **TWO_SESSIONS)
    out = tmp_path / "out"
    extract_bonuses(tmp_path, out, all_batches=True)
    assert set(pd.read_csv(out / "bonuses.csv")["prolific_id"]) == {"old1", "new1"}


def test_an_unknown_batch_is_refused(tmp_path):
    write_export(tmp_path, **TWO_SESSIONS)
    with pytest.raises(SystemExit):
        extract_bonuses(tmp_path, tmp_path / "out", batch="nope")


# ------------------------------------------------------------ lobby payment


def test_lobby_timeout_rows_pay_the_advertised_amount(monkeypatch):
    submissions = [
        {"participant_id": "a", "study_code": session.LOBBY_TIMEOUT_CODE},
        {"participant_id": "b", "study_code": session.LOBBY_TIMEOUT_CODE + "."},
        {"participant_id": "c", "study_code": session.FINISHED_CODE},
        {"participant_id": "a", "study_code": session.LOBBY_TIMEOUT_CODE},
    ]
    monkeypatch.setattr(session, "paged", lambda *a, **k: iter(submissions))
    rows = session.lobby_timeout_rows("token", "study")
    assert [r["id"] for r in rows] == ["a", "b"]
    assert {r["amount"] for r in rows} == {session.LOBBY_TIMEOUT_PAY}
    assert {r["exit_reason"] for r in rows} == {session.LOBBY_TIMEOUT_REASON}


# --------------------------------------------------------------- pagination


def paging_api(pages):
    """A fake `api` serving `pages` by offset and recording the offsets asked for."""
    asked = []

    def fake_api(method, path, token, payload=None, params=None, retries=0):
        asked.append(params["offset"])
        index = params["offset"] // session.PAGE_SIZE
        return pages[index] if index < len(pages) else {"results": [], "meta": {}}

    return fake_api, asked


def rows(start, n):
    return [{"id": f"r{i}"} for i in range(start, start + n)]


def test_paging_follows_the_count_across_pages(monkeypatch):
    full = session.PAGE_SIZE
    fake, asked = paging_api([
        {"results": rows(0, full), "meta": {"count": full + 5}},
        {"results": rows(full, 5), "meta": {"count": full + 5}},
    ])
    monkeypatch.setattr(session, "api", fake)
    assert len(list(session.paged("/x/", "token"))) == full + 5
    assert asked == [0, full]


def test_a_short_page_with_no_meta_is_the_last_one(monkeypatch):
    fake, asked = paging_api([{"results": rows(0, 7)}])
    monkeypatch.setattr(session, "api", fake)
    assert len(list(session.paged("/x/", "token"))) == 7
    assert asked == [0]


def test_a_full_page_with_no_meta_keeps_paging(monkeypatch):
    """The bug: a missing count used to stop after the first hundred submissions."""
    full = session.PAGE_SIZE
    fake, asked = paging_api([
        {"results": rows(0, full)},
        {"results": rows(full, full)},
        {"results": rows(2 * full, 3)},
    ])
    monkeypatch.setattr(session, "api", fake)
    assert len(list(session.paged("/x/", "token"))) == 2 * full + 3
    assert asked == [0, full, 2 * full]


def test_a_bare_list_endpoint_is_paged_by_length(monkeypatch):
    full = session.PAGE_SIZE
    fake, _ = paging_api([rows(0, full), rows(full, 2)])
    monkeypatch.setattr(session, "api", fake)
    assert len(list(session.paged("/x/", "token"))) == full + 2


def test_a_full_page_under_a_meta_without_a_count_fails_loudly(monkeypatch):
    fake, _ = paging_api([{"results": rows(0, session.PAGE_SIZE), "meta": {"page": 1}}])
    monkeypatch.setattr(session, "api", fake)
    with pytest.raises(SystemExit, match=r"GET /studies/s/submissions/ .*neither `total` nor `count`"):
        list(session.paged("/studies/s/submissions/", "token"))


def test_an_endpoint_that_ignores_offset_is_caught(monkeypatch):
    same = rows(0, session.PAGE_SIZE)
    fake, _ = paging_api([{"results": same}, {"results": same}, {"results": same}])
    monkeypatch.setattr(session, "api", fake)
    with pytest.raises(SystemExit, match="same page twice"):
        list(session.paged("/x/", "token"))


# ---------------------------------------------------- setup: end to end, mocked


class FakeSetupApi:
    """The template survey, its study, a template game study and the blocklist group."""

    def __init__(self, fail_on_game_study=False):
        self.calls = []
        self.fail_on_game_study = fail_on_game_study
        self.listings = {
            "/surveys/": [{"_id": "sv0", "date_created": "2026-09-01",
                           "title": "Screening survey: Group communication game [starts 8:30pm ET]"}],
            "/studies/": [
                {"id": "st0", "name": "Screening survey: Group communication game [starts 8:30pm ET]",
                 "external_study_url": "https://prolific.com/surveys/sv0", "date_created": "2026-09-01"},
                {"id": "g0", "name": session.GAME_STUDY_NAME, "date_created": "2026-09-01"},
            ],
            "/workspaces/": [{"id": "w1"}],
            "/participant-groups/": [{"id": "grp", "name": session.BLOCKLIST_GROUP_NAME,
                                      "participant_count": 5}],
        }
        self.details = {
            "/users/me/": {"id": "r1"},
            "/surveys/sv0": {"sections": survey_sections(
                "Are you available at 8:30pm ET to participate in a study?")},
            "/studies/st0/": {"id": "st0", "description": "Starts at 8:30pm ET.", "reward": 30,
                              "estimated_completion_time": 1, "privacy_notice": "notice",
                              "filters": [{"filter_id": "current_country_of_residence",
                                           "selected_values": ["1"]}],
                              "completion_codes": [{"code": "COMPLETED"}]},
            "/studies/g0/": {"id": "g0", "name": session.GAME_STUDY_NAME,
                             "description": "The game starts at 8:30pm ET.", "reward": 1200,
                             "estimated_completion_time": 50, "project": "p1",
                             "external_study_url": "https://x.test/?PROLIFIC_PID={{%PROLIFIC_PID%}}",
                             "completion_codes": good_codes(completion=["MANUALLY_REVIEW"],
                                                            partial=["REQUEST_RETURN"])},
        }

    def paged(self, path, token, params=None):
        return iter(self.listings[path])

    def api(self, method, path, token, payload=None, params=None, retries=0):
        self.calls.append((method, path, payload))
        if method == "GET":
            return self.details[path]
        if path == "/surveys/":
            return {"_id": "sv1"}
        if path == "/studies/":
            posted = sum(1 for c in self.calls if c[:2] == ("POST", "/studies/"))
            if posted == 2 and self.fail_on_game_study:
                sys.exit("simulated failure creating the game study")
            return {"id": f"st{posted}", "status": "UNPUBLISHED"}
        return {}


def setup_args(**over):
    fields = dict(
        session="s1", time="6pm PT / 9pm ET", title_time="9pm ET", condition="refer_mixed",
        set="0", places=9, survey_places=20, budget=None, blocklist_group=None,
        template_survey=None, template_study=None, study_name=session.GAME_STUDY_NAME,
        internal_name=None, workspace=None, rehearsal=None, allow_template_mismatch=False,
        yes=True,
    )
    fields.update(over)
    return SimpleNamespace(**fields)


def install_setup(monkeypatch, tmp_path, fake):
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / ".sessions")
    monkeypatch.setattr(session, "paged", fake.paged)
    monkeypatch.setattr(session, "api", fake.api)


def test_setup_records_the_ids_and_the_budget(tmp_path, monkeypatch, capsys):
    fake = FakeSetupApi()
    install_setup(monkeypatch, tmp_path, fake)
    session.cmd_setup(setup_args(), "token")
    saved = session.read_session("s1")
    assert saved["survey_id"] == "sv1"
    assert saved["screening_study_id"] == "st1"
    assert saved["game_study_id"] == "st2"
    assert saved["condition"] == "refer_mixed" and saved["tangram_set"] == "0"
    # 20 x 0.30 + 9 x 12 + 9 x 8 = 186, plus 33%.
    assert saved["budget_usd"] == round(186 * 1.33, 2)
    out = capsys.readouterr().out
    assert "no games yet" in out
    assert "This session: refer_mixed set 0" in out
    game_payload = next(p for m, path, p in fake.calls if (m, path) == ("POST", "/studies/")
                        and p.get("name") == session.GAME_STUDY_NAME)
    assert game_payload["description"] == "The game starts at 6pm PT / 9pm ET."
    joined = {c["code"] for c in game_payload["completion_codes"]
              if any(a["action"] == "ADD_TO_PARTICIPANT_GROUP" for a in c["actions"])}
    assert joined == session.PLAYED_CODES


def test_an_explicit_budget_is_recorded_instead_of_the_ceiling(tmp_path, monkeypatch):
    install_setup(monkeypatch, tmp_path, FakeSetupApi())
    session.cmd_setup(setup_args(budget=500.0), "token")
    assert session.read_session("s1")["budget_usd"] == 500.0


def test_setup_saves_each_id_as_it_is_created(tmp_path, monkeypatch):
    """A failure between creations must leave the ids made so far on disk."""
    install_setup(monkeypatch, tmp_path, FakeSetupApi(fail_on_game_study=True))
    with pytest.raises(SystemExit, match="simulated failure"):
        session.cmd_setup(setup_args(), "token")
    saved = session.read_session("s1")
    assert saved["survey_id"] == "sv1"
    assert saved["screening_study_id"] == "st1"
    assert "game_study_id" not in saved


def test_setup_refuses_a_template_whose_codes_lack_the_return_action(tmp_path, monkeypatch):
    fake = FakeSetupApi()
    fake.details["/studies/g0/"]["completion_codes"] = good_codes(
        completion=["MANUALLY_REVIEW"], partial=[]
    )
    install_setup(monkeypatch, tmp_path, fake)
    with pytest.raises(SystemExit, match="lacks REQUEST_RETURN"):
        session.cmd_setup(setup_args(), "token")
    assert not [c for c in fake.calls if c[0] == "POST"]


# --------------------------------------------------- local files and no token


def test_sessions_and_tally_never_load_a_token(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / ".sessions")
    monkeypatch.setattr(session, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session, "load_token", lambda: pytest.fail("token loaded"))
    session.write_session("s1", condition="refer_mixed", tangram_set="0", budget_usd=800.0)
    for argv in (["session.py", "sessions"], ["session.py", "tally"]):
        monkeypatch.setattr(sys, "argv", argv)
        session.main()
    out = capsys.readouterr().out
    assert "s1" in out and "budget_usd" in out and "800.0" in out
    assert "no games yet" in out


def test_session_and_ledger_files_are_written_whole(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / ".sessions")
    path = session.write_session("s1", condition="refer_mixed")
    session.write_session("s1", survey_id="sv1")
    assert json.loads(path.read_text()) == {"condition": "refer_mixed", "survey_id": "sv1"}
    session.write_ledger(tmp_path, {"bonuses": {"bulk_id": "b"}})
    assert json.loads(session.ledger_path(tmp_path).read_text()) == {"bonuses": {"bulk_id": "b"}}
    # No temp files left beside either.
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == [".sessions"]
    assert [p.name for p in (tmp_path / ".sessions").iterdir()] == ["s1.json"]


def test_no_function_imports_its_own_modules():
    source = (PROJECT_ROOT / "operations" / "session.py").read_text()
    assert not re.search(r"^[ \t]+import \w+$", source, re.M)
    assert not re.search(r"^[ \t]+from \w+ import", source, re.M)


# ------------------------------------------------------------------ retries


def test_a_transient_failure_is_retried(monkeypatch):
    attempts = []

    class Response:
        def __init__(self, status):
            self.status_code = status
            self.ok = status < 400
            self.content = b"{}"
            self.text = "boom"

        def json(self):
            return {"ok": True}

    def fake_request(*a, **k):
        attempts.append(1)
        return Response(502 if len(attempts) < 3 else 200)

    monkeypatch.setattr(session.requests, "request", fake_request)
    monkeypatch.setattr(session.time, "sleep", lambda s: None)
    ok, body, error = session.request_api("POST", "/x", "token", retries=3)
    assert ok and body == {"ok": True}
    assert len(attempts) == 3


def test_a_permanent_failure_is_not_retried(monkeypatch):
    attempts = []

    class Response:
        status_code, ok, content, text = 400, False, b"bad", "bad field"

        def json(self):
            return {}

    def fake_request(*a, **k):
        attempts.append(1)
        return Response()

    monkeypatch.setattr(session.requests, "request", fake_request)
    ok, _, error = session.request_api("POST", "/x", "token", retries=3)
    assert not ok and len(attempts) == 1
    assert "bad field" in error


def test_a_dropped_connection_is_a_message_not_a_traceback(monkeypatch):
    def fake_request(*a, **k):
        raise session.requests.ConnectionError("connection reset")

    monkeypatch.setattr(session.requests, "request", fake_request)
    ok, _, error = session.request_api("GET", "/x", "token")
    assert not ok
    assert "ConnectionError" in error
