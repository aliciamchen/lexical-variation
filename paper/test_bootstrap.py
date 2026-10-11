"""Tests for the game-level percentile bootstrap (paper/bootstrap.py).

    uv run pytest paper/test_bootstrap.py -v
"""

import numpy as np
import pandas as pd
import pytest

from paper.bootstrap import bootstrap_mean


def _frame(game_means, per_game=10, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for g, m in enumerate(game_means):
        for v in rng.normal(m, 0.01, size=per_game):
            rows.append({"gameId": f"g{g}", "y": v})
    return pd.DataFrame(rows)


def test_the_point_estimate_is_the_mean_over_rows_not_over_games():
    df = pd.DataFrame({"gameId": ["a"] * 3 + ["b"], "y": [1.0, 1.0, 1.0, 0.0]})
    est = bootstrap_mean(df, "y")
    assert est.mean == pytest.approx(0.75)  # 3 of 4 rows, not the mean of 1 and 0
    assert est.n_games == 2 and est.n_obs == 4


def test_the_interval_brackets_the_mean_and_reproduces_with_the_seed():
    df = _frame([0.2, 0.4, 0.6, 0.8, 1.0])
    a = bootstrap_mean(df, "y")
    b = bootstrap_mean(df, "y")
    assert a == b
    assert a.lower <= a.mean <= a.upper
    assert a.lower < a.upper
    assert bootstrap_mean(df, "y", seed=7) != a


def test_variation_within_a_game_does_not_widen_the_interval():
    # One game whose rows vary a lot: every draw returns the same rows, so the
    # interval is the mean itself. The bootstrap resamples games, not rows.
    df = pd.DataFrame({"gameId": "only", "y": [0.0, 1.0, 0.0, 1.0, 0.5]})
    est = bootstrap_mean(df, "y")
    assert est.lower == est.upper == est.mean == pytest.approx(0.5)


def test_variation_between_games_widens_the_interval():
    narrow = bootstrap_mean(_frame([0.5, 0.5, 0.5, 0.5]), "y")
    wide = bootstrap_mean(_frame([0.1, 0.4, 0.6, 0.9]), "y")
    assert (wide.upper - wide.lower) > 5 * (narrow.upper - narrow.lower)


def test_missing_values_are_dropped_and_an_empty_column_is_an_error():
    df = pd.DataFrame({"gameId": ["a", "a", "b"], "y": [1.0, np.nan, 3.0]})
    est = bootstrap_mean(df, "y")
    assert est.n_obs == 2 and est.mean == pytest.approx(2.0)
    with pytest.raises(ValueError):
        bootstrap_mean(pd.DataFrame({"gameId": ["a"], "y": [np.nan]}), "y")
