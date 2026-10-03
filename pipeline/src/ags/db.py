"""DuckDB connection and the canonical filtered views every dataset builds on.

The filter definitions live here and nowhere else. If you change one, update
CLAUDE.md ("Stat definitions") in the same commit.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import duckdb

from .config import GARBAGE_WP_HIGH, GARBAGE_WP_LOW

VIEWS_SQL = f"""
-- Scrimmage plays, regular season AND postseason: designed runs, dropbacks (incl. sacks and
-- scrambles). Excludes kneels, spikes, special teams and penalty-nullified plays ('no_play').
-- Only per-game postseason views (game pages) use this directly; metrics use ``plays``.
create or replace view scrimmage_plays as
select
    *,
    (wp between {GARBAGE_WP_LOW} and {GARBAGE_WP_HIGH}) as no_garbage,
    case
        when (pass = 1 and yards_gained >= 20) or (rush = 1 and yards_gained >= 10) then 1
        else 0
    end as explosive
from pbp
where play_type in ('pass', 'run')
  and epa is not null
  and posteam is not null;

-- The canonical play set: regular-season scrimmage plays.
create or replace view plays as
select * from scrimmage_plays where season_type = 'REG';

-- Every play twice-filtered: scope 'all' and scope 'no_garbage'. Datasets group by scope.
create or replace view scoped_plays as
select 'all' as scope, * from plays
union all
select 'no_garbage' as scope, * from plays where no_garbage;

-- One row per regular-season drive, attributed to both offense and defense.
create or replace view drives as
select
    season,
    week,
    game_id,
    posteam,
    defteam,
    fixed_drive,
    min(yardline_100) as min_yardline_100,
    any_value(fixed_drive_result) as result
from pbp
where season_type = 'REG'
  and posteam is not null
  and fixed_drive is not null
  and play_type in ('pass', 'run', 'field_goal', 'punt', 'qb_kneel', 'qb_spike', 'no_play')
group by all;

-- One row per game with the final score.
create or replace view games as
select
    game_id,
    any_value(season) as season,
    any_value(week) as week,
    any_value(season_type) as season_type,
    any_value(home_team) as home_team,
    any_value(away_team) as away_team,
    max(home_score) as home_score,
    max(away_score) as away_score
from pbp
group by game_id;

-- Each game from each team's perspective.
create or replace view team_games as
select game_id, season, week, season_type, home_team as team, away_team as opp,
       home_score as pf, away_score as pa
from games
union all
select game_id, season, week, season_type, away_team, home_team, away_score, home_score
from games;
"""


SCHEDULE_COLUMNS = """
    game_id, season, game_type, week, gameday, home_team, away_team, home_score, away_score,
    result, spread_line, total_line, location, home_qb_id, away_qb_id, home_qb_name,
    away_qb_name, home_rest, away_rest, div_game, home_coach, away_coach, referee,
    roof, temp, wind, gametime, stadium
"""

# nflverse schedules keep historical abbreviations; play-by-play uses current ones.
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def connect(
    pbp_files: Sequence[Path],
    schedule_file: Path | None = None,
    teams_file: Path | None = None,
    players_file: Path | None = None,
    player_ids_file: Path | None = None,
    injury_files: Sequence[Path] = (),
    snap_files: Sequence[Path] = (),
    depth_chart: tuple[int, Path | None] | None = None,
) -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with ``pbp`` plus derived views.

    Optional reference views, created only when their file is given: ``schedule``
    (nflverse games.csv), ``team_colors`` (teams_colors_logos.csv) and ``players``
    (players.parquet, keyed by ``gsis_id``), ``injuries`` (weekly injury reports, gsis ids)
    and ``snaps`` (per-game snap shares, pfr ids; team codes aliased like the schedule).
    ``depth_chart`` = (season, depth_charts parquet): for that season's unplayed games the
    schedule's QBs become the projected starters (see ``_project_starters``).
    """
    con = duckdb.connect()
    files = ", ".join(f"'{p.as_posix()}'" for p in pbp_files)
    con.execute(f"create view pbp as select * from read_parquet([{files}], union_by_name = true)")
    if schedule_file is not None:
        alias = " ".join(f"when '{a}' then '{b}'" for a, b in TEAM_ALIASES.items())
        con.execute(f"""
            create view schedule_listed as
            select * replace (
                case home_team {alias} else home_team end as home_team,
                case away_team {alias} else away_team end as away_team
            )
            from (
                select {SCHEDULE_COLUMNS}
                from read_csv('{schedule_file.as_posix()}', header = true, sample_size = -1)
            )
        """)
    if teams_file is not None:
        con.execute(f"""
            create view team_colors as
            select * from read_csv('{teams_file.as_posix()}', header = true, all_varchar = true)
        """)
    if players_file is not None:
        con.execute(
            f"create view players as select * from read_parquet('{players_file.as_posix()}')"
        )
    if player_ids_file is not None:
        con.execute(f"""
            create view player_ids as
            select * from read_csv('{player_ids_file.as_posix()}', header = true,
                                   all_varchar = true, nullstr = 'NA')
        """)
    alias = " ".join(f"when '{a}' then '{b}'" for a, b in TEAM_ALIASES.items())
    if injury_files:
        files = ", ".join(f"'{p.as_posix()}'" for p in injury_files)
        con.execute(f"""
            create view injuries as
            select season, game_type, case team {alias} else team end as team, week, gsis_id,
                   trim(position) as position, full_name, report_status, practice_status
            from read_parquet([{files}], union_by_name = true)
        """)
    if snap_files:
        files = ", ".join(f"'{p.as_posix()}'" for p in snap_files)
        con.execute(f"""
            create view snaps as
            select game_id, season, game_type, week, player, pfr_player_id, position,
                   case team {alias} else team end as team,
                   offense_pct, defense_pct
            from read_parquet([{files}], union_by_name = true)
        """)
    if schedule_file is not None:
        _project_starters(con, depth_chart)
    install_views(con)
    return con


def _project_starters(
    con: duckdb.DuckDBPyConnection, depth_chart: tuple[int, Path | None] | None
) -> None:
    """``schedule`` = nflverse's schedule, but with projected starting QBs in unplayed games.

    nflverse fills future games with each team's most recent starter, so a starter back from
    injury stays listed as his backup (SEA 2026: Lock after two Darnold absences). Rule, per
    unplayed game: the latest depth-chart QB1 starts unless the team's latest injury report
    (that week's, or the last one before it) has him Out or Doubtful; then the most recent
    actual starter (nflverse's listing) if he isn't ruled out too; else the highest-ranked QB
    who is. Played games keep the QBs who actually started, so every backtest is unchanged.
    """
    if depth_chart is None or depth_chart[1] is None:
        con.execute("create view schedule as select * from schedule_listed")
        return
    season, path = depth_chart
    alias = " ".join(f"when '{a}' then '{b}'" for a, b in TEAM_ALIASES.items())
    if has_relation(con, "injuries"):
        con.execute("""
            create view qb_reports as
            select season, team, week, gsis_id, report_status from injuries
        """)
    else:
        con.execute("""
            create view qb_reports as
            select null::int as season, null::varchar as team, null::int as week,
                   null::varchar as gsis_id, null::varchar as report_status
            where false
        """)
    con.execute(f"""
        create view qb_depth as
        with d as (
            select case team {alias} else team end as team, dt, gsis_id, player_name, pos_rank
            from read_parquet('{path.as_posix()}')
            where pos_abb = 'QB'
        )
        select d.* exclude (dt) from d
        join (select team, max(dt) as dt from d group by team) latest using (team, dt)
    """)
    con.execute(f"""
        create view schedule as
        with started as (  -- each team's QB in its latest played game
            select team, arg_max(qb, gameday) as qb from (
                select home_team as team, home_qb_id as qb, gameday from schedule_listed
                where season = {int(season)} and result is not null
                union all
                select away_team, away_qb_id, gameday from schedule_listed
                where season = {int(season)} and result is not null
            ) group by team
        ),
        sides as (
            select x.game_id, x.season, x.week, x.team, coalesce(x.listed, st.qb) as listed
            from (
                select game_id, season, week, home_team as team, home_qb_id as listed
                from schedule_listed where season = {int(season)} and result is null
                union all
                select game_id, season, week, away_team, away_qb_id
                from schedule_listed where season = {int(season)} and result is null
            ) x
            left join started st using (team)
        ),
        -- The team's latest injury report up to the game's week (next week's posts midweek,
        -- so a player out last week stays out until a newer report clears him).
        report as (
            select s.game_id, s.team, max(r.week) as week
            from sides s
            join qb_reports r on r.season = s.season and r.team = s.team and r.week <= s.week
            group by all
        ),
        ruled_out as (
            select rp.game_id, r.gsis_id
            from report rp
            join sides s using (game_id, team)
            join qb_reports r on r.season = s.season and r.team = s.team and r.week = rp.week
            where r.report_status in ('Out', 'Doubtful')
        ),
        depth as (
            select s.game_id, s.team, s.listed, d.gsis_id, d.player_name, d.pos_rank,
                   o.gsis_id is not null as is_out,
                   lo.gsis_id is not null as listed_out
            from sides s
            join qb_depth d on d.team = s.team
            left join (select distinct * from ruled_out) o
                on o.game_id = s.game_id and o.gsis_id = d.gsis_id
            left join (select distinct * from ruled_out) lo
                on lo.game_id = s.game_id and lo.gsis_id = s.listed
        ),
        pick as (
            select game_id, team,
                   arg_min(gsis_id, pos_rank) as qb1_id,
                   arg_min(player_name, pos_rank) as qb1_name,
                   arg_min(is_out, pos_rank) as qb1_out,
                   bool_or(listed_out) as listed_out,
                   any_value(listed) as listed,
                   arg_min(gsis_id, pos_rank) filter (where not is_out) as next_id,
                   arg_min(player_name, pos_rank) filter (where not is_out) as next_name
            from depth group by all
        ),
        projected as (
            select game_id, team,
                   case when not qb1_out then qb1_id
                        -- else the last starter, when he isn't ruled out
                        when listed is not null and not listed_out then listed
                        else next_id end as qb_id,
                   case when not qb1_out then qb1_name
                        when listed is not null and not listed_out then (
                            select any_value(player_name) from qb_depth d
                            where d.team = pick.team and d.gsis_id = pick.listed
                        )
                        else next_name end as qb_name
            from pick
        )
        select s.* replace (
            coalesce(h.qb_id, s.home_qb_id) as home_qb_id,
            case when h.qb_id is null or h.qb_id = s.home_qb_id
                 then coalesce(s.home_qb_name, h.qb_name) else h.qb_name end as home_qb_name,
            coalesce(a.qb_id, s.away_qb_id) as away_qb_id,
            case when a.qb_id is null or a.qb_id = s.away_qb_id
                 then coalesce(s.away_qb_name, a.qb_name) else a.qb_name end as away_qb_name
        )
        from schedule_listed s
        left join projected h on h.game_id = s.game_id and h.team = s.home_team
        left join projected a on a.game_id = s.game_id and a.team = s.away_team
    """)


def has_relation(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    """Whether a table or view called ``name`` exists (optional reference data)."""
    return bool(
        con.execute(
            "select count(*) from information_schema.tables where table_name = ?", [name]
        ).fetchone()[0]
    )


def install_views(con: duckdb.DuckDBPyConnection) -> None:
    """Create the derived views. Requires a relation named ``pbp``."""
    con.execute(VIEWS_SQL)


def records(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[dict]:
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, row, strict=True)) for row in rel.fetchall()]
