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
    away_qb_name, home_rest, away_rest, div_game, home_coach, away_coach, referee
"""

# nflverse schedules keep historical abbreviations; play-by-play uses current ones.
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def connect(
    pbp_files: Sequence[Path],
    schedule_file: Path | None = None,
    teams_file: Path | None = None,
    players_file: Path | None = None,
) -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with ``pbp`` plus derived views.

    Optional reference views, created only when their file is given: ``schedule``
    (nflverse games.csv), ``team_colors`` (teams_colors_logos.csv) and ``players``
    (players.parquet, keyed by ``gsis_id``).
    """
    con = duckdb.connect()
    files = ", ".join(f"'{p.as_posix()}'" for p in pbp_files)
    con.execute(f"create view pbp as select * from read_parquet([{files}], union_by_name = true)")
    if schedule_file is not None:
        alias = " ".join(f"when '{a}' then '{b}'" for a, b in TEAM_ALIASES.items())
        con.execute(f"""
            create view schedule as
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
    install_views(con)
    return con


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
