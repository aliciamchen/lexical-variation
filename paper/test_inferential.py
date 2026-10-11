"""
Tests for the inferential macro formatter (paper/inferential.py) on small
hand-written estimates tables: the macro families, the rules for missing rows,
and the refusal of a Bayes factor that warned.

Run with:
    uv run pytest paper/test_inferential.py -v
"""

import pandas as pd
import pytest

from paper.inferential import (
    Estimates,
    bf_macro,
    checks_macros,
    coef_macros,
    contrast_macros,
    htest_macros,
    or_macros,
    pick_row,
    primary_macros,
    read_estimates,
    secondary_macros,
)


def write(tmp_path, name, frame):
    path = tmp_path / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def test_read_estimates_is_empty_for_a_missing_table_and_exact_for_a_present_one(tmp_path):
    assert read_estimates(tmp_path, "primary/missing").empty
    write(tmp_path, "primary/x", pd.DataFrame({"estimate": [0.35821058022612084]}))
    assert read_estimates(tmp_path, "primary/x")["estimate"].iloc[0] == 0.35821058022612084


def test_pick_row_returns_one_row_or_none_and_refuses_several():
    table = pd.DataFrame({"analysis": ["a", "a", "b"], "term": ["x", "y", "x"], "estimate": [1.0, 2.0, 3.0]})
    assert pick_row(table, analysis="a", term="y")["estimate"] == 2.0
    assert pick_row(table, analysis="c") is None
    assert pick_row(table, missing_column="a") is None
    assert pick_row(pd.DataFrame(), analysis="a") is None
    with pytest.raises(ValueError, match="2 rows"):
        pick_row(table, analysis="a")


def test_macro_families_format_as_the_manuscript_expects():
    contrast = pd.Series({"estimate": 0.35821, "lower": 0.32191, "upper": 0.39451, "p_value": 9.9e-33})
    assert contrast_macros("primaryHOne", contrast) == {
        "primaryHOneEst": "0.358", "primaryHOneLo": "0.322", "primaryHOneHi": "0.395", "primaryHOneP": "< .001",
    }
    coef = pd.Series({"estimate": -0.20107, "std_error": 0.013326, "statistic": -15.0888, "p_value": 2.2e-12,
                      "odds_ratio": 2.28947, "or_lower": 2.18915, "or_upper": 2.39438})
    assert coef_macros("checksLength", coef) == {
        "checksLengthEst": "-0.201", "checksLengthSE": "0.013", "checksLengthStat": "-15.09", "checksLengthP": "< .001",
    }
    assert or_macros("checksAccuracy", coef) == {
        "checksAccuracyOR": "2.289", "checksAccuracyORLo": "2.189", "checksAccuracyORHi": "2.394",
    }
    assert or_macros("x", pd.Series({"odds_ratio": float("nan")})) == {}
    chi = pd.Series({"statistic": 2.33383, "df": 3.0, "p_value": 0.50607})
    assert htest_macros("checksDropoutPlayers", chi) == {
        "checksDropoutPlayersStat": "2.33", "checksDropoutPlayersDf": 3, "checksDropoutPlayersP": ".506",
    }
    fisher = pd.Series({"statistic": float("nan"), "df": float("nan"), "p_value": 0.62051})
    assert htest_macros("checksDropoutGames", fisher) == {"checksDropoutGamesP": ".621"}
    for family in (contrast_macros, coef_macros, or_macros, htest_macros, bf_macro):
        assert family("x", None) == {}


def test_a_bayes_factor_is_written_only_when_computed_without_a_warning(capsys):
    ok = pd.Series({"computed": True, "bf10": 0.3698, "warnings": float("nan")})
    assert bf_macro("primaryHThreeA", ok) == {"primaryHThreeABF": "0.37"}
    skipped = pd.Series({"computed": False, "bf10": float("nan"), "warnings": float("nan")})
    assert bf_macro("primaryHOne", skipped) == {}
    warned = pd.Series({"computed": True, "bf10": 2.6e-07, "warnings": "logml could not be estimated within maxiter"})
    assert bf_macro("primaryHFourA", warned) == {}
    assert "primaryHFourABF is not written" in capsys.readouterr().out


def test_the_three_files_are_built_from_the_tables_and_skip_what_is_missing(tmp_path):
    write(tmp_path, "checks/convention_trends", pd.DataFrame({
        "analysis": ["length", "accuracy"], "estimate": [-0.2, 0.8], "std_error": [0.01, 0.02],
        "statistic": [-15.1, 36.2], "p_value": [1e-12, 1e-200], "odds_ratio": [float("nan"), 2.29],
        "or_lower": [float("nan"), 2.19], "or_upper": [float("nan"), 2.39], "n_games": [90, 90], "n_rows": [9502, 18388],
    }))
    write(tmp_path, "checks/phase1_group_specificity", pd.DataFrame({
        "gameId": ["g1", "g2", "g3"], "condition": ["refer_mixed", "social_first", "refer_mixed"],
        "coefficient": [0.4, 0.3, float("nan")], "singular": [True, False, float("nan")],
        "p_value": [0.001, 0.2, float("nan")], "shared_phase1": [True, False, True],
    }))
    write(tmp_path, "checks/dropout_and_survey", pd.DataFrame({
        "analysis": ["dropout_games"], "statistic": [float("nan")], "df": [float("nan")], "p_value": [0.62],
    }))
    est = Estimates(tmp_path)
    checks = checks_macros(est)
    assert checks["checksNGamesPooled"] == 90 and checks["checksNUtterances"] == "9{,}502"
    assert checks["checksNListenerTrials"] == "18{,}388"
    assert checks["checksAccuracyOR"] == "2.290" and "checksLengthOR" not in checks
    assert "checksAdjacentEst" not in checks, "a model that was not fit contributes no macro"
    assert checks["checksNGamesGS"] == 1 and checks["checksMeanGS"] == "0.400"
    assert checks["checksNGamesPerm"] == 2 and checks["checksNGamesSigGS"] == 1
    assert checks["checksNGamesPermShared"] == 1 and checks["checksNGamesSigGSShared"] == 1
    assert checks["checksNGamesFitGS"] == 2 and checks["checksNGamesSingularGS"] == 1
    assert checks["checksDropoutGamesP"] == ".620" and "checksDropoutPlayersP" not in checks

    write(tmp_path, "primary/group_specificity", pd.DataFrame({
        "gameId": ["g1", "g1", "g2", "g2"], "window": ["phase1_final", "phase2_final"] * 2,
        "estimable": [True, True, True, False], "singular": [True, False, float("nan"), False],
    }))
    write(tmp_path, "primary/h1_h2", pd.DataFrame({
        "analysis": ["h1_h2", "h1_h2"], "term": ["H1_sep_vs_mixed", "H2_social_vs_mixed"],
        "estimate": [0.358, 0.144], "lower": [0.322, 0.109], "upper": [0.395, 0.180], "p_value": [1e-33, 1e-12], "n_games": [86, 86],
    }))
    write(tmp_path, "primary/bayes_factors", pd.DataFrame({
        "hypothesis": ["H1", "H3a"], "computed": [False, True], "bf10": [float("nan"), 0.37], "warnings": [float("nan")] * 2,
    }))
    write(tmp_path, "primary/h4_social_components", pd.DataFrame({
        "opportunities": [100, 200], "in_group_opportunities": [50, 100], "out_group_opportunities": [50, 100],
        "on_time": [90, 190], "scored": [100, 200], "hit_rate": [0.8, 0.9], "in_group_answered": [40, 80],
        "false_alarm_rate": [0.1, 0.2], "out_group_answered": [50, 100],
    }))
    write(tmp_path, "primary/robustness", pd.DataFrame({
        "analysis": ["h1_h2", "h4a"], "term": ["H1_sep_vs_mixed", "H4a_socialfirst_gt_socialmixed"],
        "restriction": ["complete_games", "three_groups"], "estimate": [0.347, 1.13], "lower": [0.308, 0.90],
        "upper": [0.386, 1.42], "p_value": [1e-21, 0.28], "n_games": [48, 43],
    }))
    primary = primary_macros(est)
    assert primary["primaryNGamesBothEndpoints"] == 1 and primary["primaryNGamesPhaseOneEndpoint"] == 2
    assert primary["primaryNGameWindows"] == 4 and primary["primaryNGameWindowsSingular"] == 1
    assert primary["primaryNGamesHOneTwo"] == 86 and primary["primaryHTwoHi"] == "0.180"
    assert "primaryHOneBF" not in primary and "primaryHThreeABF" not in primary, (
        "a Bayes factor is written beside its contrast, so H3a's needs the H3a row"
    )
    assert primary["primaryNSocialOpportunities"] == "300"
    assert primary["primarySocialOnTimeRate"] == "0.933"
    assert primary["primarySocialHitRate"] == fmt(((0.8 * 40 + 0.9 * 80) / 120))
    assert primary["primaryNGamesComplete"] == 48 and primary["primaryHOneCompleteEst"] == "0.347"
    assert "primaryHTwoCompleteEst" not in primary and "primaryNGamesThreeGroups" not in primary
    assert primary["primaryHFourAThreeGroupsEst"] == "1.130"

    write(tmp_path, "secondary/semantic_change_switched", pd.DataFrame({
        "condition": ["refer_separated", "social_first"], "prop_switched": [0.139, 0.075],
    }))
    write(tmp_path, "secondary/social_accuracy_trend", pd.DataFrame({
        "analysis": ["social_accuracy_trend"], "estimate": [0.082], "std_error": [0.015], "statistic": [5.55],
        "p_value": [1e-8], "outcome_mean": [0.8091], "n_scored": [10885],
    }))
    secondary = secondary_macros(est)
    assert secondary["secondarySwitchedReferSeparated"] == "0.139" and secondary["secondarySwitchedSocialFirst"] == "0.075"
    assert secondary["secondarySocialAccBlockStat"] == "5.55"
    assert secondary["secondarySocialAccMean"] == "0.809" and secondary["secondarySocialAccN"] == "10{,}885"
    assert "secondarySemanticSepVsMixedEst" not in secondary


def fmt(x):
    return f"{x:.3f}"
