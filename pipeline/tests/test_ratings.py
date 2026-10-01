import numpy as np
import pytest
from conftest import run

from ags import datasets, ratings


def synthetic(off, deff, mu=0.02, home=0.03, seasons=(2023,), weeks=range(1, 9)):
    """Round-robin-ish games with exact (noise-free) EPA from known parameters."""
    teams = [f"T{i}" for i in range(len(off))]
    rows = {k: [] for k in ("season", "week", "off", "opp", "home", "epa", "plays")}
    for s in seasons:
        for w in weeks:
            for i in range(len(teams)):
                j = (i + w) % len(teams)
                if i == j:
                    continue
                h = 1 if (i + w) % 2 else -1
                rows["season"].append(s)
                rows["week"].append(w)
                rows["off"].append(i)
                rows["opp"].append(j)
                rows["home"].append(h)
                rows["epa"].append(mu + off[i] + deff[j] + home * h)
                rows["plays"].append(60)
    season = np.array(rows["season"])
    week = np.array(rows["week"])
    return ratings.GameRows(
        t=ratings.time_index(season, week),
        season=season,
        week=week,
        off=np.array(rows["off"]),
        opp=np.array(rows["opp"]),
        home=np.array(rows["home"], dtype=float),
        epa=np.array(rows["epa"]),
        plays=np.array(rows["plays"], dtype=float),
        teams=teams,
    )


OFF = np.array([0.10, 0.05, 0.0, -0.05, -0.10])
DEF = np.array([-0.08, 0.02, 0.04, 0.0, 0.02])


def test_fit_recovers_parameters_up_to_centering():
    rows = synthetic(OFF, DEF)
    f = ratings.fit(rows, np.ones(len(rows.epa), bool), rows.plays, lam=1e-6)
    # Team effects are identified only relative to each other; compare centered values.
    assert f.off - f.off.mean() == pytest.approx(OFF - OFF.mean(), abs=1e-6)
    assert f.deff - f.deff.mean() == pytest.approx(DEF - DEF.mean(), abs=1e-6)
    assert f.home == pytest.approx(0.03, abs=1e-6)


def test_ridge_shrinks_toward_average():
    rows = synthetic(OFF, DEF)
    loose = ratings.fit(rows, np.ones(len(rows.epa), bool), rows.plays, lam=1)
    tight = ratings.fit(rows, np.ones(len(rows.epa), bool), rows.plays, lam=1e5)
    assert np.abs(tight.net).max() < np.abs(loose.net).max() / 5


def test_walk_forward_never_sees_the_game_it_predicts():
    rows = synthetic(OFF, DEF)
    games = [{"season": 2023, "week": 5, "home": "T0", "away": "T4"}]
    before = ratings.walk_forward(rows, games, lam=100, half_life=8)
    # Corrupt week 5 and later: a look-ahead model would change its prediction.
    tampered = rows.epa.copy()
    tampered[rows.week >= 5] += 5.0
    rows2 = ratings.GameRows(**{**rows.__dict__, "epa": tampered})
    after = ratings.walk_forward(rows2, games, lam=100, half_life=8)
    assert before == pytest.approx(after)
    assert before[0] > 0  # T0 is the best team, T4 the worst


def test_win_prob_is_symmetric_and_monotone():
    assert ratings.win_prob(0, 13.5) == pytest.approx(0.5)
    assert ratings.win_prob(7, 13.5) == pytest.approx(1 - ratings.win_prob(-7, 13.5))
    assert ratings.win_prob(3, 13.5) < ratings.win_prob(7, 13.5) < 1


def test_calibrate_recovers_exact_linear_map():
    x = np.array([0.0, 0.1, -0.2, 0.05, 0.3])
    home = np.array([1.0, 1.0, 0.0, 1.0, 0.0])
    margin = 200 * x + 1.5 * home
    b, sigma = ratings.calibrate(np.column_stack([x, home]), margin)
    assert b == pytest.approx([200, 1.5])
    assert sigma == pytest.approx(0, abs=1e-9)


def test_evaluate_counts_ats_and_pushes():
    pred = np.array([7.0, -3.0, 4.0, 10.0])
    vegas = np.array([3.0, -1.0, 4.0, 3.0])
    result = np.array([10.0, 0.0, 7.0, 3.0])  # game 3: model = line (no pick); game 4: push
    out = ratings.evaluate(pred, vegas, result)
    assert out["games"] == 4
    assert (out["ats_w"], out["ats_l"]) == (1, 1)
    assert (out["edge3_w"], out["edge3_l"]) == (1, 0)
    assert out["model_mae"] == pytest.approx((3 + 3 + 3 + 7) / 4)
    assert out["vegas_mae"] == pytest.approx((7 + 1 + 3 + 0) / 4)


def test_team_splits_rank_and_defensive_score_margin(make_pbp):
    con = make_pbp(
        [
            {"epa": 1.0, "score_differential": 10.0},
            {"posteam": "BBB", "defteam": "AAA", "epa": -0.5, "score_differential": -10.0},
            run(epa=0.2, score_differential=0.0),
        ]
    )
    rows = datasets.team_splits(con)
    aaa_def = [
        r for r in rows if r["team"] == "AAA" and r["side"] == "def" and r["split"] == "Score"
    ]
    # BBB's offense trailed by 10, so AAA's defense was up 10.
    assert [r["bucket"] for r in aaa_def] == ["Up 9+"]
    aaa_off = {
        r["bucket"]: r
        for r in rows
        if r["team"] == "AAA" and r["side"] == "off" and r["split"] == "Score"
    }
    assert aaa_off["Up 9+"]["epa"] == pytest.approx(1.0)
    assert aaa_off["Up 9+"]["rank"] == 1
