"""Synthetic play-by-play so metric logic is tested against hand-computed answers."""

from __future__ import annotations

import duckdb
import pytest

from ags.db import install_views

PBP_COLUMNS: dict[str, tuple[str, object]] = {
    "game_id": ("varchar", "2024_01_AAA_BBB"),
    "play_id": ("double", 1.0),
    "season": ("integer", 2024),
    "season_type": ("varchar", "REG"),
    "week": ("integer", 1),
    "home_team": ("varchar", "AAA"),
    "away_team": ("varchar", "BBB"),
    "home_score": ("integer", 0),
    "away_score": ("integer", 0),
    "posteam": ("varchar", "AAA"),
    "defteam": ("varchar", "BBB"),
    "play_type": ("varchar", "pass"),
    "down": ("double", 1.0),
    "yardline_100": ("double", 50.0),
    "wp": ("double", 0.5),
    "qtr": ("double", 1.0),
    "score_differential": ("double", 0.0),
    "epa": ("double", 0.0),
    "qb_epa": ("double", 0.0),
    "success": ("double", 0.0),
    "pass": ("double", 1.0),
    "rush": ("double", 0.0),
    "xpass": ("double", None),
    "pass_oe": ("double", None),
    "yards_gained": ("double", 0.0),
    "pass_attempt": ("double", 1.0),
    "complete_pass": ("double", 0.0),
    "sack": ("double", 0.0),
    "qb_scramble": ("double", 0.0),
    "interception": ("double", 0.0),
    "fumble": ("double", 0.0),
    "fumble_lost": ("double", 0.0),
    "fumble_recovery_1_team": ("varchar", None),
    "first_down": ("double", 0.0),
    "touchdown": ("double", 0.0),
    "pass_touchdown": ("double", 0.0),
    "rush_touchdown": ("double", 0.0),
    "air_yards": ("double", None),
    "yards_after_catch": ("double", None),
    "xyac_mean_yardage": ("double", None),
    "cp": ("double", None),
    "cpoe": ("double", None),
    "passing_yards": ("double", None),
    "receiving_yards": ("double", None),
    "passer_id": ("varchar", "QB1"),
    "passer": ("varchar", "A.Passer"),
    "receiver_id": ("varchar", None),
    "receiver": ("varchar", None),
    "rusher_id": ("varchar", None),
    "rusher": ("varchar", None),
    "fixed_drive": ("double", 1.0),
    "fixed_drive_result": ("varchar", "Punt"),
    "order_sequence": ("double", None),
    "ydstogo": ("double", 10.0),
    "goal_to_go": ("double", 0.0),
    "ep": ("double", None),
    "game_seconds_remaining": ("double", 1800.0),
    "home_wp": ("double", None),
    "wpa": ("double", None),
    "time": ("varchar", None),
    "desc": ("varchar", None),
    "field_goal_attempt": ("double", 0.0),
    "field_goal_result": ("varchar", None),
    "kick_distance": ("double", None),
    "total_home_score": ("double", None),
    "total_away_score": ("double", None),
    "home_wp_post": ("double", None),
    "penalty": ("double", 0.0),
    "penalty_team": ("varchar", None),
    "penalty_yards": ("double", None),
    "drive_start_yard_line": ("varchar", None),
    "drive_end_yard_line": ("varchar", None),
    "drive_time_of_possession": ("varchar", None),
    "passer_player_id": ("varchar", None),
    "passer_player_name": ("varchar", None),
    "receiver_player_id": ("varchar", None),
    "receiver_player_name": ("varchar", None),
    "rusher_player_id": ("varchar", None),
    "rusher_player_name": ("varchar", None),
    "td_player_id": ("varchar", None),
    "td_team": ("varchar", None),
    "two_point_conv_result": ("varchar", None),
    "interception_player_id": ("varchar", None),
    "kicker_player_id": ("varchar", None),
    "extra_point_result": ("varchar", None),
    "solo_tackle_1_player_id": ("varchar", None),
    "solo_tackle_1_team": ("varchar", None),
    "sack_player_id": ("varchar", None),
    "half_sack_1_player_id": ("varchar", None),
    "half_sack_2_player_id": ("varchar", None),
    "fumbled_1_player_id": ("varchar", None),
    "fumbled_1_team": ("varchar", None),
    "fumble_recovery_1_player_id": ("varchar", None),
    "punt_returner_player_id": ("varchar", None),
    "return_team": ("varchar", None),
    "rush_attempt": ("double", None),
    "return_touchdown": ("double", None),
    "two_point_attempt": ("double", None),
    "extra_point_attempt": ("double", None),
    "first_down_pass": ("double", None),
    "first_down_rush": ("double", None),
    "rushing_yards": ("double", None),
    "return_yards": ("double", None),
    "punt_fair_catch": ("double", None),
    "safety": ("double", None),
}


def make_con(rows: list[dict]) -> duckdb.DuckDBPyConnection:
    unknown = {k for r in rows for k in r} - PBP_COLUMNS.keys()
    assert not unknown, f"add {unknown} to PBP_COLUMNS"
    con = duckdb.connect()
    cols = ", ".join(f'"{c}" {t}' for c, (t, _) in PBP_COLUMNS.items())
    con.execute(f"create table pbp ({cols})")
    placeholders = ", ".join("?" for _ in PBP_COLUMNS)
    con.executemany(
        f"insert into pbp values ({placeholders})",
        [[r.get(c, d) for c, (_, d) in PBP_COLUMNS.items()] for r in rows],
    )
    install_views(con)
    return con


def run(**overrides) -> dict:
    """A designed run by AAA's RB1."""
    return {
        "play_type": "run",
        "pass": 0.0,
        "rush": 1.0,
        "pass_attempt": 0.0,
        "passer_id": None,
        "passer": None,
        "rusher_id": "RB1",
        "rusher": "R.Back",
    } | overrides


@pytest.fixture
def make_pbp():
    return make_con
