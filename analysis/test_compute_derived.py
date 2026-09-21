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

import sys

import numpy as np
import pandas as pd
import pytest

import compute_derived
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
    # word counts of the two chosen descriptions ("late" and "late")
    assert (out.iloc[0]["length1"], out.iloc[0]["length2"]) == (1, 1)


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


def test_a_filtered_file_without_a_matching_sidecar_is_refused(tmp_path, monkeypatch, capsys):
    """The derived step must never analyze filtered utterances built from a
    different messages.csv; it stops before loading the model."""
    pd.DataFrame({"gameId": ["g"], "text": ["a"]}).to_csv(tmp_path / "messages.csv", index=False)
    (tmp_path / "speaker_utterances_filtered.csv").write_text("gameId,utterance\n")
    monkeypatch.setattr(sys, "argv", ["compute_derived.py", str(tmp_path)])
    with pytest.raises(SystemExit) as excinfo:
        compute_derived.main()
    assert excinfo.value.code == 1
    assert "filtered utterances are stale" in capsys.readouterr().err


# ── Content-word overlap (Jaccard) robustness tables ────────────────────────

from compute_derived import (  # noqa: E402
    compute_block_pairwise_jaccard,
    compute_pairwise_similarities_jaccard,
    jaccard_similarity,
)


class TestJaccardSimilarity:
    def test_overlap_of_distinct_content_word_sets(self):
        # {big, red, bunny} vs {bunny, rabbit}: one shared word of four distinct
        sim = jaccard_similarity(
            pd.Series({"utterance": "the big red bunny"}),
            pd.Series({"utterance": "a bunny, rabbit"}),
        )
        assert sim == pytest.approx(0.25)

    def test_stopwords_one_character_words_and_repeats_do_not_count(self):
        # "the", "is", "a", "on" are NLTK stopwords, "x" is one character, and
        # "bunny" twice counts once; case and punctuation are ignored.
        sim = jaccard_similarity(
            pd.Series({"utterance": "the bunny is a bunny on x"}),
            pd.Series({"utterance": "Bunny!"}),
        )
        assert sim == 1.0

    def test_nan_when_either_description_has_no_content_words(self):
        assert np.isnan(
            jaccard_similarity(pd.Series({"utterance": "the a"}), pd.Series({"utterance": "bunny"}))
        )
        assert np.isnan(
            jaccard_similarity(pd.Series({"utterance": float("nan")}), pd.Series({"utterance": "bunny"}))
        )


def test_jaccard_pairwise_table_lines_up_with_the_sbert_table():
    """Same rows in the same order as the SBERT table; only `similarity` differs."""
    rows = [
        _utt("g", "p1", "A", "t", 1, 5, "big red bunny"),
        _utt("g", "p1", "A", "t", 1, 3, "early"),
        _utt("g", "p2", "B", "t", 1, 4, "bunny rabbit"),
        _utt("g", "p3", "B", "t", 1, 4, "the"),
        _utt("g", "p1", "A", "u", 1, 2, "house"),
        _utt("g", "p2", "B", "u", 1, 2, "house"),
    ]
    df = pd.DataFrame(rows)
    model = FakeModel()
    sbert = compute_pairwise_similarities(
        df, model.encode(df["utterance"].tolist()), model, "phase1_final"
    )
    jaccard = compute_pairwise_similarities_jaccard(df, "phase1_final")

    assert list(jaccard.columns) == list(sbert.columns)
    other = [c for c in sbert.columns if c != "similarity"]
    pd.testing.assert_frame_equal(jaccard[other], sbert[other])

    by_pair = jaccard.set_index(["target", "speaker1", "speaker2"])["similarity"]
    assert by_pair[("t", "p1", "p2")] == pytest.approx(0.25)  # p1's block-5 description
    assert np.isnan(by_pair[("t", "p1", "p3")])  # "the" has no content words
    assert by_pair[("u", "p1", "p2")] == 1.0
    # the SBERT table has a value where Jaccard is undefined: the row stays
    assert not np.isnan(sbert.set_index(["target", "speaker1", "speaker2"])["similarity"][("t", "p1", "p3")])


def test_jaccard_block_table_lines_up_with_the_sbert_block_table():
    rows = [
        _utt("g", "a1", "A", "t", 1, 0, "bunny"),
        _utt("g", "b1", "B", "t", 1, 0, "rabbit"),
        _utt("g", "a2", "A", "t", 1, 1, "bunny ears"),
        _utt("g", "b2", "B", "t", 1, 1, "hare"),
    ]
    df = pd.DataFrame(rows)
    games = pd.DataFrame({"gameId": ["g"], "phase1Blocks": [6], "phase2Blocks": [6]})

    sbert = compute_block_pairwise(df, FakeModel(), games)
    jaccard = compute_block_pairwise_jaccard(df)

    assert list(jaccard.columns) == list(sbert.columns)
    other = [c for c in sbert.columns if c != "similarity"]
    pd.testing.assert_frame_equal(jaccard[other], sbert[other])
    within = jaccard[jaccard["sameGroup"] == 1].set_index("group1")["similarity"]
    assert within["A"] == pytest.approx(0.5)  # {bunny} vs {bunny, ears}
    assert within["B"] == 0.0


def test_jaccard_block_table_is_empty_for_no_utterances():
    assert compute_block_pairwise_jaccard(pd.DataFrame()).empty


# ── H3c counts behind the proportions ───────────────────────────────────────
#
# The preregistered H3c models fit concreteness and lexical uniqueness as
# binomial counts, cbind(k, n - k), rather than as Gaussian proportions,
# because the denominator varies from one content word to several dozen and
# is itself expected to differ by condition. A ratio alone cannot be fit that
# way, so both numerator and denominator have to reach the CSV, and they have
# to agree with the ratio stored beside them.

_H3C_UTTS = pd.DataFrame(
    {
        "gameId": ["g1", "g1", "g2", "g2"],
        "playerId": ["p1", "p2", "p3", "p4"],
        "originalGroup": ["A", "B", "A", "B"],
        "target": ["t1", "t1", "t1", "t1"],
        "blockNum": [1, 1, 1, 1],
        "phaseNum": [1, 1, 1, 1],
        # p1: four content words, three of them concrete (triangle/arm/left)
        # p2: two content words, neither concrete
        # p3: repeats a token, so tokens and types differ
        # p4: no content words at all
        "utterance": [
            "a big triangle arm on the left",
            "zebra unicorn",
            "triangle triangle zebra",
            "the a of",
        ],
    }
)
_H3C_GAMES = pd.DataFrame(
    {"gameId": ["g1", "g2"], "condition": ["social_mixed", "social_first"]}
)


def test_description_properties_keep_the_counts_behind_concreteness():
    out = compute_derived.compute_description_properties(_H3C_UTTS, _H3C_GAMES)
    by_player = out.set_index("playerId")
    assert by_player.loc["p1", "n_content_words"] == 4
    assert by_player.loc["p1", "n_concrete"] == 3
    assert by_player.loc["p2", "n_content_words"] == 2
    assert by_player.loc["p2", "n_concrete"] == 0
    # Tokens, not types: "triangle triangle zebra" is three content words.
    assert by_player.loc["p3", "n_content_words"] == 3
    assert by_player.loc["p3", "n_concrete"] == 2


def test_lexical_uniqueness_keeps_the_counts_behind_the_proportion():
    out = compute_lexical_uniqueness(_H3C_UTTS)
    by_player = out.set_index("playerId")
    # p3's "triangle" also appears in g1 group A, so only "zebra" would be
    # unique were it not also in g1 group B: every p3 token is shared.
    assert by_player.loc["p3", "n_content_words"] == 3
    assert by_player.loc["p3", "n_unique_words"] == 0
    assert by_player.loc["p1", "n_content_words"] == 4


@pytest.mark.parametrize(
    "compute,numerator,denominator,ratio",
    [
        (
            lambda d: compute_derived.compute_description_properties(d, _H3C_GAMES),
            "n_concrete",
            "n_content_words",
            "concreteness",
        ),
        (compute_lexical_uniqueness, "n_unique_words", "n_content_words", "uniqueness"),
    ],
)
def test_counts_reproduce_the_stored_proportion(
    compute, numerator, denominator, ratio
):
    out = compute(_H3C_UTTS)
    scored = out[out[denominator] > 0]
    assert len(scored) == 3
    assert np.allclose(scored[numerator] / scored[denominator], scored[ratio])
    # A description with no content words has no proportion and no counts to
    # model; it must not become a silent zero-out-of-zero row.
    empty = out[out[denominator] == 0]
    assert len(empty) == 1
    assert empty[ratio].isna().all()


def test_counts_are_integers_so_cbind_gets_whole_numbers():
    props = compute_derived.compute_description_properties(_H3C_UTTS, _H3C_GAMES)
    uniq = compute_lexical_uniqueness(_H3C_UTTS)
    for frame, cols in (
        (props, ("n_content_words", "n_concrete")),
        (uniq, ("n_content_words", "n_unique_words")),
    ):
        for col in cols:
            assert pd.api.types.is_integer_dtype(frame[col]), col
