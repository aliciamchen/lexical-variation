"""Percentile bootstrap intervals over games.

The article's descriptive intervals and figure error bars resample games, not
observations: the observations within a game (speakers, tangrams, trials) are
not independent, and the game is the unit the conditions were assigned to.
A draw takes the games with replacement, pools the rows of the drawn games
and computes the statistic on the pool, so the point estimate is the
statistic over all rows and the interval reflects between-game variation.

    from report.bootstrap import bootstrap_mean

    est = bootstrap_mean(df, value="simPhase1Phase2", game="gameId")
    est.mean, est.lower, est.upper, est.n_games

Every call seeds its own generator, so the macros and figures reproduce run
to run; pass another `seed` for a sensitivity check.

Tests: report/test_bootstrap.py
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

N_BOOT = 2000
SEED = 20261011


@dataclass(frozen=True)
class BootstrapEstimate:
    mean: float
    lower: float
    upper: float
    n_games: int
    n_obs: int


def bootstrap_mean(
    df: pd.DataFrame,
    value: str,
    game: str = "gameId",
    n_boot: int = N_BOOT,
    level: float = 0.95,
    seed: int = SEED,
) -> BootstrapEstimate:
    """The mean of `value` over the rows of `df` with a percentile interval
    from resampling the games in `game` with replacement.

    Rows with a missing value are dropped first. With one game the interval
    is the mean itself, since every draw returns the same rows.
    """
    rows = df[[game, value]].dropna()
    if rows.empty:
        raise ValueError(f"no observations of {value!r} to bootstrap")
    values = rows[value].to_numpy(dtype=float)
    # Sum and count per game: a draw of games is then a draw of (sum, count)
    # pairs, and the pooled mean is the ratio of their totals.
    by_game = rows.groupby(game)[value].agg(["sum", "count"])
    sums = by_game["sum"].to_numpy(dtype=float)
    counts = by_game["count"].to_numpy(dtype=float)
    n_games = len(by_game)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n_games, size=(n_boot, n_games))
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    alpha = (1 - level) / 2
    lower, upper = np.quantile(means, [alpha, 1 - alpha])
    return BootstrapEstimate(
        mean=float(values.mean()),
        lower=float(lower),
        upper=float(upper),
        n_games=int(n_games),
        n_obs=int(len(values)),
    )
