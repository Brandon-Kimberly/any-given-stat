import pytest
from conftest import run

from ags import games


def _pt(qtr, gsr, home_wp):
    return {"qtr": qtr, "game_seconds_remaining": gsr, "home_wp": home_wp}


def test_elapsed_handles_overtime_and_stays_monotone():
    pts = [
        _pt(1, 3600, 0.5),
        _pt(2, 1900, 0.5),
        _pt(2, 1950, 0.6),  # clock logged out of order: held at the previous value
        _pt(4, 0, 0.5),
        _pt(5, 600, 0.5),  # 10-minute overtime
        _pt(5, 300, 0.8),
    ]
    assert games.elapsed_seconds(pts) == [0, 1700, 1700, 3600, 3600, 3900]
    fifteen = [_pt(4, 0, 0.5), _pt(5, 900, 0.5), _pt(5, 100, 0.5)]
    assert games.elapsed_seconds(fifteen) == [3600, 3600, 4400]


def test_wp_series_dedupes_consecutive_points():
    pts = [_pt(1, 3600, 0.5), _pt(1, 3600, 0.5), _pt(1, 3500, 0.5), _pt(1, 3500, 0.6)]
    assert games.wp_series(pts) == [[0, 0.5], [100, 0.5], [100, 0.6]]


def test_season_games_wp_top_plays_and_box(make_pbp):
    gid = "2024_19_BBB_AAA"
    post = {"game_id": gid, "season_type": "POST", "week": 19}
    long_desc = "x" * 250
    rows = [
        # Start-of-game row: no play type, still a WP point.
        post
        | {
            "play_type": None,
            "order_sequence": 1.0,
            "game_seconds_remaining": 3600.0,
            "home_wp": 0.6,
            "epa": None,
        },
    ]
    # Seven plays; |wpa| ranks them 7, 6, ..., 1. Odd ones are by the away team.
    for i in range(1, 8):
        away = i % 2 == 1
        rows.append(
            post
            | {
                "order_sequence": float(i + 1),
                "play_id": float(i + 1),
                "game_seconds_remaining": 3600.0 - 100 * i,
                "home_wp": 0.6 if i < 3 else 0.5 + i / 100,
                "wpa": i / 100,
                "posteam": "BBB" if away else "AAA",
                "defteam": "AAA" if away else "BBB",
                "epa": float(i),
                "yards_gained": 5.0,
                "time": f"{i:02d}:00",
                "desc": long_desc if i == 7 else f"play {i}",
                "home_score": 24,
                "away_score": 17,
            }
        )
    rows.append(post | run(order_sequence=9.0, epa=-1.0, fumble_lost=1.0, home_wp=None))
    rows.append({"game_id": "2024_01_AAA_BBB", "home_wp": 0.5})  # a REG game
    out = {g["game_id"]: g for g in games.season_games(make_pbp(rows), 2024)}
    assert list(out) == ["2024_01_AAA_BBB", gid]  # REG first, then POST
    g = out[gid]
    assert (g["season_type"], g["home"], g["away"], g["gameday"]) == ("POST", "AAA", "BBB", None)
    assert (g["home_score"], g["away_score"]) == (24, 17)

    elapsed = [p[0] for p in g["wp"]]
    assert elapsed == sorted(elapsed)
    # Plays 1 and 2 repeat the opening 0.6 but at new clock times, so they stay.
    assert g["wp"][:3] == [[0, 0.6], [100, 0.6], [200, 0.6]]
    assert len(g["wp"]) == 8

    top = g["top_plays"]
    assert [p["epa"] for p in top] == [7.0, 6.0, 5.0, 4.0, 3.0, 2.0]
    assert top[0]["home_wpa"] == pytest.approx(-0.07)  # away play: sign flipped
    assert top[1]["home_wpa"] == pytest.approx(0.06)
    assert len(top[0]["desc"]) == 200
    assert (top[1]["qtr"], top[1]["time"], top[1]["posteam"]) == (1, "06:00", "AAA")

    home, away = g["box"]["home"], g["box"]["away"]
    # Home (AAA) ran plays 2, 4, 6 plus the fumbled run; postseason still gets a box score.
    assert (home["plays"], home["yards"], home["turnovers"]) == (4, 15, 1)
    assert home["epa_play"] == pytest.approx((2 + 4 + 6 - 1) / 4)
    assert home["rush_epa"] == pytest.approx(-1.0)
    assert (away["plays"], away["pass_epa"]) == (4, pytest.approx(4.0))


def test_highlight_picks_the_weeks_wildest_game_and_counts_favorite_changes():
    from ags.games import highlight

    calm = {
        "game_id": "a",
        "season": 2026,
        "week": 3,
        "home": "H",
        "away": "A",
        "home_score": 30,
        "away_score": 3,
        "wp": [[0, 0.6], [1800, 0.8], [3600, 1.0]],
    }
    wild = {
        "game_id": "b",
        "season": 2026,
        "week": 3,
        "home": "H",
        "away": "A",
        "home_score": 21,
        "away_score": 20,
        "wp": [[0, 0.55], [900, 0.3], [1800, 0.7], [2700, 0.2], [3600, 1.0]],
    }
    other_week = {**wild, "game_id": "c", "week": 2}
    h = highlight([calm, wild, other_week], 3)
    assert h["game_id"] == "b"
    assert h["favorite_changes"] == 4
    assert h["excitement"] == round(0.25 + 0.4 + 0.5 + 0.8, 3)
    assert highlight([calm], 9) is None
