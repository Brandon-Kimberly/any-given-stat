import numpy as np
import pytest

from ags import strength
from ags.ratings import time_index


def _rows(games):
    teams = ["A", "B", "C"]
    idx = {t: i for i, t in enumerate(teams)}
    season = np.array([g[0] for g in games])
    week = np.array([g[1] for g in games])
    return strength.MovRows(
        t=time_index(season, week),
        season=season,
        home=np.array([idx[g[2]] for g in games]),
        away=np.array([idx[g[3]] for g in games]),
        home_ind=np.array([1.0 for _ in games]),
        margin=np.array([float(g[4]) for g in games]),
        teams=teams,
    )


def test_fit_mov_orders_teams_and_ignores_future_games():
    # A beats B and C by 10; B beats C by 10. Each pairing played home and away.
    g = [
        (2020, 1, "A", "B", 10), (2020, 2, "B", "A", -10),
        (2020, 3, "A", "C", 10), (2020, 4, "C", "A", -10),
        (2020, 5, "B", "C", 10), (2020, 6, "C", "B", -10),
        (2020, 9, "C", "A", 50),  # after t_now: must be ignored
    ]  # fmt: skip
    rows = _rows(g)
    s = strength.fit_mov(rows, int(time_index(2020, 7)), lam=0.01, half_life=1e9)
    assert s[0] > s[1] > s[2]
    assert s.sum() == pytest.approx(0, abs=1e-9)
    # Least squares with A-B = A-C = B-C = 10 (inconsistent): A-B = 20/3, A-C = 40/3.
    assert s[0] - s[1] == pytest.approx(20 / 3, abs=0.05)
    assert s[0] - s[2] == pytest.approx(40 / 3, abs=0.05)


def test_ridge_shrinks_toward_zero():
    rows = _rows([(2020, 1, "A", "B", 20)])
    weak = strength.fit_mov(rows, int(time_index(2020, 2)), lam=0.01, half_life=1e9)
    strong = strength.fit_mov(rows, int(time_index(2020, 2)), lam=100, half_life=1e9)
    assert abs(strong[0] - strong[1]) < abs(weak[0] - weak[1])


def test_walk_forward_uses_only_earlier_weeks():
    rows = _rows([(2020, 1, "A", "B", 14), (2020, 3, "A", "B", -30)])
    games = [{"season": 2020, "week": 2, "home": "A", "away": "B"}]
    x = strength.mov_walk_forward(rows, games, lam=1.0, half_life=1e9)
    assert x[0] > 0  # only the week-1 win is visible
