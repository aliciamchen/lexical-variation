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
    # `minutesSpent` and `gameEndTime` are set for players who finish as well
    # as those removed early (see onGameEnded), so time on task is available
    # for everyone. `quiz_attempts` is a comprehension covariate, and
    # `shuffled_tangrams` is the participant's own grid layout, which nothing
    # else records and which is what makes position-based descriptions fail.
    optional_cols = [
        "player_index",
        "exitSurvey",
        "exitReason",
        "ended",
        "gameStartTime",
        "gameEndTime",
        "minutesSpent",
        "quiz_attempts",
        "shuffled_tangrams",
        "client_context",
        "engagement_events",
        "engagement_log_truncated",
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
        "player_index": "playerIndex",
        "exitSurvey": "exitSurvey",
        "exitReason": "exitReason",
        "ended": "ended",
        "gameStartTime": "gameStartTime",
        "gameEndTime": "gameEndTime",
        "minutesSpent": "minutesSpent",
        "quiz_attempts": "quizAttempts",
        "shuffled_tangrams": "shuffledTangrams",
        "client_context": "clientContext",
        "engagement_events": "engagementEvents",
        "engagement_log_truncated": "engagementLogTruncated",
        "partialPay": "partialPay",
        "partialBasePay": "partialBasePay",
        "partialBonus": "partialBonus",
    }
    players = players.rename(columns={c: rename_map[c] for c in cols})

    # The speaker-rotation index (0, 1, 2) within the original group: the
    # designated speaker of block b is the member with index b % 3, and the
    # Phase 2 reshuffle places one player of each index in every group.
    if "playerIndex" in players.columns:
        players["playerIndex"] = players["playerIndex"].astype("Int64")

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

    # Columns that depend on the export's vintage are always present, so a
    # notebook can reference them without first checking when the data was
    # collected. Absent in an older export means empty, not missing.
    for column in ("quizAttempts", "minutesSpent", "shuffledTangrams"):
        if column not in players.columns:
            players[column] = pd.NA
    players["quizAttempts"] = players["quizAttempts"].astype("Int64")

    players = flatten_client_context(players)
    players = summarize_engagement(players)

    return players


# Coarse device fields recorded at the start of the session, and the tidy
# column each becomes. The raw user agent is deliberately absent: it is
# stripped during anonymization (see analysis/extract_run.py).
CLIENT_CONTEXT_FIELDS = {
    "viewportWidth": "clientViewportWidth",
    "viewportHeight": "clientViewportHeight",
    "screenWidth": "clientScreenWidth",
    "screenHeight": "clientScreenHeight",
    "devicePixelRatio": "clientDevicePixelRatio",
    "timezoneOffsetMin": "clientTimezoneOffsetMin",
    "language": "clientLanguage",
    "touch": "clientTouch",
}


def flatten_client_context(players: pd.DataFrame) -> pd.DataFrame:
    """Expand the recorded device/viewport blob into one column per field.

    Viewport size matters here because the task is a 4x4 grid of 16 tangrams,
    so it bears on how much visual search a selection takes. The JSON column is
    replaced by its fields; exports without it get the columns as empty, so the
    schema does not depend on the export's vintage.
    """
    if "clientContext" not in players.columns:
        for column in CLIENT_CONTEXT_FIELDS.values():
            players[column] = pd.NA
        return players

    parsed = players["clientContext"].apply(parse_json_field)
    for field, column in CLIENT_CONTEXT_FIELDS.items():
        players[column] = parsed.apply(
            lambda ctx, f=field: ctx.get(f) if isinstance(ctx, dict) else None
        )
    return players.drop(columns=["clientContext"])


def summarize_engagement(players: pd.DataFrame) -> pd.DataFrame:
    """Reduce the raw engagement log to per-player counts and hidden time.

    The log records when the tab was hidden or shown and when the browser went
    offline or came back, which is what separates a participant who was absent
    from one who was present and did not act. The per-event list stays in the
    raw export; the tidy table carries the summary the analysis uses.
    """
    summary_columns = [
        "tabHiddenCount",
        "tabHiddenMs",
        "offlineCount",
        "resizeCount",
    ]
    if "engagementEvents" not in players.columns:
        for column in summary_columns:
            players[column] = pd.NA
        if "engagementLogTruncated" not in players.columns:
            players["engagementLogTruncated"] = pd.NA
        return players

    summaries = players["engagementEvents"].apply(
        lambda raw: _engagement_summary(parse_json_field(raw))
    )
    for column in summary_columns:
        players[column] = summaries.apply(lambda d, c=column: d[c])
    return players.drop(columns=["engagementEvents"])


def _engagement_summary(events) -> dict:
    """Counts and total hidden time for one player's engagement log.

    Hidden time pairs each `hidden` with the next `visible`. A trailing
    `hidden` with no matching `visible` -- the participant closed or abandoned
    the tab -- contributes to the count but not to the total, since there is no
    defensible end for it.
    """
    empty = {
        "tabHiddenCount": pd.NA,
        "tabHiddenMs": pd.NA,
        "offlineCount": pd.NA,
        "resizeCount": pd.NA,
    }
    if not isinstance(events, list):
        return empty

    hidden_count = 0
    hidden_ms = 0
    offline_count = 0
    resize_count = 0
    hidden_since = None

    for event in events:
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        stamp = event.get("t")
        if kind == "hidden":
            hidden_count += 1
            hidden_since = stamp
        elif kind == "visible":
            if hidden_since is not None and stamp is not None:
                hidden_ms += max(0, stamp - hidden_since)
            hidden_since = None
        elif kind == "offline":
            offline_count += 1
        elif kind == "resize":
            resize_count += 1

    return {
        "tabHiddenCount": hidden_count,
        "tabHiddenMs": hidden_ms,
        "offlineCount": offline_count,
        "resizeCount": resize_count,
    }


def selection_stage_times(stage_df: pd.DataFrame | None) -> pd.DataFrame:
    """Server-clock start and end of each round's Selection stage, in epoch ms.

    Empirica stamps a `*LastChangedAt` on every attribute; these two are the
    ones the analysis needs, so they are read here rather than carried through
    every table. They are on the server's clock, unlike the participant-side
    stamps in `trials.csv`, which makes them the reference for how long a trial
    actually ran and a cross-check on a client whose clock drifted.

    Returns an empty frame with the right columns when there is no stage table
    or it lacks the timestamps, so callers can merge unconditionally.
    """
    columns = ["roundId", "selectionStartedAt", "selectionEndedAt"]
    if stage_df is None or stage_df.empty:
        return pd.DataFrame(columns=columns)

    needed = {"roundID", "name", "startedLastChangedAt", "endedLastChangedAt"}
    if not needed.issubset(stage_df.columns):
        return pd.DataFrame(columns=columns)

    selection = stage_df[stage_df["name"] == "Selection"].copy()
    if selection.empty:
        return pd.DataFrame(columns=columns)

    out = pd.DataFrame(
        {
            "roundId": selection["roundID"].values,
            "selectionStartedAt": _epoch_ms(selection["startedLastChangedAt"]),
            "selectionEndedAt": _epoch_ms(selection["endedLastChangedAt"]),
        }
    )
    # One Selection stage per round; guard against a re-exported duplicate.
    return out.drop_duplicates(subset=["roundId"])


def _epoch_ms(series: pd.Series) -> pd.Series:
    """Parse Empirica's ISO-8601 UTC timestamps to epoch milliseconds.

    Milliseconds keep the server columns in the same unit as the client-side
    `Date.now()` stamps, so differences between them are meaningful without
    per-column unit handling.
    """
    parsed = pd.to_datetime(series, format="ISO8601", utc=True, errors="coerce")
    return (parsed.astype("int64") // 1_000_000).where(parsed.notna()).astype("Int64")


def build_trials(
    player_round_df: pd.DataFrame,
    round_df: pd.DataFrame,
    game_df: pd.DataFrame,
    player_df: pd.DataFrame | None = None,
    stage_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build trials.csv: 1 row per player per round (refgame rounds only).

    `player_df` supplies each player's rotation index, used to derive whether
    the block's designated speaker was replaced in exports that predate the
    server's own `speaker_reassigned` flag. `stage_df` supplies the Selection
    stage's server-clock start and end; it is optional, and the timing columns
    are empty without it.

    Two clocks meet in this table. `selectionRenderedAt`, `tangramSelectedAt`,
    `clickedAt`, and `socialGuessSelectedAt` are stamped by the participant's
    own browser, so differences among them are valid within a participant but
    must never be compared across participants, whose clocks are not
    synchronized. `selectionStartedAt` and `selectionEndedAt` come from the
    server and are comparable across everyone.
    """
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
    # Participant-side timing (September 2026 onward; empty for the pilot).
    #
    # `clickedAt` is when the selection was committed to the server, which is
    # what the late-arrival audit needs. `tangramSelectedAt` is when the
    # participant actually chose. The two coincide in the referential
    # conditions, where a click commits at once, but not in the social
    # conditions, where both answers are held locally until submit -- so
    # `tangramSelectedAt` is the column to use for a response time, and the
    # only one comparable across conditions.
    for source, column in (
        ("clicked_at", "clickedAt"),
        ("tangram_selected_at", "tangramSelectedAt"),
        ("selection_rendered_at", "selectionRenderedAt"),
        ("social_guess_selected_at", "socialGuessSelectedAt"),
    ):
        trials[column] = (
            pd.to_numeric(pr[source], errors="coerce").values
            if source in pr.columns
            else pd.NA
        )

    # Response time from the stage appearing on this participant's screen to
    # their choice. Both ends are the same browser's clock, so clock skew
    # between participants cannot contaminate it.
    trials["selectionRt"] = pd.to_numeric(
        trials["tangramSelectedAt"], errors="coerce"
    ) - pd.to_numeric(trials["selectionRenderedAt"], errors="coerce")
    trials["socialGuessRt"] = pd.to_numeric(
        trials["socialGuessSelectedAt"], errors="coerce"
    ) - pd.to_numeric(trials["selectionRenderedAt"], errors="coerce")

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

    # The server's own record of whether the designated speaker was replaced
    # (September 2026 onward); kept aside and added last so the column order
    # does not depend on the export's vintage. Rows and `pr` are still aligned
    # here because no merge has happened yet.
    server_reassigned = (
        pr["speaker_reassigned"].fillna(False).astype(bool).values
        if "speaker_reassigned" in pr.columns
        else None
    )

    # Merge trialNum (and the reshuffle mode the server recorded on the round,
    # when present) from round, and tangramSet from game
    round_cols = ["id", "trial_num"] + (
        ["reshuffle_mode"] if "reshuffle_mode" in rd.columns else []
    )
    round_info = rd[round_cols].rename(
        columns={"id": "roundId", "trial_num": "trialNum", "reshuffle_mode": "reshuffleMode"}
    )
    trials = trials.merge(round_info, on="roundId", how="left")
    if "reshuffleMode" not in trials.columns:
        trials["reshuffleMode"] = pd.NA

    tangram_lookup = game_df[["id", "tangram_set"]].rename(
        columns={"id": "gameId", "tangram_set": "tangramSet"}
    )
    trials = trials.merge(tangram_lookup, on="gameId", how="left")

    # Server-clock stage boundaries: how long the trial actually ran, and the
    # reference against which a drifting client clock shows up.
    stage_times = selection_stage_times(stage_df)
    if stage_times.empty:
        trials["selectionStartedAt"] = pd.NA
        trials["selectionEndedAt"] = pd.NA
    else:
        trials = trials.merge(stage_times, on="roundId", how="left")
    trials["selectionDurationMs"] = pd.to_numeric(
        trials["selectionEndedAt"], errors="coerce"
    ) - pd.to_numeric(trials["selectionStartedAt"], errors="coerce")

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

    return add_network_columns(trials, player_df, server_reassigned)


def add_network_columns(
    trials: pd.DataFrame,
    player_df: pd.DataFrame | None = None,
    server_reassigned=None,
) -> pd.DataFrame:
    """Add speakerId, inGroupSpeaker, groupSize, and speakerReassigned.

    The speaker of each trial's group, each listener's in-group status, and the
    group size come from the trio membership in the table itself, which is the
    same definition the R helper `attach_speaker()` uses. The server also
    records `speaker_id` and `in_group_listener` since September 2026; deriving
    them here keeps the pilot on the same definition, and the integrity suite
    cross-checks the two where both exist.

    `speakerReassigned` is the server's flag when the export has one
    (`server_reassigned`, aligned with the rows), and otherwise is derived from
    the speaker's rotation index in `player_df`: the designated speaker of
    block b has index b % 3, so any other index means the role was reassigned
    after a removal. It is missing when neither source is available.
    """
    trials = trials.copy()
    speakers = (
        trials.loc[
            trials["role"] == "speaker",
            ["gameId", "roundId", "currentGroup", "playerId", "originalGroup"],
        ]
        .drop_duplicates(["gameId", "roundId", "currentGroup"])
        .rename(columns={"playerId": "speakerId", "originalGroup": "speakerGroup"})
    )
    trials = trials.merge(speakers, on=["gameId", "roundId", "currentGroup"], how="left")

    is_listener = (trials["role"] == "listener") & trials["speakerId"].notna()
    in_group = pd.Series(pd.NA, index=trials.index, dtype="boolean")
    in_group[is_listener] = (trials["originalGroup"] == trials["speakerGroup"])[is_listener]
    trials["inGroupSpeaker"] = in_group
    trials["groupSize"] = trials.groupby(["gameId", "roundId", "currentGroup"])[
        "playerId"
    ].transform("nunique")

    if server_reassigned is not None:
        trials["speakerReassigned"] = pd.array(server_reassigned, dtype="boolean")
    elif player_df is not None and "player_index" in player_df.columns:
        idx = drop_last_changed_cols(player_df)[["id", "player_index"]].rename(
            columns={"id": "speakerId", "player_index": "speakerIndex"}
        )
        trials = trials.merge(idx, on="speakerId", how="left")
        derived = pd.Series(pd.NA, index=trials.index, dtype="boolean")
        known = trials["speakerIndex"].notna()
        derived[known] = trials.loc[known, "speakerIndex"].astype(int) != (
            trials.loc[known, "blockNum"].astype(int) % GROUP_SIZE
        )
        trials["speakerReassigned"] = derived
        trials = trials.drop(columns=["speakerIndex"])
    else:
        trials["speakerReassigned"] = pd.Series(pd.NA, index=trials.index, dtype="boolean")

    return trials.drop(columns=["speakerGroup"])


# The conditions whose Phase 2 includes the social-identification task. Mirrors
# hasSocialGuessing() in experiment/shared/constants.js.
SOCIAL_GUESSING_CONDITIONS = ("social_mixed", "social_first")

# Players per group; mirrors GROUP_SIZE in experiment/shared/constants.js
GROUP_SIZE = 3


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
                    # How the message was produced (recorded from September
                    # 2026; absent in earlier exports, including the pilot).
                    # Both come from the sender's own clock, so composeMs below
                    # is a within-client interval.
                    "composeStartedAt": msg.get("composeStartedAt"),
                    "pasted": msg.get("pasted"),
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

        # Composition time: from the first character typed to the moment the
        # message was sent. A production-effort measure alongside word count,
        # and the clearest signal of pasted text when a long message has a
        # near-zero interval. Empty for exports that predate the instrument.
        messages["composeMs"] = (
            pd.to_numeric(messages["timestamp"], errors="coerce")
            - pd.to_numeric(messages["composeStartedAt"], errors="coerce")
        )
        messages["pasted"] = messages["pasted"].astype("boolean")

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
        "socialGuessSelectedAt",
        "socialGuessRt",
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

    # The guess-timing columns ride along from trials.csv. They are empty for
    # exports that predate the instrument, and absent entirely if a caller
    # passes a trial frame built without them, so the schema is filled in here
    # rather than assumed.
    for column in columns:
        if column not in guesses.columns:
            guesses[column] = pd.NA

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
    # Optional: older extracts may not carry it, and only the Selection stage's
    # server-clock boundaries are read from it.
    stage_path = input_dir / "stage.csv"
    stage_df = pd.read_csv(stage_path) if stage_path.exists() else None

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
        build_trials(player_round_df, round_df, game_df, player_df, stage_df),
        messages,
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
