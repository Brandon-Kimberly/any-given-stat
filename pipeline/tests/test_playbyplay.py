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
            "td_team": "AAA",
            "complete_pass": 1.0,
            "passer_player_name": "A.Passer",
            "receiver_player_name": "W.Wideout",
            "desc": "(14:20) " + "x" * 300,
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
            "extra_point_result": "good",
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
    assert g["plays_columns"][0] == "qtr"
    # Trailing nulls are dropped, so rows can be shorter than the column list.
    assert all(len(p) <= len(g["plays_columns"]) for p in g["plays"])
    assert len(g["plays"]) == 6
    col = {c: i for i, c in enumerate(g["plays_columns"])}

    def at(p, name):
        i = col[name]
        return p[i] if i < len(p) else None

    p = g["plays"][1]
    assert p[col["yl"]] == 25 and p[col["down"]] == 1 and p[col["flags"]] == "X"
    assert p[col["home_wp_after"]] == 0.612 and p[col["epa"]] == 2.5
    # The run's 45 yards took the ball from AAA's 25 to the next snap at BBB's 30.
    assert (at(p, "kind"), at(p, "yds"), at(p, "yl_end")) == ("run", 45, 70)
    td = g["plays"][2]
    assert len(td[col["desc"]]) == 180 and td[col["desc"]].startswith("x")  # clock stripped
    assert td[col["flags"]] == "TX"
    assert (at(td, "kind"), at(td, "a"), at(td, "b"), at(td, "yl_end")) == (
        "complete",
        "A.Passer",
        "W.Wideout",
        100,
    )
    assert at(g["plays"][3], "kind") == "xp_good" and at(g["plays"][3], "yl_end") is None
    assert g["plays"][4][col["flags"]] == "P"
    assert at(g["plays"][4], "kind") == "penalty"
    # The false start backed BBB up to the punt's spot: 25 -> 20.
    assert at(g["plays"][4], "yl_end") == 20

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


def test_kind_actors_detail():
    k = playbyplay.kind
    assert k({"play_type": "pass", "complete_pass": 1.0}) == "complete"
    assert k({"play_type": "pass", "complete_pass": 0.0}) == "incomplete"
    assert k({"play_type": "pass", "sack": 1.0}) == "sack"
    assert k({"play_type": "pass", "interception": 1.0}) == "interception"
    assert k({"play_type": "run", "qb_scramble": 1.0}) == "scramble"
    assert k({"play_type": "field_goal", "field_goal_result": "missed"}) == "fg_missed"
    assert k({"play_type": "extra_point", "extra_point_result": "good"}) == "xp_good"
    assert k(
        {"play_type": "pass", "two_point_attempt": 1.0, "two_point_conv_result": "success"}
    ) == ("2pt_good")
    assert k({"play_type": "punt", "punt_blocked": 1.0}) == "punt_blocked"
    assert k({"play_type": "kickoff", "own_kickoff_recovery": 1.0}) == "onside"
    assert k({"play_type": "no_play", "penalty": 1.0}) == "penalty"
    assert k({"play_type": "no_play", "penalty": 0.0}) is None
    assert k({"play_type": None, "desc": "END QUARTER 1"}) == "end"

    sack = {"passer_player_name": "Q.Back", "half_sack_1_player_name": "A.One"}
    sack["half_sack_2_player_name"] = "B.Two"
    assert playbyplay.actors(sack, "sack") == ("Q.Back", None, "A.One / B.Two")
    pick = {"passer_player_name": "Q.Back", "receiver_player_name": "W.R"}
    pick["interception_player_name"] = "C.B"
    assert playbyplay.actors(pick, "interception") == ("Q.Back", "W.R", "C.B")
    scramble = {"rusher_player_name": "Q.Back"}
    assert playbyplay.actors(scramble, "scramble") == ("Q.Back", None, None)
    fumble = {"rusher_player_name": "R.B", "fumble_lost": 1.0}
    fumble["fumble_recovery_1_player_name"] = "L.B"
    assert playbyplay.actors(fumble, "run") == ("R.B", None, "L.B")
    punt = {"punter_player_name": "P.P", "punt_returner_player_name": "K.R"}
    assert playbyplay.actors(punt, "punt") == ("P.P", "K.R", None)

    d = playbyplay.detail
    assert d({"pass_length": "deep", "pass_location": "left"}, "complete") == "deep left"
    assert d({"run_location": "middle", "run_gap": None}, "run") == "middle"
    assert d({"run_location": "left", "run_gap": "tackle"}, "run") == "left tackle"
    assert d({"punt_fair_catch": 1.0}, "punt") == "fair catch"
    assert d({"touchback": 1.0}, "kickoff") == "touchback"
    assert d({}, "punt") is None and d({"pass_length": "deep"}, "sack") is None


def test_penalty_status():
    base = {"penalty": 1.0, "penalty_team": "AAA", "penalty_yards": 5.0}
    hold = base | {"penalty_type": "Offensive Holding", "penalty_player_name": "O.L"}
    assert playbyplay.penalty(hold | {"desc": "PENALTY on AAA-70-O.L, Offensive Holding"}) == [
        "AAA",
        "Offensive Holding",
        5,
        "O.L",
        None,
    ]
    declined = hold | {
        "penalty_yards": 0.0,
        "desc": "PENALTY on AAA-70-O.L, Offensive Holding, declined.",
    }
    assert playbyplay.penalty(declined)[4] == "declined"
    # A different, declined second flag doesn't mark the first one.
    other = hold | {
        "desc": "PENALTY on AAA, Offensive Holding, 10 yards. Penalty on BBB, Offside, declined."
    }
    assert playbyplay.penalty(other)[4] is None
    assert playbyplay.penalty({"penalty": 0.0}) is None


def test_end_yardline():
    def row(**kw):
        return {"posteam": "AAA", "qtr": 1, "play_type": "run", "yardline_100": 70.0} | kw

    # Next snap by the same team: its line of scrimmage.
    assert playbyplay.end_yardline([row(), row(yardline_100=62.0)], 0) == 38
    # A punt: the other team's next snap, mirrored (their own 20 = our 80).
    rows = [row(play_type="punt"), row(posteam="BBB", yardline_100=80.0)]
    assert playbyplay.end_yardline(rows, 0) == 80
    # Touchdowns and safeties.
    assert playbyplay.end_yardline([row(touchdown=1.0, td_team="AAA")], 0) == 100
    assert playbyplay.end_yardline([row(touchdown=1.0, td_team="BBB")], 0) == 0
    assert playbyplay.end_yardline([row(safety=1.0)], 0) == 0
    # A kickoff or a new half in between: unknown.
    rows = [row(), row(play_type="kickoff", yardline_100=35.0), row(yardline_100=75.0)]
    assert playbyplay.end_yardline(rows, 0) is None
    assert playbyplay.end_yardline([row(qtr=2), row(qtr=3, yardline_100=75.0)], 0) is None
    # End-of-quarter rows are skipped within a half.
    rows = [row(), row(play_type=None, yardline_100=None, qtr=2), row(qtr=2, yardline_100=60.0)]
    assert playbyplay.end_yardline(rows, 0) == 40
    assert playbyplay.end_yardline([row()], 0) is None


def test_play_row_trims_trailing_nulls():
    r = {c: None for c in playbyplay.SOURCE_COLUMNS} | {
        "qtr": 1.0,
        "time": "15:00",
        "posteam": "AAA",
        "yardline_100": 75.0,
        "play_type": "run",
        "desc": "(15:00) R.B up the middle for 3 yards",
        "rusher_player_name": "R.B",
        "yards_gained": 3.0,
        "run_location": "middle",
        "home_wp": 0.5,
        "home_wp_post": 0.51,
    }
    out = playbyplay.play_row(r, 28)
    cols = playbyplay.PLAYS_COLUMNS
    assert len(out) == cols.index("detail") + 1
    assert out[cols.index("desc")] == "R.B up the middle for 3 yards"
    assert out[cols.index("home_wpa")] == 0.01
    assert out[cols.index("yl_end")] == 28 and out[cols.index("detail")] == "middle"
