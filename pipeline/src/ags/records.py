"""All-time leaderboards across the loaded seasons: records.json.

Season-level lists (teams, QBs, receivers, rushers) are regular season only and reuse the
rows of the published datasets. Game-level lists (upsets, excitement, comebacks, biggest
plays) include the postseason.
"""

from __future__ import annotations

import duckdb

from . import db
from .games import REGULATION_SECONDS

LIST_LEN = 20
BIGGEST_PLAYS = 25
MIN_TEAM_GAMES = 10  # keeps a hot start in an in-progress season off all-time lists
MIN_QB_DROPBACKS = 300
MIN_RUSH_CARRIES = 100
DESC_CHARS = 200
# A play's post-snap WP must agree with the next row's pre-snap WP within this much;
# nflfastR occasionally posts a bogus home_wp_post at the end of a period.
WP_CONSISTENCY = 0.1
WP_NOTE = (
    "Win-probability lists skip regular-season overtime, where nflfastR's win probability "
    "is unreliable because a tie is possible. Biggest plays also skip plays whose win "
    "probability doesn't line up with the next play's."
)


def wlt(rows: list[dict]) -> dict[tuple[int, str], dict]:
    """(season, team) -> games / wins / losses / ties from team-game rows (pf, pa)."""
    out: dict[tuple[int, str], dict] = {}
    for r in rows:
        if r["pf"] is None or r["pa"] is None:
            continue
        rec = out.setdefault(
            (r["season"], r["team"]), {"games": 0, "wins": 0, "losses": 0, "ties": 0}
        )
        rec["games"] += 1
        if r["pf"] > r["pa"]:
            rec["wins"] += 1
        elif r["pf"] < r["pa"]:
            rec["losses"] += 1
        else:
            rec["ties"] += 1
    return out


def top(rows: list[dict], key: str, n: int = LIST_LEN, lowest: bool = False) -> list[dict]:
    """The ``n`` rows with the highest (or lowest) non-null ``key``."""
    ranked = [r for r in rows if r.get(key) is not None]
    ranked.sort(key=lambda r: r[key], reverse=not lowest)
    return ranked[:n]


def team_rows(
    team_seasons: list[dict], record: dict[tuple[int, str], dict], min_games: int
) -> list[dict]:
    """No-garbage-time team-seasons with record, for team lists."""
    out = []
    for t in team_seasons:
        if t["scope"] != "no_garbage":
            continue
        rec = record.get((t["season"], t["team"]))
        if rec is None or rec["games"] < min_games:
            continue
        out.append(
            {
                "season": t["season"],
                "team": t["team"],
                **rec,
                "net_epa": t["net_epa_play"],
                "off_epa": t["off_epa_play"],
                "def_epa": t["def_epa_play"],
            }
        )
    return out


def pick(rows: list[dict], fields: list[str]) -> list[dict]:
    return [{f: r.get(f) for f in fields} for r in rows]


def upsets(games: list[dict], n: int = LIST_LEN) -> list[dict]:
    """Games the closing-line underdog won, biggest spread first.

    ``games`` rows: spread_line (> 0 = home favored), result (home margin), home, away.
    Pick'em games have no underdog.
    """
    out = []
    for g in games:
        line, result = g.get("spread_line"), g.get("result")
        if line is None or result is None or line == 0:
            continue
        home_dog = line < 0
        if (result > 0) != home_dog or result == 0:
            continue
        out.append(
            g
            | {
                "spread": abs(line),
                "underdog": g["home"] if home_dog else g["away"],
                "favorite": g["away"] if home_dog else g["home"],
            }
        )
    out.sort(key=lambda g: (-g["spread"], -abs(g["result"])))
    return out[:n]


def game_summary(g: dict) -> dict | None:
    """Excitement (sum of |change in home WP|) and the winner's lowest WP for one game.

    ``g`` is a games.season_games row (``wp`` = [[elapsed, home_wp], ...]). Regular-season
    games use regulation only (see WP_NOTE). None for games without a WP series; ties get
    no winner and no winner_min_wp.
    """
    regulation_only = g["season_type"] == "REG"
    wp = [
        p[1]
        for p in g.get("wp") or []
        if p[1] is not None and not (regulation_only and p[0] > REGULATION_SECONDS)
    ]
    if len(wp) < 2 or g["home_score"] is None or g["away_score"] is None:
        return None
    excitement = sum(abs(b - a) for a, b in zip(wp, wp[1:], strict=False))
    if g["home_score"] > g["away_score"]:
        winner, winner_min = g["home"], min(wp)
    elif g["away_score"] > g["home_score"]:
        winner, winner_min = g["away"], 1 - max(wp)
    else:
        winner, winner_min = None, None
    return {
        "game_id": g["game_id"],
        "season": g["season"],
        "week": g["week"],
        "season_type": g["season_type"],
        "home": g["home"],
        "away": g["away"],
        "home_score": g["home_score"],
        "away_score": g["away_score"],
        "winner": winner,
        "excitement": excitement,
        "winner_min_wp": winner_min,
    }


def biggest_plays(con: duckdb.DuckDBPyConnection, n: int = BIGGEST_PLAYS) -> list[dict]:
    """Single plays with the largest |WPA| (offense perspective), REG and POST.

    Drops WP artifacts (see WP_NOTE): regular-season overtime, and plays whose
    home_wp_post disagrees with the next play's home_wp (or, for a game's last play,
    with the final result).
    """
    return db.records(
        con,
        f"""
        with ordered as (
            select *,
                   lead(home_wp) over (
                       partition by game_id order by coalesce(order_sequence, play_id), play_id
                   ) as next_home_wp
            from pbp
            where home_wp is not null and play_type is not null
        )
        select o.game_id, o.season, o.week, o.season_type, o.posteam, o.defteam,
               cast(o.qtr as int) as qtr, o.time, o.wpa, o.epa,
               left(o."desc", {DESC_CHARS}) as "desc"
        from ordered o join games g using (game_id)
        where o.wpa is not null and o.posteam is not null and o.play_type is not null
          and o.home_wp_post is not null
          and not (o.season_type = 'REG' and o.qtr >= 5)
          and case when o.next_home_wp is not null
                   then abs(o.home_wp_post - o.next_home_wp) <= {WP_CONSISTENCY}
                   else g.home_score != g.away_score
                        and (o.home_wp_post >= 0.5) = (g.home_score > g.away_score) end
        order by abs(o.wpa) desc, o.game_id, o.play_id
        limit ?
        """,
        [n],
    )


def _schedule_games(con: duckdb.DuckDBPyConnection) -> list[dict]:
    if not db.has_relation(con, "schedule"):
        return []
    return db.records(
        con,
        """
        select game_id, season, week, game_type, home_team as home, away_team as away,
               home_score, away_score, result, spread_line
        from schedule
        where result is not null and spread_line is not null
          and season in (select distinct season from games)
        order by game_id
        """,
    )


def alltime(
    con: duckdb.DuckDBPyConnection,
    *,
    teams: list[dict],
    qbs: list[dict],
    receivers: list[dict],
    rushers: list[dict],
    game_summaries: list[dict],
) -> dict:
    """The records.json payload. Player rows come enriched (full_name, position)."""
    record = wlt(
        db.records(
            con,
            "select season, team, pf, pa from team_games where season_type = 'REG'",
        )
    )
    t = team_rows(teams, record, MIN_TEAM_GAMES)
    qb_fields = [
        "season",
        "player_id",
        "name",
        "full_name",
        "team",
        "dropbacks",
        "epa_db",
        "cpoe",
        "total_epa",
    ]
    qb = [r for r in qbs if r["scope"] == "all" and r["dropbacks"] >= MIN_QB_DROPBACKS]
    rec_fields = [
        "season",
        "player_id",
        "name",
        "full_name",
        "position",
        "team",
        "targets",
        "yards",
        "total_epa",
        "epa_target",
    ]
    rush_fields = [
        "season",
        "player_id",
        "name",
        "full_name",
        "position",
        "team",
        "carries",
        "yards",
        "total_epa",
        "epa_rush",
    ]
    rush = [r for r in rushers if r["carries"] >= MIN_RUSH_CARRIES]
    decided = [g for g in game_summaries if g["winner"] is not None]
    seasons = sorted({r["season"] for r in teams})
    return {
        "seasons": [seasons[0], seasons[-1]] if seasons else None,
        "thresholds": {
            "min_team_games": MIN_TEAM_GAMES,
            "min_qb_dropbacks": MIN_QB_DROPBACKS,
            "min_rush_carries": MIN_RUSH_CARRIES,
        },
        "wp_note": WP_NOTE,
        "team_best": top(t, "net_epa"),
        "team_worst": top(t, "net_epa", lowest=True),
        "offense_best": top(t, "off_epa"),
        "defense_best": top(t, "def_epa", lowest=True),
        "qb_best": pick(top(qb, "epa_db"), qb_fields),
        "qb_worst": pick(top(qb, "epa_db", lowest=True), qb_fields),
        "receiver_best": pick(top(receivers, "total_epa"), rec_fields),
        "rusher_best": pick(top(rush, "total_epa"), rush_fields),
        "upsets": upsets(_schedule_games(con)),
        "excitement": top(game_summaries, "excitement"),
        "comebacks": top(decided, "winner_min_wp", lowest=True),
        "biggest_plays": biggest_plays(con),
    }
