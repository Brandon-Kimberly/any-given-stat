from conftest import run

from ags import playbyplay


def test_flags_letters():
    assert playbyplay.flags({"touchdown": 1.0, "pass": 1.0, "yards_gained": 25.0}) == "TX"
    assert playbyplay.flags({"rush": 1.0, "yards_gained": 9.0, "fumble_lost": 1.0}) == "F"
    assert playbyplay.flags({"rush": 1.0, "yards_gained": 10.0, "down": 4, "play_type": "run"}) == (
        "X4"
    )
    assert playbyplay.flags({"down": 4, "play_type": "punt", "penalty": 1.0}) == "P"
    assert playbyplay.flags({"interception": 1.0, "sack": None}) == "I"
    assert playbyplay.flags({"sack": 1.0, "pass": 1.0, "yards_gained": -8.0}) == "S"


def test_parse_yardline_relative_to_offense():
    assert playbyplay.parse_yardline("KC 25", "KC") == 25
    assert playbyplay.parse_yardline("KC 25", "BUF") == 75
    assert playbyplay.parse_yardline("MID 50", "KC") == 50
    assert playbyplay.parse_yardline("50", "KC") == 50
    assert playbyplay.parse_yardline(None, "KC") is None
    assert playbyplay.parse_yardline("KC", "KC") is None


def _game(make_pbp):
    gid = "2024_01_BBB_AAA"  # AAA home
    base = {"game_id": gid, "home_team": "AAA", "away_team": "BBB"}
    rows = [
        # Drive 1, AAA: kickoff, two snaps, TD and PAT.
        base
        | {
            "play_id": 1.0,
            "play_type": "kickoff",
            "pass": 0.0,
            "fixed_drive": 1.0,
            "fixed_drive_result": "Touchdown",
            "drive_start_yard_line": "AAA 25",
            "drive_end_yard_line": "BBB 30",
            "drive_time_of_possession": "1:10",
            "time": "15:00",
            "yardline_100": 35.0,
            "desc": "kickoff",
            "total_home_score": 0.0,
            "total_away_score": 0.0,
        },
        base
        | run(
            play_id=2.0,
            fixed_drive=1.0,
            fixed_drive_result="Touchdown",
            time="14:55",
            yardline_100=75.0,
            down=1.0,
            ydstogo=10.0,
            yards_gained=45.0,
            epa=2.5,
            home_wp_post=0.61234,
            desc="run for 45",
            total_home_score=0.0,
            total_away_score=0.0,
        ),
        base
        | {
            "play_id": 3.0,
            "fixed_drive": 1.0,
            "fixed_drive_result": "Touchdown",
            "time": "14:20",
            "yardline_100": 30.0,
            "down": 1.0,
            "yards_gained": 30.0,
            "touchdown": 1.0,
            "desc": "x" * 300,
            "total_home_score": 6.0,
            "total_away_score": 0.0,
        },
        base
        | {
            "play_id": 4.0,
            "play_type": "extra_point",
            "pass": 0.0,
            "fixed_drive": 1.0,
            "fixed_drive_result": "Touchdown",
            "desc": "PAT good",
            "total_home_score": 7.0,
            "total_away_score": 0.0,
        },
        # Drive 2, BBB: a punt from its own 20 after a penalty.
        base
        | {
            "play_id": 5.0,
            "posteam": "BBB",
            "defteam": "AAA",
            "play_type": "no_play",
            "penalty": 1.0,
            "fixed_drive": 2.0,
            "fixed_drive_result": "Punt",
            "drive_start_yard_line": "BBB 25",
            "drive_end_yard_line": "BBB 20",
            "time": "14:10",
            "yardline_100": 75.0,
            "desc": "False start",
            "total_home_score": 7.0,
            "total_away_score": 0.0,
        },
        base
        | {
            "play_id": 6.0,
            "posteam": "BBB",
            "defteam": "AAA",
            "play_type": "punt",
            "pass": 0.0,
            "fixed_drive": 2.0,
            "fixed_drive_result": "Punt",
            "down": 4.0,
            "yardline_100": 80.0,
            "desc": "punt",
            "total_home_score": 7.0,
            "total_away_score": 0.0,
        },
        base | {"play_id": 7.0, "posteam": None, "desc": "END GAME"},  # no offense: dropped
    ]
    return make_pbp(rows), gid


def test_season_games_plays_and_drives(make_pbp):
    con, gid = _game(make_pbp)
    out = dict(playbyplay.season_games(con, 2024))
    g = out[gid]
    assert g["plays_columns"][0] == "qtr" and len(g["plays_columns"]) == len(g["plays"][0])
    assert len(g["plays"]) == 6
    col = {c: i for i, c in enumerate(g["plays_columns"])}
    p = g["plays"][1]
    assert p[col["yl"]] == 25 and p[col["down"]] == 1 and p[col["flags"]] == "X"
    assert p[col["home_wp_after"]] == 0.612 and p[col["epa"]] == 2.5
    assert len(g["plays"][2][col["desc"]]) == 180
    assert g["plays"][2][col["flags"]] == "TX"
    assert g["plays"][4][col["flags"]] == "P"

    d1, d2 = g["drives"]
    assert d1 == {
        "n": 1,
        "posteam": "AAA",
        "qtr": 1,
        "start_clock": "15:00",
        "start_yl": 25,
        "end_yl": 100,  # touchdown
        "plays": 2,
        "yards": 75,
        "result": "Touchdown",
        "top": "1:10",
        "points": 7,
    }
    assert (d2["posteam"], d2["start_yl"], d2["end_yl"], d2["yards"]) == ("BBB", 25, 20, -5)
    assert (d2["plays"], d2["points"], d2["result"]) == (1, 0, "Punt")


def test_drive_offense_is_the_team_snapping(make_pbp):
    """A recovered onside kick is filed under the next drive with the receiving team as
    posteam; the drive belongs to the kicking team that then snaps the ball."""
    rows = [
        {
            "play_type": "kickoff",
            "posteam": "BBB",
            "defteam": "AAA",
            "fixed_drive": 3.0,
            "desc": "onside, recovered by AAA",
            "total_home_score": 0.0,
            "total_away_score": 0.0,
        },
        {
            "fixed_drive": 3.0,
            "yardline_100": 52.0,
            "desc": "pass",
            "touchdown": 1.0,
            "fixed_drive_result": "Touchdown",
            "total_home_score": 6.0,
            "total_away_score": 0.0,
        },
    ]
    con = make_pbp(rows)
    (_, g), *_ = playbyplay.season_games(con, 2024)
    (d,) = g["drives"]
    assert (d["posteam"], d["points"], d["start_yl"], d["plays"]) == ("AAA", 6, 48, 1)
