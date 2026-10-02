"""Head coaches and referees: coaches.json and referees.json.

Both come from the nflverse schedule (``home_coach`` / ``away_coach``, ``referee``) joined
to play-by-play aggregates per game. Regular season only. Without the schedule view the
payloads are empty.
"""

from __future__ import annotations

from collections import defaultdict

import duckdb

from . import fourth
from .db import has_relation, records

NEUTRAL_WP = (0.2, 0.8)

COACH_GAMES_SQL = """
with g as (
    select * from schedule
    where game_type = 'REG' and result is not null
      and game_id in (select game_id from games)
)
select game_id, season, week, home_team as team, home_coach as coach,
       home_score as pf, away_score as pa, spread_line as line
from g
union all
select game_id, season, week, away_team, away_coach, away_score, home_score, -spread_line
from g
order by season, week, game_id
"""

# Per (game, team): no-garbage EPA on both sides and neutral-situation pass rate over
# expected (as a fraction: mean of pass - xpass, i.e. nflverse pass_oe / 100).
COACH_PLAYS_SQL = f"""
with off as (
    select game_id, posteam as team,
           sum(epa) filter (where no_garbage) as off_epa,
           count(*) filter (where no_garbage) as off_plays,
           sum(pass - xpass) filter (
               where xpass is not null and down in (1, 2)
                 and wp between {NEUTRAL_WP[0]} and {NEUTRAL_WP[1]}
           ) as proe_sum,
           count(*) filter (
               where xpass is not null and down in (1, 2)
                 and wp between {NEUTRAL_WP[0]} and {NEUTRAL_WP[1]}
           ) as proe_n
    from plays group by all
),
def as (
    select game_id, defteam as team,
           sum(epa) filter (where no_garbage) as def_epa,
           count(*) filter (where no_garbage) as def_plays
    from plays group by all
)
select * from off full join def using (game_id, team)
"""


def ats(margin: float, line: float | None) -> str | None:
    """Against the spread from one team's side: ``line`` is its expected margin (the
    schedule's home ``spread_line``, negated for the away team). 'w', 'l', 'p' or None."""
    if line is None:
        return None
    if margin > line:
        return "w"
    if margin < line:
        return "l"
    return "p"


def clear_go_counts(
    rows: list[dict], buckets: list[dict], clear_margin: float = fourth.CLEAR_MARGIN
) -> dict[tuple[str, str], list[int]]:
    """(game_id, team) -> [clear-go spots, went for it there], using fourth.py buckets."""
    by_key = {(b["dist_ord"], b["field_ord"]): b for b in buckets}
    out: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        b = by_key.get((r["dist_ord"], r["field_ord"]))
        if b is None or b["best"] != "go" or b["margin"] is None or b["margin"] < clear_margin:
            continue
        c = out[(r["game_id"], r["team"])]
        c[0] += 1
        c[1] += r["decision"] == "go"
    return out


SUM_FIELDS = (
    "games",
    "wins",
    "losses",
    "ties",
    "ats_w",
    "ats_l",
    "ats_push",
    "point_diff",
    "off_epa",
    "off_plays",
    "def_epa",
    "def_plays",
    "clear_go",
    "went_clear_go",
    "proe_sum",
    "proe_n",
)


def coach_game_rows(games: list[dict], plays: dict, clear_go: dict) -> list[dict]:
    """One row per (game, team, coach) with additive fields (SUM_FIELDS)."""
    out = []
    for g in games:
        if not g["coach"]:
            continue
        key = (g["game_id"], g["team"])
        p = plays.get(key, {})
        cg = clear_go.get(key, (0, 0))
        margin = g["pf"] - g["pa"]
        a = ats(margin, g["line"])
        out.append(
            {
                "coach": g["coach"],
                "season": g["season"],
                "team": g["team"],
                "games": 1,
                "wins": int(margin > 0),
                "losses": int(margin < 0),
                "ties": int(margin == 0),
                "ats_w": int(a == "w"),
                "ats_l": int(a == "l"),
                "ats_push": int(a == "p"),
                "point_diff": margin,
                "off_epa": p.get("off_epa") or 0.0,
                "off_plays": p.get("off_plays") or 0,
                "def_epa": p.get("def_epa") or 0.0,
                "def_plays": p.get("def_plays") or 0,
                "clear_go": cg[0],
                "went_clear_go": cg[1],
                "proe_sum": p.get("proe_sum") or 0.0,
                "proe_n": p.get("proe_n") or 0,
            }
        )
    return out


def _ratio(num, den):
    return num / den if den else None


def _finish_coach(acc: dict) -> dict:
    """Turn summed fields into the published rates."""
    out = {k: v for k, v in acc.items() if k not in SUM_FIELDS}
    for k in ("games", "wins", "losses", "ties", "ats_w", "ats_l", "ats_push", "point_diff"):
        out[k] = acc[k]
    out["clear_go"] = acc["clear_go"]
    off = _ratio(acc["off_epa"], acc["off_plays"])
    deff = _ratio(acc["def_epa"], acc["def_plays"])
    out["net_epa"] = None if off is None or deff is None else off - deff
    out["go_rate_clear"] = _ratio(acc["went_clear_go"], acc["clear_go"])
    out["proe"] = _ratio(acc["proe_sum"], acc["proe_n"])
    return out


def _sum_into(acc: dict, row: dict) -> None:
    for k in SUM_FIELDS:
        acc[k] = acc.get(k, 0) + row[k]


def coach_seasons(rows: list[dict]) -> list[dict]:
    """Aggregate coach_game_rows by (coach, season, team)."""
    acc: dict[tuple, dict] = {}
    for r in rows:
        a = acc.setdefault(
            (r["coach"], r["season"], r["team"]),
            {"coach": r["coach"], "season": r["season"], "team": r["team"]},
        )
        _sum_into(a, r)
    out = [_finish_coach(a) for a in acc.values()]
    out.sort(key=lambda r: (r["season"], r["team"], r["coach"]))
    return out


def coach_careers(rows: list[dict]) -> list[dict]:
    """Aggregate coach_game_rows (in chronological order) by coach."""
    acc: dict[str, dict] = {}
    for r in rows:
        a = acc.setdefault(r["coach"], {"coach": r["coach"], "_seasons": set(), "_teams": []})
        _sum_into(a, r)
        a["_seasons"].add(r["season"])
        if r["team"] not in a["_teams"]:
            a["_teams"].append(r["team"])
    out = []
    for a in acc.values():
        seasons, teams = a.pop("_seasons"), a.pop("_teams")
        row = _finish_coach(a)
        decided = row["ats_w"] + row["ats_l"]
        out.append(
            row
            | {
                "seasons": len(seasons),
                "teams": "/".join(teams),
                "win_pct": (row["wins"] + 0.5 * row["ties"]) / row["games"],
                "ats_pct": _ratio(row["ats_w"], decided),
                "first": min(seasons),
                "last": max(seasons),
            }
        )
    out.sort(key=lambda r: (-r["games"], r["coach"]))
    return out


def coaches(con: duckdb.DuckDBPyConnection, fourth_buckets: list[dict]) -> dict:
    """coaches.json: per coach-season-team rows and career totals.

    ``fourth_buckets`` is fourth_downs()["buckets"], so "clear go" means the same thing
    as on the 4th-down page.
    """
    if not has_relation(con, "schedule"):
        return {"seasons": [], "careers": []}
    games = records(con, COACH_GAMES_SQL)
    plays = {(r["game_id"], r["team"]): r for r in records(con, COACH_PLAYS_SQL)}
    clear_go = clear_go_counts(records(con, fourth.situations_sql()), fourth_buckets)
    rows = coach_game_rows(games, plays, clear_go)
    return {"seasons": coach_seasons(rows), "careers": coach_careers(rows)}


REFEREE_GAMES_SQL = """
with pen as (
    select game_id,
           count(*) as penalties,
           sum(coalesce(penalty_yards, 0)) as penalty_yards,
           count(penalty_team) as team_penalties,
           count(*) filter (where penalty_team = home_team) as home_penalties
    from pbp
    where season_type = 'REG' and penalty = 1
    group by game_id
)
select s.referee, s.season, s.game_id, s.result, s.home_score + s.away_score as points,
       coalesce(pen.penalties, 0) as penalties,
       coalesce(pen.penalty_yards, 0) as penalty_yards,
       coalesce(pen.team_penalties, 0) as team_penalties,
       coalesce(pen.home_penalties, 0) as home_penalties
from schedule s left join pen using (game_id)
where s.game_type = 'REG' and s.result is not null and s.referee is not null
  and s.game_id in (select game_id from games)
order by s.season, s.week, s.game_id
"""


def referee_rows(games: list[dict], by_season: bool) -> list[dict]:
    """Aggregate per-game referee rows by (referee, season) or by referee (careers)."""
    acc: dict[tuple, dict] = {}
    for g in games:
        key = (g["referee"], g["season"]) if by_season else (g["referee"],)
        a = acc.setdefault(
            key,
            {
                "referee": g["referee"],
                "seasons": set(),
                "games": 0,
                "penalties": 0,
                "penalty_yards": 0,
                "team_penalties": 0,
                "home_penalties": 0,
                "home_wins": 0.0,
                "points": 0,
            },
        )
        a["seasons"].add(g["season"])
        a["games"] += 1
        for k in ("penalties", "penalty_yards", "team_penalties", "home_penalties", "points"):
            a[k] += g[k]
        a["home_wins"] += 1.0 if g["result"] > 0 else 0.5 if g["result"] == 0 else 0.0
    out = []
    for a in acc.values():
        n = a["games"]
        row = {"referee": a["referee"]}
        if by_season:
            row["season"] = min(a["seasons"])
        row |= {
            "games": n,
            "penalties_pg": a["penalties"] / n,
            "penalty_yards_pg": a["penalty_yards"] / n,
            "home_penalty_share": _ratio(a["home_penalties"], a["team_penalties"]),
            "home_win_pct": a["home_wins"] / n,
            "points_pg": a["points"] / n,
        }
        if not by_season:
            row |= {
                "seasons": len(a["seasons"]),
                "first": min(a["seasons"]),
                "last": max(a["seasons"]),
            }
        out.append(row)
    if by_season:
        out.sort(key=lambda r: (r["season"], r["referee"]))
    else:
        out.sort(key=lambda r: (-r["games"], r["referee"]))
    return out


def referees(con: duckdb.DuckDBPyConnection) -> dict:
    """referees.json: per referee-season rows and career totals."""
    if not has_relation(con, "schedule"):
        return {"seasons": [], "careers": []}
    games = records(con, REFEREE_GAMES_SQL)
    return {"seasons": referee_rows(games, True), "careers": referee_rows(games, False)}
