"""
Unit tests for the model inputs (pipeline/build_model_inputs.py) on small
hand-built tables: the within-group block means, the final-phase description
properties and the per-listener in-group advantage.

Run with:
    uv run pytest pipeline/test_build_model_inputs.py -v
"""

import numpy as np
import pandas as pd

from pipeline.build_model_inputs import final_phase_properties, ingroup_advantage, within_group_block_means

GAMES = pd.DataFrame({"gameId": ["g1", "g2"], "condition": ["social_mixed", "refer_separated"], "phase1Blocks": [6, 6]})


def test_within_group_block_means_average_a_groups_pairs_and_skip_missing_similarities():
    pairs = pd.DataFrame(
        {
            "gameId": ["g1"] * 5 + ["g2"],
            "target": ["t1"] * 5 + ["t1"],
            "speaker1": ["a", "a", "b", "a", "c", "x"],
            "speaker2": ["b", "c", "c", "b", "d", "y"],
            "group1": ["A", "A", "A", "A", "B", "A"],
            "group2": ["A", "A", "A", "A", "A", "A"],
            "sameGroup": [1, 1, 1, 1, 0, 1],
            "similarity": [0.2, 0.4, np.nan, 0.8, 0.9, 0.5],
            "blockNum": [1, 1, 1, 2, 1, 0],
            "phaseNum": [1, 1, 1, 1, 1, 2],
            "allGroupsPaired": [1, 1, 1, 1, 1, 0],
        }
    )
    out = within_group_block_means(pairs, GAMES)
    assert list(out.columns) == [
        "gameId", "condition", "group", "target", "phaseNum", "blockNum", "block", "similarity", "n_pairs",
    ]
    g1_block2 = out[(out["group"] == "g1_A") & (out["block"] == 2)].iloc[0]
    assert g1_block2["blockNum"] == 1 and g1_block2["phaseNum"] == 1
    assert abs(g1_block2["similarity"] - 0.3) < 1e-12 and g1_block2["n_pairs"] == 2
    g1_block3 = out[(out["group"] == "g1_A") & (out["block"] == 3)].iloc[0]
    assert g1_block3["similarity"] == 0.8 and g1_block3["n_pairs"] == 1
    assert (out["condition"][out["gameId"] == "g2"] == "refer_separated").all()
    assert len(out) == 3, "between-group pairs and all-missing cells produce no row"


def test_final_phase_properties_keep_the_last_block_per_speaker_tangram_and_phase():
    props = pd.DataFrame(
        {
            "gameId": "g1",
            "playerId": ["p1", "p1", "p1", "p2"],
            "originalGroup": ["A", "A", "A", "B"],
            "target": "t1",
            "blockNum": [0, 3, 1, 5],
            "phaseNum": [1, 1, 2, 1],
            "utterance": ["a", "b", "c", "d"],
            "n_content_words": [3, 2, 4, 1],
            "n_concrete": [1, 1, 2, 0],
            "concreteness": [1 / 3, 0.5, 0.5, 0.0],
            "mean_zipf_freq": [4.1, 4.2, 4.3, 4.4],
        }
    )
    uniq = pd.DataFrame(
        {
            "gameId": "g1",
            "playerId": ["p1", "p1", "p1", "p2"],
            "target": "t1",
            "blockNum": [0, 3, 1, 5],
            "phaseNum": [1, 1, 2, 1],
            "uniqueness": [0.1, 0.2, 0.3, 0.4],
            "n_unique_words": [1, 1, 2, 0],
        }
    )
    out = final_phase_properties(props, uniq, GAMES)
    assert len(out) == 3
    p1_phase1 = out[(out["playerId"] == "p1") & (out["phaseNum"] == 1)].iloc[0]
    assert p1_phase1["blockNum"] == 3 and p1_phase1["block"] == 4 and p1_phase1["uniqueness"] == 0.2
    assert p1_phase1["group"] == "g1 A" and p1_phase1["condition"] == "social_mixed"
    assert out[(out["playerId"] == "p1") & (out["phaseNum"] == 2)].iloc[0]["utterance"] == "c"
    assert "n_unique_words" in out.columns


def test_ingroup_advantage_is_the_paired_difference_per_listener_with_both_cells():
    trials = pd.DataFrame(
        {
            "gameId": "g1",
            "condition": "social_mixed",
            "playerId": ["l1"] * 4 + ["l2"] * 3 + ["s1"],
            "role": ["listener"] * 7 + ["speaker"],
            "phaseNum": [2, 2, 2, 1, 2, 2, 2, 2],
            "responseOpportunity": [True, True, True, True, True, True, False, False],
            "inGroupSpeaker": [True, True, False, True, True, True, False, np.nan],
            "correct": [1, 0, 0, 1, 1, np.nan, 1, np.nan],
        }
    )
    out = ingroup_advantage(trials)
    assert list(out["playerId"]) == ["l1"], "a listener without an out-group cell has no row"
    row = out.iloc[0]
    assert row["acc_in"] == 0.5 and row["acc_out"] == 0.0 and row["advantage"] == 0.5
    assert row["n_in"] == 2 and row["n_out"] == 1
    assert row["condition"] == "social_mixed"


def test_ingroup_advantage_reads_boolean_text_as_written_by_csv():
    trials = pd.DataFrame(
        {
            "gameId": "g1",
            "condition": "refer_mixed",
            "playerId": ["l1", "l1"],
            "role": "listener",
            "phaseNum": [2.0, 2.0],
            "responseOpportunity": ["True", "True"],
            "inGroupSpeaker": ["True", "False"],
            "correct": ["1", "0"],
        }
    )
    out = ingroup_advantage(trials)
    assert len(out) == 1 and out.iloc[0]["advantage"] == 1.0
