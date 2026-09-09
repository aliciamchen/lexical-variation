"""
Unit tests for the preprocessing rules the preregistration states precisely:
the Phase 1 description-length flag used to trigger AI-use inspection, and the
treatment of speaker rounds whose messages were all classified non-referential.

Run with:
    uv run pytest analysis/test_preprocessing.py -v
"""

import numpy as np
import pandas as pd

from filter_nonreferential import build_filtered_utterances
from preprocessing import flag_length_increase


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
