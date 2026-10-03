"""Per-player and per-team stat lines for every game: box scores and fantasy scoring.

One pass over a season's play-by-play credits each play's stats to the players on it.
The keys follow Sleeper's scoring-setting names (see ``web/src/lib/fantasy/statline.ts``,
which documents every key), so the browser can score any league from the same lines the
box score shows. Official-stat conventions:

- Pass attempts exclude sacks and include spikes; rushes include scrambles and kneels.
- Two-point tries count only as ``*_2pt`` conversions, never as attempts or yards.
- Fumbles are charged to the player who fumbled; "lost" when the other team recovered.
- Team defense lines (position ``DEF``, id = team code) total the defense and special
  teams; ``pts_allow`` is the opponent's score minus 6 per opponent return TD (points the
  defense didn't allow), ``yds_allow`` the opponent's net scrimmage yards.

Validated against nflverse's weekly player stats (see ``tests/test_statlines.py``).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import duckdb

from .db import records
from .games import PLAY_ORDER

# Columns read from pbp; any missing from an older file are selected as null.
SOURCE_COLUMNS = [
    "game_id",
    "season_type",
    "week",
    "home_team",
    "away_team",
    "posteam",
    "defteam",
    "play_type",
    "yardline_100",
    "yards_gained",
    "pass_attempt",
    "rush_attempt",
    "complete_pass",
    "sack",
    "interception",
    "touchdown",
    "pass_touchdown",
    "rush_touchdown",
    "return_touchdown",
    "td_team",
    "td_player_id",
    "first_down_pass",
    "first_down_rush",
    "first_down_penalty",
    "third_down_converted",
    "third_down_failed",
    "fourth_down_converted",
    "fourth_down_failed",
    "two_point_attempt",
    "two_point_conv_result",
    "passing_yards",
    "receiving_yards",
    "rushing_yards",
    "lateral_receiving_yards",
    "lateral_rushing_yards",
    "yards_after_catch",
    "epa",
    "qb_epa",
    "passer_player_id",
    "passer_player_name",
    "receiver_player_id",
    "receiver_player_name",
    "rusher_player_id",
    "rusher_player_name",
    "lateral_receiver_player_id",
    "lateral_rusher_player_id",
    "interception_player_id",
    "interception_player_name",
    "kickoff_returner_player_id",
    "kickoff_returner_player_name",
    "punt_returner_player_id",
    "punt_returner_player_name",
    "kicker_player_id",
    "kicker_player_name",
    "punter_player_id",
    "punter_player_name",
    "return_yards",
    "return_team",
    "field_goal_attempt",
    "field_goal_result",
    "kick_distance",
    "extra_point_attempt",
    "extra_point_result",
    "punt_blocked",
    "punt_fair_catch",
    "kickoff_fair_catch",
    "punt_inside_twenty",
    "touchback",
    "blocked_player_id",
    "blocked_player_name",
    "fumbled_1_player_id",
    "fumbled_1_player_name",
    "fumbled_1_team",
    "fumbled_2_player_id",
    "fumbled_2_team",
    "fumble_recovery_1_player_id",
    "fumble_recovery_1_player_name",
    "fumble_recovery_1_team",
    "fumble_recovery_2_player_id",
    "fumble_recovery_2_team",
    "forced_fumble_player_1_player_id",
    "forced_fumble_player_1_player_name",
    "forced_fumble_player_1_team",
    "forced_fumble_player_2_player_id",
    "forced_fumble_player_2_team",
    "solo_tackle_1_player_id",
    "solo_tackle_1_player_name",
    "solo_tackle_1_team",
    "solo_tackle_2_player_id",
    "solo_tackle_2_team",
    "assist_tackle_1_player_id",
    "assist_tackle_1_player_name",
    "assist_tackle_1_team",
    "assist_tackle_2_player_id",
    "assist_tackle_2_team",
    "assist_tackle_3_player_id",
    "assist_tackle_3_team",
    "assist_tackle_4_player_id",
    "assist_tackle_4_team",
    "tackle_with_assist_1_player_id",
    "tackle_with_assist_1_team",
    "tackle_with_assist_2_player_id",
    "tackle_with_assist_2_team",
    "tackle_for_loss_1_player_id",
    "tackle_for_loss_2_player_id",
    "qb_hit_1_player_id",
    "qb_hit_2_player_id",
    "pass_defense_1_player_id",
    "pass_defense_1_player_name",
    "pass_defense_2_player_id",
    "sack_player_id",
    "sack_player_name",
    "half_sack_1_player_id",
    "half_sack_1_player_name",
    "half_sack_2_player_id",
    "half_sack_2_player_name",
    "safety",
    "safety_player_id",
    "penalty",
    "penalty_team",
    "penalty_yards",
    "fixed_drive",
    "fixed_drive_result",
    "drive_time_of_possession",
    "total_home_score",
    "total_away_score",
]

# Defensive credit columns: (id column, team column or None, stat, amount).
TACKLES = [
    ("solo_tackle_1_player_id", "solo_tackle_1_team", "tkl_solo"),
    ("solo_tackle_2_player_id", "solo_tackle_2_team", "tkl_solo"),
    ("assist_tackle_1_player_id", "assist_tackle_1_team", "tkl_ast"),
    ("assist_tackle_2_player_id", "assist_tackle_2_team", "tkl_ast"),
    ("assist_tackle_3_player_id", "assist_tackle_3_team", "tkl_ast"),
    ("assist_tackle_4_player_id", "assist_tackle_4_team", "tkl_ast"),
    ("tackle_with_assist_1_player_id", "tackle_with_assist_1_team", "tkl_ast"),
    ("tackle_with_assist_2_player_id", "tackle_with_assist_2_team", "tkl_ast"),
]
SNAP_PLAYS = ("pass", "run", "qb_kneel", "qb_spike")
KICK_PLAYS = ("kickoff", "punt", "field_goal", "extra_point")
# Box-score positions: nflverse's detailed positions folded into fantasy-relevant groups.
POSITIONS = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "HB": "RB",
    "WR": "WR",
    "TE": "TE",
    "K": "K",
    "PK": "K",
    "P": "P",
    "DE": "DL",
    "DT": "DL",
    "NT": "DL",
    "DL": "DL",
    "OLB": "LB",
    "ILB": "LB",
    "MLB": "LB",
    "LB": "LB",
    "CB": "DB",
    "S": "DB",
    "SS": "DB",
    "FS": "DB",
    "SAF": "DB",
    "DB": "DB",
}
INT_KEYS = ("pass_td_yds", "rush_td_yds", "rec_td_yds", "fgm_dists", "fgmiss_dists")
EPA_KEYS = ("pass_epa", "rush_epa", "rec_epa")


def _on(v) -> bool:
    return v is not None and v == v and v != 0


def _num(v) -> float:
    return 0.0 if v is None or v != v else float(v)


def _clock(v: str | None) -> int:
    """'MM:SS' drive time of possession -> seconds."""
    if not v or ":" not in v:
        return 0
    m, s = v.split(":", 1)
    try:
        return int(m) * 60 + int(s)
    except ValueError:
        return 0


class Lines:
    """Accumulates stat lines keyed by (game_id, player or team code)."""

    def __init__(self) -> None:
        self.stats: dict[tuple[str, str], dict] = defaultdict(lambda: defaultdict(float))
        self.team: dict[tuple[str, str], str] = {}
        self.names: dict[str, str] = {}

    def add(self, game: str, pid, team, key: str, amount: float = 1.0, name=None) -> None:
        if not pid:
            return
        s = self.stats[(game, pid)]
        s[key] += amount
        if team and (game, pid) not in self.team:
            self.team[(game, pid)] = team
        if name and pid not in self.names:
            self.names[pid] = name

    def longest(self, game: str, pid, key: str, value: float) -> None:
        if pid:
            s = self.stats[(game, pid)]
            s[key] = max(s.get(key, -999.0), value)

    def append(self, game: str, pid, key: str, value: float) -> None:
        if pid:
            s = self.stats[(game, pid)]
            s.setdefault(key, []).append(int(round(value)))


def _rec_bucket(yards: float) -> str:
    if yards >= 40:
        return "rec_40p"
    if yards >= 30:
        return "rec_30_39"
    if yards >= 20:
        return "rec_20_29"
    if yards >= 10:
        return "rec_10_19"
    if yards >= 5:
        return "rec_5_9"
    return "rec_0_4"


def credit_play(L: Lines, r: dict) -> None:
    """Credit one play's stats to its players."""
    g = r["game_id"]
    pt = r["play_type"]
    off, dfn = r["posteam"], r["defteam"]
    two_pt = _on(r["two_point_attempt"])

    if two_pt:
        if r["two_point_conv_result"] == "success":
            if _on(r["pass_attempt"]):
                L.add(g, r["passer_player_id"], off, "pass_2pt", name=r["passer_player_name"])
                L.add(g, r["receiver_player_id"], off, "rec_2pt", name=r["receiver_player_name"])
            else:
                L.add(g, r["rusher_player_id"], off, "rush_2pt", name=r["rusher_player_name"])
        return

    if pt in SNAP_PLAYS:
        passer, rusher, receiver = (
            r["passer_player_id"],
            r["rusher_player_id"],
            r["receiver_player_id"],
        )
        if _on(r["sack"]):
            yds = -_num(r["yards_gained"])
            L.add(g, passer, off, "pass_sack", name=r["passer_player_name"])
            L.add(g, passer, off, "pass_sack_yd", yds)
            L.add(g, passer, off, "pass_epa", _num(r["qb_epa"]))
            if r["sack_player_id"]:
                L.add(g, r["sack_player_id"], dfn, "sack", 1, r["sack_player_name"])
                L.add(g, r["sack_player_id"], dfn, "sack_yd", yds)
            for k in ("half_sack_1", "half_sack_2"):
                L.add(g, r[f"{k}_player_id"], dfn, "sack", 0.5, r[f"{k}_player_name"])
                L.add(g, r[f"{k}_player_id"], dfn, "sack_yd", yds / 2)
        elif passer and (_on(r["pass_attempt"]) or pt == "qb_spike"):
            L.add(g, passer, off, "pass_att", name=r["passer_player_name"])
            L.add(g, passer, off, "pass_epa", _num(r["qb_epa"]))
            if receiver:
                L.add(g, receiver, off, "rec_tgt", name=r["receiver_player_name"])
                L.add(g, receiver, off, "rec_epa", _num(r["epa"]))
            if _on(r["complete_pass"]):
                yds = _num(r["passing_yards"]) if r["passing_yards"] is not None else 0.0
                rec_yds = _num(r["receiving_yards"])
                L.add(g, passer, off, "pass_cmp")
                L.add(g, passer, off, "pass_yd", yds)
                L.longest(g, passer, "pass_lng", yds)
                if yds >= 40:
                    L.add(g, passer, off, "pass_cmp_40p")
                if _on(r["first_down_pass"]):
                    L.add(g, passer, off, "pass_fd")
                    L.add(g, receiver, off, "rec_fd")
                L.add(g, receiver, off, "rec")
                L.add(g, receiver, off, "rec_yd", rec_yds)
                L.add(g, receiver, off, "rec_yac", _num(r["yards_after_catch"]))
                L.add(g, receiver, off, _rec_bucket(rec_yds))
                L.longest(g, receiver, "rec_lng", rec_yds)
                if r["lateral_receiver_player_id"]:
                    L.add(
                        g, r["lateral_receiver_player_id"], off, "rec_yd",
                        _num(r["lateral_receiving_yards"]),
                    )  # fmt: skip
                if _on(r["pass_touchdown"]):
                    L.add(g, passer, off, "pass_td")
                    L.append(g, passer, "pass_td_yds", yds)
                    scorer = r["td_player_id"] or receiver
                    L.add(g, scorer, off, "rec_td")
                    L.append(g, scorer, "rec_td_yds", yds)
            elif not _on(r["interception"]):
                L.add(g, passer, off, "pass_inc")
            if _on(r["interception"]):
                L.add(g, passer, off, "pass_int")
                L.add(
                    g, r["interception_player_id"], dfn, "def_int", 1, r["interception_player_name"]
                )
                L.add(g, r["interception_player_id"], dfn, "int_ret_yd", _num(r["return_yards"]))
                if _on(r["return_touchdown"]) and r["td_team"] == dfn:
                    L.add(g, passer, off, "pass_int_td")
        elif rusher and (_on(r["rush_attempt"]) or pt == "qb_kneel"):
            yds = _num(r["rushing_yards"] if r["rushing_yards"] is not None else r["yards_gained"])
            L.add(g, rusher, off, "rush_att", name=r["rusher_player_name"])
            L.add(g, rusher, off, "rush_yd", yds)
            L.add(g, rusher, off, "rush_epa", _num(r["epa"]))
            L.longest(g, rusher, "rush_lng", yds)
            if yds >= 40:
                L.add(g, rusher, off, "rush_40p")
            if _on(r["first_down_rush"]):
                L.add(g, rusher, off, "rush_fd")
            if r["lateral_rusher_player_id"]:
                L.add(
                    g, r["lateral_rusher_player_id"], off, "rush_yd",
                    _num(r["lateral_rushing_yards"]),
                )  # fmt: skip
            if _on(r["rush_touchdown"]):
                scorer = r["td_player_id"] or rusher
                L.add(g, scorer, off, "rush_td")
                L.append(g, scorer, "rush_td_yds", yds)

    # Returns: on kickoffs nflverse's posteam is the receiving team; on punts, the kicking team.
    # Fair catches name the returner but aren't returns.
    if pt == "kickoff" and r["kickoff_returner_player_id"] and not _on(r["kickoff_fair_catch"]):
        p = r["kickoff_returner_player_id"]
        ret = r["return_team"] or off
        yds = _num(r["return_yards"])
        L.add(g, p, ret, "kr", 1, r["kickoff_returner_player_name"])
        L.add(g, p, ret, "kr_yd", yds)
        L.longest(g, p, "kr_lng", yds)
        if _on(r["return_touchdown"]) and r["td_player_id"] == p:
            L.add(g, p, ret, "kr_td")
    if pt == "punt":
        if r["punter_player_id"] and not _on(r["punt_blocked"]):
            p = r["punter_player_id"]
            dist = _num(r["kick_distance"])
            L.add(g, p, off, "punts", 1, r["punter_player_name"])
            L.add(g, p, off, "punt_yd", dist)
            L.longest(g, p, "punt_lng", dist)
            if _on(r["punt_inside_twenty"]):
                L.add(g, p, off, "punt_in20")
            if _on(r["touchback"]):
                L.add(g, p, off, "punt_tb")
        if r["punt_returner_player_id"] and not _on(r["punt_fair_catch"]):
            p = r["punt_returner_player_id"]
            yds = _num(r["return_yards"])
            L.add(g, p, dfn, "pr", 1, r["punt_returner_player_name"])
            L.add(g, p, dfn, "pr_yd", yds)
            L.longest(g, p, "pr_lng", yds)
            if _on(r["return_touchdown"]) and r["td_player_id"] == p:
                L.add(g, p, dfn, "pr_td")

    # Kicking.
    k = r["kicker_player_id"]
    if _on(r["field_goal_attempt"]) and k:
        dist = _num(r["kick_distance"])
        L.add(g, k, off, "fga", 1, r["kicker_player_name"])
        if r["field_goal_result"] == "made":
            L.add(g, k, off, "fgm")
            L.append(g, k, "fgm_dists", dist)
            L.longest(g, k, "fg_lng", dist)
        else:
            L.add(g, k, off, "fgmiss")
            L.append(g, k, "fgmiss_dists", dist)
    if _on(r["extra_point_attempt"]) and k:
        L.add(g, k, off, "xpa", 1, r["kicker_player_name"])
        L.add(g, k, off, "xpm" if r["extra_point_result"] == "good" else "xpmiss")

    # Fumbles, recoveries and forced fumbles (any play type).
    for i in ("1", "2"):
        f = r[f"fumbled_{i}_player_id"]
        if f:
            team = r[f"fumbled_{i}_team"]
            L.add(g, f, team, "fum", 1, r.get(f"fumbled_{i}_player_name"))
            rec_team = r[f"fumble_recovery_{i}_team"]
            if rec_team and team and rec_team != team:
                L.add(g, f, team, "fum_lost")
                L.add(g, r[f"fumble_recovery_{i}_player_id"], rec_team, "def_fum_rec", 1,
                      r.get(f"fumble_recovery_{i}_player_name"))  # fmt: skip
        ff = r[f"forced_fumble_player_{i}_player_id"]
        L.add(g, ff, r[f"forced_fumble_player_{i}_team"], "def_ff", 1,
              r.get(f"forced_fumble_player_{i}_player_name"))  # fmt: skip

    # Tackles and other defensive credits.
    for pid_col, team_col, key in TACKLES:
        L.add(g, r[pid_col], r[team_col], key, 1, r.get(pid_col.replace("_id", "_name")))
    for col in ("tackle_for_loss_1_player_id", "tackle_for_loss_2_player_id"):
        L.add(g, r[col], dfn, "tkl_loss")
    for col in ("qb_hit_1_player_id", "qb_hit_2_player_id"):
        L.add(g, r[col], dfn, "qb_hit")
    for col in ("pass_defense_1_player_id", "pass_defense_2_player_id"):
        L.add(g, r[col], dfn, "def_pd", 1, r.get(col.replace("_id", "_name")))
    if r["blocked_player_id"]:
        L.add(g, r["blocked_player_id"], dfn, "blk_kick", 1, r["blocked_player_name"])
    if _on(r["safety"]) and r["safety_player_id"]:
        L.add(g, r["safety_player_id"], dfn, "def_safe")

    # Non-offensive touchdowns credited to a player: defensive returns and own-fumble TDs.
    td_p, td_t = r["td_player_id"], r["td_team"]
    if _on(r["touchdown"]) and td_p and pt in KICK_PLAYS:
        # Any special-teams TD (returns, blocked kicks, recoveries): Sleeper's player st_td.
        L.add(g, td_p, td_t, "st_td")
    if _on(r["touchdown"]) and td_p and pt in SNAP_PLAYS:
        if td_t == dfn:
            L.add(g, td_p, dfn, "def_td")
        elif td_t == off and not _on(r["pass_touchdown"]) and not _on(r["rush_touchdown"]):
            L.add(g, td_p, off, "fum_rec_td")


def team_play(T: dict, r: dict) -> None:
    """Team box score and defense/special-teams credits for one play."""
    g, pt = r["game_id"], r["play_type"]
    off, dfn = r["posteam"], r["defteam"]
    if not off or not dfn:
        return
    o, d = T[(g, off)], T[(g, dfn)]
    for k in ("first_down_pass", "first_down_rush", "first_down_penalty"):
        o[k] += _num(r[k])
    o["third_conv"] += _num(r["third_down_converted"])
    o["third_att"] += _num(r["third_down_converted"]) + _num(r["third_down_failed"])
    o["fourth_conv"] += _num(r["fourth_down_converted"])
    o["fourth_att"] += _num(r["fourth_down_converted"]) + _num(r["fourth_down_failed"])
    if _on(r["penalty"]) and r["penalty_team"] and r["penalty_yards"] is not None:
        p = T[(g, r["penalty_team"])]
        p["penalties"] += 1
        p["penalty_yds"] += _num(r["penalty_yards"])
    if _on(r["two_point_attempt"]):
        return
    if pt in SNAP_PLAYS:
        yds = _num(r["yards_gained"])
        if _on(r["sack"]):
            o["sacked"] += 1
            o["sack_yds"] += -yds
            o["plays"] += 1
            o["net_pass_yds"] += yds
            d["d_sack"] += 1
        elif _on(r["pass_attempt"]) or pt == "qb_spike":
            o["plays"] += 1
            o["net_pass_yds"] += yds if _on(r["complete_pass"]) else 0
            if _on(r["interception"]):
                o["ints"] += 1
                d["d_int"] += 1
        elif _on(r["rush_attempt"]) or pt == "qb_kneel":
            o["plays"] += 1
            o["rush_yds"] += yds
    for i in ("1", "2"):
        team = r[f"fumbled_{i}_team"]
        rec = r[f"fumble_recovery_{i}_team"]
        if team and rec and rec != team:
            T[(g, team)]["fumbles_lost"] += 1
            T[(g, rec)]["d_fum_rec"] += 1
        if r[f"forced_fumble_player_{i}_team"]:
            T[(g, r[f"forced_fumble_player_{i}_team"])]["d_ff"] += 1
    if pt == "kickoff":
        o["kr_yd"] += _num(r["return_yards"])
    elif pt == "punt":
        d["pr_yd"] += _num(r["return_yards"])
    if (
        _on(r["punt_blocked"])
        or r["field_goal_result"] == "blocked"
        or (r["extra_point_result"] == "blocked")
    ):
        d["d_blk"] += 1
    if _on(r["safety"]):
        d["d_safe"] += 1
    if _on(r["touchdown"]) and r["td_team"]:
        scorer = T[(g, r["td_team"])]
        if pt in KICK_PLAYS and _on(r["return_touchdown"]):
            scorer["st_td"] += 1  # kick/punt return, blocked-kick return
        elif pt in KICK_PLAYS and r["td_team"] == dfn:
            scorer["st_td"] += 1
        elif pt in SNAP_PLAYS and r["td_team"] == dfn:
            scorer["def_td"] += 1


def _drives(T: dict, rows: list[dict]) -> None:
    """Time of possession and red-zone trips from drive-level fields."""
    seen: dict[tuple[str, str, float], dict] = {}
    for r in rows:
        if r["posteam"] is None or r["fixed_drive"] is None or r["play_type"] == "kickoff":
            continue
        key = (r["game_id"], r["posteam"], r["fixed_drive"])
        d = seen.setdefault(key, {"top": 0, "min_yl": 100.0, "result": None})
        d["top"] = max(d["top"], _clock(r["drive_time_of_possession"]))
        if r["yardline_100"] is not None and r["play_type"] in SNAP_PLAYS:
            d["min_yl"] = min(d["min_yl"], _num(r["yardline_100"]))
        d["result"] = r["fixed_drive_result"]
    for (g, team, _), d in seen.items():
        t = T[(g, team)]
        t["top_sec"] += d["top"]
        if d["min_yl"] <= 20:
            t["rz_trips"] += 1
            t["rz_td"] += d["result"] == "Touchdown"


def _clean(stats: dict) -> dict:
    out = {}
    for k, v in stats.items():
        if isinstance(v, list):
            out[k] = v
        elif k in EPA_KEYS:
            if v:
                out[k] = round(v, 2)
        elif v:
            out[k] = int(v) if float(v).is_integer() else round(v, 1)
    return out


def season_lines(con: duckdb.DuckDBPyConnection, season: int, directory: dict[str, dict]) -> dict:
    """Every game's player, team-defense and team box lines for ``season`` (REG and POST).

    ``directory`` maps gsis id -> {"name", "position"} (from players.py).
    Returns {"games": {game_id: meta}, "players": {...}, "lines": [...], "teams": {...}}.
    """
    available = {r[0] for r in con.execute("describe pbp").fetchall()}
    cols = ", ".join(f'"{c}"' if c in available else f'null as "{c}"' for c in SOURCE_COLUMNS)
    rows = records(
        con,
        f"select {cols} from pbp where season = ? and play_type is not null order by {PLAY_ORDER}",
        [season],
    )
    L = Lines()
    T: dict[tuple[str, str], dict] = defaultdict(lambda: defaultdict(float))
    games: dict[str, list] = {}
    final: dict[str, tuple[float, float]] = {}
    for r in rows:
        g = r["game_id"]
        if g not in games:
            games[g] = [int(r["week"]), r["season_type"], r["home_team"], r["away_team"]]
        if r["total_home_score"] is not None:
            final[g] = (_num(r["total_home_score"]), _num(r["total_away_score"]))
        credit_play(L, r)
        team_play(T, r)
    _drives(T, rows)

    lines: list[list] = []
    players: dict[str, list] = {}
    for (g, pid), stats in L.stats.items():
        team = L.team.get((g, pid))
        if not team:
            continue
        info = directory.get(pid, {})
        pos = POSITIONS.get((info.get("position") or "").upper(), "OL" if info else "")
        players.setdefault(pid, [info.get("name") or L.names.get(pid) or pid, pos or "?"])
        lines.append([g, pid, team, _clean(stats)])

    teams: dict[str, dict] = {}
    for g, (_week, _stype, home, away) in games.items():
        hs, as_ = final.get(g, (0.0, 0.0))
        for team, opp, opp_pts in ((home, away, as_), (away, home, hs)):
            t, o = T[(g, team)], T[(g, opp)]
            dst = {
                "sack": t["d_sack"],
                "def_int": t["d_int"],
                "def_fum_rec": t["d_fum_rec"],
                "def_ff": t["d_ff"],
                "def_td": t["def_td"],
                "st_td": t["st_td"],
                "def_safe": t["d_safe"],
                "blk_kick": t["d_blk"],
                "kr_yd": t["kr_yd"],
                "pr_yd": t["pr_yd"],
                "pts_allow": max(0.0, opp_pts - 6 * (o["def_td"] + o["st_td"])),
                "yds_allow": o["net_pass_yds"] + o["rush_yds"],
            }
            clean = _clean(dst)
            clean.setdefault("pts_allow", 0)  # a shutout is worth points: keep the zero
            lines.append([g, team, team, clean])
            players.setdefault(team, [team, "DEF"])
            teams[f"{g}|{team}"] = {
                "first_downs": int(
                    t["first_down_pass"] + t["first_down_rush"] + t["first_down_penalty"]
                ),
                "first_downs_pass": int(t["first_down_pass"]),
                "first_downs_rush": int(t["first_down_rush"]),
                "first_downs_pen": int(t["first_down_penalty"]),
                "third": [int(t["third_conv"]), int(t["third_att"])],
                "fourth": [int(t["fourth_conv"]), int(t["fourth_att"])],
                "plays": int(t["plays"]),
                "yards": int(t["net_pass_yds"] + t["rush_yds"]),
                "pass_yds": int(t["net_pass_yds"]),
                "rush_yds": int(t["rush_yds"]),
                "sacked": [int(t["sacked"]), int(t["sack_yds"])],
                "penalties": [int(t["penalties"]), int(t["penalty_yds"])],
                "turnovers": int(t["ints"] + t["fumbles_lost"]),
                "fumbles_lost": int(t["fumbles_lost"]),
                "ints": int(t["ints"]),
                "top_sec": int(t["top_sec"]),
                "red_zone": [int(t["rz_td"]), int(t["rz_trips"])],
                "ret_yds": int(t["kr_yd"] + t["pr_yd"]),
            }  # fmt: skip
    return {"games": games, "players": players, "lines": lines, "teams": teams}


def directory(con: duckdb.DuckDBPyConnection, ids: Iterable[str]) -> dict[str, dict]:
    """gsis id -> {"name", "position"} for the given ids, from the players table if loaded."""
    from .players import players

    return {p["player_id"]: p for p in players(con, ids)}


def player_ids(con: duckdb.DuckDBPyConnection, season: int) -> set[str]:
    """Every gsis id that appears in a credited role in ``season``'s pbp."""
    available = {r[0] for r in con.execute("describe pbp").fetchall()}
    id_cols = [c for c in SOURCE_COLUMNS if c.endswith("_player_id") and c in available]
    if not id_cols:
        return set()
    union = " union ".join(f'select "{c}" as id from pbp where season = ?' for c in id_cols)
    return {r[0] for r in con.execute(union, [season] * len(id_cols)).fetchall() if r[0]}


def fantasy_ids(con: duckdb.DuckDBPyConnection, gsis_ids: set[str]) -> dict[str, dict[str, str]]:
    """Sleeper and ESPN player ids -> gsis id, for players with stat lines.

    Sleeper ids come from dynastyprocess's id map (``player_ids`` view); ESPN ids from
    nflverse's player directory, falling back to the id map.
    """
    from .db import has_relation

    out: dict[str, dict[str, str]] = {"sleeper": {}, "espn": {}}
    if has_relation(con, "player_ids"):
        for sleeper, espn, gsis in con.execute(
            "select sleeper_id, espn_id, gsis_id from player_ids where gsis_id is not null"
        ).fetchall():
            if gsis in gsis_ids:
                if sleeper:
                    out["sleeper"][sleeper] = gsis
                if espn:
                    out["espn"][espn] = gsis
    if has_relation(con, "players"):
        for espn, gsis in con.execute(
            "select cast(espn_id as varchar), gsis_id from players where espn_id is not null"
        ).fetchall():
            if gsis in gsis_ids and espn:
                out["espn"][espn.removesuffix(".0")] = gsis
    return out


# Box-score-only fields no fantasy platform scores: left out of fantasy/<season>.json.
BOX_ONLY = {
    "pass_lng", "rush_lng", "rec_lng", "kr_lng", "pr_lng", "fg_lng",
    "pass_epa", "rush_epa", "rec_epa", "rec_yac",
    "punts", "punt_yd", "punt_in20", "punt_tb", "punt_lng", "kr", "pr",
}  # fmt: skip


def fantasy_season(season: int, lines: dict) -> dict:
    """fantasy/<season>.json: scorable lines only (no punters or linemen without stats)."""
    out = []
    used: set[str] = set()
    for g, pid, team, stats in lines["lines"]:
        slim = {k: v for k, v in stats.items() if k not in BOX_ONLY}
        if (
            not slim
            or lines["players"][pid][1] in ("P", "OL")
            and not any(k.startswith(("pass_", "rush_", "rec", "fum")) for k in slim)
        ):
            continue
        out.append([g, pid, team, slim])
        used.add(pid)
    players = {p: v for p, v in lines["players"].items() if p in used}
    return {"season": season, "players": players, "games": lines["games"], "lines": out}


def game_boxes(season: dict) -> dict[str, dict]:
    """Split ``season_lines`` output into per-game box scores.

    game_id -> {"players": {id: [name, pos]}, "lines": [[id, team, stats]], "teams": {team: box}}
    """
    out: dict[str, dict] = {}
    for g in season["games"]:
        out[g] = {"players": {}, "lines": [], "teams": {}}
    for g, pid, team, stats in season["lines"]:
        box = out[g]
        box["lines"].append([pid, team, stats])
        box["players"][pid] = season["players"][pid]
    for key, t in season["teams"].items():
        g, team = key.split("|")
        out[g]["teams"][team] = t
    return out
