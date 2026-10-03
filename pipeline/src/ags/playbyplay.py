"""Per-game play-by-play and drive charts: games/<season>/<game_id>.json.

Plays are compact arrays (column names in ``PLAYS_COLUMNS``) to keep each file small;
trailing nulls are dropped, so a row can be shorter than the column list. Every row with
a description and an offense is included, special teams and penalties too, in nflverse's
play order. The structured columns after ``drive`` (who, how far, what happened) let the
site write its own headline for each play instead of printing the raw description.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterator

import duckdb

from .db import records
from .games import PLAY_ORDER

# Bump when the per-game file format or logic changes: past seasons are only rewritten then.
VERSION = 3
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
    # v3: structured fields, ordered most-often-present first (trailing nulls are dropped).
    "home_wpa",  # home_wp_post - home_wp
    "yds",  # yards_gained
    "yl_end",  # where the ball ended up, same scale as yl (see end_yardline)
    "kind",  # what happened, see KINDS
    "a",  # actor: passer, rusher, kicker or punter
    "b",  # receiver (targeted or caught) or kick returner
    "detail",  # pass "deep left", run "left tackle", kick "touchback" / "fair catch" ...
    "air",  # air yards (passes)
    "kick",  # kick distance (kickoffs, punts, field goals, extra points)
    "ret",  # return yards (kicks, interceptions, fumbles)
    "d",  # defender who made the play: interceptor, sacker(s), recoverer, blocker
    "pen",  # [team, type, yards, player, status] for a flag; status "declined" / "offsetting"
    "fum",  # who fumbled, when the fumble was lost
]
# Columns every row has; only the structured ones after them are trimmed.
LEGACY_COLUMNS = PLAYS_COLUMNS.index("drive") + 1
# Values of the kind column.
KINDS = {
    "complete": "completed pass",
    "incomplete": "incomplete pass",
    "interception": "intercepted pass",
    "sack": "sack",
    "run": "designed run",
    "scramble": "QB scramble",
    "kneel": "kneel-down",
    "spike": "spike",
    "fg_made": "field goal, good",
    "fg_missed": "field goal, no good",
    "fg_blocked": "field goal, blocked",
    "xp_good": "extra point, good",
    "xp_failed": "extra point, no good",
    "xp_blocked": "extra point, blocked",
    "2pt_good": "two-point try, good",
    "2pt_failed": "two-point try, no good",
    "punt": "punt",
    "punt_blocked": "punt, blocked",
    "kickoff": "kickoff",
    "onside": "onside kick recovered by the kicking team",
    "penalty": "penalty, no play",
    "end": "end of a quarter or the game",
}
# Letters in the flags column, in this order.
FLAG_LEGEND = {
    "T": "touchdown",
    "I": "interception",
    "F": "fumble lost",
    "S": "sack",
    "P": "penalty",
    "X": "explosive (pass >= 20 or run >= 10 yards)",
    "4": "fourth-down attempt",
    "1": "first down",
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
    "home_wp",
    "td_team",
    "safety",
    "first_down",
    "qb_scramble",
    "qb_kneel",
    "qb_spike",
    "complete_pass",
    "two_point_attempt",
    "two_point_conv_result",
    "field_goal_result",
    "extra_point_result",
    "kick_distance",
    "return_yards",
    "air_yards",
    "pass_length",
    "pass_location",
    "run_location",
    "run_gap",
    "passer_player_name",
    "receiver_player_name",
    "rusher_player_name",
    "kicker_player_name",
    "punter_player_name",
    "punt_returner_player_name",
    "kickoff_returner_player_name",
    "interception_player_name",
    "sack_player_name",
    "half_sack_1_player_name",
    "half_sack_2_player_name",
    "fumbled_1_player_name",
    "fumble_recovery_1_player_name",
    "fumble_recovery_1_yards",
    "blocked_player_name",
    "penalty_team",
    "penalty_type",
    "penalty_yards",
    "penalty_player_name",
    "touchback",
    "punt_fair_catch",
    "punt_downed",
    "punt_out_of_bounds",
    "kickoff_fair_catch",
    "kickoff_out_of_bounds",
    "own_kickoff_recovery",
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
        ("1", _on(r.get("first_down"))),
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


def kind(r: dict) -> str | None:
    """What happened on the play, one of KINDS (None for anything else)."""
    t = r.get("play_type")
    g = r.get
    if _on(g("two_point_attempt")):
        return "2pt_good" if g("two_point_conv_result") == "success" else "2pt_failed"
    if t == "pass":
        if _on(g("sack")):
            return "sack"
        if _on(g("interception")):
            return "interception"
        return "complete" if _on(g("complete_pass")) else "incomplete"
    if t == "run":
        return "scramble" if _on(g("qb_scramble")) else "run"
    if t == "qb_kneel":
        return "kneel"
    if t == "qb_spike":
        return "spike"
    if t == "field_goal":
        res = g("field_goal_result")
        return {"made": "fg_made", "blocked": "fg_blocked"}.get(res, "fg_missed")
    if t == "extra_point":
        res = g("extra_point_result")
        return {"good": "xp_good", "blocked": "xp_blocked"}.get(res, "xp_failed")
    if t == "punt":
        return "punt_blocked" if _on(g("punt_blocked")) else "punt"
    if t == "kickoff":
        return "onside" if _on(g("own_kickoff_recovery")) else "kickoff"
    if t == "no_play" and _on(g("penalty")):
        return "penalty"
    if t is None and (g("desc") or "").startswith("END "):
        return "end"
    return None


def _name(v) -> str | None:
    return v or None


def actors(r: dict, k: str | None) -> tuple[str | None, str | None, str | None]:
    """(a, b, d): the actor, the receiver or returner, and the defender for kind ``k``."""
    g = r.get
    sackers = [n for n in (g("half_sack_1_player_name"), g("half_sack_2_player_name")) if n]
    sacker = g("sack_player_name") or (" / ".join(sackers) if sackers else None)
    passer = g("passer_player_name")
    if k in ("complete", "incomplete", "interception", "2pt_good", "2pt_failed", "spike"):
        a = passer or g("rusher_player_name")
        b = g("receiver_player_name")
        d = g("interception_player_name")
    elif k == "sack":
        a, b, d = passer, None, sacker
    elif k in ("run", "scramble", "kneel"):
        a, b, d = g("rusher_player_name") or passer, None, None
    elif k and k.startswith(("fg_", "xp_")):
        a, b, d = g("kicker_player_name"), None, g("blocked_player_name")
    elif k in ("punt", "punt_blocked"):
        a, b, d = g("punter_player_name"), g("punt_returner_player_name"), g("blocked_player_name")
    elif k in ("kickoff", "onside"):
        a, b, d = g("kicker_player_name"), g("kickoff_returner_player_name"), None
    else:
        a = b = d = None
    if _on(g("fumble_lost")) and not d:
        d = g("fumble_recovery_1_player_name")
    return _name(a), _name(b), _name(d)


def detail(r: dict, k: str | None) -> str | None:
    """Where a pass or run went, or how a kick ended."""
    g = r.get
    if k in ("complete", "incomplete", "interception"):
        parts = [g("pass_length"), g("pass_location")]
    elif k in ("run", "scramble"):
        loc, gap = g("run_location"), g("run_gap")
        parts = ["middle"] if loc == "middle" else [loc, gap]
    elif k in ("punt", "kickoff"):
        for flag, label in (
            ("touchback", "touchback"),
            ("punt_fair_catch", "fair catch"),
            ("kickoff_fair_catch", "fair catch"),
            ("punt_downed", "downed"),
            ("punt_out_of_bounds", "out of bounds"),
            ("kickoff_out_of_bounds", "out of bounds"),
        ):
            if _on(g(flag)):
                return label
        return None
    else:
        return None
    text = " ".join(p for p in parts if p)
    return text or None


_DECLINED = re.compile(r"PENALTY on [^,]+, ([^,]+), declined", re.IGNORECASE)


def penalty(r: dict) -> list | None:
    """[team, type, yards, player, status] for the play's (first) flag, or None."""
    if not _on(r.get("penalty")) or not r.get("penalty_type"):
        return None
    desc = r.get("desc") or ""
    status = None
    if "offsetting" in desc.lower():
        status = "offsetting"
    elif (m := _DECLINED.search(desc)) and m.group(1) == r["penalty_type"]:
        status = "declined"
    return [
        r.get("penalty_team"),
        r["penalty_type"],
        _int(r.get("penalty_yards")),
        _name(r.get("penalty_player_name")),
        status,
    ]


_CLOCK = re.compile(r"^\(\d*:\d+\)\s*")
_SNAPS = {"pass", "run", "punt", "field_goal", "qb_kneel", "qb_spike", "no_play"}


def _half(qtr) -> int:
    return 0 if qtr is None else (1 if qtr <= 2 else 2 if qtr <= 4 else 3)


def end_yardline(rows: list[dict], i: int) -> int | None:
    """Where play ``i`` left the ball, in yards from its offense's own goal line.

    100 for the offense's touchdown, 0 for a safety or the defense's touchdown, else the
    line of scrimmage of the next snap (penalties enforced, the other team's snap
    mirrored), as long as nothing but timeouts and end-of-quarter rows come between. A
    made kick, a try or a kickoff in between, or a new half, gives None.
    """
    r = rows[i]
    team = r["posteam"]
    if _on(r.get("touchdown")):
        return 100 if r.get("td_team") == team else 0
    if _on(r.get("safety")):
        return 0
    if r.get("play_type") in ("field_goal", "extra_point") or _on(r.get("two_point_attempt")):
        return None
    for nxt in rows[i + 1 :]:
        t = nxt.get("play_type")
        if _half(nxt.get("qtr")) != _half(r.get("qtr")):
            return None
        if t in ("kickoff", "extra_point") or _on(nxt.get("two_point_attempt")):
            return None
        if t not in _SNAPS or nxt.get("yardline_100") is None:
            continue
        yl100 = int(nxt["yardline_100"])
        return 100 - yl100 if nxt["posteam"] == team else yl100
    return None


def play_row(r: dict, yl_end: int | None = None) -> list:
    """One play as a PLAYS_COLUMNS array, trailing nulls after ``drive`` dropped."""
    yl = r["yardline_100"]
    k = kind(r)
    a, b, d = actors(r, k)
    wp, wp_post = r.get("home_wp"), r["home_wp_post"]
    passing = k in ("complete", "incomplete", "interception")
    kicking = k is not None and k.startswith(("punt", "kickoff", "onside", "fg_", "xp_"))
    ret = r.get("return_yards")
    if not ret and _on(r.get("fumble_lost")):
        ret = r.get("fumble_recovery_1_yards")
    row = [
        _int(r["qtr"]),
        r["time"],
        r["posteam"],
        _int(r["down"]),
        _int(r["ydstogo"]),
        None if yl is None else int(100 - yl),
        r["play_type"],
        _CLOCK.sub("", r["desc"] or "")[:DESC_CHARS],
        _round(r["epa"], 3),
        _round(wp_post, 3),
        _int(r["total_home_score"]),
        _int(r["total_away_score"]),
        flags(r),
        _int(r["fixed_drive"]),
        None if wp is None or wp_post is None else round(float(wp_post) - float(wp), 3),
        None if k in (None, "end", "penalty") or kicking else _int(r.get("yards_gained")),
        None if k == "end" else yl_end,
        k,
        a,
        b,
        detail(r, k),
        _int(r.get("air_yards")) if passing else None,
        _int(r.get("kick_distance")) if kicking else None,
        _int(ret) or None,
        d,
        penalty(r),
        _name(r.get("fumbled_1_player_name")) if _on(r.get("fumble_lost")) else None,
    ]
    while len(row) > LEGACY_COLUMNS and row[-1] is None:
        row.pop()
    return row


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
        "plays": [play_row(r, end_yardline(rows, i)) for i, r in enumerate(rows)],
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
