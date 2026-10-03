"""Per-game play-by-play and drive charts: games/<season>/<game_id>.json.

Plays are compact arrays (column names in ``PLAYS_COLUMNS``) to keep each file small.
Every row with a description and an offense is included, special teams and penalties
too, in nflverse's play order.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterator

import duckdb

from .db import records
from .games import PLAY_ORDER

# Bump when the per-game file format or logic changes: past seasons are only rewritten then.
VERSION = 2
DESC_CHARS = 180
PLAYS_COLUMNS = [
    "qtr",
    "time",
    "posteam",
    "down",
    "ydstogo",
    "yl",  # yards from the offense's own goal line (100 - yardline_100)
    "play_type",
    "desc",
    "epa",
    "home_wp_after",
    "home_score",  # after the play
    "away_score",
    "flags",
    "drive",  # fixed_drive number, matches drives[].n
]
# Letters in the flags column, in this order.
FLAG_LEGEND = {
    "T": "touchdown",
    "I": "interception",
    "F": "fumble lost",
    "S": "sack",
    "P": "penalty",
    "X": "explosive (pass >= 20 or run >= 10 yards)",
    "4": "fourth-down attempt",
}
# Plays that start from a snap at a meaningful line of scrimmage.
SNAP_TYPES = {"pass", "run", "punt", "field_goal", "qb_kneel", "qb_spike", "no_play"}

# Columns read from pbp; any missing from an older file are selected as null.
SOURCE_COLUMNS = [
    "game_id",
    "qtr",
    "time",
    "posteam",
    "down",
    "ydstogo",
    "yardline_100",
    "play_type",
    "desc",
    "epa",
    "home_wp_post",
    "home_team",
    "total_home_score",
    "total_away_score",
    "touchdown",
    "interception",
    "fumble_lost",
    "sack",
    "penalty",
    "pass",
    "rush",
    "yards_gained",
    "fixed_drive",
    "fixed_drive_result",
    "drive_start_yard_line",
    "drive_end_yard_line",
    "drive_time_of_possession",
]


def _on(v) -> bool:
    return v is not None and v == 1


def flags(r: dict) -> str:
    """Flag letters for one play (see FLAG_LEGEND)."""
    yards = r.get("yards_gained") or 0
    explosive = (_on(r.get("pass")) and yards >= 20) or (_on(r.get("rush")) and yards >= 10)
    fourth = r.get("down") == 4 and r.get("play_type") in ("pass", "run")
    out = [
        ("T", _on(r.get("touchdown"))),
        ("I", _on(r.get("interception"))),
        ("F", _on(r.get("fumble_lost"))),
        ("S", _on(r.get("sack"))),
        ("P", _on(r.get("penalty"))),
        ("X", explosive),
        ("4", fourth),
    ]
    return "".join(letter for letter, on in out if on)


def parse_yardline(label: str | None, posteam: str | None) -> int | None:
    """Drive-chart spot like 'KC 25' as yards from ``posteam``'s own goal line.

    'KC 25' is 25 for KC and 75 for its opponent; '50' / 'MID 50' is 50.
    """
    if not label or not posteam:
        return None
    parts = label.split()
    try:
        n = int(parts[-1])
    except ValueError:
        return None
    if n == 50:
        return 50
    if len(parts) == 1:
        return None
    return n if parts[0] == posteam else 100 - n


def _int(v) -> int | None:
    return None if v is None else int(v)


def _round(v, digits: int):
    return None if v is None else round(float(v), digits)


def play_row(r: dict) -> list:
    """One play as a PLAYS_COLUMNS array."""
    yl = r["yardline_100"]
    return [
        _int(r["qtr"]),
        r["time"],
        r["posteam"],
        _int(r["down"]),
        _int(r["ydstogo"]),
        None if yl is None else int(100 - yl),
        r["play_type"],
        (r["desc"] or "")[:DESC_CHARS],
        _round(r["epa"], 3),
        _round(r["home_wp_post"], 3),
        _int(r["total_home_score"]),
        _int(r["total_away_score"]),
        flags(r),
        _int(r["fixed_drive"]),
    ]


def _first(rows: list[dict], key: str):
    return next((r[key] for r in rows if r[key] is not None), None)


def drives(rows: list[dict]) -> list[dict]:
    """Drive summaries from one game's rows in play order.

    The offense is the team with the most snaps: nflverse files a kickoff the kicking
    team recovers (onside, muff) under the drive that follows it. ``plays`` counts snaps
    (runs, passes, punts, field goals, kneels, spikes; not penalty no-plays). ``end_yl``
    is the line of scrimmage of the drive's last snap (nflverse drive chart), or 100 for
    an offensive touchdown. ``points`` is the change in the offense's score from just
    before the drive's first row to its last row (the PAT is part of the drive), None
    when a score is missing.
    """
    by_drive: dict[int, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        if r["fixed_drive"] is not None:
            by_drive[int(r["fixed_drive"])].append(i)
    out = []
    for n in sorted(by_drive, key=lambda d: by_drive[d][0]):
        idx = by_drive[n]
        drive_rows = [rows[i] for i in idx]
        first, last = drive_rows[0], drive_rows[-1]
        snaps = [r for r in drive_rows if r["play_type"] in SNAP_TYPES]
        # Most snaps; first to snap on a tie. (A return TD's two-point try is the other
        # team's single snap.)
        team = Counter(r["posteam"] for r in snaps).most_common(1)[0][0] if snaps else None
        team = team or first["posteam"]
        own = [r for r in snaps if r["posteam"] == team] or drive_rows
        side = "total_home_score" if team == first["home_team"] else "total_away_score"
        before = rows[idx[0] - 1][side] if idx[0] > 0 else 0
        after = last[side]
        points = None if before is None or after is None else int(after - before)
        start = parse_yardline(_first(own, "drive_start_yard_line"), team)
        if start is None and snaps and own[0]["yardline_100"] is not None:
            start = int(100 - own[0]["yardline_100"])
        result = _first(drive_rows, "fixed_drive_result")
        if result == "Touchdown":
            end = 100
        else:
            end = parse_yardline(_first(own[::-1], "drive_end_yard_line"), team)
            if end is None and snaps and own[-1]["yardline_100"] is not None:
                end = int(100 - own[-1]["yardline_100"])
        out.append(
            {
                "n": n,
                "posteam": team,
                "qtr": _int(first["qtr"]),
                "start_clock": _first(drive_rows, "time"),
                "start_yl": start,
                "end_yl": end,
                "plays": sum(r["play_type"] in SNAP_TYPES - {"no_play"} for r in own),
                "yards": None if start is None or end is None else end - start,
                "result": result,
                "top": _first(own, "drive_time_of_possession")
                or _first(drive_rows, "drive_time_of_possession"),
                "points": points,
            }
        )
    return out


def game_payload(game_id: str, rows: list[dict]) -> dict:
    return {
        "game_id": game_id,
        "plays_columns": PLAYS_COLUMNS,
        "flags": FLAG_LEGEND,
        "drives": drives(rows),
        "plays": [play_row(r) for r in rows],
    }


def season_games(con: duckdb.DuckDBPyConnection, season: int) -> Iterator[tuple[str, dict]]:
    """(game_id, payload) for every game (REG and POST) in ``season``."""
    available = {r[0] for r in con.execute("describe pbp").fetchall()}
    cols = ", ".join(f'"{c}"' if c in available else f'null as "{c}"' for c in SOURCE_COLUMNS)
    rows = records(
        con,
        f"""
        select {cols} from pbp
        where season = ? and "desc" is not null and posteam is not null
        order by {PLAY_ORDER}
        """,
        [season],
    )
    by_game: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_game[r["game_id"]].append(r)
    for game_id, game_rows in by_game.items():
        yield game_id, game_payload(game_id, game_rows)
