"""Tests for operations/prolific.py and operations/game_constants.py. No API calls.

Run with `make test-ops`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "operations"))

import game_constants  # noqa: E402
import prolific  # noqa: E402


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



# --------------------------------------------------------------- pagination


def paging_api(pages):
    """A fake `api` serving `pages` by offset and recording the offsets asked for."""
    asked = []

    def fake_api(method, path, token, payload=None, params=None, retries=0):
        asked.append(params["offset"])
        index = params["offset"] // prolific.PAGE_SIZE
        return pages[index] if index < len(pages) else {"results": [], "meta": {}}

    return fake_api, asked


def rows(start, n):
    return [{"id": f"r{i}"} for i in range(start, start + n)]


def test_paging_follows_the_count_across_pages(monkeypatch):
    full = prolific.PAGE_SIZE
    fake, asked = paging_api([
        {"results": rows(0, full), "meta": {"count": full + 5}},
        {"results": rows(full, 5), "meta": {"count": full + 5}},
    ])
    monkeypatch.setattr(prolific, "api", fake)
    assert len(list(prolific.paged("/x/", "token"))) == full + 5
    assert asked == [0, full]


def test_a_short_page_with_no_meta_is_the_last_one(monkeypatch):
    fake, asked = paging_api([{"results": rows(0, 7)}])
    monkeypatch.setattr(prolific, "api", fake)
    assert len(list(prolific.paged("/x/", "token"))) == 7
    assert asked == [0]


def test_a_full_page_with_no_meta_keeps_paging(monkeypatch):
    """The bug: a missing count used to stop after the first hundred submissions."""
    full = prolific.PAGE_SIZE
    fake, asked = paging_api([
        {"results": rows(0, full)},
        {"results": rows(full, full)},
        {"results": rows(2 * full, 3)},
    ])
    monkeypatch.setattr(prolific, "api", fake)
    assert len(list(prolific.paged("/x/", "token"))) == 2 * full + 3
    assert asked == [0, full, 2 * full]


def test_a_bare_list_endpoint_is_paged_by_length(monkeypatch):
    full = prolific.PAGE_SIZE
    fake, _ = paging_api([rows(0, full), rows(full, 2)])
    monkeypatch.setattr(prolific, "api", fake)
    assert len(list(prolific.paged("/x/", "token"))) == full + 2


def test_a_full_page_under_a_meta_without_a_count_fails_loudly(monkeypatch):
    fake, _ = paging_api([{"results": rows(0, prolific.PAGE_SIZE), "meta": {"page": 1}}])
    monkeypatch.setattr(prolific, "api", fake)
    with pytest.raises(SystemExit, match=r"GET /studies/s/submissions/ .*neither `total` nor `count`"):
        list(prolific.paged("/studies/s/submissions/", "token"))


def test_an_endpoint_that_ignores_offset_is_caught(monkeypatch):
    same = rows(0, prolific.PAGE_SIZE)
    fake, _ = paging_api([{"results": same}, {"results": same}, {"results": same}])
    monkeypatch.setattr(prolific, "api", fake)
    with pytest.raises(SystemExit, match="same page twice"):
        list(prolific.paged("/x/", "token"))


