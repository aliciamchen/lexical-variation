"""
Unit tests for the preprocessing rules the preregistration states precisely:
the Phase 1 description-length flag used to trigger AI-use inspection, the
treatment of speaker rounds whose messages were all classified non-referential,
and the response-opportunity denominator shared by both accuracy outcomes.

Run with:
    uv run pytest analysis/test_preprocessing.py -v
"""

import numpy as np
import pandas as pd
import pytest

from filter_nonreferential import BatchParseError, build_filtered_utterances, parse_batch_labels
from preprocessing import (
    add_network_columns,
    build_messages,
    build_players,
    add_response_opportunity,
    build_social_guesses,
    build_trials,
    flag_length_increase,
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
