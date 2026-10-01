"""Build every published dataset into web/static/data/."""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from decimal import Decimal
from pathlib import Path

import duckdb

from . import datasets
from .config import OUT_DIR

FLOAT_DIGITS = 4


def _clean(value):
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else round(value, FLOAT_DIGITS)
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if isinstance(value, dt.date | dt.datetime):
        return value.isoformat()
    return value


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(payload), separators=(",", ":")))
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)", file=sys.stderr)


def season_status(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Per season: REG games played and last week, and whether the season is complete."""
    rows = datasets.records(
        con,
        """
        select season, count(*) as reg_games, max(week) as last_week
        from games where season_type = 'REG' and home_score is not null
        group by season order by season
        """,
    )
    for r in rows:
        # 256 games through 2020, 272 since the 17-game schedule.
        r["complete"] = r["reg_games"] >= (272 if r["season"] >= 2021 else 256)
    return rows


def build_all(con: duckdb.DuckDBPyConnection, out_dir: Path = OUT_DIR, explorer: bool = True):
    status = season_status(con)
    complete = [s["season"] for s in status if s["complete"]]

    write_json(out_dir / "teams.json", datasets.team_seasons(con))
    write_json(out_dir / "team_weeks.json", datasets.team_weeks(con))
    write_json(out_dir / "luck.json", datasets.luck(con))
    write_json(out_dir / "qbs.json", datasets.quarterbacks(con))
    write_json(out_dir / "receivers.json", datasets.receivers(con))
    write_json(out_dir / "rushers.json", datasets.rushers(con))
    write_json(out_dir / "stability.json", datasets.stability(con, complete))

    explorer_files = []
    if explorer:
        pbp_dir = out_dir / "pbp"
        pbp_dir.mkdir(parents=True, exist_ok=True)
        for s in status:
            dest = pbp_dir / f"pbp_{s['season']}.parquet"
            datasets.export_explorer_parquet(con, s["season"], dest.as_posix())
            explorer_files.append(
                {"season": s["season"], "file": f"pbp/{dest.name}", "bytes": dest.stat().st_size}
            )
            print(f"wrote {dest} ({dest.stat().st_size / 1e6:.1f} MB)", file=sys.stderr)

    write_json(
        out_dir / "meta.json",
        {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "seasons": status,
            "explorer_files": explorer_files,
            "source": "nflverse play-by-play (nflfastR models)",
        },
    )
