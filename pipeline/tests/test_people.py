import pytest
from conftest import run

from ags import people


def test_ats_from_team_perspective():
    # Home favored by 3 (spread_line 3): home covers by winning by more than 3.
    assert people.ats(7, 3.0) == "w"
    assert people.ats(3, 3.0) == "p"
    assert people.ats(1, 3.0) == "l"
    # The away side of the same game uses -spread_line: losing by 1 covers +3.
    assert people.ats(-1, -3.0) == "w"
    assert people.ats(-7, -3.0) == "l"
    assert people.ats(10, None) is None


def _cg(game_id, coach, season, team, pf, pa, line):
    return {
        "game_id": game_id,
        "coach": coach,
        "season": season,
        "team": team,
        "pf": pf,
        "pa": pa,
        "line": line,
    }


def test_coach_seasons_and_careers_aggregate():
    games = [
        _cg("g1", "Coach A", 2023, "AAA", 24, 17, 3.0),  # win, covers
        _cg("g2", "Coach A", 2023, "AAA", 10, 10, -2.0),  # tie, covers (+2 dog)
        _cg("g3", "Coach A", 2024, "BBB", 13, 20, -7.0),  # loss, push
        _cg("g4", "Coach B", 2024, "CCC", 3, 30, None),  # no line
        _cg("g5", None, 2024, "DDD", 3, 30, 1.0),  # unknown coach: skipped
    ]
    plays = {
        ("g1", "AAA"): {"off_epa": 3.0, "off_plays": 30, "def_epa": -1.0, "def_plays": 20}
        | {"proe_sum": 1.0, "proe_n": 10},
        ("g2", "AAA"): {"off_epa": 0.0, "off_plays": 10, "def_epa": 1.0, "def_plays": 20}
        | {"proe_sum": -1.0, "proe_n": 10},
    }
    clear_go = {("g1", "AAA"): [2, 1], ("g3", "BBB"): [1, 1]}
    rows = people.coach_game_rows(games, plays, clear_go)
    assert len(rows) == 4
    seasons = {(r["coach"], r["season"]): r for r in people.coach_seasons(rows)}
    a23 = seasons[("Coach A", 2023)]
    assert (a23["games"], a23["wins"], a23["losses"], a23["ties"]) == (2, 1, 0, 1)
    assert (a23["ats_w"], a23["ats_l"], a23["ats_push"], a23["point_diff"]) == (2, 0, 0, 7)
    assert a23["net_epa"] == pytest.approx(3.0 / 40 - 0.0 / 40)
    assert a23["go_rate_clear"] == pytest.approx(0.5)
    assert a23["proe"] == pytest.approx(0.0)
    assert seasons[("Coach A", 2024)]["ats_push"] == 1
    assert seasons[("Coach B", 2024)]["net_epa"] is None  # no plays
    careers = {r["coach"]: r for r in people.coach_careers(rows)}
    a = careers["Coach A"]
    assert (a["seasons"], a["teams"], a["first"], a["last"]) == (2, "AAA/BBB", 2023, 2024)
    assert a["win_pct"] == pytest.approx(1.5 / 3)
    assert a["ats_pct"] == pytest.approx(1.0)  # 2-0 with a push
    assert a["go_rate_clear"] == pytest.approx(2 / 3)
    assert careers["Coach B"]["ats_pct"] is None


def test_clear_go_counts_only_clear_go_buckets():
    buckets = [
        {"dist_ord": 1, "field_ord": 9, "best": "go", "margin": 0.5},
        {"dist_ord": 1, "field_ord": 5, "best": "go", "margin": 0.1},  # not clear
        {"dist_ord": 6, "field_ord": 1, "best": "punt", "margin": 1.0},
    ]
    rows = [
        {"game_id": "g", "team": "AAA", "dist_ord": 1, "field_ord": 9, "decision": "go"},
        {"game_id": "g", "team": "AAA", "dist_ord": 1, "field_ord": 9, "decision": "fg"},
        {"game_id": "g", "team": "AAA", "dist_ord": 1, "field_ord": 5, "decision": "go"},
        {"game_id": "g", "team": "AAA", "dist_ord": 6, "field_ord": 1, "decision": "punt"},
    ]
    assert dict(people.clear_go_counts(rows, buckets)) == {("g", "AAA"): [2, 1]}


def test_referee_rows_per_season_and_career():
    def g(ref, season, result, pens, home_pens, pts=40):
        return {
            "referee": ref,
            "season": season,
            "result": result,
            "points": pts,
            "penalties": pens,
            "penalty_yards": pens * 8,
            "team_penalties": pens,
            "home_penalties": home_pens,
        }

    games = [g("R1", 2023, 3, 10, 4), g("R1", 2023, -3, 12, 8), g("R1", 2024, 0, 8, 4)]
    seasons = people.referee_rows(games, by_season=True)
    r23 = seasons[0]
    assert (r23["referee"], r23["season"], r23["games"]) == ("R1", 2023, 2)
    assert r23["penalties_pg"] == pytest.approx(11)
    assert r23["penalty_yards_pg"] == pytest.approx(88)
    assert r23["home_penalty_share"] == pytest.approx(12 / 22)
    assert r23["home_win_pct"] == pytest.approx(0.5)
    (career,) = people.referee_rows(games, by_season=False)
    assert (career["games"], career["seasons"], career["first"], career["last"]) == (
        3,
        2,
        2023,
        2024,
    )
    assert career["home_win_pct"] == pytest.approx(1.5 / 3)


def test_coaches_and_referees_empty_without_schedule(make_pbp):
    con = make_pbp([run()])
    assert people.coaches(con, []) == {"seasons": [], "careers": []}
    assert people.referees(con) == {"seasons": [], "careers": []}


def test_referee_sql_counts_home_penalties(make_pbp):
    con = make_pbp(
        [
            {"penalty": 1.0, "penalty_team": "AAA", "penalty_yards": 5.0},
            {"penalty": 1.0, "penalty_team": "BBB", "penalty_yards": 15.0, "play_type": "punt"},
            {"penalty": 1.0, "penalty_team": "AAA", "penalty_yards": 10.0, "play_type": None},
            {"penalty": 0.0},
        ]
    )
    con.execute("""
        create table schedule as select * from (values
            ('2024_01_AAA_BBB', 2024, 'REG', 1, 'AAA', 'BBB', 20, 17, 3, 'Ref One')
        ) t(game_id, season, game_type, week, home_team, away_team, home_score, away_score,
            result, referee)
    """)
    (r,) = people.referees(con)["seasons"]
    assert (r["referee"], r["games"], r["penalties_pg"], r["penalty_yards_pg"]) == (
        "Ref One",
        1,
        3,
        30,
    )
    assert r["home_penalty_share"] == pytest.approx(2 / 3)
    assert (r["home_win_pct"], r["points_pg"]) == (1.0, 37)
