"""Pregame context the team ratings don't see: injuries, schedule spots, travel, weather,
and late-season stakes. Every feature is known before kickoff (see each function), and
every one is a home-minus-away difference or an interaction, so 0 means "no edge".

Weather is the exception that needs saying: nflverse records game-time temperature and wind,
so backtests use what happened, while live predictions use a forecast (``forecast.py``),
which is close but not identical.
"""

from __future__ import annotations

import bisect
from collections import defaultdict

import duckdb
import numpy as np

from .db import has_relation, records
from .ratings import time_index

# ---------------------------------------------------------------- injuries

# Injury report position -> group. QBs are left to the starting-QB adjustment (qb.py);
# kickers, punters and long snappers are ignored.
POSITION_GROUPS = {
    "T": "ol", "G": "ol", "C": "ol", "OT": "ol", "OG": "ol", "OL": "ol",
    "WR": "wr_te", "TE": "wr_te",
    "RB": "rb", "FB": "rb",
    "DE": "front", "DT": "front", "NT": "front", "DL": "front",
    "LB": "front", "OLB": "front", "ILB": "front", "MLB": "front",
    "CB": "db", "S": "db", "FS": "db", "SS": "db", "DB": "db",
}  # fmt: skip
INJURY_GROUPS = ("ol", "wr_te", "rb", "front", "db")
# Chance a listed player sits, fixed in advance rather than fit: Out and Doubtful players
# almost never play; Questionable players usually do.
STATUS_WEIGHT = {"Out": 1.0, "Doubtful": 1.0, "Questionable": 0.25}
ROLE_GAMES = 6  # a player's role = mean snap share over his last 6 games played


def player_impact(history: list[tuple[int, float]], team_games: list[int], t_now: int) -> float:
    """How much of a team's recent play one absent player represents, in starter-equivalents.

    ``history`` = (time index, snap share) for games he played for the team, sorted;
    ``team_games`` = the team's game time indexes, sorted. Impact = role x presence:
    role = mean snap share over his last ``ROLE_GAMES`` games before ``t_now``; presence =
    share of the team's last ``ROLE_GAMES`` games he played. A player already missing for
    weeks has low presence, because the team's recent ratings already reflect his absence.
    """
    i = bisect.bisect_left(history, (t_now, -1.0))
    played = history[max(0, i - ROLE_GAMES) : i]
    if not played:
        return 0.0
    role = sum(s for _, s in played) / len(played)
    j = bisect.bisect_left(team_games, t_now)
    window = team_games[max(0, j - ROLE_GAMES) : j]
    if not window:
        return 0.0
    mine = {t for t, _ in history[:i]}
    presence = sum(t in mine for t in window) / len(window)
    return role * presence


def injury_impacts(
    con: duckdb.DuckDBPyConnection, keys: list[tuple[int, int, str]]
) -> dict[tuple[int, int, str], dict[str, float]]:
    """(season, week, team) -> impact by position group, plus the players behind it.

    Uses that week's injury report (published before the game) and snap counts from
    earlier games only. Empty when the injury or snap data isn't loaded.
    """
    out: dict[tuple[int, int, str], dict] = {}
    if not (has_relation(con, "injuries") and has_relation(con, "snaps")):
        return out
    snap_rows = records(
        con,
        """
        select s.season, s.week, s.team, p.gsis_id,
               greatest(coalesce(s.offense_pct, 0), coalesce(s.defense_pct, 0)) as share
        from snaps s join players p on p.pfr_id = s.pfr_player_id
        where s.game_type = 'REG' and p.gsis_id is not null
        """,
    )
    hist: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
    team_t: dict[str, set[int]] = defaultdict(set)
    ts = time_index(
        np.array([r["season"] for r in snap_rows]), np.array([r["week"] for r in snap_rows])
    )
    for r, t in zip(snap_rows, ts, strict=True):
        if r["share"] > 0:
            hist[(r["gsis_id"], r["team"])].append((int(t), float(r["share"])))
        team_t[r["team"]].add(int(t))
    for v in hist.values():
        v.sort()
    team_games = {k: sorted(v) for k, v in team_t.items()}

    wanted = set(keys)
    reports = records(
        con,
        """
        select season, week, team, gsis_id, full_name, position, report_status
        from injuries
        where game_type = 'REG' and report_status in ('Out', 'Doubtful', 'Questionable')
        """,
    )
    for r in reports:
        key = (int(r["season"]), int(r["week"]), r["team"])
        group = POSITION_GROUPS.get(r["position"] or "")
        if key not in wanted or group is None:
            continue
        t_now = int(time_index(np.array([key[0]]), np.array([key[1]]))[0])
        impact = player_impact(
            hist.get((r["gsis_id"], r["team"]), []), team_games.get(r["team"], []), t_now
        )
        w = STATUS_WEIGHT[r["report_status"]] * impact
        if w <= 0:
            continue
        cur = out.setdefault(key, {g: 0.0 for g in INJURY_GROUPS} | {"players": []})
        cur[group] += w
        if impact >= 0.5:  # list regulars only
            cur["players"].append(
                {
                    "name": r["full_name"],
                    "pos": r["position"],
                    "status": r["report_status"],
                    "impact": round(impact, 2),
                }
            )
    return out


# ---------------------------------------------------------------- travel

# Home time zone offset from Eastern (DST season; Arizona doesn't observe DST, so it matches
# Pacific for most of the season).
TEAM_TZ = {
    "ARI": -3, "LA": -3, "LAC": -3, "LV": -3, "SEA": -3, "SF": -3,
    "DEN": -2,
    "CHI": -1, "DAL": -1, "GB": -1, "HOU": -1, "KC": -1, "MIN": -1, "NO": -1, "TEN": -1,
}  # fmt: skip


def travel(home: str, away: str, home_ind: float, gametime: str | None) -> tuple[float, float]:
    """(time zones crossed by the visitor, west-coast visitor at an early Eastern kickoff).

    Both 0 at neutral sites. ``gametime`` is Eastern 'HH:MM'.
    """
    if not home_ind:
        return 0.0, 0.0
    h, a = TEAM_TZ.get(home, 0), TEAM_TZ.get(away, 0)
    early = 0.0
    if gametime:
        hour = int(str(gametime)[:2])
        early = float(a <= -2 and h - a >= 2 and hour < 14)
    return float(abs(h - a)), early


# ---------------------------------------------------------------- weather


def dome_teams(con: duckdb.DuckDBPyConnection) -> dict[tuple[int, str], bool]:
    """(season, team) -> plays most home games under a roof (dome or closed retractable)."""
    rows = records(
        con,
        """
        select season, home_team as team,
               avg(case when roof in ('dome', 'closed') then 1 else 0 end) as covered
        from schedule where location = 'Home' group by all
        """,
    )
    return {(r["season"], r["team"]): r["covered"] > 0.5 for r in rows}


def weather(roof: str | None, temp: float | None, wind: float | None) -> tuple[float, float, bool]:
    """(wind over 10 mph, degrees below 40 F, outdoors). Missing readings count as calm/mild."""
    outdoors = roof in ("outdoors", "open")
    if not outdoors:
        return 0.0, 0.0, False
    w = max(0.0, float(wind) - 10.0) if wind is not None else 0.0
    c = max(0.0, 40.0 - float(temp)) if temp is not None else 0.0
    return w, c, True


# ---------------------------------------------------------------- stakes


def is_dead(p_playoffs: float, p_division: float, p_bye: float) -> bool:
    """Nothing left to play for: out of the race, or every outcome already settled."""
    settled = lambda p: p < 0.02 or p > 0.98  # noqa: E731
    return p_playoffs < 0.02 or (p_playoffs > 0.98 and settled(p_division) and settled(p_bye))


def stakes(odds: dict[int, dict], season: int, week: int, team: str) -> float:
    """1 if the team still has something to play for in week ``week`` (15+), else 0.

    Uses the playoff-odds state after week - 1 (``sim.py``), so it's known pregame. Before
    week 15, or without odds, every team has stakes.
    """
    if week < 15 or season not in odds:
        return 1.0
    for r in odds[season]["by_team_week"].get((team, week - 1), []):
        return 0.0 if is_dead(r["p_playoffs"], r["p_division"], r["p_bye"]) else 1.0
    return 1.0


def index_odds(payloads: dict[int, dict]) -> dict[int, dict]:
    """Playoff-odds payloads keyed for lookup by (team, week)."""
    out = {}
    for season, p in payloads.items():
        by = defaultdict(list)
        for r in p["rows"]:
            by[(r["team"], r["week"])].append(r)
        out[season] = {"by_team_week": by}
    return out
