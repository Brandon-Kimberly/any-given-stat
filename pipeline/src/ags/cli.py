"""Command line entry point: ``uv run ags build --seasons 2016-2026`` / ``uv run ags up``."""

from __future__ import annotations

import argparse
import datetime as dt

from .config import DEFAULT_FIRST_SEASON


def current_nfl_season(today: dt.date | None = None) -> int:
    """The NFL season year in progress (seasons start in September)."""
    today = today or dt.date.today()
    return today.year if today.month >= 9 else today.year - 1


def default_seasons() -> str:
    return f"{DEFAULT_FIRST_SEASON}-{current_nfl_season()}"


def parse_seasons(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-"))
            out.extend(range(lo, hi + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def run_build(seasons: list[int], refresh: bool = True, explorer: bool = True) -> None:
    """Download (latest season refreshed unless ``refresh`` is off) and write every dataset."""
    # Imported here so `ags up` starts instantly when the data is already built.
    from .build import build_all
    from .db import connect
    from .fetch import (
        fetch_context,
        fetch_player_ids,
        fetch_players,
        fetch_schedule,
        fetch_seasons,
        fetch_teams,
    )

    files = fetch_seasons(seasons, refresh_latest=refresh)
    injuries, snaps = fetch_context(seasons, refresh_latest=refresh)
    con = connect(
        files,
        fetch_schedule(force=refresh),
        teams_file=fetch_teams(force=refresh),
        players_file=fetch_players(force=refresh),
        player_ids_file=fetch_player_ids(force=refresh),
        injury_files=injuries,
        snap_files=snaps,
    )
    build_all(con, explorer=explorer)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ags")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="download play-by-play and build site datasets")
    b.add_argument(
        "--seasons",
        default=default_seasons(),
        help="e.g. 2016-2026 or 2023,2025 (default: %(default)s)",
    )
    b.add_argument("--no-explorer", action="store_true", help="skip per-season explorer parquet")
    b.add_argument("--no-refresh", action="store_true", help="don't re-download latest season")
    u = sub.add_parser("up", help="build what's missing, then serve the site with a Sync button")
    u.add_argument(
        "--port", type=int, default=4173, help="default: %(default)s (next free if busy)"
    )
    u.add_argument("--no-open", action="store_true", help="don't open a browser")
    u.add_argument("--no-build", action="store_true", help="skip the web app freshness check")
    u.add_argument(
        "--seasons",
        default=default_seasons(),
        help="seasons for data builds and syncs (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if args.cmd == "build":
        run_build(
            parse_seasons(args.seasons), refresh=not args.no_refresh, explorer=not args.no_explorer
        )
    elif args.cmd == "up":
        from .serve import up

        up(
            port=args.port,
            open_browser=not args.no_open,
            build_web=not args.no_build,
            seasons=args.seasons,
        )


if __name__ == "__main__":
    main()
