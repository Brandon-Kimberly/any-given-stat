"""Paths and constants shared across the pipeline."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
CACHE_DIR = REPO_ROOT / "data" / "cache"
OUT_DIR = REPO_ROOT / "web" / "static" / "data"

SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
)
RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"
TEAMS_URL = f"{RELEASES}/teams/teams_colors_logos.csv"
PLAYERS_URL = f"{RELEASES}/players/players.parquet"
INJURIES_URL = f"{RELEASES}/injuries/injuries_{{season}}.parquet"
SNAPS_URL = f"{RELEASES}/snap_counts/snap_counts_{{season}}.parquet"
# Daily depth-chart snapshots: who starts at QB in games not played yet.
DEPTH_URL = f"{RELEASES}/depth_charts/depth_charts_{{season}}.parquet"
# ESPN's public news API (news.py): league-wide headlines, and one team's (ESPN team id).
NEWS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=50"
NEWS_TEAM_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=8&team={team}"
)
# Cross-platform player ids (Sleeper, ESPN, ... -> gsis) for connecting fantasy leagues.
PLAYER_IDS_URL = (
    "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
)

# Bump when the build writes new datasets the site needs: `ags up` rebuilds older data.
# 2: box scores in per-game files, fantasy/<season>.json, fantasy_ids.json.
# 3: team logo tiles (/data/logos) and player headshots in players.json.
# 4: schedule/<season>.json, upcoming.json; predictions gain gametime, blend_wp, next_games.
DATA_VERSION = 4

# CPOE / xYAC / xpass exist from 2006 on; 2016+ keeps downloads (~20MB/season) reasonable.
DEFAULT_FIRST_SEASON = 2016

# "No garbage time" = offense win probability inside this band at the snap.
GARBAGE_WP_LOW = 0.10
GARBAGE_WP_HIGH = 0.90

# Pythagorean exponent for NFL points (Football Outsiders / Morey).
PYTHAG_EXPONENT = 2.37

# One-score game margin.
ONE_SCORE_MARGIN = 8
