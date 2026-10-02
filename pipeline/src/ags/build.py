"""Build every published dataset into web/static/data/."""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from decimal import Decimal
from pathlib import Path

import duckdb

from . import datasets, fourth, games, market, players, ratings
from .config import OUT_DIR
from .db import has_relation
from .teams import teams_meta

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
    # Reference seasons for league-wide curves and the 4th-down model: complete seasons,
    # or everything loaded when none is complete (e.g. a single in-progress season).
    reference = complete or [s["season"] for s in status]

    teams = datasets.team_seasons(con)
    if has_relation(con, "schedule"):
        adjusted = {
            (r["scope"], r["season"], r["team"]): r for r in ratings.adjusted_team_seasons(con)
        }
        for t in teams:
            adj = adjusted.get((t["scope"], t["season"], t["team"]), {})
            for k in ("adj_off_epa", "adj_def_epa", "adj_net_epa"):
                t[k] = adj.get(k)
        model = ratings.predictions(con)
        if model is None:
            print(
                "skip predictions/ratings: seasons don't cover the training window", file=sys.stderr
            )
        else:
            preds, power = model
            write_json(out_dir / "predictions.json", preds)
            write_json(out_dir / "ratings.json", power)
            params = preds["params"]
            half_life = params["half_life_weeks"] or 1e9
            experiment = market.lab(con, params["lambda"], half_life)
            if experiment is not None:
                write_json(out_dir / "lab.json", experiment)
    write_json(out_dir / "teams.json", teams)
    write_json(out_dir / "team_splits.json", datasets.team_splits(con))
    write_json(out_dir / "team_weeks.json", datasets.team_weeks(con))
    write_json(out_dir / "luck.json", datasets.luck(con))
    qbs = datasets.quarterbacks(con)
    receivers = datasets.receivers(con)
    rushers = datasets.rushers(con)
    directory = players.players(con, (r["player_id"] for r in [*qbs, *receivers, *rushers]))
    if not directory:
        print("players.parquet missing: no positions or full names", file=sys.stderr)
    players.enrich(qbs, directory, {"full_name": "name"})
    players.enrich(receivers, directory, {"position": "position", "full_name": "name"})
    players.enrich(rushers, directory, {"position": "position", "full_name": "name"})
    write_json(out_dir / "qbs.json", qbs)
    write_json(out_dir / "receivers.json", receivers)
    write_json(out_dir / "rushers.json", rushers)
    write_json(out_dir / "players.json", directory)
    write_json(out_dir / "qb_games.json", datasets.qb_games(con))
    team_meta = teams_meta(con)
    if not team_meta:
        print("teams_colors_logos.csv missing: teams_meta.json is empty", file=sys.stderr)
    write_json(out_dir / "teams_meta.json", team_meta)
    write_json(out_dir / "stability.json", datasets.stability(con, complete))
    write_json(out_dir / "concepts.json", datasets.concepts(con, reference))
    write_json(out_dir / "fourth_downs.json", fourth.fourth_downs(con, reference))

    games_index = []
    for s in status:
        season_games = games.season_games(con, s["season"])
        dest = out_dir / "games" / f"games_{s['season']}.json"
        write_json(dest, season_games)
        games_index.append(
            {"season": s["season"], "file": f"games/{dest.name}", "games": len(season_games)}
        )
    write_json(out_dir / "games" / "index.json", games_index)

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
