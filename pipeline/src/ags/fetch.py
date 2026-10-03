"""Download nflverse play-by-play parquet files into data/raw/."""

from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

from .config import (
    INJURIES_URL,
    PBP_URL,
    PLAYER_IDS_URL,
    PLAYERS_URL,
    RAW_DIR,
    SCHEDULE_URL,
    SNAPS_URL,
    TEAMS_URL,
)

RAW_GITHUB = "raw.githubusercontent.com/nflverse/nflverse-pbp/"


def pbp_path(season: int, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"play_by_play_{season}.parquet"


def fetch_season(season: int, *, force: bool = False, raw_dir: Path = RAW_DIR) -> Path:
    """Download one season. Cached unless ``force`` (use for the in-progress season)."""
    dest = pbp_path(season, raw_dir)
    if dest.exists() and not force:
        return dest
    _download(PBP_URL.format(season=season), dest)
    return dest


def fetch_schedule(*, force: bool = True, raw_dir: Path = RAW_DIR) -> Path:
    """nflverse schedule with results and closing lines (always refreshed: lines move)."""
    dest = raw_dir / "games.csv"
    if force or not dest.exists():
        _download(SCHEDULE_URL, dest)
    return dest


def fetch_optional(url: str, name: str, *, force: bool, raw_dir: Path = RAW_DIR) -> Path | None:
    """Download a reference file the build can live without (cached unless ``force``).

    A failed download falls back to the cached copy, or None if there is none.
    """
    dest = raw_dir / name
    if force or not dest.exists():
        try:
            _download(url, dest)
        except OSError as e:
            print(f"warning: could not fetch {url}: {e}", file=sys.stderr)
    return dest if dest.exists() else None


def fetch_teams(*, force: bool = False, raw_dir: Path = RAW_DIR) -> Path | None:
    """nflverse team names, divisions and colors."""
    return fetch_optional(TEAMS_URL, "teams_colors_logos.csv", force=force, raw_dir=raw_dir)


def fetch_players(*, force: bool = False, raw_dir: Path = RAW_DIR) -> Path | None:
    """nflverse player directory (positions, draft, college), keyed by gsis_id."""
    return fetch_optional(PLAYERS_URL, "players.parquet", force=force, raw_dir=raw_dir)


def fetch_logos(teams_file: Path | None, *, raw_dir: Path = RAW_DIR) -> Path | None:
    """Team logo tiles (nflverse's squared logos, ~16 KB each) into data/raw/logos, once.

    Optional: badges stand in for any logo that can't be fetched.
    """
    if teams_file is None:
        return None
    import csv

    dest = raw_dir / "logos"
    with teams_file.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = row.get("team_logo_squared") or ""
            team = row.get("team_abbr") or ""
            out = dest / f"{team}.png"
            if not url.startswith("https://") or not team.isalpha() or out.exists():
                continue
            try:
                _download(url.replace("github.com/nflverse/nflverse-pbp/raw/", RAW_GITHUB), out)
            except OSError as e:
                print(f"warning: no logo for {team}: {e}", file=sys.stderr)
    return dest if dest.exists() else None


def fetch_player_ids(*, force: bool = False, raw_dir: Path = RAW_DIR) -> Path | None:
    """dynastyprocess player id map (Sleeper/ESPN/... ids -> gsis), for fantasy leagues."""
    return fetch_optional(PLAYER_IDS_URL, "db_playerids.csv", force=force, raw_dir=raw_dir)


def fetch_context(
    seasons: list[int], *, refresh_latest: bool = True, raw_dir: Path = RAW_DIR
) -> tuple[list[Path], list[Path]]:
    """Weekly injury reports and snap counts (optional: the model runs without them).

    The latest season is refreshed (new reports post through the week); older ones are cached.
    """
    latest = max(seasons)
    injuries, snaps = [], []
    for s in seasons:
        force = refresh_latest and s == latest
        inj = fetch_optional(INJURIES_URL.format(season=s), f"injuries_{s}.parquet", force=force)
        snp = fetch_optional(SNAPS_URL.format(season=s), f"snap_counts_{s}.parquet", force=force)
        injuries += [inj] if inj else []
        snaps += [snp] if snp else []
    return injuries, snaps


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    print(f"fetch {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(dest)


def fetch_seasons(seasons: list[int], *, refresh_latest: bool = True) -> list[Path]:
    latest = max(seasons)
    return [fetch_season(s, force=refresh_latest and s == latest) for s in seasons]
