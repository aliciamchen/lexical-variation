"""
The inferential macros: checks.tex, primary.tex and secondary.tex from the
estimates tables the model scripts wrote.

The R scripts in models/ fit the models and write tidy estimates tables to
results/<dataset>/estimates/ (one row per estimated quantity; the shape is
described in models/R/tidy.R). This module reads those tables and writes the
three inferential macro files, one per preregistered family, with the macro
names the manuscript uses:

    <prefix>Est, <prefix>Lo, <prefix>Hi, <prefix>P    a planned contrast with
                                                      its 95% interval
    <prefix>Est, <prefix>SE, <prefix>Stat, <prefix>P  a model coefficient
    <prefix>OR, <prefix>ORLo, <prefix>ORHi            a logistic coefficient's
                                                      odds ratio
    <prefix>Stat, <prefix>Df, <prefix>P               a classical test
    <prefix>BF                                        a Bayes factor
    <family>N...                                      a count

A comparison the dataset could not support has no row in its table and so
contributes no macro, which makes an unavailable number fail loudly in LaTeX
rather than read as a result. A Bayes factor whose computation raised a
warning (bridge sampling that did not converge) is likewise left out, with a
note, because the number is not reliable whatever its size. Formatting every
number here, after the models have run, means a change of rounding or wording
costs seconds rather than a refit; the formatting rules themselves are in
report/stats_tex.py.

Usage:
    uv run python -m report.inferential --dataset full

Tests: report/test_inferential.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from preprocessing.dataset_paths import add_dataset_argument, dataset_dirs
from report.stats_tex import (
    check_unique_names,
    condition_macro_name,
    fmt_bf,
    fmt_count,
    fmt_pval,
    fmt_stat,
    stats_file,
    write_stats_tex,
)

SOURCE = "report/inferential.py"


# ── Reading the estimates ────────────────────────────────────


def read_estimates(estimates_dir: Path, name: str) -> pd.DataFrame:
    """The estimates table `name` ("primary/h1_h2") as written, or an empty frame when absent.

    Floats are parsed with the round-trip parser so that a number formats
    exactly as R would format the double it wrote.
    """
    path = Path(estimates_dir) / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, float_precision="round_trip")


class Estimates:
    """The estimates tables of one dataset, read on first use."""

    def __init__(self, estimates_dir: Path):
        self.dir = Path(estimates_dir)
        self._tables: dict[str, pd.DataFrame] = {}

    def table(self, name: str) -> pd.DataFrame:
        if name not in self._tables:
            self._tables[name] = read_estimates(self.dir, name)
        return self._tables[name]

    def row(self, name: str, **where) -> pd.Series | None:
        """The one row of `name` matching every condition, or None when there is none."""
        return pick_row(self.table(name), **where)


def pick_row(table: pd.DataFrame, **where) -> pd.Series | None:
    if table.empty:
        return None
    mask = pd.Series(True, index=table.index)
    for column, value in where.items():
        if column not in table.columns:
            return None
        mask &= table[column] == value
    hits = table[mask]
    if hits.empty:
        return None
    if len(hits) > 1:
        raise ValueError(f"{len(hits)} rows match {where}; expected one")
    return hits.iloc[0]


def is_true(series: pd.Series) -> pd.Series:
    """A boolean column as written by R (TRUE/FALSE, blank for NA)."""
    return series.map(lambda v: v is True or str(v).upper() == "TRUE")


def count(x) -> int:
    return int(round(float(x)))


# ── Macro families ───────────────────────────────────────────


def contrast_macros(prefix: str, r: pd.Series | None, digits: int = 3) -> dict:
    """Est, Lo, Hi and P of a contrast row; nothing for a missing row."""
    if r is None:
        return {}
    return {
        f"{prefix}Est": fmt_stat(r["estimate"], digits),
        f"{prefix}Lo": fmt_stat(r["lower"], digits),
        f"{prefix}Hi": fmt_stat(r["upper"], digits),
        f"{prefix}P": fmt_pval(r["p_value"]),
    }


def coef_macros(prefix: str, r: pd.Series | None, digits: int = 3) -> dict:
    """Est, SE, Stat (t or z, two decimals) and P of a coefficient row."""
    if r is None:
        return {}
    return {
        f"{prefix}Est": fmt_stat(r["estimate"], digits),
        f"{prefix}SE": fmt_stat(r["std_error"], digits),
        f"{prefix}Stat": fmt_stat(r["statistic"], 2),
        f"{prefix}P": fmt_pval(r["p_value"]),
    }


def or_macros(prefix: str, r: pd.Series | None) -> dict:
    """OR, ORLo and ORHi of a logistic coefficient row."""
    if r is None or pd.isna(r.get("odds_ratio")):
        return {}
    return {
        f"{prefix}OR": fmt_stat(r["odds_ratio"]),
        f"{prefix}ORLo": fmt_stat(r["or_lower"]),
        f"{prefix}ORHi": fmt_stat(r["or_upper"]),
    }


def htest_macros(prefix: str, r: pd.Series | None) -> dict:
    """Stat (two decimals), Df and P of a test row; Fisher's exact test has only P."""
    if r is None:
        return {}
    out = {}
    if not pd.isna(r["statistic"]):
        out[f"{prefix}Stat"] = fmt_stat(r["statistic"], 2)
    if not pd.isna(r["df"]):
        out[f"{prefix}Df"] = count(r["df"])
    out[f"{prefix}P"] = fmt_pval(r["p_value"])
    return out


def bf_macro(prefix: str, r: pd.Series | None) -> dict:
    """BF of a Bayes-factor row, unless it was not computed or raised a warning."""
    if r is None or not bool(r["computed"]) or pd.isna(r["bf10"]):
        return {}
    if "warnings" in r.index and isinstance(r["warnings"], str) and r["warnings"].strip():
        print(f"  note: {prefix}BF is not written; its computation warned: {r['warnings']}")
        return {}
    return {f"{prefix}BF": fmt_bf(r["bf10"])}


# ── The three files ──────────────────────────────────────────


def checks_macros(est: Estimates) -> dict:
    m: dict = {}
    trends = est.table("checks/convention_trends")
    length = pick_row(trends, analysis="length")
    accuracy = pick_row(trends, analysis="accuracy")
    adjacent = pick_row(trends, analysis="adjacent_similarity")
    if length is not None:
        m["checksNGamesPooled"] = count(length["n_games"])
        m["checksNUtterances"] = fmt_count(length["n_rows"])
    if accuracy is not None:
        m["checksNListenerTrials"] = fmt_count(accuracy["n_rows"])
    m.update(coef_macros("checksLength", length))
    m.update(coef_macros("checksAccuracy", accuracy))
    m.update(or_macros("checksAccuracy", accuracy))
    m.update(coef_macros("checksAdjacent", adjacent))

    gs = est.table("checks/phase1_group_specificity")
    if not gs.empty:
        shared = is_true(gs["shared_phase1"])
        finite = gs["coefficient"].notna()
        shared_values = gs.loc[shared & finite, "coefficient"]
        if len(shared_values):
            m["checksNGamesGS"] = int(len(shared_values))
            m["checksMeanGS"] = fmt_stat(shared_values.mean())
            m["checksMedianGS"] = fmt_stat(shared_values.median())
        has_p = gs["p_value"].notna()
        significant = gs["p_value"] < 0.05
        m["checksNGamesPerm"] = int(has_p.sum())
        m["checksNGamesSigGS"] = int(significant.sum())
        m["checksNGamesPermShared"] = int((has_p & shared).sum())
        m["checksNGamesSigGSShared"] = int((significant & shared).sum())
        if "singular" in gs.columns:
            m["checksNGamesFitGS"] = int(finite.sum())
            m["checksNGamesSingularGS"] = int(is_true(gs["singular"]).sum())

    tests = est.table("checks/dropout_and_survey")
    for analysis, prefix in (
        ("dropout_players", "checksDropoutPlayers"),
        ("dropout_games", "checksDropoutGames"),
        ("survey_identification", "checksSurveyIdentification"),
        ("survey_closeness", "checksSurveyCloseness"),
        ("survey_group_language", "checksSurveyGroupLanguage"),
    ):
        m.update(htest_macros(prefix, pick_row(tests, analysis=analysis)))
    return m


def primary_macros(est: Estimates) -> dict:
    m: dict = {}
    gs = est.table("primary/group_specificity")
    if not gs.empty:
        estimable = is_true(gs["estimable"])
        phase1 = set(gs.loc[estimable & (gs["window"] == "phase1_final"), "gameId"])
        phase2 = set(gs.loc[estimable & (gs["window"] == "phase2_final"), "gameId"])
        m["primaryNGamesBothEndpoints"] = len(phase1 & phase2)
        m["primaryNGamesPhaseOneEndpoint"] = len(phase1)
        m["primaryNGameWindows"] = int(len(gs))

    # H1 and H2: the equal-weight OLS contrasts, their Bayes factors and the
    # inverse-variance rerun
    h1 = est.row("primary/h1_h2", analysis="h1_h2", term="H1_sep_vs_mixed")
    h2 = est.row("primary/h1_h2", analysis="h1_h2", term="H2_social_vs_mixed")
    if h1 is not None:
        m["primaryNGamesHOneTwo"] = count(h1["n_games"])
    m.update(contrast_macros("primaryHOne", h1))
    m.update(contrast_macros("primaryHTwo", h2))
    if h1 is not None:
        m.update(bf_macro("primaryHOne", est.row("primary/bayes_factors", hypothesis="H1")))
        m.update(bf_macro("primaryHTwo", est.row("primary/bayes_factors", hypothesis="H2")))
    m.update(contrast_macros("primaryHOneWls", est.row("primary/h1_h2", analysis="h1_h2_wls", term="H1_sep_vs_mixed")))
    m.update(contrast_macros("primaryHTwoWls", est.row("primary/h1_h2", analysis="h1_h2_wls", term="H2_social_vs_mixed")))

    # H3a
    h3a = est.row("primary/h3a", analysis="h3a")
    if h3a is not None:
        m["primaryNGamesHThreeA"] = count(h3a["n_games"])
    m.update(contrast_macros("primaryHThreeA", h3a))
    if h3a is not None:
        m.update(bf_macro("primaryHThreeA", est.row("primary/bayes_factors", hypothesis="H3a")))

    # H3b: the rate and the alignment at block 3, reported separately
    m.update(contrast_macros("primaryHThreeB", est.row("primary/h3b", analysis="h3b_rate", measure="sbert")))
    m.update(contrast_macros("primaryHThreeBBlockThree", est.row("primary/h3b", analysis="h3b_block3", measure="sbert")))

    # H3c: the three description properties (social_first minus social_mixed)
    m.update(coef_macros("primaryHThreeCConcrete", est.row("primary/h3c", analysis="h3c_concreteness")))
    m.update(coef_macros("primaryHThreeCUnique", est.row("primary/h3c", analysis="h3c_uniqueness")))
    m.update(coef_macros("primaryHThreeCFreq", est.row("primary/h3c", analysis="h3c_word_frequency")))

    # H4a and H4b: odds-ratio contrasts with their Bayes factors
    h4a = est.row("primary/h4", analysis="h4a")
    m.update(contrast_macros("primaryHFourA", h4a))
    if h4a is not None:
        m.update(bf_macro("primaryHFourA", est.row("primary/bayes_factors", hypothesis="H4a")))
    h4b = est.row("primary/h4", analysis="h4b")
    m.update(contrast_macros("primaryHFourB", h4b))
    if h4b is not None:
        m.update(bf_macro("primaryHFourB", est.row("primary/bayes_factors", hypothesis="H4b")))

    # The signal-detection components of H4a, pooled over the social conditions
    sc = est.table("primary/h4_social_components")
    if not sc.empty:
        tot = lambda col: float(sc[col].sum())  # noqa: E731
        m["primaryNSocialOpportunities"] = fmt_count(tot("opportunities"))
        m["primaryNSocialInGroup"] = fmt_count(tot("in_group_opportunities"))
        m["primaryNSocialOutGroup"] = fmt_count(tot("out_group_opportunities"))
        m["primarySocialOnTimeRate"] = fmt_stat(tot("on_time") / tot("scored"))
        m["primarySocialHitRate"] = fmt_stat(
            float((sc["hit_rate"] * sc["in_group_answered"]).sum()) / tot("in_group_answered")
        )
        m["primarySocialFalseAlarmRate"] = fmt_stat(
            float((sc["false_alarm_rate"] * sc["out_group_answered"]).sum()) / tot("out_group_answered")
        )

    # The Jaccard robustness reruns
    m.update(contrast_macros("primaryHOneJaccard", est.row("primary/h1_h2", analysis="h1_h2_jaccard", term="H1_sep_vs_mixed")))
    m.update(contrast_macros("primaryHTwoJaccard", est.row("primary/h1_h2", analysis="h1_h2_jaccard", term="H2_social_vs_mixed")))
    m.update(contrast_macros("primaryHThreeAJaccard", est.row("primary/h3a", analysis="h3a_jaccard")))
    m.update(contrast_macros("primaryHThreeBJaccard", est.row("primary/h3b", analysis="h3b_rate", measure="jaccard")))
    m.update(contrast_macros("primaryHThreeBBlockThreeJaccard", est.row("primary/h3b", analysis="h3b_block3", measure="jaccard")))

    # The sensitivity reruns of the Phase 2 analyses: nothing is written for a
    # restriction that excluded no games, whose results are the primary ones.
    rr = est.table("primary/robustness")
    for restriction, suffix in (("complete_games", "Complete"), ("three_groups", "ThreeGroups")):
        h1r = pick_row(rr, restriction=restriction, analysis="h1_h2", term="H1_sep_vs_mixed")
        if h1r is not None:
            m[f"primaryNGames{suffix}"] = count(h1r["n_games"])
        m.update(contrast_macros(f"primaryHOne{suffix}", h1r))
        m.update(contrast_macros(f"primaryHTwo{suffix}", pick_row(rr, restriction=restriction, analysis="h1_h2", term="H2_social_vs_mixed")))
        m.update(contrast_macros(f"primaryHFourA{suffix}", pick_row(rr, restriction=restriction, analysis="h4a")))
        m.update(contrast_macros(f"primaryHFourB{suffix}", pick_row(rr, restriction=restriction, analysis="h4b")))
    m.update(contrast_macros("primaryHOneActiveGroups", pick_row(rr, restriction="active_groups", analysis="h1_h2", term="H1_sep_vs_mixed")))
    m.update(contrast_macros("primaryHTwoActiveGroups", pick_row(rr, restriction="active_groups", analysis="h1_h2", term="H2_social_vs_mixed")))

    # Per-game fits at a variance boundary
    if not gs.empty and "singular" in gs.columns:
        m["primaryNGameWindowsSingular"] = int((is_true(gs["singular"]) & is_true(gs["estimable"])).sum())
    return m


def secondary_macros(est: Estimates) -> dict:
    m: dict = {}
    m.update(contrast_macros("secondarySemanticSepVsMixed", est.row("secondary/semantic_change", term="sep_gt_mixed")))
    m.update(contrast_macros("secondarySemanticSocialVsMixed", est.row("secondary/semantic_change", term="social_gt_mixed")))

    ordering = est.table("secondary/phase2_accuracy")
    prefixes = {
        "sep_gt_mixed": "secondaryAccSepVsMixed",
        "mixed_gt_social": "secondaryAccMixedVsSocial",
        "social_gt_socialfirst": "secondaryAccSocialVsSocialFirst",
    }
    if not ordering.empty:
        for _, r in ordering[ordering["analysis"] == "phase2_accuracy_ordering"].iterrows():
            if r["term"] in prefixes:
                m.update(contrast_macros(prefixes[r["term"]], r))
    m.update(coef_macros("secondaryAccBlock", pick_row(ordering, analysis="phase2_accuracy", term="blockNum_c")))

    adv = est.row("secondary/ingroup_advantage", analysis="ingroup_advantage")
    if adv is not None:
        m["secondaryIngroupListeners"] = fmt_count(adv["n_obs"])
        m["secondaryIngroupGames"] = fmt_count(adv["n_games"])
    m.update(coef_macros("secondaryIngroupAdv", adv))
    m.update(contrast_macros("secondaryIngroupAmplify", est.row("secondary/ingroup_advantage", analysis="ingroup_advantage_amplification")))
    m.update(coef_macros("secondaryIngroupAdvMinFive", est.row("secondary/ingroup_advantage", analysis="ingroup_advantage_min_five")))

    sa = est.row("secondary/specificity_vs_social_accuracy", analysis="specificity_vs_social_accuracy")
    if sa is not None:
        m.update({
            "secondaryGsSocialEst": fmt_stat(sa["estimate"]),
            "secondaryGsSocialLo": fmt_stat(sa["lower"]),
            "secondaryGsSocialHi": fmt_stat(sa["upper"]),
            "secondaryGsSocialP": fmt_pval(sa["p_value"]),
            "secondaryGsSocialNGames": count(sa["n_games"]),
        })
    sa_wls = est.row("secondary/specificity_vs_social_accuracy", analysis="specificity_vs_social_accuracy_wls")
    if sa_wls is not None:
        m.update({
            "secondaryGsSocialWlsEst": fmt_stat(sa_wls["estimate"]),
            "secondaryGsSocialWlsLo": fmt_stat(sa_wls["lower"]),
            "secondaryGsSocialWlsHi": fmt_stat(sa_wls["upper"]),
            "secondaryGsSocialWlsP": fmt_pval(sa_wls["p_value"]),
        })

    trend = est.row("secondary/social_accuracy_trend", analysis="social_accuracy_trend")
    m.update(coef_macros("secondarySocialAccBlock", trend))
    if trend is not None:
        m["secondarySocialAccMean"] = fmt_stat(trend["outcome_mean"])
        m["secondarySocialAccN"] = fmt_count(trend["n_scored"])

    m.update(coef_macros("secondaryLengthBlock", est.row("secondary/phase2_length", analysis="phase2_length", term="blockNum_c")))

    # The share of speaker-tangram observations whose Phase 2 description
    # moved away from the Phase 1 one, by condition
    switched = est.table("secondary/semantic_change_switched")
    if not switched.empty:
        for _, r in switched.iterrows():
            m[f"secondarySwitched{condition_macro_name(r['condition'])}"] = fmt_stat(r["prop_switched"])
    return m


FAMILIES = {"checks": checks_macros, "primary": primary_macros, "secondary": secondary_macros}


def main():
    parser = argparse.ArgumentParser(description="Write the inferential macros of one dataset from its estimates tables")
    add_dataset_argument(parser)
    args = parser.parse_args()
    dirs = dataset_dirs(args.dataset)
    if not dirs.estimates.is_dir():
        raise SystemExit(f"Error: no estimates for dataset '{dirs.name}' at {dirs.estimates}; run `make models` first")
    if dirs.name != "full":
        print(f"Dataset '{dirs.name}' is not the full sample: the macros written to {dirs.stats} are not results.")
    est = Estimates(dirs.estimates)
    for family, build in FAMILIES.items():
        write_stats_tex(build(est), stats_file(family, dirs), source=SOURCE, dataset=dirs.name)
    duplicates = check_unique_names(dirs.stats)
    if duplicates:
        raise SystemExit(f"Error: macro names defined in more than one stats file: {duplicates}")


if __name__ == "__main__":
    main()
