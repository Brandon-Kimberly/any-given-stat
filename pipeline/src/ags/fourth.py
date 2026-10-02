"""An empirical 4th-down decision model: what did each choice actually yield?

Every regular-season 4th down in a competitive game state goes into a situation
bucket (distance x field position). Within a bucket, the mean EPA of going for it,
punting and kicking a field goal over the reference seasons says which choice has
paid off; the best one is the recommendation and its lead over the runner-up is the
margin. Teams are then graded on the EPA they left on the table relative to that
recommendation.

This is descriptive, not causal: coaches go for it more when they expect to
convert, so the "go" means are flattered by selection.
"""

from __future__ import annotations

from collections import defaultdict

import duckdb

from .datasets import bucket_case
from .db import records

DECISIONS = ("go", "punt", "fg")
MIN_N = 25
CLEAR_MARGIN = 0.3
WP_LOW, WP_HIGH = 0.05, 0.95

# (label, ydstogo lower bound, upper bound), in display order.
DISTANCE_BUCKETS = [
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4-5", 4, 5),
    ("6-10", 6, 10),
    ("11+", 11, 99),
]
# (label, yardline_100 lower bound, upper bound), ordered from the offense's own goal line
# toward the opponent's: field_ord 1 = 'Own 1-20', 9 = 'Opp 1-10'.
FIELD_BUCKETS = [
    ("Own 1-20", 80, 99),
    ("Own 21-30", 70, 79),
    ("Own 31-40", 60, 69),
    ("Own 41-49", 51, 59),
    ("Opp 41-50", 41, 50),
    ("Opp 31-40", 31, 40),
    ("Opp 21-30", 21, 30),
    ("Opp 11-20", 11, 20),
    ("Opp 1-10", 1, 10),
]

CAVEAT = (
    "Teams go for it more often when they expect to convert, so the “go” averages are "
    "flattered by selection and the recommendations lean toward going for it."
)


def situations_sql() -> str:
    """4th-down population, one row per play, with its bucket and the decision taken."""
    return f"""
    select game_id, season, posteam as team, epa,
           {bucket_case("ydstogo", DISTANCE_BUCKETS, True)} as distance,
           {bucket_case("ydstogo", DISTANCE_BUCKETS, False)} as dist_ord,
           {bucket_case("yardline_100", FIELD_BUCKETS, True)} as field,
           {bucket_case("yardline_100", FIELD_BUCKETS, False)} as field_ord,
           case play_type when 'punt' then 'punt' when 'field_goal' then 'fg' else 'go' end
               as decision
    from pbp
    where season_type = 'REG' and down = 4 and qtr <= 4 and posteam is not null
      and play_type in ('pass', 'run', 'punt', 'field_goal')
      and wp between {WP_LOW} and {WP_HIGH}
      and epa is not null
      and ydstogo >= 1 and yardline_100 between 1 and 99
    """


def recommend(means: dict[str, float | None]) -> tuple[str | None, float | None]:
    """Best decision (highest non-null mean) and its margin over the runner-up.

    The margin is None when fewer than two decisions have a mean.
    """
    ranked = sorted(((m, d) for d, m in means.items() if m is not None), reverse=True)
    if not ranked:
        return None, None
    best = ranked[0][1]
    margin = ranked[0][0] - ranked[1][0] if len(ranked) > 1 else None
    return best, margin


def bucket_table(rows: list[dict], min_n: int = MIN_N) -> list[dict]:
    """Aggregate per-play rows (distance, field, *_ord, decision, epa) into bucket rows."""
    acc: dict[tuple, dict] = {}
    for r in rows:
        key = (r["dist_ord"], r["field_ord"])
        b = acc.setdefault(
            key,
            {
                "distance": r["distance"],
                "field": r["field"],
                "dist_ord": r["dist_ord"],
                "field_ord": r["field_ord"],
                "sums": defaultdict(float),
                "ns": defaultdict(int),
            },
        )
        b["sums"][r["decision"]] += r["epa"]
        b["ns"][r["decision"]] += 1
    out = []
    for key in sorted(acc):
        b = acc[key]
        sums, ns = b.pop("sums"), b.pop("ns")
        means = {}
        for d in DECISIONS:
            n = ns.get(d, 0)
            means[d] = sums[d] / n if n >= min_n else None
            b[f"{d}_epa"] = means[d]
            b[f"{d}_n"] = n
        b["best"], b["margin"] = recommend(means)
        out.append(b)
    return out


def grade_teams(
    rows: list[dict], buckets: list[dict], clear_margin: float = CLEAR_MARGIN
) -> list[dict]:
    """Per (season, team): go rate, clear-go spots and EPA lost vs the bucket recommendation.

    A play counts toward ``epa_lost`` only when its bucket has a best decision and the
    decision actually taken has a mean too; it adds best mean - chosen mean (>= 0).
    """
    by_key = {(b["dist_ord"], b["field_ord"]): b for b in buckets}
    teams: dict[tuple, dict] = {}
    for r in rows:
        t = teams.setdefault(
            (r["season"], r["team"]),
            {
                "season": r["season"],
                "team": r["team"],
                "fourth_downs": 0,
                "went": 0,
                "clear_go": 0,
                "went_when_clear_go": 0,
                "epa_lost": 0.0,
            },
        )
        t["fourth_downs"] += 1
        went = r["decision"] == "go"
        t["went"] += went
        b = by_key.get((r["dist_ord"], r["field_ord"]))
        if b is None or b["best"] is None:
            continue
        if b["best"] == "go" and b["margin"] is not None and b["margin"] >= clear_margin:
            t["clear_go"] += 1
            t["went_when_clear_go"] += went
        chosen = b[f"{r['decision']}_epa"]
        if chosen is not None:
            t["epa_lost"] += b[f"{b['best']}_epa"] - chosen
    out = [
        {
            "season": t["season"],
            "team": t["team"],
            "fourth_downs": t["fourth_downs"],
            "go_rate": t["went"] / t["fourth_downs"],
            "clear_go": t["clear_go"],
            "went_when_clear_go": t["went_when_clear_go"],
            "epa_lost": t["epa_lost"],
        }
        for t in teams.values()
    ]
    by_season: dict[int, list[dict]] = defaultdict(list)
    for t in out:
        by_season[t["season"]].append(t)
    for season_rows in by_season.values():
        season_rows.sort(key=lambda t: t["epa_lost"])
        for i, t in enumerate(season_rows):
            # Competition ranking: ties share the better rank.
            prev = season_rows[i - 1] if i else None
            same = prev is not None and abs(prev["epa_lost"] - t["epa_lost"]) < 1e-9
            t["rank"] = prev["rank"] if same else i + 1
    out.sort(key=lambda t: (t["season"], t["rank"], t["team"]))
    return out


def fourth_downs(con: duckdb.DuckDBPyConnection, reference_seasons: list[int]) -> dict:
    """Bucket table from ``reference_seasons``; team grades for every loaded season."""
    rows = records(con, situations_sql() + " order by season, team")
    ref = set(reference_seasons)
    buckets = bucket_table([r for r in rows if r["season"] in ref])
    return {
        "buckets": buckets,
        "teams": grade_teams(rows, buckets),
        "meta": {
            "reference_seasons": [min(ref), max(ref)] if ref else None,
            "clear_margin": CLEAR_MARGIN,
            "min_n": MIN_N,
            "caveat": CAVEAT,
        },
    }
