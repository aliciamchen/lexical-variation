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
    add_response_opportunity,
    build_social_guesses,
    flag_length_increase,
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
