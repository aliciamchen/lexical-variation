"""
Preprocessing script for Empirica experiment data.

Parses raw Empirica export CSVs and produces clean analysis-ready CSVs.

Usage:
    uv run python analysis/preprocessing.py experiment/export-data/ --output analysis/processed_data/
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

    required_cols = [
        "id",
        "condition",
        "tangram_set",
        "actualPlayerCount",
        "active_groups",
        "phase1Blocks",
        "phase2Blocks",
    ]
    # Termination fields for attrition reporting; only present in exports
    # where a game actually ended early
    optional_cols = ["ended", "endedReason", "gameTerminated"]
    cols = required_cols + [c for c in optional_cols if c in game_df.columns]
    games = game_df[cols].copy()

    rename_map = {
        "id": "gameId",
        "condition": "condition",
        "tangram_set": "tangramSet",
        "actualPlayerCount": "numPlayers",
        "active_groups": "activeGroups",
        "phase1Blocks": "phase1Blocks",
        "phase2Blocks": "phase2Blocks",
        "ended": "ended",
        "endedReason": "endedReason",
        "gameTerminated": "gameTerminated",
    }
    games = games.rename(columns={c: rename_map[c] for c in cols})

    # Normalize condition names
    games["condition"] = games["condition"].replace({"exp2_social_goal": "social_first"})

    # Parse activeGroups from JSON list string
    games["activeGroups"] = games["activeGroups"].apply(
        lambda x: len(parse_json_field(x)) if parse_json_field(x) else None
    )

    return games


def build_players(player_df: pd.DataFrame) -> pd.DataFrame:
    """Build players.csv: 1 row per player."""
    player_df = drop_last_changed_cols(player_df)

    required_cols = [
        "id",
        "gameID",
        "name",
        "original_group",
        "original_name",
        "score",
        "bonus",
        "is_active",
        "idle_rounds",
    ]
    # Attrition/removal fields (exitReason, ended, timing, partial pay) are
    # needed to distinguish idle-timeout vs low-accuracy vs group-disbanded
    # removals when reporting exclusions
    optional_cols = [
        "exitSurvey",
        "exitReason",
        "ended",
        "gameStartTime",
        "gameEndTime",
        "partialPay",
        "partialBasePay",
        "partialBonus",
    ]

    # Only include optional columns that exist in the data
    cols = required_cols + [c for c in optional_cols if c in player_df.columns]
    players = player_df[cols].copy()

    rename_map = {
        "id": "playerId",
        "gameID": "gameId",
        "name": "name",
        "original_group": "originalGroup",
        "original_name": "originalName",
        "score": "score",
        "bonus": "bonus",
        "is_active": "isActive",
        "idle_rounds": "idleRounds",
        "exitSurvey": "exitSurvey",
        "exitReason": "exitReason",
        "ended": "ended",
        "gameStartTime": "gameStartTime",
        "gameEndTime": "gameEndTime",
        "partialPay": "partialPay",
        "partialBasePay": "partialBasePay",
        "partialBonus": "partialBonus",
    }
    players = players.rename(columns={c: rename_map[c] for c in cols})

    # Parse exitSurvey JSON and flatten (if present)
    if "exitSurvey" in players.columns:
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

    # Late clicks: a selection that reached the server after the Selection
    # deadline. The server does not score it (clickedCorrect stays null and the
    # round earns no points) but no longer counts the round as idle. Exports
    # from before September 2026 do not have these attributes.
    if "late_click" in pr.columns:
        trials["lateClick"] = pr["late_click"].fillna(False).astype(bool).values
    else:
        trials["lateClick"] = False
    trials["clickedAt"] = pr["clicked_at"].values if "clicked_at" in pr.columns else pd.NA

    # Listener timeout: no scored selection at the deadline (no click, or a
    # click that arrived late)
    trials["timeout"] = (trials["role"] == "listener") & (
        trials["clicked"].isna() | trials["lateClick"]
    )

    # Late social guesses: the social-guessing analogue of late_click, set by
    # the server at the end of the Feedback stage. Lateness has to be
    # established separately for each outcome, so a late tangram selection
    # says nothing about whether the social guess was on time.
    if "late_social_guess" in pr.columns:
        trials["lateSocialGuess"] = (
            pr["late_social_guess"].fillna(False).astype(bool).values
        )
    else:
        trials["lateSocialGuess"] = False

    # Merge trialNum from round and tangramSet from game
    round_info = rd[["id", "trial_num"]].rename(
        columns={"id": "roundId", "trial_num": "trialNum"}
    )
    trials = trials.merge(round_info, on="roundId", how="left")

    tangram_lookup = game_df[["id", "tangram_set"]].rename(
        columns={"id": "gameId", "tangram_set": "tangramSet"}
    )
    trials = trials.merge(tangram_lookup, on="gameId", how="left")

    # Compute repNum: per-phase repetition count for each speaker × tangram
    # (reset to 1 at the start of each phase)
    speaker_trials = trials[trials["role"] == "speaker"].copy()
    speaker_trials = speaker_trials.sort_values(
        ["gameId", "playerId", "target", "phaseNum", "blockNum"]
    )
    speaker_trials["repNum"] = (
        speaker_trials.groupby(["gameId", "playerId", "target", "phaseNum"]).cumcount()
        + 1
    )

    # Merge repNum back (only speakers have repNum)
    trials = trials.merge(
        speaker_trials[["gameId", "playerId", "roundId", "repNum"]],
        on=["gameId", "playerId", "roundId"],
        how="left",
    )

    return trials


# The conditions whose Phase 2 includes the social-identification task. Mirrors
# hasSocialGuessing() in experiment/shared/constants.js.
SOCIAL_GUESSING_CONDITIONS = ("social_mixed", "social_first")


def add_response_opportunity(
    trials: pd.DataFrame, messages: pd.DataFrame
) -> pd.DataFrame:
    """Add hasSpeakerMessage and responseOpportunity to trials.

    An eligible response opportunity is an active listener assigned to the
    task on a played trial with a speaker message available during the
    response period. The first two conditions need no test here: Empirica
    writes a playerRound record only for a player who is still in the game
    and was assigned a role, so a removed player or a terminated game simply
    contributes no rows (asserted by the integrity suite). What is left is
    whether the speaker of the listener's own group actually said something,
    which is why the messages table is needed.

    Trials that fail the test are excluded from the accuracy denominators
    rather than counted as failures: the listener could not have answered.
    """
    trials = trials.copy()
    if messages.empty:
        trials["hasSpeakerMessage"] = False
    else:
        spoke = (
            messages[messages["senderRole"] == "speaker"][
                ["gameId", "roundId", "group"]
            ]
            .drop_duplicates()
            .assign(hasSpeakerMessage=True)
        )
        trials = trials.merge(
            spoke,
            left_on=["gameId", "roundId", "currentGroup"],
            right_on=["gameId", "roundId", "group"],
            how="left",
        ).drop(columns=["group"])
        trials["hasSpeakerMessage"] = (
            trials["hasSpeakerMessage"].fillna(False).astype(bool)
        )

    trials["responseOpportunity"] = (trials["role"] == "listener") & trials[
        "hasSpeakerMessage"
    ]
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


LENGTH_INCREASE_THRESHOLD_WORDS = 5


def flag_length_increase(
    speaker_utterances: pd.DataFrame,
    threshold: float = LENGTH_INCREASE_THRESHOLD_WORDS,
) -> pd.DataFrame:
    """Per-player Phase 1 description-length change and the AI-use flag.

    The preregistration flags participants whose descriptions lengthened over
    Phase 1 for manual inspection of their chat logs: lengthening descriptions
    are the signature of the simulated language-model agents, whereas human
    descriptions shorten. The flag is a trigger for inspection, not an
    exclusion by itself. For each player, the mean word count of their
    descriptions in their last Phase 1 block as speaker is compared with that
    in their first; a change greater than `threshold` words sets the flag.
    Word counts come from the unfiltered utterances so the flag does not
    depend on the LLM classifier. Players who spoke in fewer than two Phase 1
    blocks get a missing change and are not flagged.

    Returns one row per (gameId, playerId) with `phase1LengthChange` and
    `lengthIncreaseFlag`.
    """
    keys = ["gameId", "playerId"]
    p1 = speaker_utterances[speaker_utterances["phaseNum"] == 1]
    per_block = (
        p1.groupby(keys + ["blockNum"])["uttLength"]
        .mean()
        .reset_index()
        .sort_values(keys + ["blockNum"])
    )
    grouped = per_block.groupby(keys)
    out = pd.DataFrame(
        {
            "n_blocks": grouped["blockNum"].nunique(),
            "phase1LengthChange": grouped["uttLength"].last()
            - grouped["uttLength"].first(),
        }
    ).reset_index()
    out.loc[out["n_blocks"] < 2, "phase1LengthChange"] = float("nan")
    out["lengthIncreaseFlag"] = out["phase1LengthChange"] > threshold
    return out[keys + ["phase1LengthChange", "lengthIncreaseFlag"]]


def build_social_guesses(
    player_round_df: pd.DataFrame, game_df: pd.DataFrame, trials: pd.DataFrame
) -> pd.DataFrame:
    """Build social_guesses.csv: 1 row per social-identification *opportunity*.

    One row per eligible Phase 2 listener in a social-guessing condition,
    whether or not a guess was submitted, because the accuracy denominator is
    response opportunities rather than submitted answers. A listener who
    never answered appears with socialGuess and socialGuessCorrect empty and
    socialTimeout true; the analysis codes those as unsuccessful. Rows where
    the speaker said nothing carry responseOpportunity false and are excluded
    from the denominator instead of counted as failures.

    socialGuessCorrect is left exactly as the server scored it: it is set only
    for guesses that arrived by the Selection deadline, so it is empty both
    for a nonresponse and for a late guess. Which of those a row is comes from
    socialTimeout and lateSocialGuess, and the 0/1 outcome is built from them
    in the analysis (analysis/R/prepare.R) rather than here.
    """
    pr = drop_last_changed_cols(player_round_df)
    pr = pr[pr["phase"] == "refgame"].copy()

    columns = [
        "gameId",
        "playerId",
        "originalGroup",
        "blockNum",
        "phase",
        "phaseNum",
        "roundId",
        "currentGroup",
        "target",
        "socialGuess",
        "socialGuessCorrect",
        "socialRoundScore",
        "socialTimeout",
        "lateSocialGuess",
        "hasSpeakerMessage",
        "responseOpportunity",
        "speakerId",
        "tangramSet",
    ]

    social_games = set(
        game_df.loc[
            game_df["condition"]
            .replace({"exp2_social_goal": "social_first"})
            .isin(SOCIAL_GUESSING_CONDITIONS),
            "id",
        ]
    )

    # The opportunity frame: every Phase 2 listener trial of a social-guessing
    # game. Removed players and terminated games contribute no trial rows, so
    # this is already restricted to listeners who were in the game.
    opportunities = trials[
        (trials["role"] == "listener")
        & (trials["phaseNum"] == 2)
        & (trials["gameId"].isin(social_games))
    ].copy()

    if opportunities.empty or "social_guess" not in pr.columns:
        return pd.DataFrame(columns=columns)

    # Speaker of each (round, group): a roundId is shared across all groups in
    # a game, so the group is required to attribute a guess to the speaker the
    # listener actually heard
    speaker_lookup = (
        pr[pr["role"] == "speaker"][["roundID", "current_group", "playerID"]]
        .drop_duplicates()
        .set_index(["roundID", "current_group"])["playerID"]
        .to_dict()
    )

    submitted = pr[pr["social_guess"].notna() & (pr["social_guess"] != "")][
        ["gameID", "playerID", "roundID", "social_guess", "social_guess_correct", "social_round_score"]
    ].rename(
        columns={
            "gameID": "gameId",
            "playerID": "playerId",
            "roundID": "roundId",
            "social_guess": "socialGuess",
            "social_guess_correct": "socialGuessCorrect",
            "social_round_score": "socialRoundScore",
        }
    )

    guesses = opportunities.merge(
        submitted, on=["gameId", "playerId", "roundId"], how="left"
    )
    guesses["socialTimeout"] = guesses["socialGuess"].isna()
    guesses["speakerId"] = [
        speaker_lookup.get((round_id, group))
        for round_id, group in zip(guesses["roundId"], guesses["currentGroup"])
    ]

    return guesses[columns]


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess Empirica export data for analysis"
    )
    parser.add_argument("input_dir", help="Path to Empirica export-data directory")
    parser.add_argument(
        "--output",
        "-o",
        default="analysis/processed_data/",
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

    # Messages are built before trials because a trial's response opportunity
    # depends on whether that group's speaker said anything.
    print("Building messages.csv...")
    messages = build_messages(player_round_df, game_df, round_df)
    messages.to_csv(output_dir / "messages.csv", index=False)
    print(f"  {len(messages)} messages")

    print("Building trials.csv...")
    trials = add_response_opportunity(
        build_trials(player_round_df, round_df, game_df), messages
    )
    trials.to_csv(output_dir / "trials.csv", index=False)
    listener_rows = int((trials["role"] == "listener").sum())
    opportunities = int(trials["responseOpportunity"].sum())
    print(
        f"  {len(trials)} trial rows; {opportunities} of {listener_rows} listener "
        f"rows are response opportunities "
        f"({listener_rows - opportunities} had no speaker message)"
    )

    print("Building speaker_utterances.csv...")
    speaker_utterances = build_speaker_utterances(messages, trials)
    speaker_utterances.to_csv(output_dir / "speaker_utterances.csv", index=False)
    print(f"  {len(speaker_utterances)} speaker utterances")

    # players.csv is written after the utterances because the AI-use flag
    # (Phase 1 description-length increase) is computed from them.
    print("Building players.csv...")
    players = build_players(player_df).merge(
        flag_length_increase(speaker_utterances), on=["gameId", "playerId"], how="left"
    )
    players["lengthIncreaseFlag"] = players["lengthIncreaseFlag"].fillna(False).astype(bool)
    players.to_csv(output_dir / "players.csv", index=False)
    print(f"  {len(players)} players, {int(players['lengthIncreaseFlag'].sum())} flagged for a Phase 1 length increase")

    print("Building social_guesses.csv...")
    social_guesses = build_social_guesses(player_round_df, game_df, trials)
    social_guesses.to_csv(output_dir / "social_guesses.csv", index=False)
    if social_guesses.empty:
        print("  no social-guessing games")
    else:
        eligible = int(social_guesses["responseOpportunity"].sum())
        answered = int((~social_guesses["socialTimeout"]).sum())
        print(
            f"  {len(social_guesses)} social-guess opportunities; {eligible} eligible, "
            f"{answered} answered"
        )

    print(f"\nAll CSVs written to {output_dir}")


if __name__ == "__main__":
    main()
