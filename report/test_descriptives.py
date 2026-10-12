"""
Unit tests for the descriptive statistics (report/descriptives.py) on
small hand-built tables: the attrition definitions, the description
coverage, the endpoint macros and the exit-survey recodes.

Run with:
    uv run pytest report/test_descriptives.py -v
"""

import numpy as np
import pandas as pd

from report.descriptives import (
    condition_count_macros,
    condition_counts,
    description_coverage,
    description_coverage_by_condition,
    endpoint_macros,
    exit_survey_responses,
    felt_human_flags,
    final_words_by_condition,
    game_status,
    group_attrition,
    listener_accuracy_by_speaker_group,
    phase1_final_words_by_condition,
    phase1_specificity_by_condition,
    phase_specificity_change_by_condition,
    player_attrition,
    response_opportunities,
    response_opportunity_macros,
    session_minutes_macros,
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
    by = description_coverage_by_condition(trials, utts)
    assert list(by["condition"].astype(str)) == ["social_mixed"], "the test game's trials are left out"
    assert by.loc[0, "speaker_trials"] == 3 and by.loc[0, "without"] == 1
    assert abs(by.loc[0, "prop_without"] - 1 / 3) < 1e-12


def test_response_opportunities_count_what_became_of_each_opportunity():
    trials = pd.DataFrame(
        {
            "gameId": ["g1"] * 6,
            "role": ["listener"] * 5 + ["speaker"],
            "phaseNum": [1.0, 1.0, 1.0, 1.0, 2.0, 1.0],
            "condition": ["social_mixed"] * 6,
            "responseOpportunity": [True, True, True, True, False, True],
            # correct on time, a timeout, a late correct answer (coded 0), an excluded row
            "correct": [1, 0, 0, np.nan, np.nan, np.nan],
            "onTime": [True, False, False, True, np.nan, np.nan],
            "lateClick": [False, False, True, False, False, False],
        }
    )
    guesses = pd.DataFrame(
        {
            "gameId": ["g1"] * 2,
            "phaseNum": [2, 2],
            "condition": ["social_mixed"] * 2,
            "responseOpportunity": [True, True],
            "correct": [1, 0],
            "onTime": [True, True],
            "lateSocialGuess": [False, False],
        }
    )
    out = response_opportunities(trials, guesses)
    ref = out[out["task"] == "referential"].iloc[0]
    assert len(out) == 2 and ref["phaseNum"] == 1, "a row that is no opportunity, or a speaker's, is not counted"
    assert ref["opportunities"] == 4 and ref["scored"] == 3 and ref["on_time"] == 1
    assert abs(ref["accuracy"] - 1 / 3) < 1e-12 and ref["accuracy_on_time"] == 1.0
    assert ref["late"] == 1 and abs(ref["late_rate"] - 1 / 3) < 1e-12
    m = response_opportunity_macros(out)
    assert m["overviewRefPhaseOneSocialMixedOpportunities"] == "4"
    assert m["overviewRefPhaseOneSocialMixedAccuracy"] == "0.333"
    assert m["overviewSocialPhaseTwoSocialMixedOnTimeRate"] == "1.000"


def test_condition_counts_follow_the_attrition_definitions():
    t = {"games": GAMES, "players": PLAYERS, "participant_exclusions": pd.DataFrame({"playerId": ["p1"], "reason": ["x"]})}
    counts = condition_counts(t).set_index("condition")
    assert list(counts.index) == ["refer_separated", "social_mixed"], "conditions with no games are left out"
    assert counts.loc["social_mixed", "games"] == 1 and counts.loc["social_mixed", "games_ran_to_completion"] == 1
    assert counts.loc["social_mixed", "removed"] == 2 and counts.loc["social_mixed", "removed_no_fault"] == 1
    assert counts.loc["social_mixed", "groups_lost"] == 2 and counts.loc["social_mixed", "excluded_participants"] == 1
    assert counts.loc["refer_separated", "games_ran_to_completion"] == 0
    m = condition_count_macros(condition_counts(t))
    assert m["overviewNGamesCompleteSocialMixed"] == 0 and m["overviewNExcludedParticipantsReferSeparated"] == 0


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


def test_semantic_drift_macros_describe_refer_separated_with_a_game_level_interval():
    from report.descriptives import semantic_drift_macros

    rows = []
    for g, m in [("a", 0.6), ("b", 0.8), ("c", 0.9)]:
        rows += [{"gameId": g, "condition": "refer_separated", "simPhase1Phase2": m + d} for d in (-0.05, 0.0, 0.05)]
    rows += [{"gameId": "z", "condition": "refer_mixed", "simPhase1Phase2": 0.1}] * 3
    out = semantic_drift_macros(pd.DataFrame(rows))
    assert set(out) == {"exploratoryDriftMean", "exploratoryDriftLo", "exploratoryDriftHi", "exploratoryDriftGames"}
    assert out["exploratoryDriftMean"] == "0.767"  # refer_separated rows only
    assert float(out["exploratoryDriftLo"]) <= 0.767 <= float(out["exploratoryDriftHi"])
    assert out["exploratoryDriftGames"] == "3"
    assert semantic_drift_macros(pd.DataFrame()) == {}


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


def test_phase_specificity_change_pairs_games_within_condition():
    gs = pd.DataFrame(
        {
            "gameId": ["g1", "g1", "g2", "g2", "g3", "g4", "g4"],
            "condition": ["refer_mixed"] * 4 + ["refer_mixed"] + ["social_mixed"] * 2,
            "window": ["phase1_final", "phase2_final"] * 2 + ["phase1_final", "phase1_final", "phase2_final"],
            "coefficient": [0.4, 0.2, 0.6, 0.3, 0.5, 0.4, 0.4],
            "estimable": [True] * 6 + [False],
        }
    )
    out = phase_specificity_change_by_condition(gs)
    out = out.set_index(out["condition"].astype(str))
    rm = out.loc["refer_mixed"]
    assert rm["games_phase1"] == 3 and rm["games_phase2"] == 2 and rm["games_paired"] == 2
    assert abs(rm["mean_phase1"] - 0.5) < 1e-12, "the Phase 1 mean uses every estimable Phase 1 game"
    assert abs(rm["change"] - (-0.25)) < 1e-12, "the change averages the paired differences"
    assert abs(rm["ratio"] - 0.5) < 1e-12, "the ratio compares the paired means"
    assert rm["change_lower"] <= rm["change"] <= rm["change_upper"]
    sm = out.loc["social_mixed"]
    assert sm["games_phase2"] == 0 and np.isnan(sm["change"]), "an inestimable endpoint gives no change"
    assert list(out.index) == ["refer_mixed", "social_mixed"]


def test_listener_accuracy_by_speaker_group_averages_listeners_with_game_intervals():
    advantage = pd.DataFrame(
        {
            "gameId": ["g1", "g1", "g2", "g3"],
            "condition": ["social_mixed", "social_mixed", "social_mixed", "refer_mixed"],
            "playerId": ["p1", "p2", "p3", "p4"],
            "acc_in": [1.0, 0.8, 0.9, 1.0],
            "acc_out": [0.5, 0.7, np.nan, 0.8],
        }
    )
    out = listener_accuracy_by_speaker_group(advantage)
    by = out.set_index([out["condition"].astype(str), "listener_type"])
    assert abs(by.loc[("social_mixed", "in_group"), "accuracy"] - 0.9) < 1e-12
    assert by.loc[("social_mixed", "in_group"), "listeners"] == 3
    assert abs(by.loc[("social_mixed", "out_group"), "accuracy"] - 0.6) < 1e-12, "a missing accuracy is dropped"
    assert by.loc[("social_mixed", "out_group"), "listeners"] == 2
    assert ("refer_mixed", "in_group") not in by.index, "one listener cannot be bootstrapped"
    assert list(out["condition"].astype(str).unique()) == ["social_mixed"]


def test_final_words_by_condition_takes_each_phase_separately():
    utts = pd.DataFrame(
        {
            "gameId": ["g1"] * 5,
            "condition": ["social_first"] * 5,
            "phaseNum": [1, 1, 2, 2, 2],
            "blockNum": [4, 5, 0, 1, 5],
            "uttLength": [6, 4, 10, 8, 2],
        }
    )
    p1 = final_words_by_condition(utts, phase=1)
    p1 = p1.set_index(p1["condition"].astype(str))
    p2 = final_words_by_condition(utts, phase=2)
    p2 = p2.set_index(p2["condition"].astype(str))
    assert p1.loc["social_first", "mean_words"] == 5.0
    assert p2.loc["social_first", "mean_words"] == 2.0, "Phase 2 blocks 0 and 1 are more than two before block 5"
    assert phase1_final_words_by_condition(utts).equals(final_words_by_condition(utts, phase=1))


def test_session_minutes_macros_take_real_games_only():
    players = PLAYERS.assign(minutesSpent=[40, 10, 50, 12, 48, 52, 30, 31, 55, 99])
    out = session_minutes_macros(players, GAMES)
    assert out["overviewMinutesN"] == "9", "the test game g0 is left out"
    assert out["overviewMinutesMedian"] == "40"
    assert out["overviewMinutesLowerDecile"] < out["overviewMinutesMedian"] < out["overviewMinutesUpperDecile"]
    assert session_minutes_macros(players.drop(columns=["minutesSpent"]), GAMES) == {}
