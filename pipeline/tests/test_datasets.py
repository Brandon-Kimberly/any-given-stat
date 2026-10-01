import math

import pytest
from conftest import run

from ags import datasets
from ags.config import PYTHAG_EXPONENT


def _one(rows, **match):
    hits = [r for r in rows if all(r[k] == v for k, v in match.items())]
    assert len(hits) == 1, hits
    return hits[0]


def test_team_seasons_offense_defense_and_net(make_pbp):
    con = make_pbp(
        [
            {"epa": 1.0, "success": 1.0},
            run(epa=-0.5),
            {"posteam": "BBB", "defteam": "AAA", "epa": -0.2},
            {"posteam": "BBB", "defteam": "AAA", "epa": 0.0, "down": 3.0, "first_down": 1.0},
        ]
    )
    rows = datasets.team_seasons(con)
    aaa = _one(rows, scope="all", team="AAA")
    assert aaa["off_plays"] == 2
    assert aaa["off_epa_play"] == pytest.approx(0.25)
    assert aaa["off_pass_epa"] == pytest.approx(1.0)
    assert aaa["off_rush_epa"] == pytest.approx(-0.5)
    assert aaa["off_pass_rate"] == pytest.approx(0.5)
    assert aaa["def_epa_play"] == pytest.approx(-0.1)
    assert aaa["net_epa_play"] == pytest.approx(0.35)
    bbb = _one(rows, scope="all", team="BBB")
    assert bbb["off_third_down_rate"] == pytest.approx(1.0)


def test_red_zone_rate_counts_drives_not_plays(make_pbp):
    con = make_pbp(
        [
            # Drive 1 reaches the 15 and scores: one trip, one TD, three plays.
            {"fixed_drive": 1.0, "yardline_100": 40.0, "fixed_drive_result": "Touchdown"},
            {"fixed_drive": 1.0, "yardline_100": 15.0, "fixed_drive_result": "Touchdown"},
            {"fixed_drive": 1.0, "yardline_100": 5.0, "fixed_drive_result": "Touchdown"},
            # Drive 2 reaches the 20 and kicks a FG.
            {"fixed_drive": 2.0, "yardline_100": 20.0, "fixed_drive_result": "Field goal"},
            # Drive 3 never reaches the red zone.
            {"fixed_drive": 3.0, "yardline_100": 60.0, "fixed_drive_result": "Punt"},
            # team_seasons needs both sides of the ball for a team to appear.
            {"posteam": "BBB", "defteam": "AAA", "fixed_drive": 4.0},
        ]
    )
    aaa = _one(datasets.team_seasons(con), scope="all", team="AAA")
    assert aaa["off_drives"] == 3
    assert aaa["off_rz_trips"] == 2
    assert aaa["off_rz_td_rate"] == pytest.approx(0.5)
    assert aaa["off_points_per_drive"] == pytest.approx((7 + 3 + 0) / 3)


def test_luck_pythag_and_one_score(make_pbp):
    games = [  # (game_id, home_score, away_score) — AAA is always home
        ("g1", 24, 21),
        ("g2", 30, 10),
        ("g3", 17, 20),
        ("g4", 20, 20),
    ]
    con = make_pbp([{"game_id": g, "home_score": h, "away_score": a} for g, h, a in games])
    aaa = _one(datasets.luck(con), team="AAA")
    pf, pa = 24 + 30 + 17 + 20, 21 + 10 + 20 + 20
    expected = pf**PYTHAG_EXPONENT / (pf**PYTHAG_EXPONENT + pa**PYTHAG_EXPONENT) * 4
    assert aaa["wins"] == 2.5
    assert aaa["pythag_wins"] == pytest.approx(expected)
    assert aaa["wins_over_pythag"] == pytest.approx(2.5 - expected)
    assert aaa["one_score_games"] == 3
    assert aaa["one_score_wins"] == 1.5


def test_fumble_recovery_counts_both_sides(make_pbp):
    con = make_pbp(
        [
            {"fumble": 1.0, "fumble_recovery_1_team": "AAA"},  # AAA offense recovers own
            {"fumble": 1.0, "fumble_recovery_1_team": "BBB", "fumble_lost": 1.0},
            {
                "posteam": "BBB",
                "defteam": "AAA",
                "fumble": 1.0,
                "fumble_recovery_1_team": "AAA",
                "fumble_lost": 1.0,
            },
        ]
    )
    aaa = _one(datasets.luck(con), team="AAA")
    assert aaa["fumbles"] == 3
    assert aaa["fumble_recovery_rate"] == pytest.approx(2 / 3)
    assert aaa["turnover_margin"] == 0


def test_qb_ci_scrambles_and_designed_runs(make_pbp):
    qb_epas = [0.5, -0.5, 1.0, 0.0]
    rows = [{"qb_epa": e, "epa": e} for e in qb_epas]
    rows.append(
        {"play_type": "run", "qb_scramble": 1.0, "pass_attempt": 0.0, "qb_epa": 1.0, "epa": 1.0}
    )  # scramble counts as a dropback
    rows.append(run(rusher_id="QB1", rusher="A.Passer", epa=0.4))  # designed QB run
    qbs = datasets.quarterbacks(make_pbp(rows), min_dropbacks=1)
    qb = _one(qbs, scope="all", player_id="QB1")
    vals = qb_epas + [1.0]
    n = len(vals)
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
    assert qb["dropbacks"] == n
    assert qb["scramble_rate"] == pytest.approx(1 / n)
    assert qb["epa_db"] == pytest.approx(mean)
    assert qb["epa_db_lo"] == pytest.approx(mean - 1.96 * sd / math.sqrt(n))
    assert qb["epa_db_hi"] == pytest.approx(mean + 1.96 * sd / math.sqrt(n))
    assert qb["designed_runs"] == 1
    assert qb["total_epa"] == pytest.approx(sum(vals) + 0.4)


def test_receiver_shares_and_wopr(make_pbp):
    def tgt(rid, air):
        return {"receiver_id": rid, "receiver": rid, "air_yards": air}

    con = make_pbp(
        [
            tgt("WR1", 10.0),
            tgt("WR1", 20.0),
            tgt("WR1", 0.0),
            tgt("TE1", 10.0),
            {"sack": 1.0, "receiver_id": None},
        ]
    )
    wr = _one(datasets.receivers(con, min_targets=1), player_id="WR1")
    assert wr["targets"] == 3
    assert wr["target_share"] == pytest.approx(0.75)
    assert wr["air_yards_share"] == pytest.approx(0.75)
    assert wr["wopr"] == pytest.approx(1.5 * 0.75 + 0.7 * 0.75)


def test_rushers_exclude_scrambles(make_pbp):
    con = make_pbp(
        [
            run(yards_gained=12.0, epa=1.0),
            run(yards_gained=0.0, epa=-1.0),
            {"play_type": "run", "qb_scramble": 1.0, "rusher_id": "RB1", "pass_attempt": 0.0},
        ]
    )
    rb = _one(datasets.rushers(con, min_carries=1), player_id="RB1")
    assert rb["carries"] == 2
    assert rb["explosive_rate"] == pytest.approx(0.5)
    assert rb["stuff_rate"] == pytest.approx(0.5)


def test_stability_perfect_signal_and_spearman_brown(make_pbp):
    # Four teams with fixed, distinct EPA every week of two seasons: perfectly stable.
    rows = []
    for season in (2023, 2024):
        for week in range(1, 5):
            for i, team in enumerate(["T1", "T2", "T3", "T4"]):
                rows.append(
                    {
                        "season": season,
                        "week": week,
                        "posteam": team,
                        "defteam": "ZZZ",
                        "epa": i * 0.1,
                        "game_id": f"{season}_{week}_{team}",
                    }
                )
    out = datasets.stability(make_pbp(rows), [2023, 2024])
    m = {r["key"]: r for r in out["metrics"]}["off_epa"]
    assert m["split_half_r"] == pytest.approx(1.0)
    assert m["yoy_r"] == pytest.approx(1.0)
    assert m["split_half_pairs"] == 8
    assert m["yoy_pairs"] == 4
    assert m["full_season_reliability"] == pytest.approx(1.0)
    assert m["n_for_half_signal"] == pytest.approx(0.0)
    assert len(out["yoy_pairs"]["off_epa"]) == 4


def test_explorer_export_writes_available_columns(make_pbp, tmp_path):
    con = make_pbp([{"epa": 1.0}, run()])
    dest = tmp_path / "pbp.parquet"
    datasets.export_explorer_parquet(con, 2024, dest.as_posix())
    (n,) = con.execute(f"select count(*) from '{dest}'").fetchone()
    assert n == 2
