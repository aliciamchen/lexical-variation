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
    monkeypatch.setattr(session, "api", lambda *a, **k: {"id": "bulk1", "total_amount": 8000})
    rows = [{"id": f"p{i}", "amount": 6.0} for i in range(10)]
    ledger = {}
    session.setup_payment(
        "token", tmp_path, "bonuses", "study", rows, ledger, max_each=30.0, max_total=None
    )
    assert ledger["bonuses"]["bulk_id"] == "bulk1"
    assert ledger["bonuses"]["participants_paid"] == [f"p{i}" for i in range(10)]
    assert ledger["bonuses"]["paid_at"] is None


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


def test_template_drift_in_the_reward_is_refused():
    payload = {
        "reward": 1500,
        "completion_codes": [{"code": c} for c in session.PROLIFIC_CODES.values()],
    }
    with pytest.raises(SystemExit, match="reward is 1500"):
        session.check_game_template(payload, allow_mismatch=False)


def test_template_drift_in_the_codes_is_refused():
    payload = {"reward": int(session.BASE_PAY * 100), "completion_codes": [{"code": "XXXX"}]}
    with pytest.raises(SystemExit, match="completion codes"):
        session.check_game_template(payload, allow_mismatch=False)


def test_a_matching_template_passes():
    payload = {
        "reward": int(session.BASE_PAY * 100),
        "completion_codes": [{"code": c} for c in session.PROLIFIC_CODES.values()],
    }
    session.check_game_template(payload, allow_mismatch=False)


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
