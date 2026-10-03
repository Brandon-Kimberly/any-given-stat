"""Player directory (nflverse players.parquet) joined onto the player datasets.

Play-by-play only carries abbreviated names ("P.Mahomes") and no positions, so the
build looks players up by gsis_id after the pbp-only datasets are computed.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import duckdb

from .db import has_relation, records


def players(con: duckdb.DuckDBPyConnection, ids: Iterable[str]) -> list[dict]:
    """Directory rows for the given gsis ids. Requires the ``players`` view; else []."""
    ids = sorted({i for i in ids if i})
    if not ids or not has_relation(con, "players"):
        return []
    cols = {r[0] for r in con.execute("describe players").fetchall()}
    headshot = "headshot" if "headshot" in cols else "null"
    return records(
        con,
        f"""
        select gsis_id as player_id, display_name as name, position, position_group,
               rookie_season, draft_year, draft_round, draft_pick, college_name as college,
               {headshot} as headshot
        from players
        where gsis_id in (select unnest(?::varchar[]))
        order by gsis_id
        """,
        [ids],
    )


def enrich(rows: list[dict], directory: list[dict], fields: dict[str, str]) -> None:
    """Add directory fields to rows in place, matched on ``player_id``.

    ``fields`` maps output field -> directory field; unknown players get None.
    """
    by_id = {p["player_id"]: p for p in directory}
    for r in rows:
        p = by_id.get(r["player_id"], {})
        for out, src in fields.items():
            r[out] = p.get(src)


# --- every player with a stat line: the page index and per-player profile files ---------
#
# players.json above covers the efficiency datasets (QBs, receivers, rushers). Kickers,
# punters, defenders and anyone else who shows up in a box score get a page from their stat
# lines instead: player_index.json lists everyone with a page (ids for links and search),
# players/<id>.json holds one profile player's bio and every game line.

# Site positions (statlines.POSITIONS groups) the efficiency datasets don't cover. A player in
# both (a two-way player, a tight end turned linebacker) keeps his efficiency page and also
# gets a profile file, which that page shows below the efficiency sections.
PROFILE_GROUPS = {"K", "P", "DL", "LB", "DB", "OL"}

# Headshot URLs share one of two long prefixes; the index stores "<key>:<token>" instead.
HEADSHOT_PREFIXES = {
    "p": "https://static.www.nfl.com/image/private/f_auto,q_auto/league/",
    "u": "https://static.www.nfl.com/image/upload/f_auto,q_auto/league/",
}

INDEX_COLUMNS = ["id", "name", "pos", "team", "season", "headshot", "efficiency"]


def short_headshot(url: str | None) -> str | None:
    """'p:abc123' for a URL under a known prefix, else the URL itself (or None)."""
    if not url:
        return None
    for key, prefix in HEADSHOT_PREFIXES.items():
        if url.startswith(prefix) and "/" not in url[len(prefix) :]:
            return f"{key}:{url[len(prefix) :]}"
    return url


def bios(con: duckdb.DuckDBPyConnection, ids: Iterable[str]) -> dict[str, dict]:
    """gsis id -> bio fields for a profile page (missing columns read as None)."""
    ids = sorted({i for i in ids if i})
    if not ids or not has_relation(con, "players"):
        return {}
    have = {r[0] for r in con.execute("describe players").fetchall()}
    want = {
        "name": "display_name",
        "position": "position",
        "position_group": "position_group",
        "jersey": "jersey_number",
        "college": "college_name",
        "headshot": "headshot",
        "height": "height",
        "weight": "weight",
        "birth_date": "birth_date",
        "rookie_season": "rookie_season",
        "draft_year": "draft_year",
        "draft_round": "draft_round",
        "draft_pick": "draft_pick",
        "draft_team": "draft_team",
    }
    cols = ", ".join(f"{src if src in have else 'null'} as {out}" for out, src in want.items())
    rows = records(
        con,
        f"""
        select gsis_id as player_id, {cols}
        from players
        where gsis_id in (select unnest(?::varchar[]))
        """,
        [ids],
    )
    return {r.pop("player_id"): r for r in rows}


def season_lines(
    con: duckdb.DuckDBPyConnection,
    season: int,
    cache_dir: Path,
    version: int | str,
    lines: dict | None = None,
) -> dict:
    """A season's player stat lines (``statlines.season_lines`` without the team boxes).

    Pass ``lines`` when the build just computed them: they're cached in ``cache_dir`` so a
    later build that skips the (unchanged) season can read them back instead of recomputing.
    """
    from . import statlines

    path = cache_dir / "player_lines" / f"{season}.json"
    if lines is None and path.exists():
        cached = json.loads(path.read_text())
        if cached.get("version") == str(version):
            return cached
    if lines is None:
        ids = statlines.player_ids(con, season)
        lines = statlines.season_lines(con, season, statlines.directory(con, ids))
    slim = {
        "version": str(version),
        "games": lines["games"],
        "players": lines["players"],
        "lines": lines["lines"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(slim, separators=(",", ":")))
    tmp.replace(path)
    return slim


def _group(position: str | None, fallback: str | None) -> str | None:
    """Site position group (QB RB WR TE K P DL LB DB OL) from an nflverse position."""
    from .statlines import POSITIONS

    if position:
        return POSITIONS.get(position.upper(), "OL")
    return fallback if fallback and fallback not in ("?", "DEF") else None


def directory_pages(
    con: duckdb.DuckDBPyConnection, seasons: dict[int, dict], efficiency: Iterable[dict]
) -> tuple[list[list], dict[str, dict]]:
    """``player_index.json`` rows and ``players/<id>.json`` payloads.

    ``seasons`` maps season -> ``season_lines`` output; ``efficiency`` is the qbs, receivers
    and rushers rows (``player_id``, ``season``, ``team``, ``name``/``full_name``,
    ``position``). Index rows follow ``INDEX_COLUMNS``. efficiency: 0 = the page is built
    from ``players/<id>.json``; 1 = the efficiency page; 2 = the efficiency page plus a
    profile file for a defensive or special-teams role.
    """
    per: dict[str, dict] = {}
    for season in sorted(seasons):
        data = seasons[season]
        for g, pid, team, stats in data["lines"]:
            meta = data["players"].get(pid)
            if not meta or meta[1] == "DEF" or not stats:
                continue
            week, stype, home, away = data["games"][g][:4]
            p = per.setdefault(pid, {"name": meta[0], "pos": meta[1], "games": [], "teams": {}})
            p["pos"] = meta[1] if meta[1] != "?" else p["pos"]
            is_home = team == home
            p["games"].append(
                [g, int(week), 0 if stype == "REG" else 1, team]
                + [away if is_home else home, 1 if is_home else 0, stats]
            )
            # Team by season: the one he played the most games for that season.
            count = p["teams"].setdefault(season, {})
            count[team] = count.pop(team, 0) + 1

    eff: dict[str, dict] = {}
    for r in efficiency:
        cur = eff.get(r["player_id"])
        if cur is None or r["season"] >= cur["season"]:
            eff[r["player_id"]] = r

    bio = bios(con, [*per, *eff])
    index: list[list] = []
    pages: dict[str, dict] = {}
    for pid in sorted({*per, *eff}):
        b = bio.get(pid, {})
        p = per.get(pid)
        e = eff.get(pid)
        group = _group(b.get("position"), p["pos"] if p else None)
        if group is None and e is not None:
            group = _group(e.get("position"), None)
        name = b.get("name") or (p and p["name"]) or (e and (e.get("full_name") or e["name"]))
        # The count dict is in last-played order, so reversed() lets a tie go to the later team.
        teams = (
            [
                [s, max(reversed(c.items()), key=lambda kv: kv[1])[0]]
                for s, c in sorted(p["teams"].items())
            ]
            if p
            else []
        )
        season, team = teams[-1] if teams else (e["season"], e["team"])
        on_efficiency = e is not None
        profile = p is not None and (not on_efficiency or group in PROFILE_GROUPS)
        index.append(
            [
                pid,
                name,
                b.get("position") or group,
                team,
                season,
                short_headshot(b.get("headshot")),
                (2 if profile else 1) if on_efficiency else 0,
            ]
        )
        if not profile:
            continue
        pages[pid] = {
            "player_id": pid,
            "name": name,
            "position": b.get("position") or group,
            "group": group,
            **{k: v for k, v in b.items() if k not in ("name", "position")},
            "teams": teams,
            "games": p["games"],
        }
    return index, pages
