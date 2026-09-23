"""Tests for operations/tally.py. No API calls; games tables are written to a temporary directory.

Run with `make test-ops`.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "operations"))

import tally  # noqa: E402


# --------------------------------------------------------------------- tally


GAMES_CSV = (
    "gameId,condition,tangramSet,numPlayers,ended,endedReason\n"
    "g1,refer_mixed,0.0,9,True,end of game\n"
    "g2,refer_separated,0.0,9,True,end of game\n"
    "g3,refer_separated,1.0,9,True,end of game\n"
    "g4,social_first,1.0,9,True,all players removed\n"
)


# Nine players in every game, one removed in g2, so g2 finished a player
# short. isActive is written by pandas, hence "True"/"False".
PLAYERS_CSV = (
    "gameId,playerId,isActive\n"
    + "".join(f"g1,g1p{i},True\n" for i in range(9))
    + "".join(f"g2,g2p{i},{'False' if i == 0 else 'True'}\n" for i in range(9))
    + "".join(f"g3,g3p{i},True\n" for i in range(9))
    + "".join(f"g4,g4p{i},False\n" for i in range(9))
)


def test_tally_counts_intact_games_per_cell_and_marks_the_emptiest(tmp_path, monkeypatch):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    counts, emptiest = tally.print_tally("full")
    assert counts[("refer_separated", "0")]["intact"] == 1
    assert counts[("refer_separated", "1")]["intact"] == 1
    assert counts[("social_first", "1")] == {
        "intact": 0, "partial": 0, "incomplete": 1
    }
    assert len(counts) == 8
    # No complete games in refer_mixed set 1, social_mixed set 0/1 or
    # social_first set 0/1; the conditions' order breaks the tie.
    assert emptiest == ("refer_mixed", "1")


def test_a_game_that_lost_a_player_is_partial_not_intact(tmp_path, monkeypatch, capsys):
    # The preregistered target counts nine-person games intact at completion,
    # so a game that ran to its end having removed someone must not fill a
    # cell: counting it did, and recruitment for that cell would have stopped
    # early.
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    (tmp_path / "data" / "full" / "players.csv").write_text(PLAYERS_CSV)
    counts, _ = tally.print_tally("full")
    assert counts[("refer_mixed", "0")] == {
        "intact": 1, "partial": 0, "incomplete": 0
    }
    assert counts[("refer_separated", "0")] == {
        "intact": 0, "partial": 1, "incomplete": 0
    }
    # g1 and g3 are intact, g2 lost a player, g4 never finished.
    assert counts[("refer_separated", "1")]["intact"] == 1
    assert "2 intact nine-player game(s)" in capsys.readouterr().out


def test_tally_warns_when_it_cannot_see_removals(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    tally.print_tally("full")
    assert "cannot be told from an intact one" in capsys.readouterr().out


def test_the_emptiest_cell_is_chosen_on_intact_games(tmp_path, monkeypatch):
    # refer_mixed set 0 has an intact game and refer_separated set 0 only a
    # partial one, so the partial cell still needs a tally.
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    games = (
        "gameId,condition,tangramSet,numPlayers,ended,endedReason\n"
        "g1,refer_mixed,0.0,9,True,end of game\n"
        "g2,refer_separated,0.0,9,True,end of game\n"
    )
    (tmp_path / "data" / "full" / "games.csv").write_text(games)
    (tmp_path / "data" / "full" / "players.csv").write_text(PLAYERS_CSV)
    counts, emptiest = tally.cell_counts(
        tally.read_games_table(tmp_path / "data" / "full" / "games.csv")
    )
    assert counts[("refer_mixed", "0")]["intact"] == 1
    assert counts[("refer_separated", "0")]["partial"] == 1
    assert emptiest != ("refer_mixed", "0")


def test_read_player_removals_ignores_a_file_it_cannot_use(tmp_path):
    path = tmp_path / "players.csv"
    assert tally.read_player_removals(path) == {}
    path.write_text("playerId,score\np1,3\n")
    assert tally.read_player_removals(path) == {}


def test_tally_lines_mark_exactly_one_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    counts, emptiest = tally.cell_counts(
        tally.read_games_table(tmp_path / "data" / "full" / "games.csv")
    )
    lines = tally.tally_lines(counts, emptiest)
    assert len(lines) == 9
    assert sum("<- emptiest" in line for line in lines) == 1
    assert any(line.startswith("  refer_mixed") and "1" in line and "<- emptiest" in line
               for line in lines)


def test_the_cap_counts_every_started_game_not_only_the_intact_ones(tmp_path, monkeypatch):
    # The preregistered cap is on games *started*, so a game that lost a
    # player or never finished still spends one of the 120. Counting only the
    # intact ones would run recruitment past the registered limit.
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    (tmp_path / "data" / "full" / "players.csv").write_text(PLAYERS_CSV)
    counts, _ = tally.cell_counts(
        tally.read_games_table(tmp_path / "data" / "full" / "games.csv")
    )
    progress = tally.stopping_rule_progress(counts)
    # g1 and g3 intact, g2 a player short, g4 never finished: four started.
    assert progress["started"] == 4
    assert progress["cap_left"] == tally.STARTED_GAMES_CAP - 4
    assert progress["intact"] == {
        "refer_mixed": 1, "refer_separated": 1, "social_mixed": 0, "social_first": 0
    }
    assert progress["short"]["refer_mixed"] == tally.INTACT_TARGET_PER_CONDITION - 1


def test_the_target_is_counted_per_condition_over_both_tangram_sets(tmp_path, monkeypatch):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    counts, _ = tally.cell_counts([])
    for tangram_set in tally.TANGRAM_SETS:
        counts[("refer_mixed", tangram_set)]["intact"] = tally.INTACT_TARGET_PER_CELL
    progress = tally.stopping_rule_progress(counts)
    assert progress["intact"]["refer_mixed"] == tally.INTACT_TARGET_PER_CONDITION
    assert "refer_mixed" not in progress["short"]
    assert set(progress["short"]) == {"refer_separated", "social_mixed", "social_first"}


def test_tally_says_stop_when_a_limit_is_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    counts, _ = tally.cell_counts([])
    assert not any("STOP" in line for line in tally.stopping_rule_lines(counts))
    # The target reached in every condition.
    for cell in counts.values():
        cell["intact"] = tally.INTACT_TARGET_PER_CELL
    assert any("STOP: every condition has reached the target" in line
               for line in tally.stopping_rule_lines(counts))
    # The cap reached first, with conditions still short.
    counts, _ = tally.cell_counts([])
    counts[("refer_mixed", "0")]["partial"] = tally.STARTED_GAMES_CAP
    lines = tally.stopping_rule_lines(counts)
    assert any("STOP: the cap is reached" in line for line in lines)
    assert any(f"{tally.STARTED_GAMES_CAP} of {tally.STARTED_GAMES_CAP} games started, 0 left"
               in line for line in lines)


def test_the_tally_prints_both_preregistered_limits(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    (tmp_path / "data" / "full" / "players.csv").write_text(PLAYERS_CSV)
    tally.print_tally("full")
    out = capsys.readouterr().out
    assert f"Target: {tally.INTACT_TARGET_PER_CONDITION} intact games per condition" in out
    assert f"Cap: 4 of {tally.STARTED_GAMES_CAP} games started" in out


def test_tally_without_games_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    assert tally.print_tally("full") is None
    assert "no games yet" in capsys.readouterr().out


def test_tangram_set_labels_agree_across_spellings():
    assert tally.tangram_set_label("0.0") == tally.tangram_set_label(0) == "0"
    assert tally.tangram_set_label("1") == "1"
    assert tally.tangram_set_label("") == "?"


