"""
Unit tests for the descriptive statistics (paper/descriptives.py) on
small hand-built tables: the attrition definitions, the description
coverage, the endpoint macros and the exit-survey recodes.

Run with:
    uv run pytest paper/test_descriptives.py -v
"""

import numpy as np
import pandas as pd

from paper.descriptives import (
    description_coverage,
    endpoint_macros,
    exit_survey_responses,
    felt_human_flags,
    game_status,
    group_attrition,
    phase1_final_words_by_condition,
    phase1_specificity_by_condition,
    player_attrition,
)

GAMES = pd.DataFrame(
    {
        "gameId": ["g1", "g2", "g0"],
        "condition": ["social_mixed", "refer_separated", None],
        "activeGroups": [3, 1, 3],
    }
)
# g1: group A keeps one of two, group B keeps one of two, group C keeps both;
# g2: both groups lose everyone or all but one; g0 is a test game
PLAYERS = pd.DataFrame(
    {
        "gameId": ["g1"] * 6 + ["g2"] * 3 + ["g0"],
        "playerId": [f"p{i}" for i in range(10)],
        "originalGroup": ["A", "A", "B", "B", "C", "C", "A", "A", "B", "A"],
        "isActive": [True, False, True, False, True, True, False, False, True, True],
        "exitReason": [None, "player timeout", None, "group disbanded", None, None,
                       "low accuracy", "low accuracy", None, None],
        "exitSurvey_understood": ["yes", "yes", None, "yes", None, None, None, None, "Yes", "yes"],
        "exitSurvey_groupIdentification": ["6", "3", None, "7", None, None, None, None, "5", "7"],
        "exitSurvey_feltHuman": ["yes", "no", None, "yes", None, None, None, None, "no", "no"],
        "exitSurvey_age": ["31", "x", None, "40", None, None, None, None, "25", "50"],
    }
)


def test_player_attrition_classifies_removals_and_no_fault():
    pa = player_attrition(PLAYERS, GAMES)
    assert len(pa) == 9, "players of the test game are left out"
    by = pa.set_index("playerId")
    assert not by.loc["p0", "removed"] and by.loc["p0", "reason"] == "completed"
    assert by.loc["p1", "reason"] == "idle" and not by.loc["p1", "no_fault"]
    assert by.loc["p3", "reason"] == "group disbanded" and by.loc["p3", "no_fault"]
    assert int(pa["removed"].sum()) == 4 and int(pa["no_fault"].sum()) == 1


def test_group_and_game_status_follow_the_servers_rules():
    ga = group_attrition(PLAYERS, GAMES)
    lost = ga.set_index(["gameId", "originalGroup"])["lost"]
    assert lost.loc[("g1", "A")] and lost.loc[("g1", "B")], "one active member left is below the minimum group size"
    assert not lost.loc[("g1", "C")]
    assert lost.loc[("g2", "A")] and lost.loc[("g2", "B")]
    assert int(ga["lost"].sum()) == 4
    status = game_status(PLAYERS, GAMES).set_index("gameId")
    assert status.loc["g1", "ran_to_completion"] and not status.loc["g1", "complete_nine"]
    assert not status.loc["g2", "ran_to_completion"]
    assert "g0" not in status.index


def test_description_coverage_counts_speaker_trials_without_an_utterance():
    trials = pd.DataFrame(
        {
            "gameId": ["g1", "g1", "g1", "g0"],
            "playerId": ["p0", "p0", "p2", "p9"],
            "role": ["speaker", "speaker", "speaker", "speaker"],
            "phaseNum": [1.0, 1.0, 2.0, 1.0],
            "blockNum": [0.0, 1.0, 0.0, 0.0],
            "target": ["t1", "t2", "t1", "t1"],
            "condition": ["social_mixed", "social_mixed", "social_mixed", None],
        }
    )
    utts = pd.DataFrame(
        {"gameId": ["g1", "g1"], "playerId": ["p0", "p0"], "phaseNum": [1, 1], "blockNum": [0, 1], "target": ["t1", "t2"]}
    )
    assert description_coverage(trials, utts) == (1, 3)


def test_endpoint_macros_report_the_first_and_last_observed_block():
    df = pd.DataFrame(
        {
            "condition": ["refer_mixed"] * 5 + [None],
            "gameBlock": [2, 2, 5, 12, 12, 1],
            "value": [0.2, 0.4, 0.5, 0.8, np.nan, 0.9],
        }
    )
    m = endpoint_macros("x", df, "value", digits=2)
    assert m == {"xN": "4", "xFirstBlock": 2, "xLastBlock": 12, "xFirst": "0.30", "xLast": "0.80"}
    assert endpoint_macros("x", df.iloc[0:0], "value") == {}


def test_phase1_specificity_and_words_by_condition_follow_the_condition_order():
    gs = pd.DataFrame(
        {
            "condition": ["social_first", "social_first", "refer_mixed", "refer_mixed", "refer_mixed"],
            "window": ["phase1_final", "phase1_final", "phase1_final", "phase2_final", "phase1_final"],
            "coefficient": [0.2, 0.4, 0.5, 9.0, np.nan],
            "estimable": [True, True, True, True, False],
        }
    )
    out = phase1_specificity_by_condition(gs)
    assert list(out["condition"].astype(str)) == ["refer_mixed", "social_first"]
    by = out.set_index(out["condition"].astype(str))
    assert by.loc["social_first", "games"] == 2 and abs(by.loc["social_first", "mean"] - 0.3) < 1e-12
    utts = pd.DataFrame(
        {
            "gameId": ["g1"] * 4 + ["g2"] * 2,
            "condition": ["social_first"] * 4 + ["refer_mixed"] * 2,
            "phaseNum": [1, 1, 1, 2, 1, 1],
            "blockNum": [0, 3, 5, 0, 4, 5],
            "uttLength": [10, 6, 4, 1, 3, 5],
        }
    )
    words = phase1_final_words_by_condition(utts)
    words = words.set_index(words["condition"].astype(str))
    assert words.loc["social_first", "mean_words"] == 5.0, "blocks 3 and 5 are within three of the game's last block"
    assert words.loc["refer_mixed", "mean_words"] == 4.0


def test_exit_survey_responses_recode_and_flag_as_the_r_helpers_do():
    survey = exit_survey_responses(PLAYERS, GAMES)
    assert set(survey["playerId"]) == {"p0", "p1", "p3", "p8"}, "respondents of real games with any answer"
    by = survey.set_index("playerId")
    assert by.loc["p0", "respondent"] == "completed" and by.loc["p1", "respondent"] == "removed"
    assert by.loc["p8", "understood"] == "yes" and by.loc["p3", "groupIdentification"] == 7.0
    assert pd.isna(by.loc["p1", "age"]) and by.loc["p0", "age"] == 31.0
    assert len(felt_human_flags(survey)) == 2 and len(felt_human_flags(survey, level="group")) == 2
