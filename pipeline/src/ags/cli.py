"""Command line entry point: ``uv run ags build --seasons 2016-2026``."""

from __future__ import annotations

import argparse
import datetime as dt

from .build import build_all
from .config import DEFAULT_FIRST_SEASON
from .db import connect
from .fetch import fetch_context, fetch_players, fetch_schedule, fetch_seasons, fetch_teams


def current_nfl_season(today: dt.date | None = None) -> int:
    """The NFL season year in progress (seasons start in September)."""
    today = today or dt.date.today()
    return today.year if today.month >= 9 else today.year - 1


def parse_seasons(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-"))
            out.extend(range(lo, hi + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ags")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="download play-by-play and build site datasets")
    b.add_argument(
        "--seasons",
        default=f"{DEFAULT_FIRST_SEASON}-{current_nfl_season()}",
        help="e.g. 2016-2026 or 2023,2025 (default: %(default)s)",
    )
    b.add_argument("--no-explorer", action="store_true", help="skip per-season explorer parquet")
    b.add_argument("--no-refresh", action="store_true", help="don't re-download latest season")
    args = parser.parse_args(argv)

    if args.cmd == "build":
        seasons = parse_seasons(args.seasons)
        files = fetch_seasons(seasons, refresh_latest=not args.no_refresh)
        refresh = not args.no_refresh
        injuries, snaps = fetch_context(seasons, refresh_latest=refresh)
        con = connect(
            files,
            fetch_schedule(force=refresh),
            teams_file=fetch_teams(force=refresh),
            players_file=fetch_players(force=refresh),
            injury_files=injuries,
            snap_files=snaps,
        )
        build_all(con, explorer=not args.no_explorer)


if __name__ == "__main__":
    main()
