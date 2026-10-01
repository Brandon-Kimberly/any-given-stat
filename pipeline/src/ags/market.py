"""Trying to beat the closing line, with a protocol that can't fool itself.

Protocol (fixed before any results were looked at):

- FIT seasons fit coefficients; VALIDATE seasons choose between the pre-registered
  VARIANTS and the bet threshold; TEST seasons are scored once, at the end.
- The bar is the closing spread (nflverse ``spread_line``). Bets are assumed to be at
  -110, so break-even is 110/210 = 52.38%.
- Every variant is reported, including the ones that fail.

All features are walk-forward: a game's inputs use only games played before its week.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import duckdb
import numpy as np

from . import ratings
from .db import records
from .qb import qb_adjustments
from .ratings import FIT_SEASONS, TEST_SEASONS, VALIDATE_SEASONS

BREAKEVEN = 110 / 210
THRESHOLDS = (0.0, 1.0, 2.0, 3.0)  # min |prediction - line| (points) to place a bet


@dataclass
class GameFrame:
    season: np.ndarray
    week: np.ndarray
    home: list[str]
    away: list[str]
    game_id: list[str]
    vegas: np.ndarray  # closing home margin
    result: np.ndarray  # actual home margin (nan if unplayed)
    home_ind: np.ndarray  # 1 home field, 0 neutral
    epa_margin: np.ndarray  # walk-forward EPA rating gap (home - away), no home field
    qb_adj: np.ndarray  # points: (home starter vs home baseline) - (away starter vs baseline)
    rest_diff: np.ndarray  # home rest days - away rest days
    div: np.ndarray


def build_frame(con: duckdb.DuckDBPyConnection, lam: float = 3000.0, half_life: float = 16.0):
    games = records(
        con,
        """
        select game_id, season, week, home_team as home, away_team as away,
               case when location = 'Neutral' then 0 else 1 end as home_ind,
               result, spread_line as vegas, home_qb_id as home_qb, away_qb_id as away_qb,
               home_rest, away_rest, div_game
        from schedule
        where game_type = 'REG' and season >= 2017
        order by season, week, game_id
        """,
    )
    rows = ratings.load_rows(con)
    seasons_loaded = set(rows.season.tolist())
    games = [g for g in games if g["season"] in seasons_loaded]
    f = lambda k: np.array([np.nan if g[k] is None else float(g[k]) for g in games])  # noqa: E731
    return GameFrame(
        season=np.array([g["season"] for g in games]),
        week=np.array([g["week"] for g in games]),
        home=[g["home"] for g in games],
        away=[g["away"] for g in games],
        game_id=[g["game_id"] for g in games],
        vegas=f("vegas"),
        result=f("result"),
        home_ind=f("home_ind"),
        epa_margin=ratings.walk_forward(rows, games, lam, half_life),
        qb_adj=np.subtract(*qb_adjustments(con, games)),
        rest_diff=np.nan_to_num(f("home_rest") - f("away_rest")),
        div=np.nan_to_num(f("div_game")),
    )


# Pre-registered variants: name -> feature columns for an OLS of the final home margin.
# "market" variants include the closing line as a feature, i.e. they ask whether anything
# adds information beyond it.
VARIANTS: dict[str, list[str]] = {
    "EPA ratings": ["epa_margin", "home_ind"],
    "EPA + QB": ["epa_margin", "qb_adj", "home_ind"],
    "EPA + QB + rest": ["epa_margin", "qb_adj", "rest_diff", "home_ind"],
    "Market + EPA": ["vegas", "epa_margin"],
    "Market + EPA + QB": ["vegas", "epa_margin", "qb_adj"],
    "Market + EPA + QB + rest + div": ["vegas", "epa_margin", "qb_adj", "rest_diff", "div"],
}


def design(fr: GameFrame, cols: list[str]) -> np.ndarray:
    return np.column_stack([getattr(fr, c) for c in cols])


def fit_variant(fr: GameFrame, cols: list[str], mask: np.ndarray) -> np.ndarray:
    X = design(fr, cols)
    ok = mask & ~np.isnan(fr.result) & ~np.isnan(X).any(axis=1)
    beta, *_ = np.linalg.lstsq(X[ok], fr.result[ok], rcond=None)
    return beta


def score(pred: np.ndarray, fr: GameFrame, mask: np.ndarray, threshold: float = 0.0) -> dict:
    """ATS record betting the model's side when |pred - line| >= threshold, plus MAE."""
    ok = mask & ~np.isnan(pred) & ~np.isnan(fr.vegas) & ~np.isnan(fr.result)
    p, v, r = pred[ok], fr.vegas[ok], fr.result[ok]
    side = np.sign(p - v)
    actual = np.sign(r - v)
    bet = (np.abs(p - v) >= max(threshold, 1e-9)) & (side != 0) & (actual != 0)
    w = int(np.sum(bet & (side == actual)))
    n = int(bet.sum())
    return {
        "games": int(ok.sum()),
        "mae": float(np.mean(np.abs(p - r))),
        "vegas_mae": float(np.mean(np.abs(v - r))),
        "bets": n,
        "wins": w,
        "win_rate": w / n if n else None,
        "p_value": binom_p_value(w, n, BREAKEVEN) if n else None,
    }


def binom_p_value(wins: int, n: int, p0: float) -> float:
    """One-sided P(X >= wins) for X ~ Binomial(n, p0), via exact summation in log space."""
    if n == 0:
        return 1.0
    log_terms = [
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p0)
        + (n - k) * math.log(1 - p0)
        for k in range(wins, n + 1)
    ]
    m = max(log_terms)
    return float(min(1.0, math.exp(m) * sum(math.exp(t - m) for t in log_terms)))


def seasons_mask(fr: GameFrame, seasons: range) -> np.ndarray:
    return np.isin(fr.season, list(seasons))


def run_selection(fr: GameFrame) -> list[dict]:
    """Fit on FIT, score every variant x threshold on VALIDATE. TEST is not touched."""
    fit_m = seasons_mask(fr, FIT_SEASONS)
    val_m = seasons_mask(fr, VALIDATE_SEASONS)
    out = []
    for name, cols in VARIANTS.items():
        beta = fit_variant(fr, cols, fit_m)
        pred = design(fr, cols) @ beta
        for th in THRESHOLDS:
            out.append(
                {"variant": name, "threshold": th, "beta": beta.tolist()}
                | {f"fit_{k}": v for k, v in score(pred, fr, fit_m, th).items()}
                | {f"val_{k}": v for k, v in score(pred, fr, val_m, th).items()}
            )
    return out


MIN_VALIDATE_BETS = 100


def choose(selection: list[dict]) -> dict | None:
    """Pre-registered rule: best validation win rate among options with enough bets."""
    eligible = [r for r in selection if r["val_bets"] >= MIN_VALIDATE_BETS]
    return max(eligible, key=lambda r: r["val_win_rate"]) if eligible else None


def lab(con: duckdb.DuckDBPyConnection, lam: float, half_life: float) -> dict | None:
    """The full beat-the-line experiment: selection on VALIDATE, one scored look at TEST."""
    fr = build_frame(con, lam, half_life)
    if not set(TEST_SEASONS) <= set(fr.season.tolist()):
        return None
    selection = run_selection(fr)
    chosen = choose(selection)
    test = None
    if chosen is not None:
        cols = VARIANTS[chosen["variant"]]
        pred = design(fr, cols) @ np.array(chosen["beta"])
        test = score(pred, fr, seasons_mask(fr, TEST_SEASONS), chosen["threshold"])
    span = lambda r: [min(r), max(r)]  # noqa: E731
    return {
        "protocol": {
            "fit_seasons": span(FIT_SEASONS),
            "validate_seasons": span(VALIDATE_SEASONS),
            "test_seasons": span(TEST_SEASONS),
            "breakeven": BREAKEVEN,
            "thresholds": list(THRESHOLDS),
            "min_validate_bets": MIN_VALIDATE_BETS,
        },
        "variants": {name: cols for name, cols in VARIANTS.items()},
        "selection": selection,
        "chosen": None
        if chosen is None
        else {"variant": chosen["variant"], "threshold": chosen["threshold"]},
        "test": test,
    }
