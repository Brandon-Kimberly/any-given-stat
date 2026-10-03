"""Stat lines on a hand-built game; every expected number is counted by hand from the plays."""

from __future__ import annotations

from conftest import run

from ags.statlines import season_lines

DEF = {"posteam": "BBB", "defteam": "AAA"}


def kick(**overrides) -> dict:
    return {
        "play_type": "field_goal",
        "pass": 0.0,
        "pass_attempt": 0.0,
        "passer_id": None,
        "kicker_player_id": "K1",
    } | overrides


PLAYS = [
    # 45-yard TD pass, then a successful two-point pass.
    dict(
        complete_pass=1.0, yards_gained=45.0, passing_yards=45.0, receiving_yards=45.0,
        yards_after_catch=20.0, first_down_pass=1.0, pass_touchdown=1.0, touchdown=1.0,
        td_team="AAA", td_player_id="WR1", passer_player_id="QB1", receiver_player_id="WR1",
    ),
    dict(
        two_point_attempt=1.0, two_point_conv_result="success", passer_player_id="QB1",
        receiver_player_id="WR1",
    ),
    dict(passer_player_id="QB1", receiver_player_id="WR1"),  # incomplete
    # Pick-six by D1.
    dict(
        interception=1.0, interception_player_id="D1", return_yards=30.0, return_touchdown=1.0,
        touchdown=1.0, td_team="BBB", td_player_id="D1", passer_player_id="QB1",
    ),
    # Sack split by D1 and D2 for -7.
    dict(sack=1.0, yards_gained=-7.0, passer_player_id="QB1", half_sack_1_player_id="D1",
         half_sack_2_player_id="D2"),
    run(yards_gained=12.0, rushing_yards=12.0, first_down_rush=1.0, rush_attempt=1.0,
        rusher_player_id="RB1"),
    run(yards_gained=3.0, rushing_yards=3.0, rush_touchdown=1.0, touchdown=1.0, td_team="AAA",
        td_player_id="RB1", rush_attempt=1.0, rusher_player_id="RB1"),
    # Fumble lost: RB1 fumbles, D2 recovers.
    run(yards_gained=2.0, rushing_yards=2.0, rush_attempt=1.0, rusher_player_id="RB1",
        fumbled_1_player_id="RB1", fumbled_1_team="AAA", fumble_recovery_1_team="BBB",
        fumble_recovery_1_player_id="D2", fumble_lost=1.0),
    kick(field_goal_attempt=1.0, field_goal_result="made", kick_distance=52.0),
    kick(field_goal_attempt=1.0, field_goal_result="missed", kick_distance=38.0),
    kick(play_type="extra_point", extra_point_attempt=1.0, extra_point_result="good"),
    run(yards_gained=20.0, rushing_yards=20.0, rush_attempt=1.0, rusher_player_id="RB9",
        total_home_score=19.0, total_away_score=6.0, **DEF),
]  # fmt: skip


def lines(make_pbp):
    con = make_pbp([{"play_id": float(i)} | p for i, p in enumerate(PLAYS, 1)])
    out = season_lines(con, 2024, {"QB1": {"name": "A. Passer", "position": "QB"}})
    by_id = {pid: stats for _, pid, _, stats in out["lines"]}
    return out, by_id


def test_passing_and_receiving(make_pbp):
    _, s = lines(make_pbp)
    assert s["QB1"] == {
        "pass_att": 3,  # TD, incompletion, interception (not the 2-pt try, not the sack)
        "pass_cmp": 1,
        "pass_inc": 1,
        "pass_int": 1,
        "pass_int_td": 1,
        "pass_yd": 45,
        "pass_td": 1,
        "pass_td_yds": [45],
        "pass_fd": 1,
        "pass_cmp_40p": 1,
        "pass_lng": 45,
        "pass_2pt": 1,
        "pass_sack": 1,
        "pass_sack_yd": 7,
    }
    assert s["WR1"] == {
        "rec_tgt": 2,
        "rec": 1,
        "rec_yd": 45,
        "rec_yac": 20,
        "rec_40p": 1,
        "rec_lng": 45,
        "rec_fd": 1,
        "rec_td": 1,
        "rec_td_yds": [45],
        "rec_2pt": 1,
    }


def test_rushing_fumbles_and_defense(make_pbp):
    _, s = lines(make_pbp)
    rb = s["RB1"]
    assert (rb["rush_att"], rb["rush_yd"], rb["rush_td"], rb["rush_fd"], rb["rush_lng"]) == (
        3, 17, 1, 1, 12,
    )  # fmt: skip
    assert rb["rush_td_yds"] == [3]
    assert (rb["fum"], rb["fum_lost"]) == (1, 1)
    assert s["D1"] == {"def_int": 1, "int_ret_yd": 30, "def_td": 1, "sack": 0.5, "sack_yd": 3.5}
    assert s["D2"]["sack"] == 0.5 and s["D2"]["def_fum_rec"] == 1


def test_kicking(make_pbp):
    _, s = lines(make_pbp)
    assert s["K1"] == {
        "fga": 2,
        "fgm": 1,
        "fgmiss": 1,
        "fgm_dists": [52],
        "fgmiss_dists": [38],
        "fg_lng": 52,
        "xpa": 1,
        "xpm": 1,
    }


def test_team_defense_lines(make_pbp):
    _, s = lines(make_pbp)
    # BBB's defense: one sack play, a pick-six, a fumble recovery. AAA scored 19, no returns.
    assert s["BBB"] == {
        "sack": 1,
        "def_int": 1,
        "def_fum_rec": 1,
        "def_td": 1,
        "pts_allow": 19,
        "yds_allow": 55,  # 45 passing - 7 sack + 17 rushing
    }
    # AAA allowed 6 points, all on BBB's pick-six: none of them on the defense. A shutout
    # keeps its explicit zero.
    assert s["AAA"] == {"pts_allow": 0, "yds_allow": 20}


def test_team_box(make_pbp):
    out, _ = lines(make_pbp)
    aaa = out["teams"]["2024_01_AAA_BBB|AAA"]
    assert aaa["plays"] == 7  # 3 passes + 1 sack + 3 runs
    assert (aaa["pass_yds"], aaa["rush_yds"], aaa["yards"]) == (38, 17, 55)
    assert aaa["sacked"] == [1, 7]
    assert aaa["turnovers"] == 2 and aaa["first_downs"] == 2
    assert out["players"]["QB1"] == ["A. Passer", "QB"]
    assert out["players"]["BBB"] == ["BBB", "DEF"]


def test_fantasy_file_drops_box_only_fields(make_pbp):
    from ags.statlines import fantasy_season

    out, _ = lines(make_pbp)
    f = {pid: st for _, pid, _, st in fantasy_season(2024, out)["lines"]}
    assert "pass_lng" not in f["QB1"] and f["QB1"]["pass_yd"] == 45
    assert "rec_yac" not in f["WR1"]
