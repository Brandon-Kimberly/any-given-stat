import math

import numpy as np
import pytest

from ags import market


def frame(vegas, result, **cols):
    n = len(vegas)
    z = np.zeros(n)
    base = dict(
        season=np.full(n, 2022),
        week=np.ones(n),
        home=[""] * n,
        away=[""] * n,
        game_id=[str(i) for i in range(n)],
        vegas=np.array(vegas, float),
        result=np.array(result, float),
        home_ind=np.ones(n),
        epa_margin=z.copy(),
        qb_adj=z.copy(),
        rest_diff=z.copy(),
        div=z.copy(),
    )
    return market.GameFrame(**(base | cols))


def test_binomial_p_value_exact():
    assert market.binom_p_value(10, 10, 0.5) == pytest.approx(1 / 1024)
    assert market.binom_p_value(0, 10, 0.5) == pytest.approx(1.0)
    # P(X >= 6), n = 10, p = 0.5 = 386 / 1024
    assert market.binom_p_value(6, 10, 0.5) == pytest.approx(386 / 1024)


def test_score_threshold_and_pushes():
    fr = frame(vegas=[3, 3, 3, 3], result=[10, 0, 3, 7])
    pred = np.array([6.0, 5.0, 7.0, 3.5])
    all_bets = market.score(pred, fr, np.ones(4, bool), threshold=0)
    # Game 3 lands on the number (push): no bet. Games 1, 4 win, game 2 loses.
    assert (all_bets["bets"], all_bets["wins"]) == (3, 2)
    big = market.score(pred, fr, np.ones(4, bool), threshold=2.5)
    assert (big["bets"], big["wins"]) == (1, 1)  # only game 1 has |pred - line| >= 2.5
    assert big["vegas_mae"] == pytest.approx((7 + 3 + 0 + 4) / 4)


def test_choose_requires_enough_validation_bets():
    rows = [
        {"variant": "a", "threshold": 0, "val_bets": 500, "val_win_rate": 0.51},
        {"variant": "b", "threshold": 3, "val_bets": 40, "val_win_rate": 0.70},
        {"variant": "c", "threshold": 1, "val_bets": 150, "val_win_rate": 0.53},
    ]
    assert market.choose(rows)["variant"] == "c"
    assert market.choose(rows[1:2]) is None


def test_selection_never_scores_test_seasons():
    n = 40
    rng = np.random.default_rng(0)
    seasons = np.repeat([2018, 2022, 2024, 2025], n // 4)
    v = rng.normal(0, 6, n)
    fr = frame(
        vegas=v, result=v + rng.normal(0, 13, n), season=seasons, epa_margin=rng.normal(0, 0.05, n)
    )
    rows = market.run_selection(fr)
    assert rows and all(not k.startswith("test") for r in rows for k in r)
    # Scores only see validation games (2022 here); test seasons stay sealed.
    assert {r["val_games"] for r in rows} == {n // 4}
    assert all(math.isfinite(r["fit_mae"]) for r in rows)
