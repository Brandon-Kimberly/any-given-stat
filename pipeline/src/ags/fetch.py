"""Download nflverse play-by-play parquet files into data/raw/."""

from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

from .config import PBP_URL, RAW_DIR


def pbp_path(season: int, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"play_by_play_{season}.parquet"


def fetch_season(season: int, *, force: bool = False, raw_dir: Path = RAW_DIR) -> Path:
    """Download one season. Cached unless ``force`` (use for the in-progress season)."""
    dest = pbp_path(season, raw_dir)
    if dest.exists() and not force:
        return dest
    raw_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    url = PBP_URL.format(season=season)
    print(f"fetch {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(dest)
    return dest


def fetch_seasons(seasons: list[int], *, refresh_latest: bool = True) -> list[Path]:
    latest = max(seasons)
    return [fetch_season(s, force=refresh_latest and s == latest) for s in seasons]
