"""Round 3: the most accurate forecast public data can make (not a betting system).

Rounds 1-2 asked "can we beat the line?". This round asks "how close can we get to what
actually happens?", judged by squared error of the predicted margin (RMSE) and by the
log loss of win probabilities, and it feeds the site's predictions and playoff odds.

Protocol, fixed before any round-3 result was looked at:

- Candidates in ``VARIANTS`` are OLS calibrations of the final home margin, coefficients
  fit on FIT. The lowest VALIDATE RMSE wins (ties: fewer features). Win probabilities
  use Normal(margin, sigma) with sigma from FIT residuals.
- TEST (2024-2025) is reported as reused (rounds 1-2 already looked there).
- The choice is frozen in ``FROZEN`` on ``FREEZE_DATE``; games after it are the clean test.
- Separately, a market blend ``line + k * (model - line)`` with k fit on FIT shows how much
  the model adds to the betting line as a forecast. It is reported, never selected on.
"""

from __future__ import annotations

import math

import duckdb
import numpy as np

from . import lab2, strength
from .ratings import FIT_SEASONS, VALIDATE_SEASONS

FREEZE_DATE = "2026-10-02"
# From run_selection() on FREEZE_DATE, committed before any TEST or live result was computed:
# validate RMSE 12.677 vs 12.768 for the round-2 model (Vegas: 12.281), log loss 0.6414.
FROZEN: dict | None = {"variant": "EPA + points ratings + QB + injuries"}

RATING = ["epa_margin", "home_ind"]
VARIANTS: dict[str, list[str]] = {
    "Round 2 model: EPA + QB + injuries": ["epa_margin", "qb_adj", "home_ind", "inj_total"],
    "EPA + points ratings + QB + injuries": [
        "epa_margin",
        "mov_margin",
        "qb_adj",
        "home_ind",
        "inj_total",
    ],
    "Points ratings + QB + injuries": ["mov_margin", "qb_adj", "home_ind", "inj_total"],
    "EPA + points + QB + injuries by position": [
        "epa_margin",
        "mov_margin",
        "qb_adj",
        "home_ind",
        *lab2.INJ_GROUPS,
    ],
    "EPA + points + QB + injuries + spots + weather": [
        "epa_margin",
        "mov_margin",
        "qb_adj",
        "home_ind",
        "inj_total",
        *lab2.SPOTS,
        *lab2.WEATHER_DIV,
    ],
}
LABELS = lab2.LABELS | {"mov_margin": "Points ratings"}


def add_mov(con: duckdb.DuckDBPyConnection, games: list[dict], f: dict[str, np.ndarray]) -> dict:
    """Add walk-forward points-rating margins (tuned on FIT) to the feature frame."""
    from . import ratings

    teams = ratings.load_rows(con).teams
    rows = strength.load_mov_rows(con, teams)
    lam, hl, x = strength.tune_mov(rows, games, f["result"], f["home_ind"])
    f["mov_margin"] = x
    return {"lambda": lam, "half_life_weeks": hl}


def normal_cdf(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))


def metrics(pred: np.ndarray, sigma: float, f: dict[str, np.ndarray], mask: np.ndarray) -> dict:
    """RMSE / MAE of the margin, and win-probability log loss / Brier (ties excluded)."""
    y = f["result"]
    ok = mask & ~np.isnan(pred) & ~np.isnan(y)
    if not ok.any():
        return {"games": 0}
    e = pred[ok] - y[ok]
    decided = ok & (y != 0)
    p = np.clip(normal_cdf(pred[decided] / sigma), 1e-6, 1 - 1e-6)
    won = (y[decided] > 0).astype(float)
    return {
        "games": int(ok.sum()),
        "rmse": float(np.sqrt(np.mean(e**2))),
        "mae": float(np.mean(np.abs(e))),
        "log_loss": float(-np.mean(won * np.log(p) + (1 - won) * np.log(1 - p))),
        "brier": float(np.mean((p - won) ** 2)),
        "winner": float(np.mean((pred[decided] > 0) == (won == 1))),
    }


def run_selection(f: dict[str, np.ndarray]) -> list[dict]:
    fit_m = lab2.seasons_mask(f, FIT_SEASONS)
    val_m = lab2.seasons_mask(f, VALIDATE_SEASONS)
    out = []
    for name, cols in VARIANTS.items():
        beta, _ = lab2.fit(f, cols, fit_m)
        pred = lab2.design(f, cols) @ beta
        resid = (pred - f["result"])[fit_m & ~np.isnan(f["result"]) & ~np.isnan(pred)]
        sigma = float(np.sqrt(np.mean(resid**2)))
        out.append(
            {"variant": name, "features": len(cols), "sigma": sigma}
            | {f"fit_{k}": v for k, v in metrics(pred, sigma, f, fit_m).items()}
            | {f"val_{k}": v for k, v in metrics(pred, sigma, f, val_m).items()}
        )
    return out


def choose(selection: list[dict]) -> dict:
    return min(selection, key=lambda r: (round(r["val_rmse"], 3), r["features"]))
