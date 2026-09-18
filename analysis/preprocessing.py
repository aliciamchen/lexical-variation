"""
Preprocessing script for Empirica experiment data.

Parses raw Empirica export CSVs and produces clean analysis-ready CSVs.

Usage:
    uv run python analysis/preprocessing.py data/<dataset>/raw_anonymized/ --output data/<dataset>/

process_data.py runs this as its first step with those two paths for the
active dataset.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from dataset_paths import (
    FILTERED_UTTERANCES_FILE,
    FILTERED_UTTERANCES_SIDECAR,
    filtered_utterances_status,
)


def drop_last_changed_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Drop all *LastChangedAt columns."""
    return df[[c for c in df.columns if not c.endswith("LastChangedAt")]]


# Malformed JSON values swallowed by parse_json_field, counted per column so
# that a corrupt export is reported once per column instead of silently
# yielding empty values. Reported by report_malformed_json() at the end of a
# run (and reset), so a value that cannot be parsed can never pass unnoticed.
_MALFORMED_JSON: Counter = Counter()


def parse_json_field(val, column: str | None = None):
    """Safely parse a JSON string, returning None on failure.

    A missing or empty value is simply None. A value that is present but not
    valid JSON is also None, but is counted under `column` (or "<unknown>")
    so the run can report how many such values each column had.
    """
    if pd.isna(val) or val == "":
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        _MALFORMED_JSON[column or "<unknown>"] += 1
        return None


def parse_json_column(series: pd.Series, column: str | None = None) -> pd.Series:
    """parse_json_field over a whole column, attributing failures to its name."""
    name = column or (str(series.name) if series.name is not None else None)
    return series.apply(lambda raw: parse_json_field(raw, name))


def report_malformed_json() -> dict[str, int]:
    """Print one line per column that had unparsable JSON, then reset the count."""
    counts = dict(_MALFORMED_JSON)
    for column, n in sorted(counts.items()):
        print(
            f"  Warning: {n} value(s) in column {column!r} were not valid JSON and "
            "were treated as missing"
        )
    _MALFORMED_JSON.clear()
    return counts


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
    # where a game actually ended early. `callbackErrors` and
    # `lastCallbackError` are written by the server's callback guard
    # (experiment/server/src/guard.js): Empirica does not catch what a callback
    # throws, and the guard contains the error so the other players can finish,
    # which means the game looks healthy from the browser and this count is the
    # only trace in the data. A game with a non-zero count is one to inspect
    # before trusting its rows.
    optional_cols = [
        "ended",
        "endedReason",
        "gameTerminated",
        "callbackErrors",
        "lastCallbackError",
    ]
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

    # activeGroups is the number of original groups still viable when the game
    # ended, from the JSON list the server keeps on the game. An empty list is a
    # game whose groups were all disbanded, so it counts as 0; only a missing or
    # unparsable value is left empty.
    def count_groups(raw):
        parsed = parse_json_field(raw, "active_groups")
        return len(parsed) if isinstance(parsed, list) else None

    games["activeGroups"] = games["activeGroups"].apply(count_groups).astype("Int64")

    # Provenance: the Empirica batch the game ran in (one batch per session)
    # and the export it was read from (combine_runs.py stamps `_sourceRun`
    # with the export timestamp). Both let a game be traced back to a session
    # and to the ledger that paid it. Added last so the column order of older
    # exports is unchanged.
    games["batchId"] = (
        game_df["batchID"].values if "batchID" in game_df.columns else pd.NA
    )
    games["sourceRun"] = (
        game_df["_sourceRun"].values if "_sourceRun" in game_df.columns else pd.NA
    )

    return games


def add_active_groups_min(
    games: pd.DataFrame, round_df: pd.DataFrame, trials: pd.DataFrame
) -> pd.DataFrame:
    """Add activeGroupsMin: the smallest number of groups any Phase 2 trial was played with.

    `activeGroups` is the server's count of viable *original* groups at the end
    of the game. In the mixed conditions the Phase 2 roster is reshuffled into
    new groups every trial, and after removals it can form fewer groups than
    there are viable original groups (five players make a trio and a pair, not
    three groups), so the two can differ. This column is what the roster-size
    checks in the analysis need: per Phase 2 refgame round it takes the
    server's `reshuffle_groups` when the export has it, otherwise the number
    of distinct `currentGroup` values with a speaker in that round's trials,
    and reports the minimum. Rounds with neither (created but never played)
    are skipped, and a game with no usable Phase 2 round falls back to
    `activeGroups`.
    """
    games = games.copy()
    rd = drop_last_changed_cols(round_df)
    p2_rounds = rd[(rd["phase"] == "refgame") & (rd["phase_num"] == 2)]
    has_server_count = "reshuffle_groups" in p2_rounds.columns

    speakers = trials[(trials["role"] == "speaker") & (trials["phaseNum"] == 2)]
    groups_per_round = speakers.groupby("roundId")["currentGroup"].nunique()

    minima = {}
    for game_id, rounds in p2_rounds.groupby("gameID"):
        counts = []
        for _, rnd in rounds.iterrows():
            if has_server_count and pd.notna(rnd["reshuffle_groups"]):
                counts.append(int(rnd["reshuffle_groups"]))
            elif rnd["id"] in groups_per_round.index:
                counts.append(int(groups_per_round[rnd["id"]]))
        if counts:
            minima[game_id] = min(counts)

    games["activeGroupsMin"] = (
        games["gameId"].map(minima).astype("Int64").fillna(games["activeGroups"])
    ).astype("Int64")
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
            survey = parse_json_field(row["exitSurvey"], "exitSurvey")
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

    parsed = parse_json_column(players["clientContext"], "client_context")
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
        lambda raw: _engagement_summary(parse_json_field(raw, "engagement_events"))
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
    # Subtracting the epoch and floor-dividing by one millisecond is
    # resolution-independent. `parsed.astype("int64") // 1_000_000` is not:
    # pandas 2 keeps the resolution it parsed, and these timestamps carry
    # microseconds, so int64 yields microseconds and that formula returned
    # SECONDS while the name, the docstring and every consumer said
    # milliseconds. Every value was 1000x too small, which is how a 45-second
    # stage came out as "45 ms" and made client response times look longer than
    # the stage that contained them.
    delta = parsed - pd.Timestamp(0, unit="ms", tz="UTC")
    return (delta // pd.Timedelta(milliseconds=1)).astype("Int64")


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
    # A stage cannot last no time at all, let alone a negative time. Both ends
    # come from Empirica's `*LastChangedAt` columns, which record when an
    # attribute was last modified rather than when the stage truly began and
    # ended, so a re-write of `started` can land after `ended` and yield a
    # negative span. That is an artifact of the source, not a measurement, and
    # leaving it in would put nonsense into every response-time comparison, so
    # those stages are recorded as unknown.
    unusable = trials["selectionDurationMs"].notna() & (trials["selectionDurationMs"] <= 0)
    if unusable.any():
        rounds = trials.loc[unusable, "roundId"].nunique()
        print(
            f"  {int(unusable.sum())} trial rows in {rounds} round(s) had an "
            "unusable Selection stage span (ended at or before it started); "
            "recorded as unknown"
        )
        trials.loc[unusable, "selectionDurationMs"] = pd.NA

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
    group size are *derived* here from the trio membership in the table itself
    (the rows sharing a game, round, and currentGroup), which is the same
    definition the R helper `attach_speaker()` uses. That keeps every export,
    including the pilot, on one definition. The server has recorded its own
    `speaker_id`, `in_group_listener`, and `group_size` on each player-round
    since September 2026; those are carried separately as `serverSpeakerId`,
    `serverInGroupListener`, and `serverGroupSize` by
    `add_server_network_columns()` (empty for the pilot), and the integrity
    suite (`TestReshuffleNetwork`) checks that the derived and recorded values
    agree wherever the recorded ones exist.

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


# Server-recorded network attributes (September 2026 onward): the player-round
# keys and the round keys, each with the trials.csv column it becomes. All are
# empty for the pilot, whose exports predate them.
SERVER_PLAYER_ROUND_COLUMNS = {
    "speaker_id": "serverSpeakerId",
    "in_group_listener": "serverInGroupListener",
    "group_size": "serverGroupSize",
}
SERVER_ROUND_COLUMNS = {
    "reshuffle_groups": "reshuffleGroups",
    "reshuffle_trios": "reshuffleTrios",
    "reshuffle_trios_ok": "reshuffleTriosOk",
    "reshuffle_pairs": "reshufflePairs",
}


def add_server_network_columns(
    trials: pd.DataFrame, player_round_df: pd.DataFrame, round_df: pd.DataFrame
) -> pd.DataFrame:
    """Carry the server's own record of the network beside the derived columns.

    `speakerId`, `inGroupSpeaker`, and `groupSize` are derived from the trio
    membership in the table (see `add_network_columns`). Since September 2026
    the server also writes `speaker_id`, `in_group_listener`, and `group_size`
    on every player-round, and on every mixed Phase 2 round the outcome of the
    reshuffle: how many groups it formed, how many were trios, how many of
    those trios had exactly one in-group listener, and how many were pairs.
    Those come through here as `server*` and `reshuffle*` columns so the two
    accounts can be compared row by row; the integrity suite does that
    wherever the server columns are non-empty. Every column exists whatever
    the export's vintage, empty when the export predates the record.
    """
    trials = trials.copy()
    keys = ["gameId", "playerId", "roundId"]

    pr = drop_last_changed_cols(player_round_df)
    pr = pr[pr["phase"] == "refgame"]
    present = [c for c in SERVER_PLAYER_ROUND_COLUMNS if c in pr.columns]
    if present:
        server = pr[["gameID", "playerID", "roundID"] + present].rename(
            columns={"gameID": "gameId", "playerID": "playerId", "roundID": "roundId",
                     **SERVER_PLAYER_ROUND_COLUMNS}
        ).drop_duplicates(keys)
        trials = trials.merge(server, on=keys, how="left")
    for column in SERVER_PLAYER_ROUND_COLUMNS.values():
        if column not in trials.columns:
            trials[column] = pd.NA
    trials["serverInGroupListener"] = trials["serverInGroupListener"].astype("boolean")
    trials["serverGroupSize"] = pd.to_numeric(trials["serverGroupSize"], errors="coerce").astype("Int64")

    rd = drop_last_changed_cols(round_df)
    present = [c for c in SERVER_ROUND_COLUMNS if c in rd.columns]
    if present:
        counts = rd[["id"] + present].rename(
            columns={"id": "roundId", **SERVER_ROUND_COLUMNS}
        ).drop_duplicates("roundId")
        trials = trials.merge(counts, on="roundId", how="left")
    for column in SERVER_ROUND_COLUMNS.values():
        if column not in trials.columns:
            trials[column] = pd.NA
        trials[column] = pd.to_numeric(trials[column], errors="coerce").astype("Int64")
    return trials


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


# ── Participant exclusions ───────────────────────────────────────────────────

PARTICIPANT_EXCLUSIONS_FILE = "participant_exclusions.csv"


def read_participant_exclusions(path: Path) -> pd.DataFrame:
    """Read data/<dataset>/participant_exclusions.csv (playerId, reason).

    The file lists participants whose data are excluded after the fact -- a
    confirmed AI-assisted player, a participant who reported not understanding
    the task, a duplicate account. It is optional; when present every row needs
    a non-empty reason, so an exclusion can never be silent, and a player id
    may appear only once. Returns an empty frame with the two columns when the
    file does not exist.
    """
    columns = ["playerId", "reason"]
    if not path.exists():
        return pd.DataFrame(columns=columns)
    exclusions = pd.read_csv(path, dtype=str)
    missing = [c for c in columns if c not in exclusions.columns]
    if missing:
        raise ValueError(f"{path.name} must have columns playerId,reason; missing {missing}")
    exclusions = exclusions[columns].copy()
    exclusions["playerId"] = exclusions["playerId"].fillna("").str.strip()
    exclusions["reason"] = exclusions["reason"].fillna("").str.strip()
    blank = exclusions[(exclusions["playerId"] == "") | (exclusions["reason"] == "")]
    if not blank.empty:
        raise ValueError(
            f"{len(blank)} row(s) of {path.name} have an empty playerId or reason; every "
            "exclusion needs both"
        )
    dup = exclusions["playerId"].duplicated()
    if dup.any():
        raise ValueError(
            f"{path.name} lists the same playerId more than once: "
            f"{sorted(exclusions.loc[dup, 'playerId'].unique())}"
        )
    return exclusions.reset_index(drop=True)


def apply_participant_exclusions(
    trials: pd.DataFrame, exclusions: pd.DataFrame
) -> pd.DataFrame:
    """Add `excluded` and `exclusionReason` to a trial-level table.

    A row is excluded when it is the excluded player's own, or when it is a
    listener's row on a trial the excluded player spoke in: a listener's
    selection is only as good as the description it answered, so the
    listener's data for that trial go with the speaker's. The reason is the
    participant's own on their rows and `speaker excluded: <reason>` on the
    listener rows, so the two kinds stay distinguishable. Nothing else is
    changed; in particular `responseOpportunity` is computed before this and
    still says whether the listener *could* have answered.

    Works on any frame with playerId, role, and speakerId (trials.csv and the
    social-guess opportunity frame).
    """
    trials = trials.copy()
    reasons = dict(zip(exclusions["playerId"], exclusions["reason"]))
    own = trials["playerId"].map(reasons)
    via_speaker = pd.Series(pd.NA, index=trials.index, dtype="object")
    if "speakerId" in trials.columns:
        listener = trials["role"] == "listener"
        via_speaker[listener] = trials.loc[listener, "speakerId"].map(reasons)
    via_speaker = via_speaker.where(via_speaker.isna(), "speaker excluded: " + via_speaker.astype(str))
    reason = own.where(own.notna(), via_speaker)
    trials["excluded"] = reason.notna()
    trials["exclusionReason"] = reason.fillna("")
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
        chat_json = parse_json_field(row.get("chat"), "chat")
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
        # The chat array is copied onto every group member's round, so each
        # message arrives once per member and the copies must collapse. `text`
        # is part of the key so that two genuinely different messages can never
        # merge: without it, one sender posting twice inside the same
        # millisecond would silently lose a line of the transcript, which is
        # the study's data. Adding it cannot keep a duplicate copy, because the
        # copies are identical by construction. (Checked against the pilot and
        # a rapid-burst export: no key holds two distinct texts, so this does
        # not change either output.)
        messages = messages.drop_duplicates(
            subset=["roundId", "senderId", "timestamp", "text"]
        )
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


# The columns that identify one speaker's turn in one round. Every speaker
# message of a round shares them, so grouping on them concatenates the round's
# messages into a single utterance.
UTTERANCE_KEY_COLUMNS = [
    "gameId", "roundId", "senderId", "blockNum", "phase", "phaseNum", "target",
    "trialNum", "tangramSet",
]

# Column order of speaker_utterances.csv and speaker_utterances_filtered.csv.
SPEAKER_UTTERANCE_COLUMNS = [
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


def assemble_speaker_utterances(
    speaker_msgs: pd.DataFrame, trials: pd.DataFrame
) -> pd.DataFrame:
    """One utterance per speaker per round from the given speaker messages.

    The messages of a round are joined in timestamp order with ", ", counted
    in words, and given the speaker's group and repetition number from their
    trial row. This is the one definition of an utterance: `build_speaker_
    utterances` passes every speaker message, and `filter_nonreferential.
    build_filtered_utterances` passes only the referential ones, so the two
    files can differ only in which messages went in.

    The grouping keys must be complete. pandas drops NaN keys from a groupby
    by default, which would lose a round's utterance without any trace, so the
    grouping keeps NaN keys and a NaN in any key column is an error here.
    """
    missing = speaker_msgs[UTTERANCE_KEY_COLUMNS].isna().sum()
    if (missing > 0).any():
        raise ValueError(
            "speaker messages have missing values in utterance key column(s) "
            f"{missing[missing > 0].to_dict()}; every message needs a complete key"
        )

    speaker_msgs = speaker_msgs.sort_values(["roundId", "timestamp"])
    utterances = (
        speaker_msgs.groupby(UTTERANCE_KEY_COLUMNS, dropna=False)
        .agg(utterance=("text", lambda x: ", ".join(x.astype(str))))
        .reset_index()
    )
    utterances["uttLength"] = utterances["utterance"].apply(lambda x: len(x.split()))

    # The speaker's own trial row (senderId == playerId) supplies their group
    # and the repetition number of the target.
    speaker_trials = trials[trials["role"] == "speaker"][
        ["gameId", "playerId", "originalGroup", "currentGroup", "roundId", "repNum"]
    ].drop_duplicates()
    utterances = utterances.merge(
        speaker_trials,
        left_on=["gameId", "roundId", "senderId"],
        right_on=["gameId", "roundId", "playerId"],
        how="left",
    )
    return utterances[[c for c in SPEAKER_UTTERANCE_COLUMNS if c in utterances.columns]]


def build_speaker_utterances(
    messages: pd.DataFrame, trials: pd.DataFrame
) -> pd.DataFrame:
    """Build speaker_utterances.csv: 1 row per speaker per trial."""
    speaker_msgs = messages[messages["senderRole"] == "speaker"].copy()
    utterances = assemble_speaker_utterances(speaker_msgs, trials)
    return utterances.sort_values(["gameId", "playerId", "blockNum", "target"])


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
        # Whether the speaker shared the listener's original group: the ground
        # truth every guess is judged against, and the in-group/out-group split
        # of the opportunity counts the analysis reports. The server records it
        # only for guesses it scored, so it is completed here from the
        # speaker's own original group, which is known for every opportunity.
        "speakerWasSameGroup",
        # From trials.csv (apply_participant_exclusions): the guesser's own
        # exclusion or their speaker's.
        "excluded",
        "exclusionReason",
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
    # A trial frame built without the exclusion pass (unit tests, older
    # callers) means nobody is excluded, not that the columns are unknown.
    if "excluded" not in opportunities.columns:
        opportunities["excluded"] = False
        opportunities["exclusionReason"] = ""

    # Speaker of each (round, group): a roundId is shared across all groups in
    # a game, so the group is required to attribute a guess to the speaker the
    # listener actually heard
    speaker_lookup = (
        pr[pr["role"] == "speaker"][["roundID", "current_group", "playerID"]]
        .drop_duplicates()
        .set_index(["roundID", "current_group"])["playerID"]
        .to_dict()
    )

    submitted_cols = [
        "gameID", "playerID", "roundID", "social_guess", "social_guess_correct",
        "social_round_score",
    ] + (["speaker_was_same_group"] if "speaker_was_same_group" in pr.columns else [])
    submitted = pr[pr["social_guess"].notna() & (pr["social_guess"] != "")][
        submitted_cols
    ].rename(
        columns={
            "gameID": "gameId",
            "playerID": "playerId",
            "roundID": "roundId",
            "social_guess": "socialGuess",
            "social_guess_correct": "socialGuessCorrect",
            "social_round_score": "socialRoundScore",
            "speaker_was_same_group": "speakerWasSameGroup",
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

    # Complete the ground truth over every opportunity. `scoring.js` writes
    # `speaker_was_same_group` only inside the branch that scores a submitted
    # guess, so taking the server's record alone would leave it empty exactly
    # for the nonresponses, and the in-group and out-group opportunity counts
    # the analysis reports would silently become answered-only. The speaker's
    # own original group is recorded on their trial row whether or not anyone
    # answered, so it is derived from there and the server's record is kept as
    # a cross-check.
    speaker_group_lookup = (
        trials[trials["role"] == "speaker"][["roundId", "currentGroup", "originalGroup"]]
        .drop_duplicates()
        .set_index(["roundId", "currentGroup"])["originalGroup"]
        .to_dict()
    )
    derived = []
    for round_id, group, listener_group in zip(
        guesses["roundId"], guesses["currentGroup"], guesses["originalGroup"]
    ):
        speaker_group = speaker_group_lookup.get((round_id, group))
        derived.append(pd.NA if speaker_group is None else speaker_group == listener_group)
    derived = pd.Series(derived, index=guesses.index, dtype="boolean")

    recorded = guesses["speakerWasSameGroup"].astype("boolean")
    both = recorded.notna() & derived.notna()
    if both.any() and not (recorded[both] == derived[both]).all():
        disagree = guesses.loc[both & (recorded != derived), ["gameId", "roundId", "playerId"]]
        raise ValueError(
            "speaker_was_same_group disagrees with the speaker's original group on "
            f"{len(disagree)} opportunities, so the speaker attribution is wrong:\n"
            f"{disagree.to_string(index=False)}"
        )
    guesses["speakerWasSameGroup"] = recorded.fillna(derived)

    return guesses[columns]


def retire_stale_filtered_utterances(output_dir: Path) -> bool:
    """Delete a speaker_utterances_filtered.csv built from a different messages.csv.

    Called right after messages.csv is rewritten. The filtered utterances are
    derived from messages.csv through the classifier's labels, and every later
    step prefers them when they exist, so a filtered file left over from a
    previous messages.csv would be analyzed in place of the current data. When
    the sidecar written by `filter_nonreferential.py apply` no longer matches,
    the file and its sidecar are deleted and the deletion is printed; the
    filter has to be rerun (`classify` sends only the messages it has not
    labeled before). A filtered file with no sidecar at all is left in place
    but announced, because the derived step will refuse it. Returns whether
    anything was deleted.
    """
    status, detail = filtered_utterances_status(output_dir)
    if status == "stale":
        for name in (FILTERED_UTTERANCES_FILE, FILTERED_UTTERANCES_SIDECAR):
            path = output_dir / name
            if path.exists():
                path.unlink()
                print(f"  Deleted stale {name}")
        print(f"  ({detail})")
        print("  Rerun filter_nonreferential.py classify + apply to rebuild it.")
        return True
    if status == "unverified":
        print(f"  Warning: {detail}; compute_derived.py will refuse it until the filter is rerun")
    elif status == "current":
        print(f"  {detail}")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess Empirica export data for analysis"
    )
    parser.add_argument(
        "input_dir",
        help="Directory of raw Empirica CSVs (data/<dataset>/raw_anonymized/ from combine_runs.py)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/pilots/",
        help="Output directory for the analysis-ready CSVs (data/<dataset>/; default: the pilot)",
    )
    parser.add_argument(
        "--exclusions",
        default=None,
        help=(
            "participant_exclusions.csv (playerId,reason); default: the file of that "
            "name in the output directory, if present"
        ),
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    exclusions_path = (
        Path(args.exclusions) if args.exclusions else output_dir / PARTICIPANT_EXCLUSIONS_FILE
    )
    if args.exclusions and not exclusions_path.exists():
        parser.error(f"--exclusions file not found: {exclusions_path}")

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

    # Build each output. games.csv is written after trials because the Phase 2
    # roster minimum (activeGroupsMin) is read off the trials table.
    print("Building games.csv...")
    games = build_games(game_df)

    # Participant exclusions are read first so a malformed file fails before
    # anything is written.
    exclusions = read_participant_exclusions(exclusions_path)
    if not exclusions.empty:
        unknown = sorted(set(exclusions["playerId"]) - set(player_df["id"].astype(str)))
        if unknown:
            raise SystemExit(
                f"Error: {exclusions_path.name} names {len(unknown)} playerId(s) not in "
                f"player.csv: {unknown}"
            )
        print(f"Excluding {len(exclusions)} participant(s) listed in {exclusions_path}")

    # Messages are built before trials because a trial's response opportunity
    # depends on whether that group's speaker said anything. Response
    # opportunities are computed from *all* messages, before excluded players'
    # messages are dropped: whether a listener could have answered does not
    # change because their speaker was excluded later.
    print("Building messages.csv...")
    messages = build_messages(player_round_df, game_df, round_df)
    all_messages = messages

    print("Building trials.csv...")
    trials = add_response_opportunity(
        build_trials(player_round_df, round_df, game_df, player_df, stage_df),
        all_messages,
    )
    trials = add_server_network_columns(trials, player_round_df, round_df)
    trials = apply_participant_exclusions(trials, exclusions)
    if not exclusions.empty:
        excluded_ids = set(exclusions["playerId"])
        own_rows = int(trials["playerId"].isin(excluded_ids).sum())
        print(
            f"  {int(trials['excluded'].sum())} trial rows flagged excluded "
            f"({own_rows} of the excluded players' own, the rest listeners they spoke to)"
        )
        dropped = messages["senderId"].isin(excluded_ids)
        messages = messages[~dropped].copy()
        print(f"  Dropped {int(dropped.sum())} messages sent by excluded participants")
    messages.to_csv(output_dir / "messages.csv", index=False)
    print(f"  {len(messages)} messages written to messages.csv")
    retire_stale_filtered_utterances(output_dir)
    trials.to_csv(output_dir / "trials.csv", index=False)
    listener_rows = int((trials["role"] == "listener").sum())
    opportunities = int(trials["responseOpportunity"].sum())
    print(
        f"  {len(trials)} trial rows; {opportunities} of {listener_rows} listener "
        f"rows are response opportunities "
        f"({listener_rows - opportunities} had no speaker message)"
    )

    games = add_active_groups_min(games, round_df, trials)
    games.to_csv(output_dir / "games.csv", index=False)
    print(f"  {len(games)} games written to games.csv")

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

    # JSON columns of the export that could not be parsed were treated as
    # missing above; say so once per column rather than never.
    if report_malformed_json():
        print("  Check the export: malformed JSON usually means a truncated or corrupted copy.")

    print(f"\nAll CSVs written to {output_dir}")


if __name__ == "__main__":
    main()
