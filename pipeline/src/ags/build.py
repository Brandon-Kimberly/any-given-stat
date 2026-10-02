"""Build every published dataset into web/static/data/."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import math
import sys
import time
from decimal import Decimal
from pathlib import Path

import duckdb

from . import (
    datasets,
    fourth,
    games,
    lab2,
    lab3,
    market,
    people,
    playbyplay,
    players,
    ratings,
    records,
    sim,
)
from .config import CACHE_DIR, OUT_DIR
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


def write_json(path: Path, payload, quiet: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(payload), separators=(",", ":")))
    if not quiet:
        print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)", file=sys.stderr)


def write_by_season(out_dir: Path, name: str, rows: list[dict]) -> None:
    """``name``/<season>.json for each season in ``rows`` (same row shape as the combined
    file), so pages can load one season at a time."""
    seasons = sorted({r["season"] for r in rows})
    for s in seasons:
        write_json(out_dir / name / f"{s}.json", [r for r in rows if r["season"] == s], True)
    print(f"wrote {out_dir / name}/ ({len(seasons)} seasons)", file=sys.stderr)


@contextlib.contextmanager
def timed(label: str):
    start = time.perf_counter()
    yield
    print(f"[time] {label}: {time.perf_counter() - start:.1f}s", file=sys.stderr)


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
            write_json(out_dir / "ratings.json", power)
            write_by_season(out_dir, "ratings", power)
            params = preds["params"]
            half_life = params["half_life_weeks"] or 1e9
            # --- round-3 forecast (lab3.py): the site's predictions and the simulator's
            # game model. Stakes need playoff odds, which need the forecast, so the frame
            # is built without odds and the stakes feature is filled in afterwards.
            with timed("forecast features"):
                frame = lab2.build_frame(con, params["lambda"], half_life, {})
                games3, f3, inj3 = frame
                mov = lab3.add_mov(con, games3, f3)
                fc = lab3.fit_forecast(f3)
                sim_model, overrides = lab3.sim_inputs(fc, games3, f3, mov, params)
            preds = lab3.apply_to_predictions(preds, games3, f3, fc)
            write_json(out_dir / "predictions.json", preds)
            # --- playoff odds (sim.py) ---
            with timed("playoff odds"):
                odds_index = []
                odds_payloads = {}
                for season, payload in sim.playoff_odds(
                    con, sim_model, overrides=overrides, cache_dir=CACHE_DIR / "odds"
                ):
                    odds_payloads[season] = payload
                    dest = out_dir / "playoff_odds" / f"{season}.json"
                    write_json(dest, payload)
                    odds_index.append(
                        {"season": season, "file": f"playoff_odds/{dest.name}"}
                        | {"weeks": payload["weeks"]}
                    )
                if odds_index:
                    write_json(out_dir / "playoff_odds" / "index.json", odds_index)
                else:
                    print("skip playoff odds: no team alignment (teams csv)", file=sys.stderr)
            lab2.set_stakes(games3, f3, odds_payloads)
            experiment = market.lab(con, params["lambda"], half_life)
            if experiment is not None:
                write_json(out_dir / "lab.json", experiment)
            with timed("beat-the-line round 2"):
                round2 = lab2.lab(con, params["lambda"], half_life, odds_payloads, frame=frame)
            if round2 is not None:
                write_json(out_dir / "lab2.json", round2)
            v1 = json.loads((Path(__file__).parent / "reference" / "sim_v1_brier.json").read_text())
            round3 = lab3.lab(games3, f3, fc, inj3, sorted(odds_payloads.items()), v1["seasons"])
            write_json(out_dir / "lab3.json", round3)
    write_json(out_dir / "teams.json", teams)
    splits = datasets.team_splits(con)
    write_json(out_dir / "team_splits.json", splits)
    write_by_season(out_dir, "team_splits", splits)
    weeks = datasets.team_weeks(con)
    write_json(out_dir / "team_weeks.json", weeks)
    write_by_season(out_dir, "team_weeks", weeks)
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
    qb_game_rows = datasets.qb_games(con)
    write_json(out_dir / "qb_games.json", qb_game_rows)
    write_by_season(out_dir, "qb_games", qb_game_rows)
    team_meta = teams_meta(con)
    if not team_meta:
        print("teams_colors_logos.csv missing: teams_meta.json is empty", file=sys.stderr)
    write_json(out_dir / "teams_meta.json", team_meta)
    write_json(out_dir / "stability.json", datasets.stability(con, complete))
    write_json(out_dir / "concepts.json", datasets.concepts(con, reference))
    fourth_payload = fourth.fourth_downs(con, reference)
    write_json(out_dir / "fourth_downs.json", fourth_payload)

    games_index = []
    game_summaries = []
    for s in status:
        season_games = games.season_games(con, s["season"])
        dest = out_dir / "games" / f"games_{s['season']}.json"
        write_json(dest, season_games)
        games_index.append(
            {"season": s["season"], "file": f"games/{dest.name}", "games": len(season_games)}
        )
        game_summaries.extend(filter(None, map(records.game_summary, season_games)))
    write_json(out_dir / "games" / "index.json", games_index)

    # --- per-game play-by-play and drives (playbyplay.py) ---
    with timed("play-by-play files"):
        for s in status:
            n = size = 0
            for game_id, payload in playbyplay.season_games(con, s["season"]):
                dest = out_dir / "games" / str(s["season"]) / f"{game_id}.json"
                write_json(dest, payload, quiet=True)
                n += 1
                size += dest.stat().st_size
            print(
                f"wrote {out_dir / 'games' / str(s['season'])}/ ({n} games, {size / 1e6:.1f} MB)",
                file=sys.stderr,
            )

    # --- all-time records, coaches, referees (records.py, people.py) ---
    with timed("records"):
        write_json(
            out_dir / "records.json",
            records.alltime(
                con,
                teams=teams,
                qbs=qbs,
                receivers=receivers,
                rushers=rushers,
                game_summaries=game_summaries,
            ),
        )
    with timed("coaches + referees"):
        if not has_relation(con, "schedule"):
            print("no schedule: coaches.json / referees.json are empty", file=sys.stderr)
        write_json(out_dir / "coaches.json", people.coaches(con, fourth_payload["buckets"]))
        write_json(out_dir / "referees.json", people.referees(con))

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
