import pytest

from ags import records


def test_wlt_counts_wins_losses_ties():
    rows = [
        {"season": 2024, "team": "AAA", "pf": 20, "pa": 10},
        {"season": 2024, "team": "AAA", "pf": 10, "pa": 20},
        {"season": 2024, "team": "AAA", "pf": 17, "pa": 17},
        {"season": 2024, "team": "AAA", "pf": 31, "pa": 3},
        {"season": 2024, "team": "AAA", "pf": None, "pa": None},  # unplayed
        {"season": 2025, "team": "AAA", "pf": 0, "pa": 3},
    ]
    out = records.wlt(rows)
    assert out[(2024, "AAA")] == {"games": 4, "wins": 2, "losses": 1, "ties": 1}
    assert out[(2025, "AAA")] == {"games": 1, "wins": 0, "losses": 1, "ties": 0}


def _g(game_id, line, result, home="HHH", away="AAA"):
    return {"game_id": game_id, "home": home, "away": away, "spread_line": line, "result": result}


def test_upsets_pick_underdog_wins_by_spread():
    games = [
        _g("fav_home_won", 7.0, 10),  # favorite won: not an upset
        _g("home_dog_won", -9.5, 3),  # away favored by 9.5, home won
        _g("away_dog_won", 13.5, -1),  # home favored by 13.5, away won
        _g("small", 2.5, -20),
        _g("pickem", 0.0, -7),  # no underdog
        _g("tie", -3.0, 0),  # nobody won
        _g("no_line", None, -3),
    ]
    out = records.upsets(games)
    assert [g["game_id"] for g in out] == ["away_dog_won", "home_dog_won", "small"]
    assert (out[0]["spread"], out[0]["underdog"], out[0]["favorite"]) == (13.5, "AAA", "HHH")
    assert out[1]["underdog"] == "HHH"
    assert len(records.upsets(games, n=1)) == 1


def _game(wp, home_score, away_score):
    return {
        "game_id": "g",
        "season": 2024,
        "week": 1,
        "season_type": "REG",
        "home": "HHH",
        "away": "AAA",
        "home_score": home_score,
        "away_score": away_score,
        "wp": [[i * 100, p] for i, p in enumerate(wp)],
    }


def test_game_summary_excitement_and_comeback():
    s = records.game_summary(_game([0.5, 0.2, 0.6, 0.1, 0.9], 24, 21))
    assert s["excitement"] == pytest.approx(0.3 + 0.4 + 0.5 + 0.8)
    assert (s["winner"], s["winner_min_wp"]) == ("HHH", pytest.approx(0.1))
    away = records.game_summary(_game([0.5, 0.95, 0.3], 10, 13))
    assert (away["winner"], away["winner_min_wp"]) == ("AAA", pytest.approx(0.05))
    # Regular season: overtime points (elapsed > 3600) are ignored; postseason keeps them.
    ot = _game([0.5, 0.4, 0.6], 20, 17)
    ot["wp"] = [[0, 0.5], [3600, 0.4], [3700, 0.01], [3800, 1.0]]
    assert records.game_summary(ot)["excitement"] == pytest.approx(0.1)
    assert records.game_summary(ot | {"season_type": "POST"})["winner_min_wp"] == 0.01
    tie = records.game_summary(_game([0.5, 0.5], 10, 10))
    assert tie["winner"] is None and tie["winner_min_wp"] is None
    assert records.game_summary(_game([0.5], 7, 0)) is None


def test_team_rows_require_min_games_and_no_garbage_scope():
    seasons = [
        {"scope": "no_garbage", "season": 2024, "team": t, "net_epa_play": n}
        | {"off_epa_play": n, "def_epa_play": 0.0}
        for t, n in (("AAA", 0.2), ("BBB", -0.1), ("CCC", 0.5))
    ] + [
        {"scope": "all", "season": 2024, "team": "AAA", "net_epa_play": 9.0}
        | {"off_epa_play": 9.0, "def_epa_play": 0.0}
    ]
    rec = {
        (2024, "AAA"): {"games": 17, "wins": 12, "losses": 5, "ties": 0},
        (2024, "BBB"): {"games": 17, "wins": 4, "losses": 13, "ties": 0},
        (2024, "CCC"): {"games": 3, "wins": 3, "losses": 0, "ties": 0},  # too few games
    }
    rows = records.team_rows(seasons, rec, min_games=10)
    assert [r["team"] for r in records.top(rows, "net_epa")] == ["AAA", "BBB"]
    assert records.top(rows, "net_epa", lowest=True)[0]["team"] == "BBB"
    assert rows[0]["wins"] == 12 and rows[0]["net_epa"] == 0.2


def test_biggest_plays_skip_wp_artifacts_and_regular_season_overtime(make_pbp):
    def play(gid, pid, wpa, home_wp, post, **kw):
        return {
            "game_id": gid,
            "play_id": float(pid),
            "wpa": wpa,
            "home_wp": home_wp,
            "home_wp_post": post,
            "home_score": 20,
            "away_score": 17,
        } | kw

    rows = [
        play("2024_01_BBB_AAA", 1, 0.30, 0.50, 0.80),  # next row agrees: kept
        play("2024_01_BBB_AAA", 2, 0.90, 0.80, 0.05),  # next row says 0.85: artifact
        play("2024_01_BBB_AAA", 3, 0.10, 0.85, 0.95),  # last row, home won: kept
        play("2024_02_CCC_DDD", 1, 0.95, 0.40, 0.99, qtr=5.0),  # regular-season OT
        play("2024_02_CCC_DDD", 2, 0.00, 0.99, 0.99, qtr=5.0),
        # A bogus post-snap WP repeated on a non-play row; the next play disagrees.
        play("2024_03_EEE_FFF", 1, 0.99, 0.01, 1.0),
        play("2024_03_EEE_FFF", 2, 0.0, 1.0, 0.0, play_type=None),
        play("2024_03_EEE_FFF", 3, 0.0, 0.0, 0.0),
    ]
    out = records.biggest_plays(make_pbp(rows))
    assert [p["wpa"] for p in out] == [pytest.approx(0.30), pytest.approx(0.10)]
