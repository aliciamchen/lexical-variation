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


def test_tally_counts_games_per_cell_and_marks_the_next(tmp_path, monkeypatch):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    counts, next_cell = tally.print_tally("full")
    assert counts[("refer_separated", "0")]["intact"] == 1
    assert counts[("refer_separated", "1")]["intact"] == 1
    assert counts[("social_first", "1")] == {
        "intact": 0, "partial": 0, "incomplete": 1
    }
    assert len(counts) == 8
    # No games started in refer_mixed set 1, social_mixed set 0/1 or
    # social_first set 0; the conditions' order breaks the tie.
    assert next_cell == ("refer_mixed", "1")


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


def test_the_next_cell_is_chosen_on_started_games_not_intact_ones():
    # Every cell has two partial games except refer_mixed set 0, which has one
    # intact game. Balancing by intact games would send the next session
    # anywhere but there; balancing by started games, as decided, sends it
    # there, because it has spent the fewest of its share of the cap.
    games = [(c, s, "partial") for c in tally.CONDITIONS for s in tally.TANGRAM_SETS for _ in range(2)
             if (c, s) != ("refer_mixed", "0")]
    games.append(("refer_mixed", "0", "intact"))
    counts, next_cell = tally.cell_counts(games)
    assert next_cell == ("refer_mixed", "0")


def test_a_tie_on_started_games_goes_to_the_cell_with_fewer_intact():
    games = [(c, s, "intact") for c in tally.CONDITIONS for s in tally.TANGRAM_SETS for _ in range(2)]
    games = [g for g in games if g[:2] != ("social_first", "1")]
    games += [("social_first", "1", "partial"), ("social_first", "1", "partial")]
    _, next_cell = tally.cell_counts(games)
    assert next_cell == ("social_first", "1")


def test_read_player_removals_ignores_a_file_it_cannot_use(tmp_path):
    path = tmp_path / "players.csv"
    assert tally.read_player_removals(path) == {}
    path.write_text("playerId,score\np1,3\n")
    assert tally.read_player_removals(path) == {}


def test_tally_lines_mark_exactly_one_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    counts, next_cell = tally.cell_counts(
        tally.read_games_table(tmp_path / "data" / "full" / "games.csv")
    )
    lines = tally.tally_lines(counts, next_cell)
    assert len(lines) == 9
    assert sum("<- next" in line for line in lines) == 1
    assert any(line.startswith("  refer_mixed") and "1" in line and "<- next" in line
               for line in lines)
    assert any(f"1/{tally.STARTED_TARGET_PER_CELL}" in line for line in lines)


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
    assert progress["started_by_condition"] == {
        "refer_mixed": 1, "refer_separated": 2, "social_mixed": 0, "social_first": 1
    }


def test_the_target_splits_the_cap_evenly_over_conditions_and_sets():
    assert tally.STARTED_TARGET_PER_CONDITION * len(tally.CONDITIONS) == tally.STARTED_GAMES_CAP
    assert tally.STARTED_TARGET_PER_CONDITION == 30
    assert tally.STARTED_TARGET_PER_CELL == 15
    counts, _ = tally.cell_counts([])
    counts[("refer_mixed", "0")]["partial"] = 4
    counts[("refer_mixed", "1")]["incomplete"] = 1
    progress = tally.stopping_rule_progress(counts)
    assert progress["started_by_condition"]["refer_mixed"] == 5


def test_tally_says_stop_only_at_the_cap():
    counts, _ = tally.cell_counts([])
    assert not any("STOP" in line for line in tally.stopping_rule_lines(counts))
    # Twenty intact games in every condition does not stop collection: the
    # author runs to the cap of started games.
    for cell in counts.values():
        cell["intact"] = tally.INTACT_TARGET_PER_CONDITION // len(tally.TANGRAM_SETS)
    assert not any("STOP" in line for line in tally.stopping_rule_lines(counts))
    counts, _ = tally.cell_counts([])
    counts[("refer_mixed", "0")]["partial"] = tally.STARTED_GAMES_CAP
    lines = tally.stopping_rule_lines(counts)
    assert any(f"STOP: {tally.STARTED_GAMES_CAP} games have been started" in line for line in lines)
    assert any(f"Started: {tally.STARTED_GAMES_CAP} of {tally.STARTED_GAMES_CAP}, 0 left" in line
               for line in lines)


def test_the_tally_prints_the_cap_and_the_intact_counts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    (tmp_path / "data" / "full").mkdir(parents=True)
    (tmp_path / "data" / "full" / "games.csv").write_text(GAMES_CSV)
    (tmp_path / "data" / "full" / "players.csv").write_text(PLAYERS_CSV)
    tally.print_tally("full")
    out = capsys.readouterr().out
    assert f"Started: 4 of {tally.STARTED_GAMES_CAP}" in out
    assert f"other limit is {tally.INTACT_TARGET_PER_CONDITION} per condition" in out


def test_tally_without_games_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tally, "PROJECT_ROOT", tmp_path)
    assert tally.print_tally("full") is None
    assert "no games yet" in capsys.readouterr().out


def test_tangram_set_labels_agree_across_spellings():
    assert tally.tangram_set_label("0.0") == tally.tangram_set_label(0) == "0"
    assert tally.tangram_set_label("1") == "1"
    assert tally.tangram_set_label("") == "?"


