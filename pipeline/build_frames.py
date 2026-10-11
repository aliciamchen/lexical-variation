"""
Build the model-input frames: the unit-of-analysis tables that the R models
fit and the Python descriptives summarize.

The processed tables hold one row per observation and the derived tables one
row per description or pair of descriptions. Several analyses work on an
aggregate of those, such as the mean within-group similarity of a group's
descriptions of one tangram in one block. Those aggregates are built here,
once, from the processed and derived tables, and written beside the derived
tables, so that R and Python read the same rows rather than each aggregating
its own version. Every frame keeps every phase and every condition; a model
restricts to the conditions it needs when it is fit.

Usage:
    uv run python -m pipeline.build_frames --dataset full

Writes into analysis/derived/<dataset>/:
    within_group_block_means.csv          mean SBERT similarity of a group's
                                          descriptions of a tangram, per block
    within_group_block_means_jaccard.csv  the same with content-word Jaccard
    final_phase_properties.csv            the H3c description properties of each
                                          speaker's final description of each
                                          tangram in each phase
    ingroup_advantage.csv                 per listener, Phase 2 accuracy with an
                                          in-group speaker minus with an out-group
                                          speaker

Tests: pipeline/test_build_frames.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.dataset_paths import add_dataset_argument, dataset_dirs

PROPERTY_KEYS = ["gameId", "playerId", "target", "blockNum", "phaseNum"]
UNIQUENESS_COLUMNS = ["uniqueness", "n_unique_words"]


def _condition_of(df: pd.DataFrame, games: pd.DataFrame) -> pd.Series:
    return df["gameId"].map(games.set_index("gameId")["condition"])


def _as_bool(series: pd.Series) -> pd.Series:
    """True/False/NA from a column that may hold booleans or their text."""
    truthy = {True, "True", "true", "TRUE", 1, 1.0}
    falsy = {False, "False", "false", "FALSE", 0, 0.0}
    values = [True if v in truthy else False if v in falsy else pd.NA for v in series]
    return pd.Series(values, index=series.index, dtype="boolean")


def within_group_block_means(block_pairwise: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One mean per original group, tangram and block over its within-group pairs.

    Overlapping speaker pairs of one group are not independent observations,
    so a group's pairs for a tangram in a block are averaged into one row.
    `group` is the game-qualified original group (gameId_A), `block` the
    1-indexed block within the phase and `n_pairs` how many pairs the mean
    covers. A pair with no similarity (a description with no content words
    under Jaccard) is left out of the mean, and a cell with no such pair has
    no row: nothing is filled from another block. Every within-group pair
    enters; the paired-groups start rule of the specificity trajectory does
    not apply to a group's own convergence.
    """
    df = block_pairwise[block_pairwise["sameGroup"] == 1].copy()
    df["similarity"] = pd.to_numeric(df["similarity"], errors="coerce")
    df = df[np.isfinite(df["similarity"])]
    df["condition"] = _condition_of(df, games)
    df["group"] = df["gameId"].astype(str) + "_" + df["group1"].astype(str)
    df["blockNum"] = pd.to_numeric(df["blockNum"]).astype(int)
    df["phaseNum"] = pd.to_numeric(df["phaseNum"]).astype(int)
    df["block"] = df["blockNum"] + 1
    out = (
        df.groupby(
            ["gameId", "condition", "group", "target", "phaseNum", "blockNum", "block"],
            dropna=False,
        )
        .agg(similarity=("similarity", "mean"), n_pairs=("similarity", "size"))
        .reset_index()
        .sort_values(["gameId", "group", "target", "phaseNum", "block"])
        .reset_index(drop=True)
    )
    return out


def final_phase_properties(
    desc_props: pd.DataFrame, lex_uniq: pd.DataFrame, games: pd.DataFrame
) -> pd.DataFrame:
    """The description properties of each speaker's final description of each tangram in each phase.

    Joins the lexical-uniqueness table onto the description-properties table
    on the description's key, keeps the last block in which the speaker
    described the tangram within the phase, and adds the condition, the
    game-qualified original group (`gameId A`, the group intercept of the H3c
    models) and the 1-indexed block.
    """
    uniq_cols = [c for c in UNIQUENESS_COLUMNS if c in lex_uniq.columns]
    merged = desc_props.merge(lex_uniq[PROPERTY_KEYS + uniq_cols], on=PROPERTY_KEYS, how="left")
    merged["condition"] = _condition_of(merged, games)
    merged["group"] = merged["gameId"].astype(str) + " " + merged["originalGroup"].astype(str)
    merged["blockNum"] = pd.to_numeric(merged["blockNum"]).astype(int)
    merged["phaseNum"] = pd.to_numeric(merged["phaseNum"]).astype(int)
    merged["block"] = merged["blockNum"] + 1
    last = merged.groupby(["gameId", "playerId", "target", "phaseNum"])["blockNum"].transform("max")
    out = merged[merged["blockNum"] == last]
    return out.sort_values(["gameId", "playerId", "target", "phaseNum"]).reset_index(drop=True)


def ingroup_advantage(trials: pd.DataFrame) -> pd.DataFrame:
    """Per listener, Phase 2 referential accuracy with an in-group speaker minus with an out-group speaker.

    The in-group status of the speaker varies within every listener, which is
    why the contrast is taken as a paired difference per listener rather than
    modeled at the trial level (see analysis/R/prepare.R). The frame has one
    row per listener who has both cells, with the two accuracies and the two
    cell sizes so coverage and a minimum-trials sensitivity check can be
    applied when the model is fit. Accuracy is the coded outcome `correct`
    over response opportunities; an observation with no outcome (excluded)
    does not count.
    """
    listeners = trials[(trials["role"] == "listener") & (pd.to_numeric(trials["phaseNum"]) == 2)].copy()
    listeners = listeners[_as_bool(listeners["responseOpportunity"]).fillna(False).astype(bool)]
    listeners["correct"] = pd.to_numeric(listeners["correct"], errors="coerce")
    listeners["in_group"] = _as_bool(listeners["inGroupSpeaker"])
    listeners = listeners[listeners["correct"].notna() & listeners["in_group"].notna()]
    listeners["cell"] = np.where(listeners["in_group"].astype(bool), "in", "out")
    cells = (
        listeners.groupby(["gameId", "condition", "playerId", "cell"], dropna=False)
        .agg(acc=("correct", "mean"), n=("correct", "size"))
        .reset_index()
    )
    wide = cells.pivot(index=["gameId", "condition", "playerId"], columns="cell", values=["acc", "n"])
    wide.columns = [f"{value}_{cell}" for value, cell in wide.columns]
    wide = wide.reset_index()
    for column in ("acc_in", "acc_out", "n_in", "n_out"):
        if column not in wide.columns:
            wide[column] = np.nan
    wide = wide[wide["acc_in"].notna() & wide["acc_out"].notna()].copy()
    wide["n_in"] = wide["n_in"].astype(int)
    wide["n_out"] = wide["n_out"].astype(int)
    wide["advantage"] = wide["acc_in"] - wide["acc_out"]
    return (
        wide[["gameId", "condition", "playerId", "acc_in", "acc_out", "n_in", "n_out", "advantage"]]
        .sort_values(["gameId", "playerId"])
        .reset_index(drop=True)
    )


def build_all(data_dir: Path, derived_dir: Path) -> dict[str, int]:
    """Build every frame from the tables in data_dir and derived_dir; returns row counts."""
    games = pd.read_csv(data_dir / "games.csv")
    trials = pd.read_csv(data_dir / "trials.csv", low_memory=False)
    desc_props = pd.read_csv(derived_dir / "description_properties.csv")
    lex_uniq = pd.read_csv(derived_dir / "lexical_uniqueness.csv")
    counts = {}

    for measure, suffix in (("block_pairwise_similarities.csv", ""), ("block_pairwise_similarities_jaccard.csv", "_jaccard")):
        path = derived_dir / measure
        if not path.exists():
            print(f"  {measure} not present; skipping within_group_block_means{suffix}.csv")
            continue
        frame = within_group_block_means(pd.read_csv(path), games)
        name = f"within_group_block_means{suffix}.csv"
        frame.to_csv(derived_dir / name, index=False)
        counts[name] = len(frame)

    frame = final_phase_properties(desc_props, lex_uniq, games)
    frame.to_csv(derived_dir / "final_phase_properties.csv", index=False)
    counts["final_phase_properties.csv"] = len(frame)

    frame = ingroup_advantage(trials)
    frame.to_csv(derived_dir / "ingroup_advantage.csv", index=False)
    counts["ingroup_advantage.csv"] = len(frame)
    return counts


def main():
    parser = argparse.ArgumentParser(description="Build the model-input frames of one dataset")
    add_dataset_argument(parser)
    args = parser.parse_args()
    dirs = dataset_dirs(args.dataset)
    if not (dirs.data / "trials.csv").exists():
        raise SystemExit(f"Error: no processed data for dataset '{dirs.name}' at {dirs.data}")
    if not (dirs.derived / "description_properties.csv").exists():
        raise SystemExit(f"Error: no derived tables for dataset '{dirs.name}' at {dirs.derived}")
    print(f"Building the model-input frames for dataset '{dirs.name}' into {dirs.derived}")
    for name, rows in build_all(dirs.data, dirs.derived).items():
        print(f"  {name}: {rows} rows")


if __name__ == "__main__":
    main()
