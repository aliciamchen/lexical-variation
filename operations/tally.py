"""Games per (condition, tangram set) cell, so the next session fills the emptiest.

    uv run python operations/tally.py              # the full sample (DATASET or `full`)
    uv run python operations/tally.py --dataset full

Reads data/<dataset>/games.csv and players.csv (run the pipeline first) and
needs no Prolific token. It also prints progress against the preregistered
stopping rule: 20 intact nine-player games per condition, or 120 games started,
whichever comes first.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_constants import ConstantsError  # noqa: E402
from game_constants import load as load_game_constants  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    GAME = load_game_constants()
except ConstantsError as error:
    sys.exit(f"Cannot read the experiment's constants: {error}")

CONDITIONS = GAME["conditions"]
PLAYERS_PER_GAME = GAME["players_per_game"]
TANGRAM_SETS = ("0", "1")
# The preregistered stopping rule (writing/preregistration/main.tex, "Sampling
# plan"): run games until every condition has 20 intact nine-player games, or
# until 120 games have been started in total, whichever comes first. Each
# condition is split over two tangram sets, so a cell's share of the target is
# half the per-condition figure.
INTACT_TARGET_PER_CONDITION = 20
INTACT_TARGET_PER_CELL = INTACT_TARGET_PER_CONDITION // len(TANGRAM_SETS)
STARTED_GAMES_CAP = 120


def active_dataset():
    """DATASET, defaulting to `full`: never the frozen pilot."""
    return os.environ.get("DATASET") or "full"


def tangram_set_label(raw):
    """One spelling for a tangram set: "0.0", "0", 0 and 0.0 are all "0"."""
    text = ("" if raw is None else str(raw)).strip()
    if not text:
        return "?"
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def read_player_removals(path):
    """{gameId: (players, removed)} from a players.csv; {} when it cannot say.

    A removed player is one whose `isActive` is false, which is how
    analysis/R/attrition.R defines it, so the two agree on what an intact game
    is.
    """
    if not path.exists():
        return {}
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if "gameId" not in fields or "isActive" not in fields:
            return {}
        per_game = {}
        for row in reader:
            game = (row.get("gameId") or "").strip()
            if not game:
                continue
            players, removed = per_game.get(game, (0, 0))
            active = (row.get("isActive") or "").strip().lower() in ("true", "1")
            per_game[game] = (players + 1, removed + (0 if active else 1))
    return per_game


def game_status_label(row, removals):
    """"intact", "partial" or "incomplete" for one games.csv row.

    The stopping rule counts games that finished with all nine players still
    in them, so that is what "intact" means and what a cell's target is
    measured in. A game that finished a player short still yields usable data,
    so it is counted separately rather than discarded or counted as whole.
    """
    reason = (row.get("endedReason") or "").strip()
    if reason and reason != "end of game":
        return "incomplete"
    game_id = (row.get("gameId") or "").strip()
    if game_id in removals:
        players, removed = removals[game_id]
        return "intact" if players == PLAYERS_PER_GAME and removed == 0 else "partial"
    # No players.csv to check against: fall back to the roster size the game
    # recorded, which cannot see a removal; print_tally warns when it does this.
    try:
        assigned = int(float(row.get("numPlayers") or 0))
    except ValueError:
        assigned = 0
    return "intact" if assigned == PLAYERS_PER_GAME else "partial"


def read_games_table(path, removals=None):
    """[(condition, set, status)] for every game in a games.csv."""
    if removals is None:
        removals = read_player_removals(Path(path).parent / "players.csv")
    with open(path, newline="") as handle:
        games = []
        for row in csv.DictReader(handle):
            condition = (row.get("condition") or "").strip()
            if not condition:
                continue
            games.append((condition, tangram_set_label(row.get("tangramSet")), game_status_label(row, removals)))
    return games


def empty_cell():
    return {"intact": 0, "partial": 0, "incomplete": 0}


def cell_counts(games):
    """Games per (condition, set) cell, every cell present, and the emptiest cell.

    The emptiest cell has the fewest intact games, then comes first in the
    conditions' order and the tangram sets' order.
    """
    counts = {(condition, tangram_set): empty_cell() for condition in CONDITIONS for tangram_set in TANGRAM_SETS}
    for condition, tangram_set, status in games:
        counts.setdefault((condition, tangram_set), empty_cell())[status] += 1

    def order(cell):
        condition, tangram_set = cell
        rank = CONDITIONS.index(condition) if condition in CONDITIONS else len(CONDITIONS)
        return (counts[cell]["intact"], rank, tangram_set)

    return counts, min(counts, key=order)


def tally_lines(counts, emptiest):
    lines = [f"  {'condition':18s} {'set':>3s} {'intact':>6s} {'partial':>8s} {'incomplete':>11s}"]
    for (condition, tangram_set), cell in counts.items():
        marker = "   <- emptiest" if (condition, tangram_set) == emptiest else ""
        lines.append(
            f"  {condition:18s} {tangram_set:>3s} {cell['intact']:6d} {cell['partial']:8d} "
            f"{cell['incomplete']:11d}{marker}"
        )
    return lines


def stopping_rule_progress(counts):
    """How far recruitment has run against the two preregistered limits.

    Every game in `counts` counts towards the cap, including the partial and
    incomplete ones: the cap is on games started, and a game that never
    started carries no condition (the server writes it in onGameStart), which
    read_games_table drops.
    """
    started = sum(cell["intact"] + cell["partial"] + cell["incomplete"] for cell in counts.values())
    intact = {}
    for (condition, _), cell in counts.items():
        intact[condition] = intact.get(condition, 0) + cell["intact"]
    return {
        "started": started,
        "cap_left": max(STARTED_GAMES_CAP - started, 0),
        "intact": intact,
        "short": {c: INTACT_TARGET_PER_CONDITION - n for c, n in intact.items() if n < INTACT_TARGET_PER_CONDITION},
    }


def stopping_rule_lines(counts):
    """The two preregistered limits and how much of each is left."""
    progress = stopping_rule_progress(counts)
    ordered = sorted(progress["intact"], key=lambda c: CONDITIONS.index(c) if c in CONDITIONS else len(CONDITIONS))
    per_condition = ", ".join(f"{c} {progress['intact'][c]}/{INTACT_TARGET_PER_CONDITION}" for c in ordered)
    lines = [
        f"  Target: {INTACT_TARGET_PER_CONDITION} intact games per condition "
        f"({INTACT_TARGET_PER_CELL} per cell) -- {per_condition}.",
        f"  Cap: {progress['started']} of {STARTED_GAMES_CAP} games started, {progress['cap_left']} left.",
    ]
    if not progress["short"]:
        lines.append("  STOP: every condition has reached the target.")
    elif not progress["cap_left"]:
        lines.append("  STOP: the cap is reached. Games short of the target stay short; "
                     "the analyses use every eligible game.")
    return lines


def print_tally(dataset=None):
    """Print games per treatment cell; returns (counts, emptiest), or None with no games yet."""
    dataset = dataset or active_dataset()
    games_path = PROJECT_ROOT / "data" / dataset / "games.csv"
    if not games_path.exists():
        print(f"no games yet (no {games_path.relative_to(PROJECT_ROOT)})")
        return None
    players_path = games_path.parent / "players.csv"
    removals = read_player_removals(players_path)
    games = read_games_table(games_path, removals)
    intact = sum(1 for g in games if g[2] == "intact")
    others = len(games) - intact
    print(f"{intact} intact nine-player game(s) in data/{dataset}/games.csv"
          + (f", {others} that lost a player or did not finish" if others else "") + ":")
    if not removals:
        print(f"  WARNING: no usable {players_path.name} beside games.csv, so a game that lost a "
              "player cannot be told from an intact one. The intact count below is an upper bound.")
    counts, emptiest = cell_counts(games)
    for line in tally_lines(counts, emptiest):
        print(line)
    print("  Intact = finished with all nine players, which is what the stopping rule counts.")
    print("  Partial games still yield data; they do not count towards a cell's target.")
    for line in stopping_rule_lines(counts):
        print(line)
    return counts, emptiest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", default=None, help="Dataset name (default: DATASET or `full`)")
    print_tally(parser.parse_args(argv).dataset)


if __name__ == "__main__":
    main()
