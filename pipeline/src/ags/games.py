"""Per-game pages: win-probability chart, biggest plays and a team box score.

One file per season (regular season and postseason), written by build.py to
games/games_<season>.json, plus games/index.json.
"""

from __future__ import annotations

from collections import defaultdict

import duckdb

from .db import has_relation, records

TOP_PLAYS = 6
DESC_CHARS = 200
REGULATION_SECONDS = 3600

# Per game and offense. ``scrimmage_plays`` = the ``plays`` filters minus season type, so
# postseason games get the same box score definitions as regular-season ones.
BOX_SQL = """
select game_id, posteam as team,
       count(*) as plays,
       avg(epa) as epa_play,
       avg(success) as success_rate,
       avg(epa) filter (where pass = 1) as pass_epa,
       avg(epa) filter (where rush = 1) as rush_epa,
       cast(coalesce(sum(yards_gained), 0) as int) as yards,
       cast(sum(coalesce(interception, 0) + coalesce(fumble_lost, 0)) as int) as turnovers
from scrimmage_plays
where season = ?
group by all
"""

# Play order within a game: nflverse's order_sequence fixes the few play_ids out of order
# (e.g. timeouts logged late).
PLAY_ORDER = "game_id, coalesce(order_sequence, play_id), play_id"


def elapsed_seconds(points: list[dict]) -> list[int]:
    """Game clock elapsed for each play row (qtr, game_seconds_remaining), in game order.

    Regulation: 3600 - game_seconds_remaining. Overtime rows count the OT period's clock
    (nflverse resets game_seconds_remaining to the period clock: 600 for a 10-minute OT,
    900 for 15) on top of 3600. The result is forced non-decreasing.
    """
    ot_len: dict[int, float] = {}
    for p in points:
        if p["qtr"] >= 5:
            ot_len[p["qtr"]] = max(ot_len.get(p["qtr"], 0.0), p["game_seconds_remaining"])
    length = 600.0 if ot_len and max(ot_len.values()) <= 600 else 900.0
    out: list[int] = []
    for p in points:
        gsr = p["game_seconds_remaining"]
        if p["qtr"] >= 5:
            e = REGULATION_SECONDS + (p["qtr"] - 5) * length + (length - gsr)
        else:
            e = REGULATION_SECONDS - gsr
        e = int(e)  # the clock is whole seconds; ints keep the files small
        out.append(max(e, out[-1]) if out else e)
    return out


def wp_series(points: list[dict]) -> list[list]:
    """[[elapsed, home_wp], ...] for one game's rows in order, consecutive duplicates removed."""
    series: list[list] = []
    for e, p in zip(elapsed_seconds(points), points, strict=True):
        pt = [e, p["home_wp"]]
        if not series or series[-1] != pt:
            series.append(pt)
    return series


def top_plays(rows: list[dict], home: str, n: int = TOP_PLAYS) -> list[dict]:
    """The ``n`` plays with the largest |wpa|, biggest first, from the home team's view."""
    ranked = sorted(rows, key=lambda r: -abs(r["wpa"]))[:n]
    return [
        {
            "qtr": r["qtr"],
            "time": r["time"],
            "posteam": r["posteam"],
            "desc": (r["desc"] or "")[:DESC_CHARS],
            "home_wpa": r["wpa"] if r["posteam"] == home else -r["wpa"],
            "epa": r["epa"],
        }
        for r in ranked
    ]


def season_games(con: duckdb.DuckDBPyConnection, season: int) -> list[dict]:
    """Every game (REG and POST) in ``season`` with WP series, top plays and box score."""
    gameday = (
        "(select any_value(gameday) from schedule s where s.game_id = g.game_id)"
        if has_relation(con, "schedule")
        else "null"
    )
    games = records(
        con,
        f"""
        select g.game_id, g.season, g.week, g.season_type,
               g.home_team as home, g.away_team as away, g.home_score, g.away_score,
               {gameday} as gameday
        from games g
        where g.season = ?
        order by g.season_type desc, g.week, g.game_id
        """,
        [season],
    )
    wp_rows: dict[str, list[dict]] = defaultdict(list)
    for r in records(
        con,
        f"""
        select game_id, qtr, game_seconds_remaining, home_wp
        from pbp
        where season = ? and home_wp is not null and qtr is not null
          and game_seconds_remaining is not null
        order by {PLAY_ORDER}
        """,
        [season],
    ):
        wp_rows[r["game_id"]].append(r)
    swing_rows: dict[str, list[dict]] = defaultdict(list)
    for r in records(
        con,
        f"""
        select game_id, cast(qtr as int) as qtr, time, posteam, "desc", wpa, epa
        from pbp
        where season = ? and wpa is not null and posteam is not null
          and play_type is not null
        order by {PLAY_ORDER}
        """,
        [season],
    ):
        swing_rows[r["game_id"]].append(r)
    box: dict[tuple[str, str], dict] = {}
    for r in records(con, BOX_SQL, [season]):
        box[(r.pop("game_id"), r.pop("team"))] = r
    for g in games:
        gid = g["game_id"]
        g["wp"] = wp_series(wp_rows.get(gid, []))
        g["top_plays"] = top_plays(swing_rows.get(gid, []), g["home"])
        g["box"] = {
            "home": box.get((gid, g["home"])),
            "away": box.get((gid, g["away"])),
        }
    return games
