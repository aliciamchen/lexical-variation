"""
The descriptive statistics the article quotes, written as LaTeX macros.

Reads the processed tables, the measures and the per-game group-specificity
estimates models/primary/group_specificity.R wrote, computes the descriptive
summaries (counts, attrition, endpoint means, survey responses) and writes
them as macros to results/<dataset>/stats/overview.tex, exploratory.tex and
survey.tex. Nothing here fits a model; report/inferential.py writes the
inferential files (checks, primary, secondary) from the estimates tables.

Usage:
    uv run python -m report.descriptives --dataset full

Tests: report/test_descriptives.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from preprocessing.dataset_paths import (
    FILTERED_UTTERANCES_FILE,
    add_dataset_argument,
    dataset_dirs,
    filtered_utterances_status,
    stale_filtered_message,
)
from report.bootstrap import bootstrap_mean
from report.plot_style import CONDITION_ORDER
from preprocessing.preprocessing import (
    PARTICIPANT_EXCLUSIONS_FILE,
    TECHNICAL_EXCLUSIONS_FILE,
    read_participant_exclusions,
    read_technical_exclusions,
)
from report.stats_tex import condition_macro_name, fmt_count, fmt_stat, stats_file, write_stats_tex

SOURCE = "report/descriptives.py"

# ── Attrition definitions ────────────────────────────────────
# The server's exit reasons (EXIT_REASONS in experiment/shared/constants.js)
# and the report category each falls in. A removal is through no fault of the
# participant when their group fell apart, too few groups remained for the
# game to go on, or the batch was stopped; those players are compensated for
# their time and reported apart from the players removed for their own
# inactivity or their group's low accuracy.
REMOVAL_REASONS = {
    "player timeout": "idle",
    "low accuracy": "low accuracy",
    "group disbanded": "group disbanded",
    "insufficient groups": "insufficient groups",
    "insufficient groups after accuracy check": "insufficient groups",
    "game terminated": "game terminated",
}
NO_FAULT_REASONS = {"group disbanded", "insufficient groups", "game terminated"}
MIN_GROUP_SIZE = 2  # the server removes a group's last member once it falls below this


def _true(series: pd.Series) -> pd.Series:
    return series.map(lambda v: v in (True, "True", "true", "TRUE")).astype(bool)


def in_conditions(df: pd.DataFrame) -> pd.DataFrame:
    """Rows of the four conditions (test games have none)."""
    return df[df["condition"].isin(CONDITION_ORDER)]


def utterances_file(tables_dir: Path) -> str:
    """The utterance file the analyses read: the filtered one when current, as config.R chooses."""
    status, detail = filtered_utterances_status(tables_dir)
    if status == "current":
        return FILTERED_UTTERANCES_FILE
    if status == "absent":
        return "speaker_utterances.csv"
    raise SystemExit(f"Error: {stale_filtered_message(status, detail)}")


def load_tables(dirs) -> dict:
    """Every table the descriptives read, as the R model scripts read them."""
    inputs, t, measures, estimates = dirs.data, dirs.tables, dirs.measures, dirs.estimates
    gs_path = estimates / "primary" / "group_specificity.csv"
    tables = {
        "games": pd.read_csv(t / "games.csv"),
        "players": pd.read_csv(t / "players.csv", low_memory=False),
        "trials": pd.read_csv(t / "trials.csv", low_memory=False),
        "messages": pd.read_csv(t / "messages.csv", low_memory=False),
        "speaker_utts": pd.read_csv(t / utterances_file(t)),
        "social_guesses": pd.read_csv(t / "social_guesses.csv", low_memory=False),
        "dropouts": pd.read_csv(t / "dropouts.csv") if (t / "dropouts.csv").exists() else pd.DataFrame(),
        "participant_exclusions": read_participant_exclusions(inputs / PARTICIPANT_EXCLUSIONS_FILE),
        "technical_exclusions": read_technical_exclusions(inputs / TECHNICAL_EXCLUSIONS_FILE),
        "adjacent_sim": pd.read_csv(measures / "adjacent_similarities.csv")
        if (measures / "adjacent_similarities.csv").exists() else pd.DataFrame(),
        "phase_change": pd.read_csv(measures / "phase_change_similarities.csv")
        if (measures / "phase_change_similarities.csv").exists() else pd.DataFrame(),
        "gs_by_game": pd.read_csv(gs_path) if gs_path.exists() else pd.DataFrame(),
    }
    return tables


# ── Attrition ────────────────────────────────────────────────


def player_attrition(players: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One row per player of a real game: condition, removed, reason, no_fault.

    A player was removed when `isActive` is false; the reason is the report
    category of their exit reason ("other" when the server's reason is not
    one of the known ones) and "completed" for everyone else.
    """
    real = games[games["condition"].notna()][["gameId", "condition"]]
    out = players.merge(real, on="gameId", how="inner")
    out["removed"] = ~_true(out["isActive"])
    reason = out["exitReason"].map(REMOVAL_REASONS)
    out["reason"] = np.where(out["removed"], reason.where(reason.notna(), "other"), "completed")
    out["no_fault"] = out["removed"] & out["reason"].isin(NO_FAULT_REASONS)
    return out[["gameId", "playerId", "condition", "originalGroup", "removed", "reason", "no_fault"]]


def group_attrition(players: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One row per original group of a real game, with whether it was lost (fewer than two active members at the end)."""
    pa = player_attrition(players, games)
    out = (
        pa.groupby(["gameId", "condition", "originalGroup"], dropna=False)
        .agg(players=("removed", "size"), active_at_end=("removed", lambda r: int((~r).sum())), removed=("removed", "sum"))
        .reset_index()
    )
    out["lost"] = out["active_at_end"] < MIN_GROUP_SIZE
    return out


def game_status(players: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One row per real game: ran to completion (two or more groups reached the end) and complete nine-player."""
    pa = player_attrition(players, games)
    per_game = pa.groupby("gameId").agg(players=("removed", "size"), removed=("removed", "sum")).reset_index()
    out = games[games["condition"].notna()][["gameId", "condition", "activeGroups"]].merge(per_game, on="gameId", how="left")
    out["players"] = out["players"].fillna(0).astype(int)
    out["removed"] = out["removed"].fillna(0).astype(int)
    active = pd.to_numeric(out["activeGroups"], errors="coerce")
    out["ran_to_completion"] = active.notna() & (active >= 2)
    out["complete_nine"] = out["ran_to_completion"] & (out["players"] == 9) & (out["removed"] == 0)
    return out


def quiz_failures(dropouts: pd.DataFrame) -> int:
    if dropouts.empty or "exitReason" not in dropouts.columns:
        return 0
    return int((dropouts["exitReason"] == "quiz failed").sum())


# ── Descriptions ─────────────────────────────────────────────

DESCRIPTION_KEYS = ["gameId", "playerId", "phaseNum", "blockNum", "target"]


def description_coverage(trials: pd.DataFrame, speaker_utts: pd.DataFrame) -> tuple[int, int]:
    """Speaker trials of the four conditions without an analyzable description, and all speaker trials.

    A description is analyzable when the speaker's trial has a row in the
    utterance table: a speaker who said nothing, an excluded participant or a
    speaker whose messages were all classified non-referential has none.
    """
    speakers = in_conditions(trials[trials["role"] == "speaker"]).copy()
    described = speaker_utts[DESCRIPTION_KEYS].drop_duplicates().assign(has_description=True)
    for key in ("phaseNum", "blockNum"):
        speakers[key] = pd.to_numeric(speakers[key], errors="coerce")
        described[key] = pd.to_numeric(described[key], errors="coerce")
    merged = speakers.merge(described, on=DESCRIPTION_KEYS, how="left")
    without = int((~merged["has_description"].fillna(False).astype(bool)).sum())
    return without, len(merged)


# ── Macros ───────────────────────────────────────────────────


def overview_macros(t: dict) -> dict:
    games, players, trials = t["games"], t["players"], t["trials"]
    pa = player_attrition(players, games)
    ga = group_attrition(players, games)
    status = game_status(players, games)
    excluded_rows = in_conditions(trials)
    excluded_rows = excluded_rows[_true(excluded_rows["excluded"])] if "excluded" in trials.columns else excluded_rows.iloc[0:0]
    without, speaker_trials = description_coverage(trials, t["speaker_utts"])
    listeners = trials[trials["role"] == "listener"]
    return {
        "overviewNExcludedParticipants": len(t["participant_exclusions"]),
        "overviewNExcludedTrialRows": len(excluded_rows),
        "overviewNTechnicalExclusions": len(t["technical_exclusions"]),
        "overviewPropNoDescription": fmt_stat(without / speaker_trials, 3),
        "overviewNGames": int(games["condition"].notna().sum()),
        "overviewNPlayers": len(pa),
        "overviewNTrials": fmt_count(len(trials)),
        "overviewNMessages": fmt_count(len(t["messages"])),
        "overviewNSpeakerUtts": fmt_count(len(t["speaker_utts"])),
        "overviewNRemoved": int(pa["removed"].sum()),
        "overviewNRemovedNoFault": int(pa["no_fault"].sum()),
        "overviewNGroupsLost": int(ga["lost"].sum()),
        "overviewNGamesComplete": int(status["complete_nine"].sum()),
        "overviewNGamesRanToCompletion": int(status["ran_to_completion"].sum()),
        "overviewNDropouts": len(t["dropouts"]),
        "overviewNQuizFailed": quiz_failures(t["dropouts"]),
        "overviewNNoOpportunity": int((~_true(listeners["responseOpportunity"])).sum()),
    }


def endpoint_macros(prefix: str, df: pd.DataFrame, value: str, digits: int = 3) -> dict:
    """The mean of a measure in its first and last observed game block, with the two block numbers and the observation count.

    A measure that only starts once a pair of descriptions exists (adjacent
    similarity) is thereby reported from its own first block, not from block 1.
    """
    d = in_conditions(df).copy()
    d[value] = pd.to_numeric(d[value], errors="coerce")
    d["gameBlock"] = pd.to_numeric(d["gameBlock"], errors="coerce")
    d = d[np.isfinite(d[value]) & d["gameBlock"].notna()]
    if d.empty:
        return {}
    first, last = int(d["gameBlock"].min()), int(d["gameBlock"].max())
    return {
        f"{prefix}N": fmt_count(len(d)),
        f"{prefix}FirstBlock": first,
        f"{prefix}LastBlock": last,
        f"{prefix}First": fmt_stat(d.loc[d["gameBlock"] == first, value].mean(), digits),
        f"{prefix}Last": fmt_stat(d.loc[d["gameBlock"] == last, value].mean(), digits),
    }


def phase1_specificity_by_condition(gs_by_game: pd.DataFrame) -> pd.DataFrame:
    """Games, mean and SD of the estimable final Phase 1 group-specificity estimates, by condition."""
    if gs_by_game.empty:
        return pd.DataFrame(columns=["condition", "games", "mean", "sd"])
    gs = gs_by_game[(gs_by_game["window"] == "phase1_final") & _true(gs_by_game["estimable"])]
    gs = in_conditions(gs)
    out = (
        gs.groupby("condition")["coefficient"]
        .agg(games="size", mean="mean", sd=lambda s: s.std(ddof=1))
        .reset_index()
    )
    out["condition"] = pd.Categorical(out["condition"], CONDITION_ORDER, ordered=True)
    return out.sort_values("condition").reset_index(drop=True)


def phase1_final_words_by_condition(speaker_utts: pd.DataFrame) -> pd.DataFrame:
    """Words per description in each game's final three Phase 1 blocks, averaged within game first, by condition."""
    p1 = in_conditions(speaker_utts[pd.to_numeric(speaker_utts["phaseNum"]) == 1]).copy()
    p1["blockNum"] = pd.to_numeric(p1["blockNum"])
    last_three = p1[p1["blockNum"] >= p1.groupby("gameId")["blockNum"].transform("max") - 2]
    per_game = last_three.groupby(["condition", "gameId"])["uttLength"].mean().reset_index(name="words")
    out = per_game.groupby("condition")["words"].agg(games="size", mean_words="mean", sd="std").reset_index()
    out["condition"] = pd.Categorical(out["condition"], CONDITION_ORDER, ordered=True)
    return out.sort_values("condition").reset_index(drop=True)


def semantic_drift_macros(phase_change: pd.DataFrame) -> dict:
    """The baseline drift: how similar a refer_separated speaker's final Phase 2
    description of a tangram is to their final Phase 1 description, where no
    other group was ever heard, as a mean over speaker-tangram observations
    with a game-level bootstrap interval (ceiling 1). The secondary semantic-
    change model estimates the condition differences; this is the descriptive anchor."""
    if phase_change.empty or "simPhase1Phase2" not in phase_change:
        return {}
    drift = phase_change[phase_change["condition"] == "refer_separated"]
    if drift["simPhase1Phase2"].notna().sum() < 2:
        return {}
    est = bootstrap_mean(drift, "simPhase1Phase2")
    return {
        "exploratoryDriftMean": fmt_stat(est.mean),
        "exploratoryDriftLo": fmt_stat(est.lower),
        "exploratoryDriftHi": fmt_stat(est.upper),
        "exploratoryDriftGames": fmt_count(est.n_games),
    }


def exploratory_macros(t: dict) -> dict:
    trials, utts = t["trials"], t["speaker_utts"]
    listeners = trials[(trials["role"] == "listener") & pd.to_numeric(trials["correct"], errors="coerce").notna()]
    macros = {}
    macros.update(endpoint_macros("exploratoryLength", utts, "uttLength", digits=2))
    macros.update(endpoint_macros("exploratoryAccuracy", listeners, "correct"))
    if not t["adjacent_sim"].empty and "gameBlock" in t["adjacent_sim"].columns:
        macros.update(endpoint_macros("exploratorySimAdjacent", t["adjacent_sim"], "simAdjacent"))
    for _, row in phase1_specificity_by_condition(t["gs_by_game"]).iterrows():
        cond = condition_macro_name(str(row["condition"]))
        macros[f"exploratoryPhaseOneGs{cond}N"] = int(row["games"])
        macros[f"exploratoryPhaseOneGs{cond}Mean"] = fmt_stat(row["mean"])
        macros[f"exploratoryPhaseOneGs{cond}SD"] = fmt_stat(row["sd"])
    for _, row in phase1_final_words_by_condition(utts).iterrows():
        macros[f"exploratoryPhaseOneWords{condition_macro_name(str(row['condition']))}"] = fmt_stat(row["mean_words"], 2)
    macros.update(semantic_drift_macros(t["phase_change"]))
    return macros


# ── Exit survey ──────────────────────────────────────────────

NUMERIC_ITEMS = ["groupIdentification", "groupCloseness", "age"]
CATEGORICAL_ITEMS = ["gender", "education", "understood", "groupLanguage", "feltHuman"]


def exit_survey_responses(players: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One row per respondent (any survey field answered) in a real game, with the prefix removed, the condition and whether the player completed the game or was removed."""
    survey_cols = [c for c in players.columns if c.startswith("exitSurvey_")]
    if not survey_cols:
        return pd.DataFrame()
    real = games[games["condition"].notna()][["gameId", "condition"]]
    df = players.merge(real, on="gameId", how="inner")
    answered = df[survey_cols].notna() & (df[survey_cols].astype(str) != "")
    df = df[answered.any(axis=1)].copy()
    df = df.rename(columns={c: c[len("exitSurvey_"):] for c in survey_cols})
    df["respondent"] = np.where(_true(df["isActive"]), "completed", "removed")
    for item in NUMERIC_ITEMS:
        if item in df.columns:
            df[item] = pd.to_numeric(df[item], errors="coerce")
    for item in CATEGORICAL_ITEMS:
        if item in df.columns:
            df[item] = df[item].map(lambda v: v if pd.isna(v) else str(v).lower())
    return df


def has_field(survey: pd.DataFrame, field: str) -> bool:
    return field in survey.columns and survey[field].notna().any()


def felt_human_flags(survey: pd.DataFrame, level: str = "game") -> pd.DataFrame:
    """Games (or original groups) in which any respondent said they were not playing with humans."""
    keys = ["gameId", "condition"] if level == "game" else ["gameId", "condition", "originalGroup"]
    if not has_field(survey, "feltHuman"):
        return pd.DataFrame(columns=keys + ["said_no"])
    said_no = survey.assign(said_no=(survey["feltHuman"] == "no").astype(int)).groupby(keys)["said_no"].sum().reset_index()
    return said_no[said_no["said_no"] > 0]


def survey_macros(t: dict) -> dict:
    games, players = t["games"], t["players"]
    survey = exit_survey_responses(players, games)
    real_players = players[players["gameId"].isin(games.loc[games["condition"].notna(), "gameId"])]
    macros = {
        "surveyNRespondents": len(survey),
        "surveyNPlayers": len(real_players),
        "surveyNRemovedRespondents": int((survey["respondent"] == "removed").sum()) if not survey.empty else 0,
    }

    def item(prefix, field):
        if not has_field(survey, field):
            return {}
        v = survey[field].dropna()
        return {f"{prefix}N": len(v), f"{prefix}Mean": fmt_stat(v.mean(), 2), f"{prefix}SD": fmt_stat(v.std(ddof=1), 2)}

    def yes(prefix, field):
        if not has_field(survey, field):
            return {}
        v = survey[field].dropna()
        return {f"{prefix}N": len(v), f"{prefix}Yes": int((v == "yes").sum()), f"{prefix}PropYes": fmt_stat((v == "yes").mean())}

    macros.update(item("surveyIdentification", "groupIdentification"))
    macros.update(item("surveyCloseness", "groupCloseness"))
    macros.update(yes("surveyGroupLanguage", "groupLanguage"))
    macros.update(item("surveyAge", "age"))
    if has_field(survey, "feltHuman"):
        fh = survey[survey["feltHuman"].notna()]
        macros.update({
            "surveyFeltHumanN": len(fh),
            "surveyFeltHumanNo": int((fh["feltHuman"] == "no").sum()),
            "surveyFeltHumanPropNo": fmt_stat((fh["feltHuman"] == "no").mean()),
            "surveyNGamesFlagged": len(felt_human_flags(survey)),
            "surveyNGroupsFlagged": len(felt_human_flags(survey, level="group")),
            "surveyFeltHumanPropNoSeparated": fmt_stat((fh.loc[fh["condition"] == "refer_separated", "feltHuman"] == "no").mean()),
            "surveyFeltHumanPropNoMixed": fmt_stat((fh.loc[fh["condition"] != "refer_separated", "feltHuman"] == "no").mean()),
        })
    if has_field(survey, "understood"):
        u = survey["understood"].dropna()
        macros.update({"surveyUnderstoodN": len(u), "surveyUnderstoodYes": int((u == "yes").sum())})
    return macros


def main():
    parser = argparse.ArgumentParser(description="Write the article's descriptive macros for one dataset")
    add_dataset_argument(parser)
    args = parser.parse_args()
    dirs = dataset_dirs(args.dataset)
    if not (dirs.tables / "trials.csv").exists():
        raise SystemExit(f"Error: no processed data for dataset '{dirs.name}' at {dirs.tables}")
    if dirs.name != "full":
        print(f"Dataset '{dirs.name}' is not the full sample: the macros written to {dirs.stats} are not results.")
    t = load_tables(dirs)
    if t["gs_by_game"].empty:
        print(f"  note: {dirs.estimates / 'primary' / 'group_specificity.csv'} is missing; run "
              "`Rscript models/primary/group_specificity.R` (or `make models`) first for the "
              "Phase 1 group-specificity macros")
    write_stats_tex(overview_macros(t), stats_file("overview", dirs), source=SOURCE, dataset=dirs.name)
    write_stats_tex(exploratory_macros(t), stats_file("exploratory", dirs), source=SOURCE, dataset=dirs.name)
    write_stats_tex(survey_macros(t), stats_file("survey", dirs), source=SOURCE, dataset=dirs.name)


if __name__ == "__main__":
    main()
