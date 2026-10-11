"""Games per treatment (condition by tangram set), so the next session runs the one furthest behind.

    uv run python operations/tally.py              # the full sample (DATASET or `full`)
    uv run python operations/tally.py --dataset full

Reads data/<dataset>/tables/games.csv and players.csv (run the pipeline first) and
needs no Prolific token. Collection runs to the preregistered cap of 120
started games, balanced by started games: 30 per condition, 15 per treatment.
The intact games (finished with all nine players) are shown alongside, with the
preregistration's other limit of 20 per condition, but they do not steer which
treatment runs next.
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
# plan") has two limits: 20 intact nine-player games per condition, or 120
# games started in total, whichever comes first. With roughly half the games
# intact, the cap is the one that ends collection, so the author decided on
# 2026-10-04 to balance by started games: an equal share of the 120 for every
# condition, split evenly over the two tangram sets.
STARTED_GAMES_CAP = 120
STARTED_TARGET_PER_CONDITION = STARTED_GAMES_CAP // len(CONDITIONS)
STARTED_TARGET_PER_CELL = STARTED_TARGET_PER_CONDITION // len(TANGRAM_SETS)
INTACT_TARGET_PER_CONDITION = 20


def active_dataset():
    """The dataset named by DATASET, defaulting to `full`."""
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
    models/R/attrition.R defines it, so the two agree on what an intact game
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

    "Intact" is a game that finished with all nine players still in it, the
    unit of the preregistration's per-condition limit; a game that finished a
    player short still yields usable data, so it is "partial" rather than
    discarded. All three count as started games, which is what the target
    and the cap are measured in.
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


def started(cell):
    """Games started in a cell: every game the server gave a condition, finished or not."""
    return cell["intact"] + cell["partial"] + cell["incomplete"]


def cell_counts(games):
    """Games per treatment cell, every cell present, and the cell the next session should run.

    The next cell has the fewest started games; ties go to the one with fewer
    intact games, then to the conditions' order and the tangram sets' order.
    """
    counts = {(condition, tangram_set): empty_cell() for condition in CONDITIONS for tangram_set in TANGRAM_SETS}
    for condition, tangram_set, status in games:
        counts.setdefault((condition, tangram_set), empty_cell())[status] += 1

    def order(cell):
        condition, tangram_set = cell
        rank = CONDITIONS.index(condition) if condition in CONDITIONS else len(CONDITIONS)
        return (started(counts[cell]), counts[cell]["intact"], rank, tangram_set)

    return counts, min(counts, key=order)


def tally_lines(counts, next_cell):
    lines = [f"  {'condition':18s} {'set':>3s} {'intact':>6s} {'partial':>8s} {'incomplete':>11s} "
             f"{'started':>8s}"]
    for (condition, tangram_set), cell in counts.items():
        marker = "   <- next" if (condition, tangram_set) == next_cell else ""
        progress = f"{started(cell)}/{STARTED_TARGET_PER_CELL}"
        lines.append(
            f"  {condition:18s} {tangram_set:>3s} {cell['intact']:6d} {cell['partial']:8d} "
            f"{cell['incomplete']:11d} {progress:>8s}{marker}"
        )
    return lines


def stopping_rule_progress(counts):
    """Games started against the cap and the per-condition share, plus intact games.

    Every game in `counts` counts towards the cap, including the partial and
    incomplete ones: the cap is on games started, and a game that never
    started carries no condition (the server writes it in onGameStart), which
    read_games_table drops.
    """
    per_condition = {}
    intact = {}
    for (condition, _), cell in counts.items():
        per_condition[condition] = per_condition.get(condition, 0) + started(cell)
        intact[condition] = intact.get(condition, 0) + cell["intact"]
    total = sum(per_condition.values())
    return {
        "started": total,
        "cap_left": max(STARTED_GAMES_CAP - total, 0),
        "started_by_condition": per_condition,
        "intact": intact,
    }


def stopping_rule_lines(counts):
    """Progress towards the cap, per condition, and the intact games for reference."""
    progress = stopping_rule_progress(counts)

    def by_condition(values, target):
        ordered = sorted(values, key=lambda c: CONDITIONS.index(c) if c in CONDITIONS else len(CONDITIONS))
        return ", ".join(f"{c} {values[c]}/{target}" for c in ordered)

    lines = [
        f"  Started: {progress['started']} of {STARTED_GAMES_CAP}, {progress['cap_left']} left; "
        f"target {STARTED_TARGET_PER_CONDITION} per condition, {STARTED_TARGET_PER_CELL} per treatment -- "
        f"{by_condition(progress['started_by_condition'], STARTED_TARGET_PER_CONDITION)}.",
        f"  Intact (the preregistration's other limit is {INTACT_TARGET_PER_CONDITION} per condition) -- "
        f"{by_condition(progress['intact'], INTACT_TARGET_PER_CONDITION)}.",
    ]
    if not progress["cap_left"]:
        lines.append(f"  STOP: {STARTED_GAMES_CAP} games have been started. Games already underway "
                     "finish; the analyses use every eligible game.")
    return lines


def print_tally(dataset=None):
    """Print games per treatment cell; returns (counts, next_cell), or None with no games yet."""
    dataset = dataset or active_dataset()
    games_path = PROJECT_ROOT / "data" / dataset / "tables" / "games.csv"
    if not games_path.exists():
        print(f"no games yet (no {games_path.relative_to(PROJECT_ROOT)})")
        return None
    players_path = games_path.parent / "players.csv"
    removals = read_player_removals(players_path)
    games = read_games_table(games_path, removals)
    intact = sum(1 for g in games if g[2] == "intact")
    others = len(games) - intact
    print(f"{intact} intact nine-player game(s) in data/{dataset}/tables/games.csv"
          + (f", {others} that lost a player or did not finish" if others else "") + ":")
    if not removals:
        print(f"  WARNING: no usable {players_path.name} beside games.csv, so a game that lost a "
              "player cannot be told from an intact one. The intact count below is an upper bound.")
    counts, next_cell = cell_counts(games)
    for line in tally_lines(counts, next_cell):
        print(line)
    print("  Intact = finished with all nine players; partial = finished a player or more short;")
    print("  incomplete = ended early. All three are started games, which is what the target counts.")
    for line in stopping_rule_lines(counts):
        print(line)
    return counts, next_cell


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", default=None, help="Dataset name (default: DATASET or `full`)")
    print_tally(parser.parse_args(argv).dataset)


if __name__ == "__main__":
    main()
