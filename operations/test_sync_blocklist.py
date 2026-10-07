"""Tests for operations/sync_blocklist.py. The Prolific calls are replaced by a fake; nothing is sent.

Run with `make test-ops`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "operations"))

import sync_blocklist  # noqa: E402

A, B, C = "a" * 24, "b" * 24, "c" * 24


def test_read_blocklist_keeps_valid_ids_and_reports_the_rest(tmp_path):
    path = tmp_path / "blocklist_ids.txt"
    path.write_text(f"{B}\n{A}\n\n{A}\nnot-an-id\n{'A' * 24}\n")
    valid, invalid = sync_blocklist.read_blocklist(path)
    assert valid == [A, B]
    assert invalid == ["not-an-id", "A" * 24]


def test_plan_adds_only_missing_ids_and_never_removes():
    to_add, extra = sync_blocklist.plan([A, B], {B, C})
    assert to_add == [A]
    assert extra == [C]


def test_chunks_cover_every_id_once():
    ids = [f"{i:024x}" for i in range(450)]
    parts = sync_blocklist.chunks(ids, 200)
    assert [len(p) for p in parts] == [200, 200, 50]
    assert sum(parts, []) == ids


class FakeProlific:
    """Records calls; a group with one member, B, in one workspace."""

    def __init__(self):
        self.members, self.posts = {B}, []

    def api(self, method, path, token, payload=None, params=None, retries=2):
        if path == "/workspaces/":
            return {"results": [{"id": "w1"}]}
        if path == "/participant-groups/":
            return {"results": [{"id": "g1", "name": sync_blocklist.GROUP_NAME, "is_deleted": False},
                                {"id": "g2", "name": "something else", "is_deleted": False}]}
        if path == "/participant-groups/g1/participants/" and method == "GET":
            return {"results": [{"participant_id": m} for m in sorted(self.members)], "_links": {}}
        if path == "/participant-groups/g1/participants/" and method == "POST":
            self.posts.append(payload["participant_ids"])
            self.members |= set(payload["participant_ids"])
            return {"results": []}
        raise AssertionError(f"unexpected call {method} {path}")


@pytest.fixture
def fake(monkeypatch, tmp_path):
    fake = FakeProlific()
    monkeypatch.setattr(sync_blocklist.prolific, "api", fake.api)
    monkeypatch.setattr(sync_blocklist.prolific, "load_token", lambda: "token")
    monkeypatch.setattr(sync_blocklist, "PAYMENTS_DIR", tmp_path)
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "blocklist_ids.txt").write_text(f"{A}\n{B}\n")
    return fake


def test_dry_run_sends_nothing(fake, capsys):
    sync_blocklist.main(["--dataset", "full", "--dry-run"])
    assert fake.posts == []
    assert "1 on the list are not yet in the group" in capsys.readouterr().out


def test_yes_adds_only_the_missing_members(fake):
    sync_blocklist.main(["--dataset", "full", "--yes"])
    assert fake.posts == [[A]]
    assert fake.members == {A, B}


def test_without_yes_a_no_answer_changes_nothing(fake, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    sync_blocklist.main(["--dataset", "full"])
    assert fake.posts == []


def test_without_a_terminal_to_answer_nothing_changes(fake, monkeypatch, capsys):
    def no_terminal(prompt):
        raise EOFError
    monkeypatch.setattr("builtins.input", no_terminal)
    sync_blocklist.main(["--dataset", "full"])
    assert fake.posts == []
    assert "SYNC_ARGS=--yes" in capsys.readouterr().out


def test_a_second_run_has_nothing_to_add(fake, capsys):
    sync_blocklist.main(["--dataset", "full", "--yes"])
    sync_blocklist.main(["--dataset", "full", "--yes"])
    assert fake.posts == [[A]]
    assert "Nothing to add" in capsys.readouterr().out
