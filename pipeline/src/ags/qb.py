"""Walk-forward starting-QB adjustment.

For each side of a game: quality of the listed starter minus the dropback-weighted quality of
the QBs whose play built the team's current rating. Positive = the starter is better than
what the team's numbers assume (e.g. a star returning); negative = a downgrade (injury,
rest, benching). Everything is as known before the game's week.
"""

from __future__ import annotations

from collections import defaultdict

import duckdb
import numpy as np

from .db import records
from .ratings import OFFSEASON_WEEKS, time_index

# QB quality: EPA/dropback shrunk toward a prior. 430 dropbacks is where QB EPA/dropback
# is half signal (see the stability page), so it is the natural shrinkage weight.
QB_PRIOR_DROPBACKS = 430.0
QB_PRIOR_EPA = -0.05  # unknown QBs (rookies, backups) start below average
QB_HALF_LIFE_WEEKS = 32.0
DROPBACKS_PER_GAME = 35.0


def _qb_games(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Dropbacks and QB EPA per (game, team, passer), regular season."""
    return records(
        con,
        """
        select p.game_id, p.season, p.week, p.posteam as team, p.passer_id as qb,
               count(*) as dropbacks, sum(p.qb_epa) as epa
        from plays p
        where p.pass = 1 and p.passer_id is not null and p.qb_epa is not null
        group by all
        order by p.season, p.week
        """,
    )


def qb_adjustments(
    con: duckdb.DuckDBPyConnection, games: list[dict]
) -> tuple[np.ndarray, np.ndarray]:
    """(home, away) starter-vs-baseline adjustments in points for each game.

    ``games`` need season, week, home, away, home_qb, away_qb (gsis ids; None = unknown).
    """
    rows = _qb_games(con)
    t_rows = time_index(np.array([r["season"] for r in rows]), np.array([r["week"] for r in rows]))
    order = np.argsort(t_rows, kind="stable")
    rows = [rows[i] for i in order]
    t_rows = t_rows[order]

    qb_hist: dict[str, list[tuple[int, float, float]]] = defaultdict(list)  # qb -> (t, n, epa)
    team_hist: dict[str, list[tuple[int, str, float]]] = defaultdict(list)  # team -> (t, qb, n)

    def quality(qb: str | None, t_now: int) -> float:
        if not qb:
            return QB_PRIOR_EPA
        n = epa = 0.0
        for t, dn, de in qb_hist.get(qb, ()):
            w = 0.5 ** ((t_now - t) / QB_HALF_LIFE_WEEKS)
            n += w * dn
            epa += w * de
        return (epa + QB_PRIOR_DROPBACKS * QB_PRIOR_EPA) / (n + QB_PRIOR_DROPBACKS)

    def baseline(team: str, t_now: int) -> float | None:
        window = 2 * (18 + OFFSEASON_WEEKS)
        num = den = 0.0
        for t, qb, n in team_hist.get(team, ()):
            if t_now - window <= t < t_now:
                w = n * 0.5 ** ((t_now - t) / 16.0)
                num += w * quality(qb, t_now)
                den += w
        return num / den if den else None

    home_adj = np.zeros(len(games))
    away_adj = np.zeros(len(games))
    g_t = time_index(np.array([g["season"] for g in games]), np.array([g["week"] for g in games]))
    i = 0
    for gi in np.argsort(g_t, kind="stable"):
        t_now = int(g_t[gi])
        while i < len(rows) and t_rows[i] < t_now:  # absorb strictly earlier weeks
            r = rows[i]
            qb_hist[r["qb"]].append((int(t_rows[i]), float(r["dropbacks"]), float(r["epa"])))
            team_hist[r["team"]].append((int(t_rows[i]), r["qb"], float(r["dropbacks"])))
            i += 1
        g = games[gi]
        side = []
        for team, qb in ((g["home"], g["home_qb"]), (g["away"], g["away_qb"])):
            base = baseline(team, t_now)
            side.append(0.0 if base is None else quality(qb, t_now) - base)
        home_adj[gi] = side[0] * DROPBACKS_PER_GAME
        away_adj[gi] = side[1] * DROPBACKS_PER_GAME
    return home_adj, away_adj
