"""Each function returns JSON-ready rows for one published dataset.

All rate stats are per-play means over the ``plays`` / ``scoped_plays`` views
(see db.py). Regular season only.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from .config import ONE_SCORE_MARGIN, PYTHAG_EXPONENT
from .db import records

# name -> SQL aggregate over scoped_plays rows for one team on one side of the ball.
TEAM_PLAY_METRICS: dict[str, str] = {
    "plays": "count(*)",
    "epa_play": "avg(epa)",
    "pass_epa": "avg(epa) filter (where pass = 1)",
    "rush_epa": "avg(epa) filter (where rush = 1)",
    "success_rate": "avg(success)",
    "pass_success": "avg(success) filter (where pass = 1)",
    "rush_success": "avg(success) filter (where rush = 1)",
    "pass_rate": "avg(pass)",
    "early_down_pass_rate": "avg(pass) filter (where down in (1, 2))",
    "proe": "avg(pass - xpass) filter (where xpass is not null)",
    "explosive_rate": "avg(explosive)",
    "turnover_rate": "avg(coalesce(interception, 0) + coalesce(fumble_lost, 0))",
    "sack_rate": "avg(sack) filter (where pass = 1)",
    "adot": "avg(air_yards) filter (where pass_attempt = 1 and sack = 0 and air_yards is not null)",
    "third_down_rate": (
        "avg(case when first_down = 1 or touchdown = 1 then 1 else 0 end) filter (where down = 3)"
    ),
}

# Approximate drive points by result (ignores missed PATs / 2-pt tries).
DRIVE_POINTS_SQL = "case result when 'Touchdown' then 7 when 'Field goal' then 3 else 0 end"


def _side_select(side_col: str, prefix: str) -> str:
    aggs = ",\n        ".join(
        f"{expr} as {prefix}{name}" for name, expr in TEAM_PLAY_METRICS.items()
    )
    return f"""
        select scope, season, {side_col} as team,
        {aggs}
        from scoped_plays group by all"""


def team_seasons(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """One row per (scope, season, team) with offense (off_*) and defense (def_*) metrics."""
    sql = f"""
    with off as ({_side_select("posteam", "off_")}),
    def as ({_side_select("defteam", "def_")}),
    drv_off as (
        select season, posteam as team,
               count(*) as off_drives,
               avg({DRIVE_POINTS_SQL}) as off_points_per_drive,
               count(*) filter (where min_yardline_100 <= 20) as off_rz_trips,
               avg(case when result = 'Touchdown' then 1 else 0 end)
                   filter (where min_yardline_100 <= 20) as off_rz_td_rate
        from drives group by all
    ),
    drv_def as (
        select season, defteam as team,
               count(*) as def_drives,
               avg({DRIVE_POINTS_SQL}) as def_points_per_drive,
               count(*) filter (where min_yardline_100 <= 20) as def_rz_trips,
               avg(case when result = 'Touchdown' then 1 else 0 end)
                   filter (where min_yardline_100 <= 20) as def_rz_td_rate
        from drives group by all
    )
    select off.*, def.* exclude (scope, season, team),
           off.off_epa_play - def.def_epa_play as net_epa_play,
           drv_off.* exclude (season, team), drv_def.* exclude (season, team)
    from off
    join def using (scope, season, team)
    left join drv_off using (season, team)
    left join drv_def using (season, team)
    order by scope, season, team
    """
    return records(con, sql)


def team_weeks(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Per team-game offense/defense EPA and score, for trend lines."""
    sql = """
    with off as (
        select season, week, posteam as team, avg(epa) as off_epa, count(*) as off_plays
        from plays group by all
    ),
    def as (
        select season, week, defteam as team, avg(epa) as def_epa, count(*) as def_plays
        from plays group by all
    )
    select tg.season, tg.week, tg.team, tg.opp, tg.pf, tg.pa,
           off.off_epa, off.off_plays, def.def_epa, def.def_plays
    from team_games tg
    join off using (season, week, team)
    join def using (season, week, team)
    where tg.season_type = 'REG'
    order by season, team, week
    """
    return records(con, sql)


def luck(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Record vs Pythagorean expectation, one-score record, fumble recovery and turnover margin."""
    sql = f"""
    with g as (
        select * from team_games where season_type = 'REG' and pf is not null
    ),
    rec as (
        select season, team,
               count(*) as games,
               sum(case when pf > pa then 1 when pf = pa then 0.5 else 0 end) as wins,
               sum(pf) as points_for,
               sum(pa) as points_against,
               count(*) filter (where abs(pf - pa) <= {ONE_SCORE_MARGIN}) as one_score_games,
               sum(case when pf > pa then 1 when pf = pa then 0.5 else 0 end)
                   filter (where abs(pf - pa) <= {ONE_SCORE_MARGIN}) as one_score_wins
        from g group by all
    ),
    fum as (
        select season, team, count(*) as fumbles,
               avg(case when fumble_recovery_1_team = team then 1 else 0 end)
                   as fumble_recovery_rate
        from (
            select season, posteam as team, fumble_recovery_1_team from pbp
            where season_type = 'REG' and fumble = 1 and fumble_recovery_1_team is not null
              and posteam is not null
            union all
            select season, defteam, fumble_recovery_1_team from pbp
            where season_type = 'REG' and fumble = 1 and fumble_recovery_1_team is not null
              and defteam is not null
        ) group by all
    ),
    giveaways as (
        select season, posteam as team,
               sum(coalesce(interception, 0) + coalesce(fumble_lost, 0)) as giveaways
        from plays group by all
    ),
    takeaways as (
        select season, defteam as team,
               sum(coalesce(interception, 0) + coalesce(fumble_lost, 0)) as takeaways
        from plays group by all
    )
    select rec.*,
           pow(points_for, {PYTHAG_EXPONENT})
               / (pow(points_for, {PYTHAG_EXPONENT}) + pow(points_against, {PYTHAG_EXPONENT}))
               * games as pythag_wins,
           wins - pythag_wins as wins_over_pythag,
           fum.fumbles, fum.fumble_recovery_rate,
           takeaways.takeaways, giveaways.giveaways,
           takeaways.takeaways - giveaways.giveaways as turnover_margin
    from rec
    left join fum using (season, team)
    left join giveaways using (season, team)
    left join takeaways using (season, team)
    order by season, team
    """
    return records(con, sql)


def quarterbacks(con: duckdb.DuckDBPyConnection, min_dropbacks: int = 50) -> list[dict]:
    """QB dropback efficiency with a normal-approximation 95% CI on EPA/dropback."""
    sql = """
    with db as (
        select * from scoped_plays where pass = 1 and passer_id is not null
    ),
    runs as (
        select scope, season, rusher_id as player_id,
               count(*) as designed_runs, sum(epa) as designed_run_epa
        from scoped_plays where rush = 1 and rusher_id is not null
        group by all
    ),
    agg as (
        select scope, season, passer_id as player_id,
               mode(passer) as name,
               mode(posteam) as team,
               string_agg(distinct posteam, '/') as teams,
               count(*) as dropbacks,
               avg(qb_epa) as epa_db,
               stddev_samp(qb_epa) as epa_sd,
               sum(qb_epa) as dropback_epa,
               avg(success) as success_rate,
               avg(cpoe) as cpoe,
               avg(air_yards) filter (where sack = 0 and air_yards is not null) as adot,
               avg(sack) as sack_rate,
               avg(qb_scramble) as scramble_rate,
               avg(interception) as int_rate,
               sum(pass_touchdown) as pass_tds,
               sum(interception) as ints,
               sum(passing_yards) as pass_yards,
               avg(pass_oe) filter (where pass_oe is not null) as team_proe
        from db group by all
        having count(*) >= ?
    )
    select agg.*,
           epa_db - 1.96 * epa_sd / sqrt(dropbacks) as epa_db_lo,
           epa_db + 1.96 * epa_sd / sqrt(dropbacks) as epa_db_hi,
           coalesce(runs.designed_runs, 0) as designed_runs,
           coalesce(runs.designed_run_epa, 0) as designed_run_epa,
           dropback_epa + coalesce(runs.designed_run_epa, 0) as total_epa
    from agg left join runs using (scope, season, player_id)
    order by scope, season, epa_db desc
    """
    rows = records(con, sql, [min_dropbacks])
    for r in rows:
        r.pop("epa_sd", None)
        r.pop("team_proe", None)
    return rows


def receivers(con: duckdb.DuckDBPyConnection, min_targets: int = 10) -> list[dict]:
    """Targets per (season, team, player) with usage shares and efficiency over expectation."""
    sql = """
    with t as (
        select * from plays
        where pass = 1 and pass_attempt = 1 and sack = 0 and receiver_id is not null
    ),
    team_tot as (
        select season, posteam, count(*) as team_targets, sum(air_yards) as team_air_yards
        from t group by all
    ),
    agg as (
        select season, posteam, receiver_id as player_id,
               mode(receiver) as name,
               count(*) as targets,
               sum(complete_pass) as receptions,
               coalesce(sum(receiving_yards), 0) as yards,
               sum(pass_touchdown) as tds,
               sum(air_yards) as air_yards,
               avg(air_yards) as adot,
               avg(epa) as epa_target,
               sum(epa) as total_epa,
               avg(success) as success_rate,
               avg(complete_pass - cp) filter (where cp is not null) as catch_rate_oe,
               avg(yards_after_catch - xyac_mean_yardage)
                   filter (where complete_pass = 1 and xyac_mean_yardage is not null) as yac_oe
        from t group by all
        having count(*) >= ?
    )
    select agg.season, agg.posteam as team, agg.* exclude (season, posteam),
           targets / team_targets as target_share,
           air_yards / nullif(team_air_yards, 0) as air_yards_share,
           1.5 * (targets / team_targets) + 0.7 * (air_yards / nullif(team_air_yards, 0)) as wopr
    from agg join team_tot using (season, posteam)
    order by season, total_epa desc
    """
    return records(con, sql, [min_targets])


def rushers(con: duckdb.DuckDBPyConnection, min_carries: int = 20) -> list[dict]:
    """Designed-run efficiency per (season, player). Scrambles are excluded."""
    sql = """
    select season, rusher_id as player_id,
           mode(rusher) as name,
           mode(posteam) as team,
           count(*) as carries,
           sum(yards_gained) as yards,
           sum(rush_touchdown) as tds,
           avg(epa) as epa_rush,
           sum(epa) as total_epa,
           avg(success) as success_rate,
           avg(explosive) as explosive_rate,
           avg(case when yards_gained <= 0 then 1 else 0 end) as stuff_rate,
           avg(yards_gained) as ypc
    from plays
    where rush = 1 and rusher_id is not null
    group by all
    having count(*) >= ?
    order by season, total_epa desc
    """
    return records(con, sql, [min_carries])


@dataclass(frozen=True)
class StabilityMetric:
    key: str
    label: str
    group: str  # "team offense", "team defense", "team luck", "player"
    unit: str  # SQL expression for the entity (team or player id)
    x: str  # SQL expression for the per-row value; the metric is mean(x)
    source: str  # relation the rows come from
    where: str = "true"
    min_half: int = 1  # minimum rows per half for a split-half pair
    min_season: int = 1  # minimum rows per season for a year-over-year pair
    denominator: str = "plays"


NG = "no_garbage"
STABILITY_METRICS: list[StabilityMetric] = [
    StabilityMetric("off_epa", "Offense EPA/play", "team offense", "posteam", "epa", "plays", NG),
    StabilityMetric(
        "off_pass_epa",
        "Offense pass EPA/play",
        "team offense",
        "posteam",
        "epa",
        "plays",
        f"{NG} and pass = 1",
        denominator="dropbacks",
    ),
    StabilityMetric(
        "off_rush_epa",
        "Offense rush EPA/play",
        "team offense",
        "posteam",
        "epa",
        "plays",
        f"{NG} and rush = 1",
        denominator="rushes",
    ),
    StabilityMetric(
        "off_success", "Offense success rate", "team offense", "posteam", "success", "plays", NG
    ),
    StabilityMetric(
        "off_proe",
        "Pass rate over expected",
        "team offense",
        "posteam",
        "pass - xpass",
        "plays",
        f"{NG} and xpass is not null",
    ),
    StabilityMetric(
        "off_third_down",
        "3rd down conversion rate",
        "team offense",
        "posteam",
        "case when first_down = 1 or touchdown = 1 then 1 else 0 end",
        "plays",
        f"{NG} and down = 3",
        denominator="3rd downs",
    ),
    StabilityMetric(
        "off_turnover",
        "Offense turnover rate",
        "team offense",
        "posteam",
        "coalesce(interception, 0) + coalesce(fumble_lost, 0)",
        "plays",
        NG,
    ),
    StabilityMetric(
        "off_rz_td",
        "Red zone TD rate",
        "team offense",
        "posteam",
        "case when result = 'Touchdown' then 1 else 0 end",
        "drives",
        "min_yardline_100 <= 20",
        denominator="red zone trips",
    ),
    StabilityMetric("def_epa", "Defense EPA/play", "team defense", "defteam", "epa", "plays", NG),
    StabilityMetric(
        "def_pass_epa",
        "Defense pass EPA/play",
        "team defense",
        "defteam",
        "epa",
        "plays",
        f"{NG} and pass = 1",
        denominator="dropbacks",
    ),
    StabilityMetric(
        "def_rush_epa",
        "Defense rush EPA/play",
        "team defense",
        "defteam",
        "epa",
        "plays",
        f"{NG} and rush = 1",
        denominator="rushes",
    ),
    StabilityMetric(
        "def_takeaway",
        "Defense takeaway rate",
        "team defense",
        "defteam",
        "coalesce(interception, 0) + coalesce(fumble_lost, 0)",
        "plays",
        NG,
    ),
    StabilityMetric(
        "fumble_recovery",
        "Fumble recovery rate",
        "team luck",
        "team",
        "case when fumble_recovery_1_team = team then 1 else 0 end",
        "fumble_rows",
        denominator="fumbles",
    ),
    StabilityMetric(
        "qb_epa",
        "QB EPA/dropback",
        "player",
        "passer_id",
        "qb_epa",
        "plays",
        f"{NG} and pass = 1 and passer_id is not null",
        min_half=100,
        min_season=250,
        denominator="dropbacks",
    ),
    StabilityMetric(
        "qb_cpoe",
        "QB CPOE",
        "player",
        "passer_id",
        "cpoe",
        "plays",
        f"{NG} and cpoe is not null and passer_id is not null",
        min_half=100,
        min_season=250,
        denominator="attempts",
    ),
    StabilityMetric(
        "qb_sack_rate",
        "QB sack rate",
        "player",
        "passer_id",
        "sack",
        "plays",
        f"{NG} and pass = 1 and passer_id is not null",
        min_half=100,
        min_season=250,
        denominator="dropbacks",
    ),
    StabilityMetric(
        "qb_int_rate",
        "QB interception rate",
        "player",
        "passer_id",
        "interception",
        "plays",
        f"{NG} and pass = 1 and passer_id is not null",
        min_half=100,
        min_season=250,
        denominator="dropbacks",
    ),
    StabilityMetric(
        "rb_epa",
        "Rusher EPA/carry",
        "player",
        "rusher_id",
        "epa",
        "plays",
        f"{NG} and rush = 1 and rusher_id is not null",
        min_half=50,
        min_season=120,
        denominator="carries",
    ),
    StabilityMetric(
        "rb_success",
        "Rusher success rate",
        "player",
        "rusher_id",
        "success",
        "plays",
        f"{NG} and rush = 1 and rusher_id is not null",
        min_half=50,
        min_season=120,
        denominator="carries",
    ),
    StabilityMetric(
        "wr_epa_target",
        "Receiver EPA/target",
        "player",
        "receiver_id",
        "epa",
        "plays",
        f"{NG} and pass = 1 and sack = 0 and receiver_id is not null",
        min_half=30,
        min_season=60,
        denominator="targets",
    ),
]

FUMBLE_ROWS_SQL = """
create or replace temp view fumble_rows as
select season, week, posteam as team, fumble_recovery_1_team from pbp
where season_type = 'REG' and fumble = 1 and fumble_recovery_1_team is not null
  and posteam is not null
union all
select season, week, defteam, fumble_recovery_1_team from pbp
where season_type = 'REG' and fumble = 1 and fumble_recovery_1_team is not null
  and defteam is not null
"""


def stability(con: duckdb.DuckDBPyConnection, seasons: list[int]) -> dict:
    """Split-half (odd vs even weeks) and year-over-year reliability for each metric.

    ``seasons`` should contain only complete seasons. Returns summary rows plus
    the raw year-over-year pairs so the site can draw Year N vs Year N+1 scatters.

    Reliability math: if r is the correlation between two halves of n rows each,
    the Spearman-Brown full-season reliability is 2r / (1 + r), and the sample
    size at which reliability reaches 0.5 is n * (1 - r) / r.
    """
    con.execute(FUMBLE_ROWS_SQL)
    season_list = ", ".join(str(s) for s in seasons) or "null"
    summary: list[dict] = []
    pairs: dict[str, list[dict]] = {}
    for m in STABILITY_METRICS:
        base = f"""
        with r as (
            select season, week, {m.unit} as unit, ({m.x})::double as x
            from {m.source}
            where ({m.where}) and season in ({season_list}) and ({m.x}) is not null
        ),
        half as (
            select season, unit, week % 2 as h, avg(x) as m, count(*) as n from r group by all
        ),
        split as (
            select a.m as odd, b.m as even, (a.n + b.n) / 2.0 as n
            from half a join half b using (season, unit)
            where a.h = 1 and b.h = 0 and a.n >= {m.min_half} and b.n >= {m.min_half}
        ),
        full_season as (
            select season, unit, avg(x) as m, count(*) as n from r group by all
            having count(*) >= {m.min_season}
        ),
        yoy as (
            select a.unit, a.season, a.m as y1, b.m as y2
            from full_season a join full_season b
              on a.unit = b.unit and b.season = a.season + 1
        )
        """
        stats = records(
            con,
            base
            + """
            select (select corr(odd, even) from split) as split_half_r,
                   (select count(*) from split) as split_half_pairs,
                   (select avg(n) from split) as avg_half_n,
                   (select corr(y1, y2) from yoy) as yoy_r,
                   (select count(*) from yoy) as yoy_pairs,
                   (select avg(n) from full_season) as avg_season_n
            """,
        )[0]
        r = stats["split_half_r"]
        if r is not None and r > 0:
            stats["full_season_reliability"] = 2 * r / (1 + r)
            stats["n_for_half_signal"] = stats["avg_half_n"] * (1 - r) / r
        else:
            stats["full_season_reliability"] = None
            stats["n_for_half_signal"] = None
        summary.append(
            {"key": m.key, "label": m.label, "group": m.group, "denominator": m.denominator} | stats
        )
        pairs[m.key] = records(
            con, base + "select unit, season, y1, y2 from yoy order by season, unit"
        )
    return {"metrics": summary, "yoy_pairs": pairs}


EXPLORER_COLUMNS = [
    "game_id",
    "season",
    "season_type",
    "week",
    "game_date",
    "home_team",
    "away_team",
    "posteam",
    "defteam",
    "qtr",
    "down",
    "ydstogo",
    "yardline_100",
    "goal_to_go",
    "game_seconds_remaining",
    "half_seconds_remaining",
    "score_differential",
    "wp",
    "vegas_wp",
    "play_type",
    "pass",
    "rush",
    "qb_dropback",
    "qb_scramble",
    "shotgun",
    "no_huddle",
    "pass_length",
    "pass_location",
    "air_yards",
    "yards_after_catch",
    "run_location",
    "run_gap",
    "yards_gained",
    "epa",
    "wpa",
    "success",
    "first_down",
    "touchdown",
    "pass_touchdown",
    "rush_touchdown",
    "interception",
    "fumble_lost",
    "sack",
    "complete_pass",
    "penalty",
    "penalty_type",
    "cp",
    "cpoe",
    "xpass",
    "pass_oe",
    "xyac_mean_yardage",
    "qb_epa",
    "passer_id",
    "passer",
    "receiver_id",
    "receiver",
    "rusher_id",
    "rusher",
    "fixed_drive",
    "fixed_drive_result",
    "series_success",
    "roof",
    "surface",
    "temp",
    "wind",
    "spread_line",
    "total_line",
    "div_game",
    "desc",
]


def export_explorer_parquet(con: duckdb.DuckDBPyConnection, season: int, dest: str) -> None:
    """Slim, per-season play-by-play for the in-browser SQL explorer."""
    available = {r[0] for r in con.execute("describe pbp").fetchall()}
    cols = ", ".join(f'"{c}"' for c in EXPLORER_COLUMNS if c in available)
    con.execute(
        f"copy (select {cols} from pbp where season = {int(season)} "
        f"and play_type is not null order by game_id, play_id) "
        f"to '{dest}' (format parquet, compression zstd, row_group_size 20000)"
    )


# (split, bucket expression, sort-order expression). Score buckets use the side's own margin.
SPLITS = [
    (
        "Down",
        "cast(down as int)::varchar || case cast(down as int) when 1 then 'st' "
        "when 2 then 'nd' when 3 then 'rd' else 'th' end || ' down'",
        "down",
    ),
    (
        "Field position",
        "case when yardline_100 >= 80 then 'Own 1-20' when yardline_100 >= 50 then 'Own 21-50' "
        "when yardline_100 > 20 then 'Opp 49-21' else 'Red zone' end",
        "-yardline_100",
    ),
    ("Quarter", "'Q' || cast(qtr as int)", "qtr"),
    (
        "Score",
        "case when margin <= -9 then 'Down 9+' when margin < 0 then 'Down 1-8' "
        "when margin = 0 then 'Tied' when margin <= 8 then 'Up 1-8' else 'Up 9+' end",
        "margin",
    ),
    (
        "Play type",
        "case when down in (1, 2) then 'Early down' else 'Late down' end "
        "|| case when pass = 1 then ' pass' else ' run' end",
        "case when down in (1, 2) then 0 else 2 end + case when pass = 1 then 0 else 1 end",
    ),
]


def team_splits(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Team EPA/play and success rate by situation, offense and defense, with league rank.

    All plays (garbage time included) so score-state splits keep the lopsided buckets.
    Regulation only: overtime samples are a handful of plays.
    Rank 1 = best: highest EPA on offense, lowest EPA allowed on defense.
    """
    parts = []
    for side, team_col, margin in (
        ("off", "posteam", "score_differential"),
        ("def", "defteam", "-score_differential"),
    ):
        for split, bucket, order in SPLITS:
            parts.append(f"""
                select season, {team_col} as team, '{side}' as side, '{split}' as split,
                       {bucket} as bucket, min({order}) as ord,
                       count(*) as plays, avg(epa) as epa, avg(success) as success
                from (
                    select *, {margin} as margin from plays where down is not null and qtr <= 4
                )
                group by season, {team_col}, {bucket}""")
    sql = f"""
    with s as ({" union all ".join(parts)}),
    bucket_order as (
        select split, bucket, dense_rank() over (partition by split order by min(ord)) as ord
        from s group by split, bucket
    )
    select season, team, side, split, bucket, plays, epa, success,
           rank() over (
               partition by season, side, split, bucket
               order by case when side = 'off' then -epa else epa end
           ) as rank,
           bucket_order.ord
    from s join bucket_order using (split, bucket)
    order by season, team, side, split, bucket_order.ord
    """
    return records(con, sql)
