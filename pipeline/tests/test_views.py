from conftest import run


def test_plays_view_keeps_only_regular_season_scrimmage_plays(make_pbp):
    con = make_pbp(
        [
            {"epa": 1.0},
            run(epa=0.5),
            {"play_type": "no_play", "epa": 3.0},
            {"play_type": "qb_kneel", "pass": 0.0, "epa": -1.0},
            {"play_type": "qb_spike", "pass": 0.0, "epa": -1.0},
            {"play_type": "punt", "pass": 0.0, "epa": 2.0},
            {"season_type": "POST", "epa": 9.0},
            {"epa": None},
        ]
    )
    assert con.execute("select count(*), sum(epa) from plays").fetchone() == (2, 1.5)


def test_garbage_time_band_is_inclusive(make_pbp):
    con = make_pbp([{"wp": 0.10}, {"wp": 0.90}, {"wp": 0.09}, {"wp": 0.91}])
    scoped = dict(con.execute("select scope, count(*) from scoped_plays group by 1").fetchall())
    assert scoped == {"all": 4, "no_garbage": 2}


def test_explosive_thresholds_differ_for_pass_and_rush(make_pbp):
    con = make_pbp(
        [
            {"yards_gained": 20.0},
            {"yards_gained": 19.0},
            run(yards_gained=10.0),
            run(yards_gained=9.0),
        ]
    )
    assert con.execute("select sum(explosive) from plays").fetchone()[0] == 2
