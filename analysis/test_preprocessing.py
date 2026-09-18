"""
Unit tests for the preprocessing rules the preregistration states precisely:
the Phase 1 description-length flag used to trigger AI-use inspection, the
treatment of speaker rounds whose messages were all classified non-referential,
and the response-opportunity denominator shared by both accuracy outcomes.

Run with:
    uv run pytest analysis/test_preprocessing.py -v
"""

import json
import sys

import numpy as np
import pandas as pd
import pytest

import preprocessing

from dataset_paths import (
    FILTERED_UTTERANCES_FILE,
    FILTERED_UTTERANCES_SIDECAR,
    filtered_utterances_status,
    write_filtered_sidecar,
)
from filter_nonreferential import (
    BatchParseError,
    attach_labels,
    build_filtered_utterances,
    parse_batch_labels,
)
from combine_runs import DROPOUT_COLUMNS, exclude_games, read_excluded_games, split_dropouts
from preprocessing import (
    add_active_groups_min,
    add_network_columns,
    add_server_network_columns,
    apply_participant_exclusions,
    build_games,
    build_messages,
    build_players,
    add_response_opportunity,
    build_social_guesses,
    build_trials,
    flag_length_increase,
    read_participant_exclusions,
    retire_stale_filtered_utterances,
    selection_stage_times,
)


def _utt(player, phase, block, n_words, game="g1"):
    return {
        "gameId": game,
        "playerId": player,
        "phaseNum": phase,
        "blockNum": block,
        "utterance": " ".join(["w"] * n_words),
        "uttLength": n_words,
    }


def test_flag_is_set_only_when_last_block_exceeds_first_by_more_than_threshold():
    utterances = pd.DataFrame(
        [
            # shortening speaker: never flagged
            _utt("shortens", 1, 0, 12),
            _utt("shortens", 1, 0, 8),
            _utt("shortens", 1, 3, 3),
            # lengthening by exactly the threshold: not flagged
            _utt("at_threshold", 1, 1, 4),
            _utt("at_threshold", 1, 4, 9),
            # lengthening by more than the threshold: flagged
            _utt("lengthens", 1, 2, 6),
            _utt("lengthens", 1, 5, 12),
        ]
    )
    flags = flag_length_increase(utterances, threshold=5).set_index("playerId")

    assert flags.loc["shortens", "phase1LengthChange"] == 3 - 10
    assert not flags.loc["shortens", "lengthIncreaseFlag"]
    assert flags.loc["at_threshold", "phase1LengthChange"] == 5
    assert not flags.loc["at_threshold", "lengthIncreaseFlag"]
    assert flags.loc["lengthens", "phase1LengthChange"] == 6
    assert flags.loc["lengthens", "lengthIncreaseFlag"]


def test_flag_uses_first_and_last_speaker_block_regardless_of_row_order():
    utterances = pd.DataFrame(
        [
            _utt("p", 1, 5, 20),  # last block listed first
            _utt("p", 1, 2, 4),
            _utt("p", 1, 0, 6),
        ]
    )
    flags = flag_length_increase(utterances, threshold=5).set_index("playerId")
    assert flags.loc["p", "phase1LengthChange"] == 20 - 6
    assert flags.loc["p", "lengthIncreaseFlag"]


def test_flag_ignores_phase_2_and_needs_two_phase_1_blocks():
    utterances = pd.DataFrame(
        [
            # grows a lot in Phase 2 only: no flag
            _utt("p2_only", 1, 0, 5),
            _utt("p2_only", 1, 3, 5),
            _utt("p2_only", 2, 0, 30),
            # a single Phase 1 speaker block: change undefined, no flag
            _utt("one_block", 1, 1, 5),
            _utt("one_block", 1, 1, 9),
        ]
    )
    flags = flag_length_increase(utterances, threshold=5).set_index("playerId")
    assert flags.loc["p2_only", "phase1LengthChange"] == 0
    assert not flags.loc["p2_only", "lengthIncreaseFlag"]
    assert np.isnan(flags.loc["one_block", "phase1LengthChange"])
    assert not flags.loc["one_block", "lengthIncreaseFlag"]


def _msg(round_id, sender, text, referential, ts, role="speaker"):
    return {
        "gameId": "g1",
        "roundId": round_id,
        "senderId": sender,
        "blockNum": 0,
        "phase": "refgame",
        "phaseNum": 1,
        "target": "t1",
        "trialNum": 0,
        "tangramSet": 0,
        "senderRole": role,
        "text": text,
        "timestamp": ts,
        "is_referential": referential,
    }


def test_rounds_with_only_non_referential_messages_are_dropped_not_emptied():
    messages = pd.DataFrame(
        [
            _msg("r1", "s1", "the dancer", True, 1),
            _msg("r1", "s1", "thanks all", False, 2),
            _msg("r2", "s2", "good job", False, 1),
            _msg("r2", "s2", "lol", False, 2),
            _msg("r2", "l1", "which one?", True, 3, role="listener"),
        ]
    )
    trials = pd.DataFrame(
        [
            {"gameId": "g1", "playerId": "s1", "originalGroup": "A", "currentGroup": "A",
             "roundId": "r1", "repNum": 0, "role": "speaker"},
            {"gameId": "g1", "playerId": "s2", "originalGroup": "B", "currentGroup": "B",
             "roundId": "r2", "repNum": 0, "role": "speaker"},
        ]
    )
    utterances, n_dropped = build_filtered_utterances(messages, trials)

    assert n_dropped == 1
    assert utterances["playerId"].tolist() == ["s1"]
    assert utterances["utterance"].tolist() == ["the dancer"]
    assert utterances["uttLength"].tolist() == [2]
    assert (utterances["utterance"].str.strip() != "").all()


def test_batch_labels_are_matched_by_message_number_not_line_position():
    text = "3: NR\n1: R\n\n2: R\n"
    assert parse_batch_labels(text, 3) == ["R", "R", "NR"]


def test_batch_labels_accept_common_formatting_variants():
    text = "**1**: R\n2. NR\n3) r\n4 - **NR** (a greeting)"
    assert parse_batch_labels(text, 4) == ["R", "NR", "R", "NR"]


def test_batch_labels_fail_loudly_when_a_message_is_unlabeled():
    with pytest.raises(BatchParseError, match=r"no label for message\(s\) \[2\]"):
        parse_batch_labels("1: R\n3: NR", 3)


def test_batch_labels_fail_loudly_on_extra_or_conflicting_numbers():
    with pytest.raises(BatchParseError, match="outside the batch"):
        parse_batch_labels("1: R\n2: R\n3: NR", 2)
    with pytest.raises(BatchParseError, match="conflicting"):
        parse_batch_labels("1: R\n1: NR\n2: R", 2)


def test_batch_labels_ignore_prose_lines_without_a_number():
    text = "Here are the labels:\n1: R\n2: NR\nDone."
    assert parse_batch_labels(text, 2) == ["R", "NR"]


# ── Response opportunities ──────────────────────────────────────────────────


def _trial(player, role, round_id="r1", group="A", phase=2, game="g1"):
    return {
        "gameId": game,
        "playerId": player,
        "roundId": round_id,
        "role": role,
        "currentGroup": group,
        "originalGroup": group,
        "phaseNum": phase,
        "blockNum": 0,
        "target": "t1",
        # As build_trials() writes them, so the fixture matches trials.csv
        "phase": "refgame",
        "tangramSet": 0,
        "lateSocialGuess": False,
    }


def _message(sender, role, round_id="r1", group="A", game="g1"):
    return {
        "gameId": game,
        "roundId": round_id,
        "group": group,
        "senderId": sender,
        "senderRole": role,
        "text": "a description",
    }


class TestResponseOpportunity:
    def test_listener_with_a_speaking_speaker_has_an_opportunity(self):
        trials = pd.DataFrame([_trial("s1", "speaker"), _trial("l1", "listener")])
        messages = pd.DataFrame([_message("s1", "speaker")])
        out = add_response_opportunity(trials, messages)
        assert out.loc[out.playerId == "l1", "responseOpportunity"].item()

    def test_a_silent_speaker_leaves_the_listener_no_opportunity(self):
        trials = pd.DataFrame([_trial("s1", "speaker"), _trial("l1", "listener")])
        # Only a listener spoke, so the speaker never described the target.
        messages = pd.DataFrame([_message("l1", "listener")])
        out = add_response_opportunity(trials, messages)
        assert not out["hasSpeakerMessage"].any()
        assert not out["responseOpportunity"].any()

    def test_opportunity_is_per_group_not_per_round(self):
        """A roundId is shared across groups, so one group's speaker
        speaking must not create an opportunity in another group."""
        trials = pd.DataFrame([
            _trial("s1", "speaker", group="A"),
            _trial("l1", "listener", group="A"),
            _trial("s2", "speaker", group="B"),
            _trial("l2", "listener", group="B"),
        ])
        messages = pd.DataFrame([_message("s1", "speaker", group="A")])
        out = add_response_opportunity(trials, messages).set_index("playerId")
        assert out.loc["l1", "responseOpportunity"]
        assert not out.loc["l2", "responseOpportunity"]

    def test_speakers_are_never_opportunities(self):
        trials = pd.DataFrame([_trial("s1", "speaker"), _trial("l1", "listener")])
        messages = pd.DataFrame([_message("s1", "speaker")])
        out = add_response_opportunity(trials, messages).set_index("playerId")
        assert not out.loc["s1", "responseOpportunity"]

    def test_no_messages_at_all_means_no_opportunities(self):
        trials = pd.DataFrame([_trial("l1", "listener")])
        out = add_response_opportunity(trials, pd.DataFrame())
        assert not out["responseOpportunity"].any()

    def test_row_count_is_unchanged(self):
        """The merge must not duplicate trials when a speaker sent several
        messages in the same round."""
        trials = pd.DataFrame([_trial("s1", "speaker"), _trial("l1", "listener")])
        messages = pd.DataFrame([
            _message("s1", "speaker"),
            dict(_message("s1", "speaker"), text="and another"),
        ])
        assert len(add_response_opportunity(trials, messages)) == len(trials)


class TestSocialGuessOpportunityFrame:
    @staticmethod
    def _games():
        return pd.DataFrame([
            {"id": "g1", "condition": "social_mixed"},
            {"id": "g2", "condition": "refer_mixed"},
        ])

    @staticmethod
    def _player_rounds(guesses):
        rows = [{
            "gameID": "g1", "playerID": "s1", "roundID": "r1", "phase": "refgame",
            "role": "speaker", "current_group": "A",
            "social_guess": None, "social_guess_correct": None,
            "social_round_score": None,
        }]
        for player, guess, correct in guesses:
            rows.append({
                "gameID": "g1", "playerID": player, "roundID": "r1",
                "phase": "refgame", "role": "listener", "current_group": "A",
                "social_guess": guess, "social_guess_correct": correct,
                "social_round_score": 1 if correct else 0,
            })
        return pd.DataFrame(rows)

    def _trials(self):
        return add_response_opportunity(
            pd.DataFrame([
                _trial("s1", "speaker"),
                _trial("l1", "listener"),
                _trial("l2", "listener"),
                _trial("l3", "listener", game="g2"),
            ]),
            pd.DataFrame([
                _message("s1", "speaker"),
                _message("s2", "speaker", game="g2"),
            ]),
        )

    def test_a_listener_who_never_answered_still_gets_a_row(self):
        out = build_social_guesses(
            self._player_rounds([("l1", "same_group", True)]),
            self._games(),
            self._trials(),
        )
        assert set(out["playerId"]) == {"l1", "l2"}
        l2 = out[out.playerId == "l2"].iloc[0]
        assert pd.isna(l2["socialGuess"]) and l2["socialTimeout"]
        l1 = out[out.playerId == "l1"].iloc[0]
        assert l1["socialGuess"] == "same_group" and not l1["socialTimeout"]

    def test_only_social_guessing_games_contribute_opportunities(self):
        out = build_social_guesses(
            self._player_rounds([("l1", "same_group", True)]),
            self._games(),
            self._trials(),
        )
        assert set(out["gameId"]) == {"g1"}

    def test_the_speaker_is_attributed_to_every_opportunity(self):
        out = build_social_guesses(
            self._player_rounds([("l1", "different_group", False)]),
            self._games(),
            self._trials(),
        )
        assert (out["speakerId"] == "s1").all()

    def test_eligibility_travels_with_the_opportunity(self):
        out = build_social_guesses(
            self._player_rounds([("l1", "same_group", True)]),
            self._games(),
            self._trials(),
        )
        assert out["responseOpportunity"].all()


# ── Network columns (speakerId, inGroupSpeaker, groupSize, speakerReassigned) ──


def _network_fixture():
    """One Phase 2 round: a trio with exactly one in-group listener and a pair
    whose speaker is not the block's designated one (block 0 designates index
    0, but C1 with index 1 speaks)."""
    rows = [
        ("g", "r1", "A0", "A", "X", "speaker", 0),
        ("g", "r1", "A1", "A", "X", "listener", 0),
        ("g", "r1", "B2", "B", "X", "listener", 0),
        ("g", "r1", "C1", "C", "Y", "speaker", 0),
        ("g", "r1", "B1", "B", "Y", "listener", 0),
    ]
    trials = pd.DataFrame(
        rows,
        columns=["gameId", "roundId", "playerId", "originalGroup", "currentGroup", "role", "blockNum"],
    )
    player_df = pd.DataFrame(
        {"id": ["A0", "A1", "B2", "C1", "B1"], "player_index": [0, 1, 2, 1, 1]}
    )
    return trials, player_df


def test_network_columns_come_from_the_trio_membership():
    trials, player_df = _network_fixture()
    out = add_network_columns(trials, player_df).set_index("playerId")
    assert out.loc["A1", "speakerId"] == "A0"
    assert out.loc["B2", "speakerId"] == "A0"
    assert out.loc["B1", "speakerId"] == "C1"
    assert out.loc["A0", "speakerId"] == "A0"
    assert bool(out.loc["A1", "inGroupSpeaker"]) is True
    assert bool(out.loc["B2", "inGroupSpeaker"]) is False
    assert pd.isna(out.loc["A0", "inGroupSpeaker"])
    assert out.loc["A1", "groupSize"] == 3 and out.loc["B1", "groupSize"] == 2
    # Derived from the rotation index: A0 is block 0's designated speaker, C1 is not
    assert bool(out.loc["A0", "speakerReassigned"]) is False
    assert bool(out.loc["A1", "speakerReassigned"]) is False
    assert bool(out.loc["C1", "speakerReassigned"]) is True
    assert bool(out.loc["B1", "speakerReassigned"]) is True
    assert "speakerGroup" not in out.columns


def test_server_reassignment_flag_takes_precedence_and_missing_sources_give_na():
    trials, player_df = _network_fixture()
    flag = np.array([False, False, False, True, True])
    out = add_network_columns(trials, player_df, server_reassigned=flag)
    assert out["speakerReassigned"].tolist() == [False, False, False, True, True]
    out_none = add_network_columns(trials)
    assert out_none["speakerReassigned"].isna().all()
    assert out_none["speakerId"].tolist() == ["A0", "A0", "A0", "C1", "C1"]


def test_build_players_exports_the_rotation_index_as_a_nullable_integer():
    player_df = pd.DataFrame(
        {
            "id": ["p1", "p2"],
            "gameID": ["g", "g"],
            "name": ["Repi", "Minu"],
            "original_group": ["A", "A"],
            "original_name": ["Repi", "Minu"],
            "score": [4, 6],
            "bonus": [0.2, 0.3],
            "is_active": [True, True],
            "idle_rounds": [0, 0],
            "player_index": [0.0, np.nan],
        }
    )
    players = build_players(player_df)
    assert str(players["playerIndex"].dtype) == "Int64"
    assert players["playerIndex"].tolist()[0] == 0
    assert pd.isna(players["playerIndex"].tolist()[1])



# --- Session instrumentation -------------------------------------------------
#
# Timing, device, and engagement records added in September 2026. Every one of
# them has to survive an export that predates it, because the pilot has none of
# them and still has to process unchanged.


def _minimal_player_df(**extra):
    """One player, with only the columns build_players requires."""
    base = {
        "id": ["p1"],
        "gameID": ["g"],
        "name": ["Repi"],
        "original_group": ["A"],
        "original_name": ["Repi"],
        "score": [4],
        "bonus": [0.2],
        "is_active": [True],
        "idle_rounds": [0],
    }
    base.update(extra)
    return pd.DataFrame(base)


class TestClientContext:
    def test_the_recorded_device_blob_is_flattened_into_columns(self):
        players = build_players(
            _minimal_player_df(
                client_context=[
                    '{"viewportWidth": 1440, "viewportHeight": 900,'
                    ' "screenWidth": 1920, "screenHeight": 1080,'
                    ' "devicePixelRatio": 2, "timezoneOffsetMin": 300,'
                    ' "language": "en-US", "touch": false}'
                ]
            )
        )
        assert players["clientViewportWidth"].tolist() == [1440]
        assert players["clientScreenHeight"].tolist() == [1080]
        assert players["clientLanguage"].tolist() == ["en-US"]
        assert players["clientTouch"].tolist() == [False]
        # The raw blob is replaced by its fields, not carried twice.
        assert "clientContext" not in players.columns

    def test_an_export_without_the_device_record_still_has_the_columns(self):
        players = build_players(_minimal_player_df())
        assert players["clientViewportWidth"].isna().all()
        assert players["clientTouch"].isna().all()


class TestEngagementSummary:
    def test_hidden_time_pairs_each_hidden_with_the_next_visible(self):
        events = (
            '[{"t": 1000, "type": "hidden"}, {"t": 4000, "type": "visible"},'
            ' {"t": 9000, "type": "hidden"}, {"t": 10000, "type": "visible"},'
            ' {"t": 11000, "type": "offline"}, {"t": 12000, "type": "online"},'
            ' {"t": 13000, "type": "resize"}]'
        )
        players = build_players(_minimal_player_df(engagement_events=[events]))
        assert players["tabHiddenCount"].tolist() == [2]
        assert players["tabHiddenMs"].tolist() == [4000]
        assert players["offlineCount"].tolist() == [1]
        assert players["resizeCount"].tolist() == [1]

    def test_a_tab_hidden_at_the_end_counts_but_adds_no_time(self):
        # The participant closed or abandoned the tab, so the interval has no
        # defensible end and must not be invented.
        events = '[{"t": 1000, "type": "hidden"}]'
        players = build_players(_minimal_player_df(engagement_events=[events]))
        assert players["tabHiddenCount"].tolist() == [1]
        assert players["tabHiddenMs"].tolist() == [0]

    def test_an_export_without_an_engagement_log_still_has_the_columns(self):
        players = build_players(_minimal_player_df())
        assert players["tabHiddenCount"].isna().all()
        assert players["offlineCount"].isna().all()


class TestPlayerSchemaIsStableAcrossExportVintages:
    def test_columns_added_later_are_present_and_empty_in_an_older_export(self):
        players = build_players(_minimal_player_df())
        for column in ("quizAttempts", "minutesSpent", "shuffledTangrams"):
            assert column in players.columns
            assert players[column].isna().all()

    def test_quiz_attempts_is_a_nullable_integer_when_recorded(self):
        players = build_players(_minimal_player_df(quiz_attempts=[2]))
        assert str(players["quizAttempts"].dtype) == "Int64"
        assert players["quizAttempts"].tolist() == [2]


class TestSelectionStageTimes:
    def test_only_the_selection_stage_is_read_and_it_is_converted_to_epoch_ms(self):
        stage_df = pd.DataFrame(
            {
                "roundID": ["r1", "r1"],
                "name": ["Selection", "Feedback"],
                "startedLastChangedAt": [
                    "2026-03-01T17:39:43.120697707Z",
                    "2026-03-01T17:40:26.000000000Z",
                ],
                "endedLastChangedAt": [
                    "2026-03-01T17:40:25.904136542Z",
                    "2026-03-01T17:40:41.000000000Z",
                ],
            }
        )
        times = selection_stage_times(stage_df)
        assert times["roundId"].tolist() == ["r1"]
        duration = times["selectionEndedAt"][0] - times["selectionStartedAt"][0]
        assert duration == pytest.approx(42783, abs=1)

    def test_a_missing_or_unusable_stage_table_yields_an_empty_frame(self):
        expected = ["roundId", "selectionStartedAt", "selectionEndedAt"]
        assert selection_stage_times(None).columns.tolist() == expected
        # A table without the timestamp columns is unusable, not an error.
        bare = pd.DataFrame({"roundID": ["r1"], "name": ["Selection"]})
        assert selection_stage_times(bare).empty


def _trial_inputs(**player_round_extra):
    """The smallest playerRound/round/game trio build_trials accepts."""
    player_round = {
        "gameID": ["g", "g"],
        "playerID": ["p1", "p2"],
        "roundID": ["r1", "r1"],
        "name": ["Repi", "Minu"],
        "original_group": ["A", "A"],
        "current_group": ["A", "A"],
        "role": ["speaker", "listener"],
        "block_num": [0, 0],
        "phase": ["refgame", "refgame"],
        "phase_num": [1, 1],
        "target": ["t1", "t1"],
        "clicked": [None, "t1"],
        "clicked_correct": [None, True],
        "round_score": [2, 2],
    }
    player_round.update(player_round_extra)
    round_df = pd.DataFrame({"id": ["r1"], "trial_num": [0]})
    game_df = pd.DataFrame({"id": ["g"], "tangram_set": [0]})
    return pd.DataFrame(player_round), round_df, game_df


class TestTrialResponseTimes:
    def test_the_response_time_is_measured_within_the_participants_own_clock(self):
        # Stage rendered at 1000 on this browser, tangram chosen at 3500.
        pr, rd, gd = _trial_inputs(
            selection_rendered_at=[1000, 1000],
            tangram_selected_at=[None, 3500],
            clicked_at=[None, 3600],
        )
        trials = build_trials(pr, rd, gd)
        listener = trials[trials["role"] == "listener"].iloc[0]
        assert listener["selectionRt"] == 2500
        # The commit time is kept separately; it is what the late-arrival
        # audit uses and it is not the response time.
        assert listener["clickedAt"] == 3600

    def test_an_export_without_the_stamps_leaves_the_timing_columns_empty(self):
        pr, rd, gd = _trial_inputs()
        trials = build_trials(pr, rd, gd)
        for column in (
            "tangramSelectedAt",
            "selectionRenderedAt",
            "selectionRt",
            "selectionStartedAt",
            "selectionDurationMs",
        ):
            assert column in trials.columns
            assert trials[column].isna().all()

    def test_the_server_clock_duration_comes_from_the_stage_table(self):
        pr, rd, gd = _trial_inputs()
        stage_df = pd.DataFrame(
            {
                "roundID": ["r1"],
                "name": ["Selection"],
                "startedLastChangedAt": ["2026-03-01T17:39:43.000000000Z"],
                "endedLastChangedAt": ["2026-03-01T17:40:03.000000000Z"],
            }
        )
        trials = build_trials(pr, rd, gd, stage_df=stage_df)
        assert (trials["selectionDurationMs"] == 20000).all()


class TestMessageComposition:
    def _message_inputs(self, chat_json):
        player_round = pd.DataFrame(
            {
                "gameID": ["g"],
                "playerID": ["p1"],
                "roundID": ["r1"],
                "current_group": ["A"],
                "block_num": [0],
                "phase": ["refgame"],
                "phase_num": [1],
                "target": ["t1"],
                "chat": [chat_json],
            }
        )
        round_df = pd.DataFrame({"id": ["r1"], "trial_num": [0]})
        game_df = pd.DataFrame({"id": ["g"], "tangram_set": [0]})
        return player_round, game_df, round_df

    def test_composition_time_spans_the_first_keystroke_to_the_send(self):
        chat = (
            '[{"id": "m1", "text": "person kneeling", "timestamp": 5000,'
            ' "composeStartedAt": 1500, "pasted": false,'
            ' "sender": {"id": "p1", "name": "Repi (Speaker)"}}]'
        )
        messages = build_messages(*self._message_inputs(chat))
        assert messages["composeMs"].tolist() == [3500]
        assert messages["pasted"].tolist() == [False]

    def test_a_pasted_message_is_flagged(self):
        chat = (
            '[{"id": "m1", "text": "a long description", "timestamp": 5000,'
            ' "composeStartedAt": 4990, "pasted": true,'
            ' "sender": {"id": "p1", "name": "Repi (Speaker)"}}]'
        )
        messages = build_messages(*self._message_inputs(chat))
        assert messages["pasted"].tolist() == [True]
        assert messages["composeMs"].tolist() == [10]

    def test_messages_from_before_the_instrument_have_no_composition_time(self):
        chat = (
            '[{"id": "m1", "text": "person kneeling", "timestamp": 5000,'
            ' "sender": {"id": "p1", "name": "Repi (Speaker)"}}]'
        )
        messages = build_messages(*self._message_inputs(chat))
        assert messages["composeMs"].isna().all()
        assert messages["pasted"].isna().all()


# ── Filtered utterances and their sidecar ────────────────────────────────────
#
# speaker_utterances_filtered.csv is derived from messages.csv, and every later
# step prefers it when it exists. The sidecar written by `apply` is what stops
# a filtered file from an earlier messages.csv being analyzed in place of the
# current data.


def _messages_frame(texts=("the dancer", "thanks")):
    rows = []
    for i, text in enumerate(texts):
        rows.append(
            {
                "gameId": "g1",
                "roundId": "r1",
                "blockNum": 0,
                "phase": "refgame",
                "phaseNum": 1,
                "target": "t1",
                "group": "A",
                "senderId": "s1",
                "senderName": "Repi",
                "senderRole": "speaker",
                "text": text,
                "timestamp": 1000 + i,
                "trialNum": 0,
                "tangramSet": 0,
            }
        )
    return pd.DataFrame(rows)


def _write_filtered_dataset(tmp_path):
    _messages_frame().to_csv(tmp_path / "messages.csv", index=False)
    (tmp_path / FILTERED_UTTERANCES_FILE).write_text("gameId,utterance\ng1,the dancer\n")
    write_filtered_sidecar(tmp_path)


class TestFilteredUtterancesSidecar:
    def test_status_follows_the_sidecar_and_messages_csv(self, tmp_path):
        assert filtered_utterances_status(tmp_path)[0] == "absent"
        _write_filtered_dataset(tmp_path)
        assert filtered_utterances_status(tmp_path)[0] == "current"
        record = json.loads((tmp_path / FILTERED_UTTERANCES_SIDECAR).read_text())
        assert record["source"] == "messages.csv" and record["rows"] == 2
        # messages.csv changes underneath the filtered file: stale
        _messages_frame(("the dancer", "thanks", "a third")).to_csv(
            tmp_path / "messages.csv", index=False
        )
        status, detail = filtered_utterances_status(tmp_path)
        assert status == "stale"
        assert "2 rows" in detail and "3 rows" in detail
        # no sidecar at all: cannot be verified
        (tmp_path / FILTERED_UTTERANCES_SIDECAR).unlink()
        assert filtered_utterances_status(tmp_path)[0] == "unverified"

    def test_preprocessing_deletes_a_stale_filtered_file_and_keeps_a_current_one(
        self, tmp_path, capsys
    ):
        _write_filtered_dataset(tmp_path)
        assert retire_stale_filtered_utterances(tmp_path) is False
        assert (tmp_path / FILTERED_UTTERANCES_FILE).exists()

        _messages_frame(("changed",)).to_csv(tmp_path / "messages.csv", index=False)
        assert retire_stale_filtered_utterances(tmp_path) is True
        assert not (tmp_path / FILTERED_UTTERANCES_FILE).exists()
        assert not (tmp_path / FILTERED_UTTERANCES_SIDECAR).exists()
        out = capsys.readouterr().out
        assert f"Deleted stale {FILTERED_UTTERANCES_FILE}" in out

    def test_a_filtered_file_without_a_sidecar_is_left_but_reported(self, tmp_path, capsys):
        _messages_frame().to_csv(tmp_path / "messages.csv", index=False)
        (tmp_path / FILTERED_UTTERANCES_FILE).write_text("gameId,utterance\n")
        assert retire_stale_filtered_utterances(tmp_path) is False
        assert (tmp_path / FILTERED_UTTERANCES_FILE).exists()
        assert "Warning" in capsys.readouterr().out


class TestAttachLabels:
    """`apply` joins the classifier's labels onto the current messages.csv."""

    def test_labels_are_joined_by_message_key_and_listeners_default_to_referential(self):
        messages = _messages_frame(("the dancer", "thanks"))
        listener = messages.iloc[[0]].assign(senderId="l1", senderRole="listener", text="which?")
        messages = pd.concat([messages, listener], ignore_index=True)
        # The cache lists the messages in another order and with extra columns
        # of its own; only the key decides the match.
        classified = _messages_frame(("the dancer", "thanks")).assign(
            is_referential=[True, False], llm_label=["R", "NR"], extra=1
        ).iloc[::-1]
        out = attach_labels(messages, classified)
        by_text = out.set_index("text")
        assert by_text.loc["the dancer", "llm_label"] == "R"
        assert bool(by_text.loc["thanks", "is_referential"]) is False
        assert by_text.loc["which?", "llm_label"] == "" and bool(by_text.loc["which?", "is_referential"])

    def test_an_unlabeled_speaker_message_is_an_error_not_a_default(self):
        messages = _messages_frame(("the dancer", "brand new message"))
        classified = _messages_frame(("the dancer",)).assign(is_referential=[True], llm_label=["R"])
        with pytest.raises(ValueError, match="1 of 2 speaker messages .* have no label"):
            attach_labels(messages, classified)

    def test_timestamps_read_back_as_floats_still_match(self):
        messages = _messages_frame(("the dancer",))
        classified = _messages_frame(("the dancer",)).assign(
            is_referential=[True], llm_label=["R"]
        )
        classified["timestamp"] = classified["timestamp"].astype(float)
        assert attach_labels(messages, classified)["llm_label"].tolist() == ["R"]


# ── Game exclusions and provenance ───────────────────────────────────────────


class TestExcludeGames:
    def test_the_exclusion_file_ignores_comments_and_blank_lines(self, tmp_path):
        (tmp_path / "exclude_games.txt").write_text(
            "# rehearsal with lab members\nGAME_A\n\nGAME_B  # deploy check\n"
        )
        assert read_excluded_games(tmp_path) == ["GAME_A", "GAME_B"]
        assert read_excluded_games(tmp_path / "missing") == []

    def test_an_excluded_game_takes_every_dependent_row_with_it(self, capsys):
        combined = {
            "game.csv": pd.DataFrame({"id": ["GAME_A", "GAME_B"], "condition": ["refer_mixed"] * 2}),
            "player.csv": pd.DataFrame({"id": ["p1", "p2"], "gameID": ["GAME_A", "GAME_B"]}),
            "playerRound.csv": pd.DataFrame({"id": ["pr1", "pr2", "pr3"], "gameID": ["GAME_A", "GAME_A", "GAME_B"]}),
            "batch.csv": pd.DataFrame({"id": ["b1"]}),
        }
        out, found = exclude_games(combined, ["GAME_A", "NOT_A_GAME"])
        assert found == ["GAME_A"]
        assert out["game.csv"]["id"].tolist() == ["GAME_B"]
        assert out["player.csv"]["id"].tolist() == ["p2"]
        assert out["playerRound.csv"]["id"].tolist() == ["pr3"]
        assert len(out["batch.csv"]) == 1  # no gameID column: untouched
        printed = capsys.readouterr().out
        assert "NOT_A_GAME" in printed and "Excluding 1 game(s)" in printed


def _game_df(**extra):
    base = {
        "id": ["g"],
        "condition": ["refer_mixed"],
        "tangram_set": [0],
        "actualPlayerCount": [9],
        "active_groups": ['["A","B","C"]'],
        "phase1Blocks": [6],
        "phase2Blocks": [6],
    }
    base.update(extra)
    return pd.DataFrame(base)


class TestGamesProvenance:
    def test_batch_and_source_run_are_carried_into_games_csv(self):
        games = build_games(_game_df(batchID=["batch1"], _sourceRun=["20260301_132907"]))
        assert games["batchId"].tolist() == ["batch1"]
        assert games["sourceRun"].tolist() == ["20260301_132907"]

    def test_an_export_without_them_still_has_the_columns(self):
        games = build_games(_game_df())
        assert games["batchId"].isna().all() and games["sourceRun"].isna().all()
        # appended after the existing columns, so older files keep their order
        assert games.columns.tolist()[:7] == [
            "gameId", "condition", "tangramSet", "numPlayers", "activeGroups",
            "phase1Blocks", "phase2Blocks",
        ]


# ── Active groups ────────────────────────────────────────────────────────────


class TestActiveGroups:
    def test_an_empty_group_list_counts_as_zero_and_a_missing_one_stays_empty(self):
        games = build_games(_game_df(id=["g1", "g2", "g3"], condition=["refer_mixed"] * 3,
                                     tangram_set=[0] * 3, actualPlayerCount=[9] * 3,
                                     active_groups=['["A","B","C"]', "[]", None],
                                     phase1Blocks=[6] * 3, phase2Blocks=[6] * 3))
        assert games["activeGroups"].tolist()[:2] == [3, 0]
        assert pd.isna(games["activeGroups"].tolist()[2])

    @staticmethod
    def _rounds(reshuffle_groups=None):
        rounds = pd.DataFrame(
            {
                "id": ["p1r", "r1", "r2", "r3"],
                "gameID": ["g"] * 4,
                "phase": ["refgame"] * 4,
                "phase_num": [1, 2, 2, 2],
            }
        )
        if reshuffle_groups is not None:
            rounds["reshuffle_groups"] = reshuffle_groups
        return rounds

    @staticmethod
    def _trials():
        rows = []
        # Phase 1 round with three groups; Phase 2 rounds with 3, then 2 groups;
        # r3 was created but never played (no trial rows).
        for rid, phase, groups in (("p1r", 1, "ABC"), ("r1", 2, "XYZ"), ("r2", 2, "XY")):
            for g in groups:
                rows.append({"gameId": "g", "roundId": rid, "phaseNum": phase,
                             "currentGroup": g, "role": "speaker", "playerId": f"s{g}"})
                rows.append({"gameId": "g", "roundId": rid, "phaseNum": phase,
                             "currentGroup": g, "role": "listener", "playerId": f"l{g}"})
        return pd.DataFrame(rows)

    def test_minimum_comes_from_the_trials_when_the_server_count_is_absent(self):
        games = pd.DataFrame({"gameId": ["g"], "activeGroups": pd.array([3], dtype="Int64")})
        out = add_active_groups_min(games, self._rounds(), self._trials())
        assert out["activeGroupsMin"].tolist() == [2]

    def test_the_server_count_takes_precedence_where_recorded(self):
        games = pd.DataFrame({"gameId": ["g"], "activeGroups": pd.array([3], dtype="Int64")})
        # r3 has a server count of 1 although it has no trials; r1 and r2 fall
        # back to the trials (3 and 2)
        rounds = self._rounds(reshuffle_groups=[None, None, None, 1])
        out = add_active_groups_min(games, rounds, self._trials())
        assert out["activeGroupsMin"].tolist() == [1]

    def test_a_game_without_phase_2_trials_falls_back_to_active_groups(self):
        games = pd.DataFrame({"gameId": ["g", "other"], "activeGroups": pd.array([3, 2], dtype="Int64")})
        trials = self._trials()
        trials = trials[trials["phaseNum"] == 1]
        out = add_active_groups_min(games, self._rounds(), trials).set_index("gameId")
        assert out.loc["g", "activeGroupsMin"] == 3
        assert out.loc["other", "activeGroupsMin"] == 2


# ── Server-recorded network columns ──────────────────────────────────────────


class TestServerNetworkColumns:
    def test_the_servers_record_rides_beside_the_derived_columns(self):
        pr, rd, gd = _trial_inputs(
            speaker_id=["p1", "p1"], in_group_listener=[None, True], group_size=[2, 2]
        )
        rd = rd.assign(reshuffle_groups=[3], reshuffle_trios=[2], reshuffle_trios_ok=[1], reshuffle_pairs=[1])
        trials = add_server_network_columns(build_trials(pr, rd, gd), pr, rd)
        listener = trials[trials["role"] == "listener"].iloc[0]
        assert listener["serverSpeakerId"] == "p1" and listener["speakerId"] == "p1"
        assert bool(listener["serverInGroupListener"]) is True
        assert listener["serverGroupSize"] == 2
        assert (trials["reshuffleGroups"] == 3).all() and (trials["reshuffleTriosOk"] == 1).all()
        assert (trials["reshufflePairs"] == 1).all()
        # the server does not record in_group_listener for the speaker
        assert pd.isna(trials[trials["role"] == "speaker"]["serverInGroupListener"].iloc[0])

    def test_an_export_without_the_record_has_the_columns_empty(self):
        pr, rd, gd = _trial_inputs()
        trials = add_server_network_columns(build_trials(pr, rd, gd), pr, rd)
        for column in (
            "serverSpeakerId", "serverInGroupListener", "serverGroupSize",
            "reshuffleGroups", "reshuffleTrios", "reshuffleTriosOk", "reshufflePairs",
        ):
            assert column in trials.columns and trials[column].isna().all()
        assert len(trials) == 2


def test_social_guesses_carry_the_servers_same_group_record():
    games = pd.DataFrame([{"id": "g1", "condition": "social_mixed"}])
    pr = pd.DataFrame([
        {"gameID": "g1", "playerID": "s1", "roundID": "r1", "phase": "refgame", "role": "speaker",
         "current_group": "A", "social_guess": None, "social_guess_correct": None,
         "social_round_score": None, "speaker_was_same_group": None},
        {"gameID": "g1", "playerID": "l1", "roundID": "r1", "phase": "refgame", "role": "listener",
         "current_group": "A", "social_guess": "same_group", "social_guess_correct": True,
         "social_round_score": 6, "speaker_was_same_group": True},
        {"gameID": "g1", "playerID": "l2", "roundID": "r1", "phase": "refgame", "role": "listener",
         "current_group": "A", "social_guess": None, "social_guess_correct": None,
         "social_round_score": None, "speaker_was_same_group": None},
    ])
    trials = add_response_opportunity(
        pd.DataFrame([_trial("s1", "speaker"), _trial("l1", "listener"), _trial("l2", "listener")]),
        pd.DataFrame([_message("s1", "speaker")]),
    )
    out = build_social_guesses(pr, games, trials).set_index("playerId")
    assert bool(out.loc["l1", "speakerWasSameGroup"]) is True
    # l2 never answered, so the server recorded nothing, but the speaker's own
    # original group is known and the ground truth is completed from it: the
    # in-group/out-group opportunity counts must cover the nonresponses too.
    assert bool(out.loc["l2", "speakerWasSameGroup"]) is True
    # appended after the columns older files have, together with the exclusion flags
    assert out.columns.tolist()[-3:] == ["speakerWasSameGroup", "excluded", "exclusionReason"]


def test_same_group_ground_truth_covers_out_group_nonresponses():
    games = pd.DataFrame([{"id": "g1", "condition": "social_mixed"}])
    pr = pd.DataFrame([
        {"gameID": "g1", "playerID": "s1", "roundID": "r1", "phase": "refgame", "role": "speaker",
         "current_group": "A", "social_guess": None, "social_guess_correct": None,
         "social_round_score": None, "speaker_was_same_group": None},
        {"gameID": "g1", "playerID": "l2", "roundID": "r1", "phase": "refgame", "role": "listener",
         "current_group": "A", "social_guess": None, "social_guess_correct": None,
         "social_round_score": None, "speaker_was_same_group": None},
    ])
    speaker = _trial("s1", "speaker")
    listener = _trial("l2", "listener")
    listener["originalGroup"] = "B"  # reshuffled into the speaker's current group
    trials = add_response_opportunity(
        pd.DataFrame([speaker, listener]), pd.DataFrame([_message("s1", "speaker")])
    )
    out = build_social_guesses(pr, games, trials).set_index("playerId")
    assert bool(out.loc["l2", "speakerWasSameGroup"]) is False


def test_same_group_ground_truth_is_missing_only_when_the_speaker_is_unknown():
    games = pd.DataFrame([{"id": "g1", "condition": "social_mixed"}])
    pr = pd.DataFrame([
        {"gameID": "g1", "playerID": "l2", "roundID": "r1", "phase": "refgame", "role": "listener",
         "current_group": "A", "social_guess": None, "social_guess_correct": None,
         "social_round_score": None, "speaker_was_same_group": None},
    ])
    # No speaker row at all: nothing to compare the listener's group against.
    trials = add_response_opportunity(
        pd.DataFrame([_trial("l2", "listener")]), pd.DataFrame([_message("s1", "speaker")])
    )
    out = build_social_guesses(pr, games, trials).set_index("playerId")
    assert pd.isna(out.loc["l2", "speakerWasSameGroup"])


# ── Participant exclusions ───────────────────────────────────────────────────


class TestParticipantExclusionsFile:
    def test_a_missing_file_means_no_exclusions(self, tmp_path):
        out = read_participant_exclusions(tmp_path / "participant_exclusions.csv")
        assert out.empty and out.columns.tolist() == ["playerId", "reason"]

    def test_every_row_needs_a_reason(self, tmp_path):
        path = tmp_path / "participant_exclusions.csv"
        path.write_text("playerId,reason\np1,confirmed AI use\np2,\n")
        with pytest.raises(ValueError, match="empty playerId or reason"):
            read_participant_exclusions(path)

    def test_a_player_may_be_listed_once(self, tmp_path):
        path = tmp_path / "participant_exclusions.csv"
        path.write_text("playerId,reason\np1,a\np1,b\n")
        with pytest.raises(ValueError, match="more than once"):
            read_participant_exclusions(path)


def test_exclusion_marks_own_rows_and_the_listeners_of_an_excluded_speaker():
    trials = pd.DataFrame([
        {"playerId": "A0", "role": "speaker", "speakerId": "A0", "roundId": "r1"},
        {"playerId": "A1", "role": "listener", "speakerId": "A0", "roundId": "r1"},
        {"playerId": "A2", "role": "listener", "speakerId": "A0", "roundId": "r1"},
        {"playerId": "A1", "role": "speaker", "speakerId": "A1", "roundId": "r2"},
        {"playerId": "A0", "role": "listener", "speakerId": "A1", "roundId": "r2"},
        {"playerId": "A2", "role": "listener", "speakerId": "A1", "roundId": "r2"},
    ])
    exclusions = pd.DataFrame({"playerId": ["A0"], "reason": ["confirmed AI use"]})
    out = apply_participant_exclusions(trials, exclusions)
    assert out["excluded"].tolist() == [True, True, True, False, True, False]
    assert out["exclusionReason"].tolist() == [
        "confirmed AI use",
        "speaker excluded: confirmed AI use",
        "speaker excluded: confirmed AI use",
        "",
        "confirmed AI use",
        "",
    ]


def _raw_dataset(tmp_path):
    """A one-group game with two Phase 1 rounds, written as raw Empirica CSVs.

    Round r1: A0 speaks ("the dancer"), A1 and A2 listen and click. Round r2:
    A1 speaks ("kneeling man"), A0 and A2 listen.
    """
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame({
        "id": ["g"], "condition": ["refer_separated"], "tangram_set": [0],
        "actualPlayerCount": [3], "active_groups": ['["A"]'], "phase1Blocks": [6],
        "phase2Blocks": [6], "batchID": ["b1"], "_sourceRun": ["20260101_000000"],
    }).to_csv(raw / "game.csv", index=False)
    pd.DataFrame({
        "id": ["A0", "A1", "A2"], "gameID": ["g"] * 3, "name": ["Repi", "Minu", "Laju"],
        "original_group": ["A"] * 3, "original_name": ["Repi", "Minu", "Laju"],
        "score": [4, 4, 4], "bonus": [0.2] * 3, "is_active": [True] * 3, "idle_rounds": [0] * 3,
        "player_index": [0, 1, 2],
    }).to_csv(raw / "player.csv", index=False)
    pd.DataFrame({
        "id": ["r1", "r2"], "gameID": ["g", "g"], "trial_num": [0, 1], "phase": ["refgame"] * 2,
        "phase_num": [1, 1], "block_num": [0, 1],
    }).to_csv(raw / "round.csv", index=False)

    def chat(sender, name, text, ts):
        return json.dumps([{"id": f"m{ts}", "text": text, "timestamp": ts,
                            "sender": {"id": sender, "name": f"{name} (Speaker)"}}])

    rows = []
    for rid, block, speaker, text, ts in (("r1", 0, "A0", "the dancer", 1000), ("r2", 1, "A1", "kneeling man", 2000)):
        for pid, name in (("A0", "Repi"), ("A1", "Minu"), ("A2", "Laju")):
            is_speaker = pid == speaker
            rows.append({
                "gameID": "g", "playerID": pid, "roundID": rid, "name": name,
                "original_group": "A", "current_group": "A",
                "role": "speaker" if is_speaker else "listener", "block_num": block,
                "phase": "refgame", "phase_num": 1, "target": "t1",
                "clicked": None if is_speaker else "t1", "clicked_correct": None if is_speaker else True,
                "round_score": 2, "chat": chat(speaker, "Repi" if speaker == "A0" else "Minu", text, ts),
            })
    pd.DataFrame(rows).to_csv(raw / "playerRound.csv", index=False)
    return raw


def _run_preprocessing(raw, out, monkeypatch, *extra):
    monkeypatch.setattr(sys, "argv", ["preprocessing.py", str(raw), "--output", str(out), *extra])
    preprocessing.main()


class TestExclusionEndToEnd:
    def test_an_excluded_players_messages_and_utterances_are_dropped_and_rows_flagged(
        self, tmp_path, monkeypatch
    ):
        raw = _raw_dataset(tmp_path)
        out = tmp_path / "data"
        out.mkdir()
        (out / "participant_exclusions.csv").write_text("playerId,reason\nA0,confirmed AI use\n")
        _run_preprocessing(raw, out, monkeypatch)

        messages = pd.read_csv(out / "messages.csv")
        assert "A0" not in set(messages["senderId"]) and len(messages) == 1
        utterances = pd.read_csv(out / "speaker_utterances.csv")
        assert utterances["playerId"].tolist() == ["A1"]

        trials = pd.read_csv(out / "trials.csv").set_index(["roundId", "playerId"])
        assert bool(trials.loc[("r1", "A0"), "excluded"])
        assert trials.loc[("r1", "A0"), "exclusionReason"] == "confirmed AI use"
        assert bool(trials.loc[("r1", "A1"), "excluded"])
        assert trials.loc[("r1", "A1"), "exclusionReason"] == "speaker excluded: confirmed AI use"
        assert bool(trials.loc[("r2", "A0"), "excluded"])
        assert not bool(trials.loc[("r2", "A1"), "excluded"])
        assert not bool(trials.loc[("r2", "A2"), "excluded"])
        assert pd.isna(trials.loc[("r2", "A2"), "exclusionReason"])  # empty string in the CSV
        # The response opportunity is what it was: A0 did speak in r1.
        assert bool(trials.loc[("r1", "A1"), "responseOpportunity"])
        assert bool(trials.loc[("r1", "A1"), "hasSpeakerMessage"])

    def test_the_derived_step_sees_only_the_remaining_speakers(self, tmp_path, monkeypatch):
        """The derived measures are computed from the post-exclusion utterances.

        Separate from the test above, and skipped where the derived stack is not
        installed, because CI deliberately runs this file without nltk and the
        sentence-transformer dependencies (see .github/workflows/ci.yml). Keeping
        it in the same test cost CI the preprocessing assertions too, which are
        the ones worth having there.
        """
        pytest.importorskip("nltk")
        from compute_derived import compute_lexical_uniqueness

        raw = _raw_dataset(tmp_path)
        out = tmp_path / "data"
        out.mkdir()
        (out / "participant_exclusions.csv").write_text("playerId,reason\nA0,confirmed AI use\n")
        _run_preprocessing(raw, out, monkeypatch)

        utterances = pd.read_csv(out / "speaker_utterances.csv")
        assert set(compute_lexical_uniqueness(utterances)["playerId"]) == {"A1"}

    def test_without_an_exclusion_file_nothing_is_flagged(self, tmp_path, monkeypatch):
        raw = _raw_dataset(tmp_path)
        out = tmp_path / "data"
        out.mkdir()
        _run_preprocessing(raw, out, monkeypatch)
        trials = pd.read_csv(out / "trials.csv")
        assert not trials["excluded"].any()
        assert trials["exclusionReason"].isna().all()  # written as empty strings
        assert len(pd.read_csv(out / "messages.csv")) == 2

    def test_an_unknown_player_id_is_refused(self, tmp_path, monkeypatch):
        raw = _raw_dataset(tmp_path)
        out = tmp_path / "data"
        out.mkdir()
        (out / "participant_exclusions.csv").write_text("playerId,reason\nZZ,typo\n")
        with pytest.raises(SystemExit, match="not in player.csv"):
            _run_preprocessing(raw, out, monkeypatch)


# ── Dropouts ─────────────────────────────────────────────────────────────────


class TestDropouts:
    @staticmethod
    def _tables():
        players_all = pd.DataFrame({
            "id": ["p_ok", "p_lobby", "p_quiz", "p_late", "p_never", "p_rehearsal"],
            "gameID": ["REAL", "FAILED", "FAILED", None, "REAL", "REHEARSAL"],
            "original_group": ["A", None, None, None, None, "A"],
            "ended": ["game ended", "game failed", "game failed", "no more games", None, "game ended"],
            "exitReason": [None, None, "quiz failed", None, None, None],
            "quiz_attempts": [1, None, 3, None, None, 1],
        })
        games_all = pd.DataFrame({
            "id": ["REAL", "FAILED", "REHEARSAL"],
            "batchID": ["b1", "b1", "b0"],
            "condition": ["refer_mixed", None, "refer_mixed"],
        })
        combined = {
            "game.csv": games_all[games_all["id"] == "REAL"].copy(),
            "player.csv": players_all[players_all["gameID"] == "REAL"].copy(),
        }
        return players_all, games_all, combined

    def test_every_record_without_a_real_game_is_a_dropout_except_excluded_games(self):
        players_all, games_all, combined = self._tables()
        combined, dropouts = split_dropouts(players_all, games_all, combined, ["REHEARSAL"])
        assert dropouts.columns.tolist() == DROPOUT_COLUMNS
        by_id = dropouts.set_index("playerId")
        assert set(by_id.index) == {"p_lobby", "p_quiz", "p_late", "p_never"}
        assert by_id.loc["p_quiz", "exitReason"] == "quiz failed"
        assert by_id.loc["p_quiz", "quizAttempts"] == 3
        assert by_id.loc["p_lobby", "batchId"] == "b1"
        assert pd.isna(by_id.loc["p_late", "batchId"])  # never reached a game
        # the never-started record leaves player.csv
        assert combined["player.csv"]["id"].tolist() == ["p_ok"]

    def test_no_dropouts_gives_an_empty_frame_with_the_header(self):
        players_all, games_all, combined = self._tables()
        only_real = players_all[players_all["id"] == "p_ok"]
        _, dropouts = split_dropouts(only_real, games_all, combined, [])
        assert dropouts.empty and dropouts.columns.tolist() == DROPOUT_COLUMNS


# ── Utterance assembly, malformed JSON, and the command-line guards ─────────

import extract_run  # noqa: E402
from combine_runs import frozen_dataset_error  # noqa: E402
from filter_nonreferential import (  # noqa: E402
    cached_labels,
    classified_frame,
    read_human_labels,
)
from preprocessing import (  # noqa: E402
    assemble_speaker_utterances,
    build_speaker_utterances,
    parse_json_column,
    report_malformed_json,
)


def _speaker_messages():
    return pd.DataFrame({
        "gameId": ["g"] * 3,
        "roundId": ["r1", "r1", "r2"],
        "senderId": ["p1", "p1", "p2"],
        "senderRole": ["speaker"] * 3,
        "blockNum": [0, 0, 0],
        "phase": ["refgame"] * 3,
        "phaseNum": [1, 1, 1],
        "target": ["t", "t", "u"],
        "trialNum": [0, 0, 1],
        "tangramSet": ["set1"] * 3,
        "text": ["a bunny", "with ears", "house"],
        "timestamp": [2, 1, 3],  # out of order on purpose
    })


def _speaker_trials():
    return pd.DataFrame({
        "gameId": ["g", "g"],
        "playerId": ["p1", "p2"],
        "originalGroup": ["A", "B"],
        "currentGroup": ["A", "B"],
        "roundId": ["r1", "r2"],
        "repNum": [0, 0],
        "role": ["speaker", "speaker"],
    })


class TestUtteranceAssembly:
    def test_messages_of_a_round_are_joined_in_timestamp_order(self):
        out = assemble_speaker_utterances(_speaker_messages(), _speaker_trials())
        assert len(out) == 2
        r1 = out[out["playerId"] == "p1"].iloc[0]
        assert r1["utterance"] == "with ears, a bunny"
        assert r1["uttLength"] == 4
        assert r1["originalGroup"] == "A" and r1["repNum"] == 0

    def test_a_missing_key_is_an_error_not_a_silently_dropped_round(self):
        msgs = _speaker_messages()
        msgs.loc[2, "tangramSet"] = None
        with pytest.raises(ValueError, match="tangramSet"):
            assemble_speaker_utterances(msgs, _speaker_trials())

    def test_filtered_and_unfiltered_files_share_one_definition(self):
        msgs = _speaker_messages()
        msgs["is_referential"] = True
        unfiltered = build_speaker_utterances(msgs, _speaker_trials())
        filtered, n_dropped = build_filtered_utterances(msgs, _speaker_trials())
        assert n_dropped == 0
        key = ["gameId", "playerId", "blockNum", "target"]
        pd.testing.assert_frame_equal(
            unfiltered.sort_values(key).reset_index(drop=True),
            filtered.sort_values(key).reset_index(drop=True),
        )


class TestMalformedJsonReport:
    def test_malformed_values_are_counted_per_column_and_reported_once(self, capsys):
        report_malformed_json()  # reset any count left by another test
        parsed = parse_json_column(
            pd.Series(['{"a": 1}', "not json", "{oops", None, ""]), "exitSurvey"
        )
        assert parsed.iloc[0] == {"a": 1}
        assert parsed.iloc[1] is None and parsed.iloc[2] is None
        assert parsed.iloc[3] is None and parsed.iloc[4] is None  # missing, not malformed
        counts = report_malformed_json()
        assert counts == {"exitSurvey": 2}
        out = capsys.readouterr().out
        assert out.count("exitSurvey") == 1 and "2 value(s)" in out
        assert report_malformed_json() == {}  # reported once, then reset


class TestFrozenPilotGuard:
    def test_positional_runs_equal_to_runs_txt_pass(self):
        assert frozen_dataset_error("pilots", ["b", "a"], ["a", "b"], False) is None

    def test_other_runs_are_refused_unless_allowed(self):
        message = frozen_dataset_error("pilots", ["c"], ["a", "b"], False)
        assert message and "frozen" in message and "--allow-pilot" in message
        assert frozen_dataset_error("pilots", ["c"], ["a", "b"], True) is None

    def test_other_datasets_and_the_default_form_are_never_blocked(self):
        assert frozen_dataset_error("full", ["c"], [], False) is None
        assert frozen_dataset_error("pilots", [], ["a"], False) is None


class TestExtractRunCommandLine:
    def test_options_may_come_before_or_after_the_zip(self):
        a = extract_run.parse_args(["x.zip", "--dataset", "smoke", "--no-register"])
        b = extract_run.parse_args(["--dataset", "smoke", "--no-register", "x.zip"])
        for args in (a, b):
            assert args.command == "extract"
            assert args.zip == "x.zip" and args.dataset == "smoke" and args.no_register

    def test_a_bare_call_and_flags_alone_are_extracts(self):
        args = extract_run.parse_args([])
        assert args.command == "extract" and args.zip is None and args.dataset is None
        assert not args.no_register and not args.all_batches and args.batch is None
        args = extract_run.parse_args(["--batch", "b1", "--all-batches"])
        assert args.batch == "b1" and args.all_batches and args.zip is None

    def test_subcommands_keep_their_run_option(self):
        assert extract_run.parse_args(["list"]).command == "list"
        args = extract_run.parse_args(["bonuses", "--run", "20260301_132907"])
        assert args.command == "bonuses" and args.run == "20260301_132907"
        assert extract_run.parse_args(["early-ended"]).run is None


class TestClassifierCache:
    def _messages(self):
        return pd.DataFrame({
            "gameId": ["g"] * 3,
            "roundId": ["r"] * 3,
            "senderId": ["p1", "p1", "p2"],
            "senderRole": ["speaker", "speaker", "listener"],
            "timestamp": [1, 2, 3],
            "text": ["bunny", "thanks", "ok"],
        })

    def test_no_cache_means_every_message_is_unlabeled(self):
        msgs = self._messages()
        assert cached_labels(msgs, None).isna().all()

    def test_only_messages_without_a_cached_label_are_left_to_classify(self):
        msgs = self._messages()
        cache = classified_frame(msgs, pd.Series(["R", pd.NA, pd.NA], index=msgs.index))
        labels = cached_labels(msgs, cache)
        assert labels.iloc[0] == "R" and pd.isna(labels.iloc[1]) and pd.isna(labels.iloc[2])
        speaker = msgs["senderRole"] == "speaker"
        assert list(msgs.index[speaker & labels.isna()]) == [1]

    def test_a_changed_text_is_not_matched_to_the_old_label(self):
        msgs = self._messages()
        cache = classified_frame(msgs, pd.Series(["R", "NR", pd.NA], index=msgs.index))
        changed = msgs.copy()
        changed.loc[1, "text"] = "thanks bunny"
        labels = cached_labels(changed, cache)
        assert labels.iloc[0] == "R" and pd.isna(labels.iloc[1])

    def test_classified_frame_marks_unlabeled_and_listener_rows_referential_with_empty_label(self):
        msgs = self._messages()
        out = classified_frame(msgs, pd.Series(["NR", pd.NA, pd.NA], index=msgs.index))
        assert out["llm_label"].tolist() == ["NR", "", ""]
        assert out["is_referential"].tolist() == [False, True, True]

    def test_labels_survive_a_csv_round_trip(self, tmp_path):
        msgs = self._messages()
        path = tmp_path / "messages_classified.csv"
        classified_frame(msgs, pd.Series(["R", "NR", pd.NA], index=msgs.index)).to_csv(path, index=False)
        labels = cached_labels(msgs, pd.read_csv(path))
        assert labels.tolist()[:2] == ["R", "NR"] and pd.isna(labels.iloc[2])


class TestHumanLabels:
    def _write(self, path, labels):
        pd.DataFrame({
            "gameId": ["g"] * len(labels),
            "roundId": ["r"] * len(labels),
            "senderId": ["p"] * len(labels),
            "text": [f"m{i}" for i in range(len(labels))],
            "human_label": labels,
        }).to_csv(path, index=False)

    def test_empty_labels_are_refused(self, tmp_path):
        path = tmp_path / "human_labels.csv"
        self._write(path, ["R", None])
        with pytest.raises(ValueError, match="no human_label"):
            read_human_labels(path)

    def test_complete_labels_are_normalized(self, tmp_path):
        path = tmp_path / "human_labels.csv"
        self._write(path, ["r", " NR "])
        assert read_human_labels(path)["human_label"].tolist() == ["R", "NR"]

    def test_a_missing_file_names_the_annotation_step(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="annotation_sample.csv"):
            read_human_labels(tmp_path / "human_labels.csv")
