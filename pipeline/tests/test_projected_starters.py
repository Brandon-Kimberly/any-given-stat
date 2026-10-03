import csv

import duckdb
from conftest import make_con, run

from ags.db import SCHEDULE_COLUMNS, connect

COLS = [c.strip() for c in SCHEDULE_COLUMNS.split(",")]


def _schedule(tmp_path, rows):
    path = tmp_path / "games.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})
    return path


def _parquet(tmp_path, name, sql):
    path = tmp_path / name
    duckdb.connect().execute(f"copy ({sql}) to '{path.as_posix()}' (format parquet)")
    return path


def _game(gid, week, home, away, home_qb, result=""):
    return {
        "game_id": gid,
        "season": 2026,
        "game_type": "REG",
        "week": week,
        "home_team": home,
        "away_team": away,
        "result": result,
        "home_qb_id": home_qb[0],
        "home_qb_name": home_qb[1],
        "away_qb_id": "A1",
        "away_qb_name": "Away QB",
    }


def test_unplayed_games_start_the_depth_chart_qb1_unless_ruled_out(tmp_path):
    lock, darnold = ("L1", "Drew Lock"), ("D1", "Sam Darnold")
    schedule = _schedule(
        tmp_path,
        [
            _game("2026_03_X_SEA", 3, "SEA", "X", lock, result="2"),  # played: Lock started
            _game("2026_04_Y_SEA", 4, "SEA", "Y", lock),  # nflverse carries Lock forward
            _game("2026_05_Z_SEA", 5, "SEA", "Z", lock),
        ],
    )
    depth = _parquet(
        tmp_path,
        "depth.parquet",
        """
        select * from (values
            ('2026-09-20T00:00:00Z', 'SEA', 'Drew Lock', 'L1', 'QB', 1),
            ('2026-10-03T00:00:00Z', 'SEA', 'Sam Darnold', 'D1', 'QB', 1),
            ('2026-10-03T00:00:00Z', 'SEA', 'Drew Lock', 'L1', 'QB', 2)
        ) t(dt, team, player_name, gsis_id, pos_abb, pos_rank)
    """,
    )
    injuries = _parquet(
        tmp_path,
        "inj.parquet",
        """
        select 2026 as season, 'REG' as game_type, 'SEA' as team, 5 as week, 'D1' as gsis_id,
               'QB' as position, 'Sam Darnold' as full_name, 'Out' as report_status,
               null as practice_status
    """,
    )
    pbp = tmp_path / "pbp.parquet"
    make_con([run(season=2026, week=1)]).execute(f"copy pbp to '{pbp.as_posix()}' (format parquet)")
    con = connect([pbp], schedule, injury_files=[injuries], depth_chart=(2026, depth))
    got = {
        r[0]: (r[1], r[2])
        for r in con.execute(
            "select game_id, home_qb_id, home_qb_name from schedule order by week"
        ).fetchall()
    }
    assert got["2026_03_X_SEA"] == lock  # played games keep the actual starter
    assert got["2026_04_Y_SEA"] == darnold  # back from injury: depth-chart QB1 starts
    assert got["2026_05_Z_SEA"] == lock  # QB1 ruled Out that week: the last starter
    away = con.execute("select distinct away_qb_id from schedule").fetchall()
    assert away == [("A1",)]  # teams without a depth chart keep nflverse's listing


def test_when_qb1_and_the_last_starter_are_both_out_the_next_healthy_qb_starts(tmp_path):
    schedule = _schedule(tmp_path, [_game("2026_05_Z_CHI", 5, "CHI", "Z", ("K1", "Case Keenum"))])
    depth = _parquet(
        tmp_path,
        "depth.parquet",
        """
        select * from (values
            ('2026-10-03T00:00:00Z', 'CHI', 'Caleb Williams', 'W1', 'QB', 1),
            ('2026-10-03T00:00:00Z', 'CHI', 'Tyson Bagent', 'B1', 'QB', 2),
            ('2026-10-03T00:00:00Z', 'CHI', 'Case Keenum', 'K1', 'QB', 3)
        ) t(dt, team, player_name, gsis_id, pos_abb, pos_rank)
    """,
    )
    injuries = _parquet(
        tmp_path,
        "inj.parquet",
        """
        select 2026 as season, 'REG' as game_type, 'CHI' as team, 5 as week, gsis_id,
               'QB' as position, 'x' as full_name, 'Out' as report_status,
               null as practice_status
        from (values ('W1'), ('K1')) t(gsis_id)
    """,
    )
    pbp = tmp_path / "pbp.parquet"
    make_con([run(season=2026, week=1)]).execute(f"copy pbp to '{pbp.as_posix()}' (format parquet)")
    con = connect([pbp], schedule, injury_files=[injuries], depth_chart=(2026, depth))
    assert con.execute("select home_qb_name from schedule").fetchall() == [("Tyson Bagent",)]


def test_a_qb_out_on_the_latest_report_stays_out_until_a_newer_report(tmp_path):
    """Week 5's report isn't out yet; week 4 had QB1 out, so he is still out for week 5. A
    newer report that leaves him off (SEA's week 3 for Darnold) clears him."""
    schedule = _schedule(tmp_path, [_game("2026_05_Z_CHI", 5, "CHI", "Z", ("K1", "Case Keenum"))])
    depth = _parquet(
        tmp_path,
        "depth.parquet",
        """
        select * from (values
            ('2026-10-03T00:00:00Z', 'CHI', 'Caleb Williams', 'W1', 'QB', 1),
            ('2026-10-03T00:00:00Z', 'CHI', 'Case Keenum', 'K1', 'QB', 2)
        ) t(dt, team, player_name, gsis_id, pos_abb, pos_rank)
    """,
    )
    injuries = _parquet(
        tmp_path,
        "inj.parquet",
        """
        select 2026 as season, 'REG' as game_type, 'CHI' as team, 4 as week, 'W1' as gsis_id,
               'QB' as position, 'Caleb Williams' as full_name, 'Out' as report_status,
               null as practice_status
    """,
    )
    pbp = tmp_path / "pbp.parquet"
    make_con([run(season=2026, week=1)]).execute(f"copy pbp to '{pbp.as_posix()}' (format parquet)")
    con = connect([pbp], schedule, injury_files=[injuries], depth_chart=(2026, depth))
    assert con.execute("select home_qb_name from schedule").fetchall() == [("Case Keenum",)]


def test_unlisted_future_games_fall_back_to_the_last_actual_starter(tmp_path):
    keenum = ("K1", "Case Keenum")
    schedule = _schedule(
        tmp_path,
        [
            {**_game("2026_04_Y_CHI", 4, "CHI", "Y", keenum, result="3"), "gameday": "2026-10-04"},
            _game("2026_06_Z_CHI", 6, "CHI", "Z", ("", "")),  # nflverse lists nobody this far out
        ],
    )
    depth = _parquet(
        tmp_path,
        "depth.parquet",
        """
        select * from (values
            ('2026-10-03T00:00:00Z', 'CHI', 'Caleb Williams', 'W1', 'QB', 1),
            ('2026-10-03T00:00:00Z', 'CHI', 'Tyson Bagent', 'B1', 'QB', 2),
            ('2026-10-03T00:00:00Z', 'CHI', 'Case Keenum', 'K1', 'QB', 3)
        ) t(dt, team, player_name, gsis_id, pos_abb, pos_rank)
    """,
    )
    injuries = _parquet(
        tmp_path,
        "inj.parquet",
        """
        select 2026 as season, 'REG' as game_type, 'CHI' as team, 4 as week, 'W1' as gsis_id,
               'QB' as position, 'Caleb Williams' as full_name, 'Out' as report_status,
               null as practice_status
    """,
    )
    pbp = tmp_path / "pbp.parquet"
    make_con([run(season=2026, week=1)]).execute(f"copy pbp to '{pbp.as_posix()}' (format parquet)")
    con = connect([pbp], schedule, injury_files=[injuries], depth_chart=(2026, depth))
    got = con.execute("select home_qb_id, home_qb_name from schedule where week = 6").fetchall()
    assert got == [keenum]


def test_without_a_depth_chart_the_schedule_is_unchanged(tmp_path):
    schedule = _schedule(tmp_path, [_game("2026_04_Y_SEA", 4, "SEA", "Y", ("L1", "Drew Lock"))])
    pbp = tmp_path / "pbp.parquet"
    make_con([run(season=2026, week=1)]).execute(f"copy pbp to '{pbp.as_posix()}' (format parquet)")
    con = connect([pbp], schedule)
    assert con.execute("select home_qb_name from schedule").fetchall() == [("Drew Lock",)]
