"""Opponent-adjusted team ratings and a walk-forward spread model.

Model (one row per team-game offense, weighted by plays):

    epa_per_play = mu + off[team] + def[opponent] + h * home + noise

``off`` is how many EPA/play an offense adds over average; ``def`` is how many
EPA/play a defense *allows* over average (lower is better). Team coefficients
get a ridge penalty, which shrinks thin samples toward league average: a
penalty of ``lam`` acts like ``lam`` extra plays of exactly-average football.

Predictions are walk-forward: a game in week w is predicted only from games
played before week w, so the backtest has no look-ahead. Point margins come from
the rating gap plus a starting-QB adjustment (qb.py) and home field.

Season splits are shared with market.py: hyperparameters and coefficients are fit
on FIT_SEASONS, model choices were made on VALIDATE_SEASONS, and TEST_SEASONS are
reported, never tuned on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import duckdb
import numpy as np

from .db import records

FIT_SEASONS = range(2017, 2022)
VALIDATE_SEASONS = range(2022, 2024)
TEST_SEASONS = range(2024, 2026)
LAMBDAS = (300.0, 1000.0, 3000.0, 10000.0, 30000.0)
HALF_LIVES = (4.0, 8.0, 16.0, 1e9)  # in weeks; 1e9 = no decay
OFFSEASON_WEEKS = 12  # time gap between a season's last week and the next season's week 1
# Descriptive (season-only, no decay) adjustment: light shrinkage only.
DESCRIPTIVE_LAMBDA = 50.0


@dataclass(frozen=True)
class GameRows:
    """Team-game offense rows as parallel arrays."""

    t: np.ndarray  # time index (season * (18 + OFFSEASON_WEEKS) + week)
    season: np.ndarray
    week: np.ndarray
    off: np.ndarray  # team index
    opp: np.ndarray  # team index
    home: np.ndarray  # +1 home, -1 away, 0 neutral
    epa: np.ndarray  # epa per play
    plays: np.ndarray
    teams: list[str]


def time_index(season, week):
    return np.asarray(season) * (18 + OFFSEASON_WEEKS) + np.asarray(week)


def load_rows(con: duckdb.DuckDBPyConnection, scope: str = "no_garbage") -> GameRows:
    where = "no_garbage" if scope == "no_garbage" else "true"
    rows = records(
        con,
        f"""
        select p.season, p.week, p.posteam as off, p.defteam as opp,
               case when s.location = 'Neutral' then 0
                    when p.posteam = s.home_team then 1 else -1 end as home,
               avg(p.epa) as epa, count(*) as plays
        from plays p join schedule s using (game_id)
        where {where}
        group by all
        order by p.season, p.week
        """,
    )
    teams = sorted({r["off"] for r in rows} | {r["opp"] for r in rows})
    idx = {t: i for i, t in enumerate(teams)}
    arr = lambda k, f=float: np.array([f(r[k]) for r in rows])  # noqa: E731
    season = arr("season", int)
    week = arr("week", int)
    return GameRows(
        t=time_index(season, week),
        season=season,
        week=week,
        off=np.array([idx[r["off"]] for r in rows], dtype=int),
        opp=np.array([idx[r["opp"]] for r in rows], dtype=int),
        home=arr("home"),
        epa=arr("epa"),
        plays=arr("plays"),
        teams=teams,
    )


@dataclass(frozen=True)
class Fit:
    mu: float
    home: float
    off: np.ndarray  # per team
    deff: np.ndarray  # per team (EPA allowed; lower is better)

    @property
    def net(self) -> np.ndarray:
        return self.off - self.deff


def fit(rows: GameRows, mask: np.ndarray, weights: np.ndarray, lam: float) -> Fit:
    """Weighted ridge solve over the masked rows. Unseen teams get 0 (league average)."""
    n_teams = len(rows.teams)
    sel = np.flatnonzero(mask)
    k = 2 + 2 * n_teams  # mu, home, off[], def[]
    X = np.zeros((len(sel), k))
    X[:, 0] = 1.0
    X[:, 1] = rows.home[sel]
    X[np.arange(len(sel)), 2 + rows.off[sel]] = 1.0
    X[np.arange(len(sel)), 2 + n_teams + rows.opp[sel]] = 1.0
    w = weights[sel]
    y = rows.epa[sel]
    penalty = np.full(k, lam)
    penalty[:2] = 1e-9  # don't shrink intercept or home field
    A = X.T @ (X * w[:, None]) + np.diag(penalty)
    b = X.T @ (w * y)
    beta = np.linalg.solve(A, b)
    return Fit(
        mu=float(beta[0]),
        home=float(beta[1]),
        off=beta[2 : 2 + n_teams],
        deff=beta[2 + n_teams :],
    )


def fit_before(rows: GameRows, t_now: int, lam: float, half_life: float) -> Fit:
    """Fit on games strictly before ``t_now`` from the current and previous season."""
    mask = (rows.t < t_now) & (rows.t >= t_now - 2 * (18 + OFFSEASON_WEEKS))
    decay = 0.5 ** ((t_now - rows.t) / half_life)
    return fit(rows, mask, rows.plays * decay, lam)


def epa_margin(f: Fit, home: int, away: int) -> float:
    """Expected (home offense EPA/play) - (away offense EPA/play), excluding home field."""
    return float((f.off[home] - f.deff[home]) - (f.off[away] - f.deff[away]))


def calibrate(X: np.ndarray, margin: np.ndarray):
    """OLS of point margin on feature columns (no intercept). Returns (b, sigma)."""
    b, *_ = np.linalg.lstsq(X, margin, rcond=None)
    resid = margin - X @ b
    sigma = float(np.sqrt(resid @ resid / max(1, len(margin) - X.shape[1])))
    return b, sigma


def win_prob(margin: float, sigma: float) -> float:
    """P(home wins) assuming final margin ~ Normal(predicted margin, sigma)."""
    return 0.5 * (1 + math.erf(margin / (sigma * math.sqrt(2))))


def walk_forward(rows: GameRows, games: list[dict], lam: float, half_life: float) -> np.ndarray:
    """EPA-margin prediction for each game using only earlier weeks. ``games`` need
    season, week, home, away (team names)."""
    idx = {t: i for i, t in enumerate(rows.teams)}
    out = np.full(len(games), np.nan)
    cache: dict[int, Fit] = {}
    for i, g in enumerate(games):
        if g["home"] not in idx or g["away"] not in idx:
            continue
        t_now = int(time_index(g["season"], g["week"]))
        if t_now not in cache:
            cache[t_now] = fit_before(rows, t_now, lam, half_life)
        out[i] = epa_margin(cache[t_now], idx[g["home"]], idx[g["away"]])
    return out


def _schedule_games(con: duckdb.DuckDBPyConnection) -> list[dict]:
    return records(
        con,
        """
        select game_id, season, week, gameday, home_team as home, away_team as away,
               case when location = 'Neutral' then 0 else 1 end as home_ind,
               result, spread_line as vegas,
               home_qb_id as home_qb, away_qb_id as away_qb,
               home_qb_name, away_qb_name
        from schedule
        where game_type = 'REG' and season >= 2017
        order by season, week, gameday, game_id
        """,
    )


def evaluate(pred: np.ndarray, vegas: np.ndarray, result: np.ndarray) -> dict:
    """Accuracy of model margins vs Vegas on games with a result and a line."""
    ok = ~np.isnan(pred) & ~np.isnan(vegas) & ~np.isnan(result)
    p, v, r = pred[ok], vegas[ok], result[ok]
    # Against the spread: back the side the model likes relative to the line; pushes excluded.
    model_side = np.sign(p - v)
    actual_side = np.sign(r - v)
    decided = (model_side != 0) & (actual_side != 0)
    ats_w = int(np.sum(decided & (model_side == actual_side)))
    ats_l = int(np.sum(decided & (model_side != actual_side)))
    edge = decided & (np.abs(p - v) >= 3)
    edge_w = int(np.sum(edge & (model_side == actual_side)))
    edge_l = int(np.sum(edge & (model_side != actual_side)))
    nontie = r != 0
    return {
        "games": int(ok.sum()),
        "model_mae": float(np.mean(np.abs(p - r))),
        "vegas_mae": float(np.mean(np.abs(v - r))),
        "model_su": float(np.mean(np.sign(p[nontie]) == np.sign(r[nontie]))),
        "vegas_su": float(np.mean(np.sign(v[nontie]) == np.sign(r[nontie]))),
        "ats_w": ats_w,
        "ats_l": ats_l,
        "edge3_w": edge_w,
        "edge3_l": edge_l,
    }


def predictions(con: duckdb.DuckDBPyConnection) -> tuple[dict, list[dict]] | None:
    """Walk-forward backtest + upcoming-game predictions, and weekly power ratings.

    Returns (predictions payload, ratings rows), or None when the loaded seasons don't
    cover FIT_SEASONS (e.g. a single-season dev or CI build).
    """
    from .qb import qb_adjustments  # qb imports this module

    rows = load_rows(con)
    games = _schedule_games(con)
    played_seasons = set(rows.season.tolist())
    games = [g for g in games if g["season"] in played_seasons]
    season = np.array([g["season"] for g in games])
    result = np.array([np.nan if g["result"] is None else float(g["result"]) for g in games])
    vegas = np.array([np.nan if g["vegas"] is None else float(g["vegas"]) for g in games])
    home_ind = np.array([float(g["home_ind"]) for g in games])
    fit_m = np.isin(season, list(FIT_SEASONS)) & ~np.isnan(result)
    if not set(FIT_SEASONS) <= played_seasons or fit_m.sum() < 100:
        return None

    # Tune ridge strength and recency on FIT only (by point-margin MAE after calibration).
    best = None
    for lam in LAMBDAS:
        for hl in HALF_LIVES:
            x = walk_forward(rows, games, lam, hl)
            m = fit_m & ~np.isnan(x)
            X = np.column_stack([x, home_ind])
            b, _ = calibrate(X[m], result[m])
            mae = float(np.mean(np.abs(X[m] @ b - result[m])))
            if best is None or mae < best[0]:
                best = (mae, lam, hl, x)
    _, lam, hl, x = best

    home_qb, away_qb = qb_adjustments(con, games)
    X = np.column_stack([x, home_qb - away_qb, home_ind])
    usable = ~np.isnan(x)

    # Honest numbers: coefficients from FIT only, scored on every split.
    m = fit_m & usable
    b_fit, sigma_fit = calibrate(X[m], result[m])
    pred_fit = X @ b_fit
    summary = []
    for name, seasons in (
        ("fit", FIT_SEASONS),
        ("validate", VALIDATE_SEASONS),
        ("test", TEST_SEASONS),
    ):
        sel = np.isin(season, list(seasons))
        summary.append({"split": name} | evaluate(pred_fit[sel], vegas[sel], result[sel]))
    by_season = []
    for s in sorted(set(season.tolist())):
        sel = season == s
        if np.any(~np.isnan(result[sel])):
            by_season.append({"season": s} | evaluate(pred_fit[sel], vegas[sel], result[sel]))

    # Production coefficients: every completed game, for the in-season forecasts.
    done = ~np.isnan(result) & usable
    b_all, sigma_all = calibrate(X[done], result[done])
    pred = X @ b_all

    game_rows = []
    upcoming = []
    latest = max(played_seasons)
    for i, g in enumerate(games):
        if not usable[i]:
            continue
        played = not np.isnan(result[i])
        # Backtest rows use FIT-only coefficients so they match the reported metrics.
        b = b_fit if played else b_all
        margin = float(pred_fit[i] if played else pred[i])
        row = {
            "season": g["season"],
            "week": g["week"],
            "game_id": g["game_id"],
            "gameday": g["gameday"],
            "home": g["home"],
            "away": g["away"],
            "neutral": not g["home_ind"],
            "model": margin,
            "vegas": None if np.isnan(vegas[i]) else float(vegas[i]),
            "home_wp": win_prob(margin, sigma_fit if played else sigma_all),
            # Points the starting-QB adjustment adds to each side's expected score.
            "home_qb_pts": float(home_qb[i] * b[1]),
            "away_qb_pts": float(away_qb[i] * b[1]),
            "home_qb": g["home_qb_name"],
            "away_qb": g["away_qb_name"],
        }
        if not played:
            if g["season"] == latest:
                upcoming.append(row)
        else:
            game_rows.append(row | {"result": float(result[i])})

    # Only the next unplayed week is a real forecast; later weeks would reuse stale ratings.
    if upcoming:
        next_week = min(u["week"] for u in upcoming)
        upcoming = [u for u in upcoming if u["week"] == next_week]

    span = lambda r: [min(r), max(r)]  # noqa: E731
    payload = {
        "params": {
            "lambda": lam,
            "half_life_weeks": None if hl >= 1e9 else hl,
            "points_per_epa": float(b_all[0]),
            "qb_weight": float(b_all[1]),
            "home_points": float(b_all[2]),
            "sigma": sigma_all,
            "fit_seasons": span(FIT_SEASONS),
            "validate_seasons": span(VALIDATE_SEASONS),
            "test_seasons": span(TEST_SEASONS),
        },
        "summary": summary,
        "by_season": by_season,
        "games": game_rows,
        "upcoming": upcoming,
    }
    return payload, weekly_ratings(rows, lam, hl, b_all[0])


def weekly_ratings(rows: GameRows, lam: float, half_life: float, pts_per_epa: float) -> list[dict]:
    """Predictive power rating for each team after each completed week of each season."""
    out = []
    for s in sorted(set(rows.season.tolist())):
        if s == rows.season.min():
            continue  # first season has no prior-year data to stabilize early weeks
        for w in sorted(set(rows.week[rows.season == s].tolist())):
            f = fit_before(rows, int(time_index(s, w + 1)), lam, half_life)
            played = set(rows.off[(rows.season == s) & (rows.week <= w)].tolist())
            order = np.argsort(-f.net)
            rank = np.empty(len(order), dtype=int)
            rank[order] = np.arange(1, len(order) + 1)
            for i, team in enumerate(rows.teams):
                if i not in played:
                    continue
                out.append(
                    {
                        "season": s,
                        "week": w,
                        "team": team,
                        "off": float(f.off[i]),
                        "def": float(f.deff[i]),
                        "net": float(f.net[i]),
                        "points": float(f.net[i] * pts_per_epa),
                        # Points contributed by each unit; positive is good for both.
                        "off_points": float(f.off[i] * pts_per_epa),
                        "def_points": float(-f.deff[i] * pts_per_epa),
                        "rank": int(rank[i]),
                    }
                )
    return out


def adjusted_team_seasons(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Season-only opponent- and home-adjusted EPA/play per team, for both scopes."""
    out = []
    for scope in ("all", "no_garbage"):
        rows = load_rows(con, scope)
        for s in sorted(set(rows.season.tolist())):
            mask = rows.season == s
            f = fit(rows, mask, rows.plays, DESCRIPTIVE_LAMBDA)
            present = set(rows.off[mask].tolist())
            for i, team in enumerate(rows.teams):
                if i in present:
                    out.append(
                        {
                            "scope": scope,
                            "season": s,
                            "team": team,
                            "adj_off_epa": f.mu + float(f.off[i]),
                            "adj_def_epa": f.mu + float(f.deff[i]),
                            "adj_net_epa": float(f.net[i]),
                        }
                    )
    return out
