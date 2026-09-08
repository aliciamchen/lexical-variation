"""
Unit tests for the derived-metric functions in compute_derived.py that the
preregistration defines precisely: which utterance counts as a speaker's
"latest" description, when the block-by-block group-specificity trajectory
starts, and which vocabulary lexical uniqueness is measured against.

A stand-in for the sentence-transformer model gives identical texts a cosine
similarity of 1 and different texts 0, so expected values are exact.

Run with:
    uv run pytest analysis/test_compute_derived.py -v
"""

import numpy as np
import pandas as pd

from compute_derived import (
    compute_block_pairwise,
    compute_lexical_uniqueness,
    compute_pairwise_similarities,
)


class _Sim:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class FakeModel:
    """One-hot embeddings: equal texts are identical, different texts orthogonal."""

    def __init__(self):
        self.vocab = {}

    def encode(self, texts, show_progress_bar=False):
        for t in texts:
            self.vocab.setdefault(t, len(self.vocab))
        dim = max(len(self.vocab), 1)
        out = np.zeros((len(texts), dim))
        for i, t in enumerate(texts):
            out[i, self.vocab[t]] = 1.0
        return out

    def similarity(self, a, b):
        n = min(len(a), len(b))
        return _Sim(float(np.dot(a[:n], b[:n])))


def _utt(game, player, group, target, phase, block, text):
    return {
        "gameId": game,
        "playerId": player,
        "originalGroup": group,
        "target": target,
        "phaseNum": phase,
        "blockNum": block,
        "utterance": text,
    }


def test_latest_utterance_is_chosen_by_block_not_row_order():
    # p1 spoke about t in blocks 3 and 5, but the later block appears FIRST in
    # the frame, as it does in the filtered utterance file (ordered by round
    # id, not by block). p2's description equals p1's block-5 description.
    rows = [
        _utt("g", "p1", "A", "t", 1, 5, "late"),
        _utt("g", "p1", "A", "t", 1, 3, "early"),
        _utt("g", "p2", "B", "t", 1, 4, "late"),
    ]
    df = pd.DataFrame(rows)
    model = FakeModel()
    embeddings = model.encode(df["utterance"].tolist())

    out = compute_pairwise_similarities(df, embeddings, model, "phase1_final")

    assert len(out) == 1
    assert out.iloc[0]["similarity"] == 1.0  # used p1's block-5 utterance
    assert out.iloc[0]["sameGroup"] == 0


def test_block_trajectory_starts_once_two_participants_per_group_have_spoken():
    # Two groups of two. Block 0: one speaker per group. Block 1: the other
    # member of each group speaks. The trajectory must skip block 0 and start
    # at block 1, when every group has two participants with a description.
    rows = [
        _utt("g", "a1", "A", "t", 1, 0, "bunny"),
        _utt("g", "b1", "B", "t", 1, 0, "rabbit"),
        _utt("g", "a2", "A", "t", 1, 1, "bunny"),
        _utt("g", "b2", "B", "t", 1, 1, "hare"),
    ]
    df = pd.DataFrame(rows)
    games = pd.DataFrame({"gameId": ["g"], "phase1Blocks": [6], "phase2Blocks": [6]})

    out = compute_block_pairwise(df, FakeModel(), games)

    assert set(out["blockNum"]) == {1}
    # 4 participants -> 6 pairs, two of them within-group
    assert len(out) == 6
    assert out["sameGroup"].sum() == 2
    within = out[out["sameGroup"] == 1].set_index("group1")["similarity"]
    assert within["A"] == 1.0 and within["B"] == 0.0


def test_block_trajectory_still_requires_two_participants_total():
    rows = [_utt("g", "a1", "A", "t", 1, 0, "bunny"), _utt("g", "a2", "A", "t", 1, 1, "bunny")]
    df = pd.DataFrame(rows)
    games = pd.DataFrame({"gameId": ["g"], "phase1Blocks": [6], "phase2Blocks": [6]})
    out = compute_block_pairwise(df, FakeModel(), games)
    # Only one group: within-group pair exists from block 1 onward
    assert set(out["blockNum"]) == {1}
    assert len(out) == 1


def test_lexical_uniqueness_compares_within_the_same_phase():
    # Group A calls the tangram "bunny" in Phase 1. Group B says "rabbit" in
    # Phase 1 but borrows "bunny" in Phase 2 (mixing). A's Phase 1 word must
    # stay unique; B's Phase 2 "bunny" is not unique against A's Phase 2 use.
    rows = [
        _utt("g1", "a1", "A", "t", 1, 5, "bunny"),
        _utt("g1", "b1", "B", "t", 1, 5, "rabbit"),
        _utt("g1", "a1", "A", "t", 2, 5, "bunny"),
        _utt("g1", "b1", "B", "t", 2, 5, "bunny"),
    ]
    out = compute_lexical_uniqueness(pd.DataFrame(rows))
    val = out.set_index(["playerId", "phaseNum"])["uniqueness"]

    assert val[("a1", 1)] == 1.0  # B's Phase 2 borrowing does not leak into Phase 1
    assert val[("b1", 1)] == 1.0
    assert val[("a1", 2)] == 0.0  # shared in Phase 2
    assert val[("b1", 2)] == 0.0


def test_lexical_uniqueness_is_across_games():
    rows = [
        _utt("g1", "a1", "A", "t", 1, 5, "bunny"),
        _utt("g2", "c1", "A", "t", 1, 5, "bunny"),  # same label, different game
    ]
    out = compute_lexical_uniqueness(pd.DataFrame(rows))
    assert (out["uniqueness"] == 0.0).all()


def test_social_guess_retention_uses_phase2_retention_and_speaker_attribution():
    from compute_derived import compute_social_guess_retention

    social_guesses = pd.DataFrame([
        {"gameId": "g", "playerId": "l1", "originalGroup": "A", "blockNum": 0, "phaseNum": 2,
         "roundId": "r1", "currentGroup": "X", "target": "t", "socialGuess": True,
         "socialGuessCorrect": True, "speakerId": "s1"},
    ])
    trials = pd.DataFrame([
        {"gameId": "g", "playerId": "s1", "originalGroup": "A", "role": "speaker", "blockNum": 0,
         "target": "t", "roundId": "r1", "currentGroup": "X"},
        {"gameId": "g", "playerId": "l1", "originalGroup": "A", "role": "listener", "blockNum": 0,
         "target": "t", "roundId": "r1", "currentGroup": "X"},
    ])
    # Same speaker/target/block index in both phases: only the Phase 2 row may be joined
    term_retention = pd.DataFrame([
        {"gameId": "g", "playerId": "s1", "target": "t", "blockNum": 0, "phaseNum": 1, "retention": 0.1},
        {"gameId": "g", "playerId": "s1", "target": "t", "blockNum": 0, "phaseNum": 2, "retention": 0.9},
    ])
    games = pd.DataFrame({"gameId": ["g"], "condition": ["social_mixed"]})

    out = compute_social_guess_retention(social_guesses, trials, term_retention, games)

    assert len(out) == 1  # one row per guess, no duplication across phases
    assert out.iloc[0]["speakerRetention"] == 0.9
    assert out.iloc[0]["speakerOriginalGroup"] == "A"
    assert out.iloc[0]["speakerWasSameGroup"] == 1
