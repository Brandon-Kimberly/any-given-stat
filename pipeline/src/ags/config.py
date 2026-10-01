"""Paths and constants shared across the pipeline."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
OUT_DIR = REPO_ROOT / "web" / "static" / "data"

PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
)

# CPOE / xYAC / xpass exist from 2006 on; 2016+ keeps downloads (~20MB/season) reasonable.
DEFAULT_FIRST_SEASON = 2016

# "No garbage time" = offense win probability inside this band at the snap.
GARBAGE_WP_LOW = 0.10
GARBAGE_WP_HIGH = 0.90

# Pythagorean exponent for NFL points (Football Outsiders / Morey).
PYTHAG_EXPONENT = 2.37

# One-score game margin.
ONE_SCORE_MARGIN = 8
