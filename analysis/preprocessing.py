"""
Preprocessing script for Empirica experiment data.

Parses raw Empirica export CSVs and produces clean analysis-ready CSVs.

Usage:
    uv run python analysis/preprocessing.py experiment/export-data/ --output analysis/data/
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd


def drop_last_changed_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Drop all *LastChangedAt columns."""
    return df[[c for c in df.columns if not c.endswith("LastChangedAt")]]


def parse_json_field(val):
    """Safely parse a JSON string, returning None on failure."""
    if pd.isna(val) or val == "":
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


def build_games(game_df: pd.DataFrame) -> pd.DataFrame:
    """Build games.csv: 1 row per game."""
    game_df = drop_last_changed_cols(game_df)

    games = game_df[
        [
            "id",
            "condition",
            "tangram_set",
            "actualPlayerCount",
            "active_groups",
            "phase1Blocks",
            "phase2Blocks",
        ]
    ].copy()
    games.columns = [
        "gameId",
        "condition",
        "tangramSet",
        "numPlayers",
        "activeGroups",
        "phase1Blocks",
        "phase2Blocks",
    ]

    # Parse activeGroups from JSON list string
    games["activeGroups"] = games["activeGroups"].apply(
        lambda x: len(parse_json_field(x)) if parse_json_field(x) else None
    )

    return games


def build_players(player_df: pd.DataFrame) -> pd.DataFrame:
    """Build players.csv: 1 row per player."""
    player_df = drop_last_changed_cols(player_df)

    players = player_df[
        [
            "id",
            "gameID",
            "name",
            "original_group",
            "original_name",
            "score",
            "bonus",
            "is_active",
            "idle_rounds",
            "exitSurvey",
        ]
    ].copy()
    players.columns = [
        "playerId",
        "gameId",
        "name",
        "originalGroup",
        "originalName",
        "score",
        "bonus",
        "isActive",
        "idleRounds",
        "exitSurvey",
    ]

    # Parse exitSurvey JSON and flatten
    def parse_exit_survey(row):
        survey = parse_json_field(row["exitSurvey"])
        if survey and isinstance(survey, dict):
            for key, val in survey.items():
                row[f"exitSurvey_{key}"] = val
        return row

    players = players.apply(parse_exit_survey, axis=1)
    players = players.drop(columns=["exitSurvey"])

    return players


def build_trials(
    player_round_df: pd.DataFrame, round_df: pd.DataFrame, game_df: pd.DataFrame
) -> pd.DataFrame:
    """Build trials.csv: 1 row per player per round (refgame rounds only)."""
    pr = drop_last_changed_cols(player_round_df)
    rd = drop_last_changed_cols(round_df)

    # Filter to refgame rounds only
    pr = pr[pr["phase"] == "refgame"].copy()

    # Select and rename columns from playerRound
    trials = pr[
        [
            "gameID",
            "playerID",
            "name",
            "original_group",
            "current_group",
            "role",
            "block_num",
            "phase",
            "phase_num",
            "target",
            "clicked",
            "clicked_correct",
            "round_score",
            "roundID",
        ]
    ].copy()
    trials.columns = [
        "gameId",
        "playerId",
        "playerName",
        "originalGroup",
        "currentGroup",
        "role",
        "blockNum",
        "phase",
        "phaseNum",
        "target",
        "clicked",
        "clickedCorrect",
        "roundScore",
        "roundId",
    ]

    # Merge trialNum from round and tangramSet from game
    round_info = rd[["id", "trial_num"]].rename(
        columns={"id": "roundId", "trial_num": "trialNum"}
    )
    trials = trials.merge(round_info, on="roundId", how="left")

    tangram_lookup = game_df[["id", "tangram_set"]].rename(
        columns={"id": "gameId", "tangram_set": "tangramSet"}
    )
    trials = trials.merge(tangram_lookup, on="gameId", how="left")

    # Compute repNum: for each speaker × tangram, number repetitions by block order
    speaker_trials = trials[trials["role"] == "speaker"].copy()
    speaker_trials = speaker_trials.sort_values(
        ["gameId", "playerId", "target", "blockNum"]
    )
    speaker_trials["repNum"] = (
        speaker_trials.groupby(["gameId", "playerId", "target"]).cumcount() + 1
    )

    # Merge repNum back (only speakers have repNum)
    trials = trials.merge(
        speaker_trials[["gameId", "playerId", "roundId", "repNum"]],
        on=["gameId", "playerId", "roundId"],
        how="left",
    )

    return trials


def build_messages(
    player_round_df: pd.DataFrame, game_df: pd.DataFrame, round_df: pd.DataFrame
) -> pd.DataFrame:
    """Build messages.csv: 1 row per chat message."""
    pr = drop_last_changed_cols(player_round_df)
    rd = drop_last_changed_cols(round_df)

    # Filter to refgame rounds only
    pr = pr[pr["phase"] == "refgame"].copy()

    # Build a lookup of (roundId, playerId) -> current_group from playerRound
    # so we can assign the sender's actual group to each message
    sender_group_lookup = (
        pr[["roundID", "playerID", "current_group"]]
        .drop_duplicates()
        .set_index(["roundID", "playerID"])["current_group"]
        .to_dict()
    )

    rows = []
    for _, row in pr.iterrows():
        chat_json = parse_json_field(row.get("chat"))
        if not chat_json or not isinstance(chat_json, list):
            continue

        for msg in chat_json:
            sender = msg.get("sender", {})
            sender_name_raw = sender.get("name", "")
            sender_id = sender.get("id")

            # Parse role from sender name format: "Name (Speaker)" → role = "speaker"
            role_match = re.search(r"\((Speaker|Listener)\)", sender_name_raw)
            sender_role = role_match.group(1).lower() if role_match else None
            # Clean name: remove role suffix
            sender_name = re.sub(
                r"\s*\((?:Speaker|Listener)\)", "", sender_name_raw
            ).strip()

            # Use the sender's actual group, not the iterating player's group
            sender_group = sender_group_lookup.get(
                (row["roundID"], sender_id), row["current_group"]
            )

            rows.append(
                {
                    "gameId": row["gameID"],
                    "roundId": row["roundID"],
                    "blockNum": row["block_num"],
                    "phase": row["phase"],
                    "phaseNum": row["phase_num"],
                    "target": row["target"],
                    "group": sender_group,
                    "senderId": sender_id,
                    "senderName": sender_name,
                    "senderRole": sender_role,
                    "text": msg.get("text", ""),
                    "timestamp": msg.get("timestamp"),
                }
            )

    messages = pd.DataFrame(rows)

    # Deduplicate: each message appears once per player in the group,
    # so we keep only unique messages by (roundId, senderId, timestamp)
    if not messages.empty:
        messages = messages.drop_duplicates(subset=["roundId", "senderId", "timestamp"])
        messages = messages.sort_values(["gameId", "roundId", "timestamp"])

        # Merge trialNum from round and tangramSet from game
        round_info = rd[["id", "trial_num"]].rename(
            columns={"id": "roundId", "trial_num": "trialNum"}
        )
        messages = messages.merge(round_info, on="roundId", how="left")

        tangram_lookup = game_df[["id", "tangram_set"]].rename(
            columns={"id": "gameId", "tangram_set": "tangramSet"}
        )
        messages = messages.merge(tangram_lookup, on="gameId", how="left")

    return messages


def build_speaker_utterances(
    messages: pd.DataFrame, trials: pd.DataFrame
) -> pd.DataFrame:
    """Build speaker_utterances.csv: 1 row per speaker per trial."""
    # Filter to speaker messages only
    speaker_msgs = messages[messages["senderRole"] == "speaker"].copy()
    speaker_msgs = speaker_msgs.sort_values(["roundId", "timestamp"])

    # Concatenate speaker messages per round (one utterance per speaker per round)
    groupby_cols = [
        "gameId", "roundId", "senderId", "blockNum", "phase", "phaseNum", "target",
        "trialNum", "tangramSet",
    ]
    utterances = (
        speaker_msgs.groupby(groupby_cols)
        .agg(utterance=("text", lambda x: ", ".join(x.astype(str))))
        .reset_index()
    )

    utterances["uttLength"] = utterances["utterance"].apply(lambda x: len(x.split()))

    # Merge in player info from trials (speaker rows only)
    # Use senderId == playerId to get the correct speaker's trial row
    speaker_trials = trials[trials["role"] == "speaker"][
        ["gameId", "playerId", "originalGroup", "currentGroup", "roundId", "repNum"]
    ].drop_duplicates()

    utterances = utterances.merge(
        speaker_trials,
        left_on=["gameId", "roundId", "senderId"],
        right_on=["gameId", "roundId", "playerId"],
        how="left",
    )

    # Select and order final columns
    cols = [
        "gameId",
        "playerId",
        "originalGroup",
        "currentGroup",
        "tangramSet",
        "blockNum",
        "trialNum",
        "phase",
        "phaseNum",
        "target",
        "repNum",
        "utterance",
        "uttLength",
    ]
    utterances = utterances[[c for c in cols if c in utterances.columns]]
    utterances = utterances.sort_values(["gameId", "playerId", "blockNum", "target"])

    return utterances


def build_social_guesses(
    player_round_df: pd.DataFrame, game_df: pd.DataFrame
) -> pd.DataFrame:
    """Build social_guesses.csv: 1 row per listener social guess (social_mixed only)."""
    pr = drop_last_changed_cols(player_round_df)

    # Filter to refgame rounds with social guess data
    pr = pr[pr["phase"] == "refgame"].copy()
    pr = pr[pr["social_guess"].notna() & (pr["social_guess"] != "")].copy()

    if pr.empty:
        return pd.DataFrame(
            columns=[
                "gameId",
                "playerId",
                "originalGroup",
                "tangramSet",
                "blockNum",
                "phase",
                "target",
                "socialGuess",
                "socialGuessCorrect",
                "socialRoundScore",
            ]
        )

    guesses = pr[
        [
            "gameID",
            "playerID",
            "original_group",
            "block_num",
            "phase",
            "target",
            "social_guess",
            "social_guess_correct",
            "social_round_score",
        ]
    ].copy()
    guesses.columns = [
        "gameId",
        "playerId",
        "originalGroup",
        "blockNum",
        "phase",
        "target",
        "socialGuess",
        "socialGuessCorrect",
        "socialRoundScore",
    ]

    # Merge tangramSet from game
    tangram_lookup = game_df[["id", "tangram_set"]].rename(
        columns={"id": "gameId", "tangram_set": "tangramSet"}
    )
    guesses = guesses.merge(tangram_lookup, on="gameId", how="left")

    return guesses


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess Empirica export data for analysis"
    )
    parser.add_argument("input_dir", help="Path to Empirica export-data directory")
    parser.add_argument(
        "--output",
        "-o",
        default="analysis/data/",
        help="Output directory for clean CSVs",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading data from {input_dir}")

    # Load raw CSVs
    game_df = pd.read_csv(input_dir / "game.csv")
    player_df = pd.read_csv(input_dir / "player.csv")
    player_round_df = pd.read_csv(input_dir / "playerRound.csv")
    round_df = pd.read_csv(input_dir / "round.csv")

    # Build each output
    print("Building games.csv...")
    games = build_games(game_df)
    games.to_csv(output_dir / "games.csv", index=False)
    print(f"  {len(games)} games")

    print("Building players.csv...")
    players = build_players(player_df)
    players.to_csv(output_dir / "players.csv", index=False)
    print(f"  {len(players)} players")

    print("Building trials.csv...")
    trials = build_trials(player_round_df, round_df, game_df)
    trials.to_csv(output_dir / "trials.csv", index=False)
    print(f"  {len(trials)} trial rows")

    print("Building messages.csv...")
    messages = build_messages(player_round_df, game_df, round_df)
    messages.to_csv(output_dir / "messages.csv", index=False)
    print(f"  {len(messages)} messages")

    print("Building speaker_utterances.csv...")
    speaker_utterances = build_speaker_utterances(messages, trials)
    speaker_utterances.to_csv(output_dir / "speaker_utterances.csv", index=False)
    print(f"  {len(speaker_utterances)} speaker utterances")

    print("Building social_guesses.csv...")
    social_guesses = build_social_guesses(player_round_df, game_df)
    social_guesses.to_csv(output_dir / "social_guesses.csv", index=False)
    print(f"  {len(social_guesses)} social guesses")

    print(f"\nAll CSVs written to {output_dir}")


if __name__ == "__main__":
    main()
