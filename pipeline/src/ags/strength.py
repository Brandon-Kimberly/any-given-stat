"""Margin-of-victory team ratings, a second opinion next to the EPA ratings (ratings.py).

Model (one row per regular-season game, weighted by recency):

    home_margin = h * home_ind + s[home] - s[away] + noise

Team strengths ``s`` get a ridge penalty ``lam`` (in games of exactly-average results),
so a team with few games stays near 0. Like the EPA ratings, a game in week w is
predicted only from games before week w, using the current and previous season.

Points are noisier than EPA per play but measure the thing being predicted, including
what EPA misses (special teams, turnovers' full value, end-game decisions), so the two
can complement each other. Which mix forecasts best is decided on held-out seasons
(lab3.py), not assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np

from .db import records
from .ratings import FIT_SEASONS, OFFSEASON_WEEKS, time_index

MOV_LAMBDAS = (4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0)
MOV_HALF_LIVES = (4.0, 8.0, 16.0, 32.0, 64.0)


@dataclass(frozen=True)
class MovRows:
    t: np.ndarray
    season: np.ndarray
    home: np.ndarray  # team index
    away: np.ndarray
    home_ind: np.ndarray
    margin: np.ndarray
    teams: list[str]


def load_mov_rows(con: duckdb.DuckDBPyConnection, teams: list[str]) -> MovRows:
    """Completed regular-season games from the schedule, teams indexed like ``teams``."""
    rows = records(
        con,
        """
        select season, week, home_team as home, away_team as away, result,
               case when location = 'Neutral' then 0 else 1 end as home_ind
        from schedule
        where game_type = 'REG' and result is not null
        order by season, week
        """,
    )
    idx = {t: i for i, t in enumerate(teams)}
    rows = [r for r in rows if r["home"] in idx and r["away"] in idx]
    season = np.array([r["season"] for r in rows], dtype=int)
    week = np.array([r["week"] for r in rows], dtype=int)
    return MovRows(
        t=time_index(season, week),
        season=season,
        home=np.array([idx[r["home"]] for r in rows], dtype=int),
        away=np.array([idx[r["away"]] for r in rows], dtype=int),
        home_ind=np.array([float(r["home_ind"]) for r in rows]),
        margin=np.array([float(r["result"]) for r in rows]),
        teams=list(teams),
    )


def fit_mov(rows: MovRows, t_now: int, lam: float, half_life: float) -> np.ndarray:
    """Team strengths (points vs average, no home field) from games before ``t_now``."""
    n = len(rows.teams)
    mask = (rows.t < t_now) & (rows.t >= t_now - 2 * (18 + OFFSEASON_WEEKS))
    sel = np.flatnonzero(mask)
    if not len(sel):
        return np.zeros(n)
    X = np.zeros((len(sel), n + 1))
    X[:, 0] = rows.home_ind[sel]
    X[np.arange(len(sel)), 1 + rows.home[sel]] = 1.0
    X[np.arange(len(sel)), 1 + rows.away[sel]] -= 1.0
    w = 0.5 ** ((t_now - rows.t[sel]) / half_life)
    penalty = np.full(n + 1, lam)
    penalty[0] = 1e-9
    A = X.T @ (X * w[:, None]) + np.diag(penalty)
    beta = np.linalg.solve(A, X.T @ (w * rows.margin[sel]))
    s = beta[1:]
    return s - s.mean()


def mov_walk_forward(rows: MovRows, games: list[dict], lam: float, half_life: float) -> np.ndarray:
    """s[home] - s[away] for each game from earlier weeks only (nan for unknown teams)."""
    idx = {t: i for i, t in enumerate(rows.teams)}
    out = np.full(len(games), np.nan)
    cache: dict[int, np.ndarray] = {}
    for i, g in enumerate(games):
        if g["home"] not in idx or g["away"] not in idx:
            continue
        t_now = int(time_index(g["season"], g["week"]))
        if t_now not in cache:
            cache[t_now] = fit_mov(rows, t_now, lam, half_life)
        s = cache[t_now]
        out[i] = s[idx[g["home"]]] - s[idx[g["away"]]]
    return out


def tune_mov(rows: MovRows, games: list[dict], result: np.ndarray, home_ind: np.ndarray):
    """(lam, half_life, margins) minimizing FIT-season MAE of margin ~ mov + home."""
    season = np.array([g["season"] for g in games])
    fit_m = np.isin(season, list(FIT_SEASONS)) & ~np.isnan(result)
    best = None
    for lam in MOV_LAMBDAS:
        for hl in MOV_HALF_LIVES:
            x = mov_walk_forward(rows, games, lam, hl)
            m = fit_m & ~np.isnan(x)
            X = np.column_stack([x, home_ind])[m]
            b, *_ = np.linalg.lstsq(X, result[m], rcond=None)
            mae = float(np.mean(np.abs(X @ b - result[m])))
            if best is None or mae < best[0]:
                best = (mae, lam, hl, x)
    _, lam, hl, x = best
    return lam, hl, x
