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
from dataclasses import dataclass

import duckdb
import numpy as np

from . import lab2, strength
from .ratings import FIT_SEASONS, TEST_SEASONS, VALIDATE_SEASONS

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


# ---------------------------------------------------------------- production forecast

ROUND1 = ["epa_margin", "qb_adj", "home_ind"]
ROUND2 = VARIANTS["Round 2 model: EPA + QB + injuries"]
SIM_FEATURES = ["epa_margin", "mov_margin", "home_ind"]


@dataclass
class Forecast:
    """The frozen round-3 model, fit two ways: FIT-only (backtests, simulator) and on
    every completed season before the current one (live forecasts)."""

    cols: list[str]
    beta_fit: np.ndarray
    sigma_fit: float
    beta_live: np.ndarray
    se_live: np.ndarray
    sigma_live: float
    blend_k: float  # market blend: line + k * (model - line), k fit on FIT
    pred_fit: np.ndarray  # per game, FIT coefficients
    pred_live: np.ndarray  # per game, live coefficients
    sim_beta: np.ndarray  # rating-only (epa, mov, home), FIT
    sim_sigma: float
    current: int


def _sigma(pred: np.ndarray, y: np.ndarray, mask: np.ndarray) -> float:
    ok = mask & ~np.isnan(pred) & ~np.isnan(y)
    return float(np.sqrt(np.mean((pred - y)[ok] ** 2)))


def fit_forecast(f: dict[str, np.ndarray]) -> Forecast:
    cols = VARIANTS[(FROZEN or {"variant": choose(run_selection(f))["variant"]})["variant"]]
    fit_m = lab2.seasons_mask(f, FIT_SEASONS)
    current = int(np.nanmax(f["season"]))
    before = f["season"] < current
    X = lab2.design(f, cols)
    b_fit, _ = lab2.fit(f, cols, fit_m)
    b_live, se_live = lab2.fit(f, cols, before)
    pred_fit, pred_live = X @ b_fit, X @ b_live
    ok = fit_m & ~np.isnan(f["vegas"]) & ~np.isnan(pred_fit) & ~np.isnan(f["result"])
    d = (pred_fit - f["vegas"])[ok]
    k = float(d @ (f["result"] - f["vegas"])[ok] / (d @ d))
    sb, _ = lab2.fit(f, SIM_FEATURES, fit_m)
    sim_pred = lab2.design(f, SIM_FEATURES) @ sb
    return Forecast(
        cols=cols,
        beta_fit=b_fit,
        sigma_fit=_sigma(pred_fit, f["result"], fit_m),
        beta_live=b_live,
        se_live=se_live,
        sigma_live=_sigma(pred_live, f["result"], before),
        blend_k=k,
        pred_fit=pred_fit,
        pred_live=pred_live,
        sim_beta=sb,
        sim_sigma=_sigma(sim_pred, f["result"], fit_m),
        current=current,
    )


def blend(line: np.ndarray, model: np.ndarray, k: float) -> np.ndarray:
    return np.where(np.isnan(line), model, line + k * (model - line))


def sim_inputs(fc: Forecast, games: list[dict], f: dict[str, np.ndarray], mov: dict, params):
    """(SimModel, overrides) for sim.playoff_odds: FIT-only rating coefficients, and for
    each game the best pregame number (market blend, else the full model)."""
    from .sim import SimModel

    pred = np.where(f["season"] == fc.current, fc.pred_live, fc.pred_fit)
    best = blend(f["vegas"], pred, fc.blend_k)
    overrides = {g["game_id"]: float(best[i]) for i, g in enumerate(games) if np.isfinite(best[i])}
    model = SimModel(
        epa_lam=params["lambda"],
        epa_half_life=params["half_life_weeks"] or 1e9,
        mov_lam=mov["lambda"],
        mov_half_life=mov["half_life_weeks"],
        b_epa=float(fc.sim_beta[0]),
        b_mov=float(fc.sim_beta[1]),
        b_home=float(fc.sim_beta[2]),
        sigma=fc.sim_sigma,
    )
    return model, overrides


def paired(a: np.ndarray, b: np.ndarray, y: np.ndarray, mask: np.ndarray) -> dict | None:
    """Mean difference in squared error (a - b) with its standard error; < 0 favors a."""
    ok = mask & ~np.isnan(a) & ~np.isnan(b) & ~np.isnan(y)
    if ok.sum() < 2:
        return None
    d = (a - y)[ok] ** 2 - (b - y)[ok] ** 2
    se = float(d.std(ddof=1) / np.sqrt(len(d)))
    return {"games": int(ok.sum()), "diff": float(d.mean()), "se": se}


def lab(
    games: list[dict],
    f: dict[str, np.ndarray],
    fc: Forecast,
    inj: dict,
    odds: list[tuple[int, dict]],
    v1_brier: dict,
) -> dict:
    selection = run_selection(f)
    chosen = choose(selection)
    frozen = FROZEN or {"variant": chosen["variant"]}
    y, line = f["result"], f["vegas"]
    days = np.array([str(g["gameday"]) for g in games])
    cur = f["season"] == fc.current
    has_line = ~np.isnan(line)
    splits = {
        "fit": lab2.seasons_mask(f, FIT_SEASONS),
        "validate": lab2.seasons_mask(f, VALIDATE_SEASONS),
        "test": lab2.seasons_mask(f, TEST_SEASONS),
        "pre_freeze": cur & (days <= FREEZE_DATE),
        "sealed": cur & (days > FREEZE_DATE),
    }
    fit_m = splits["fit"]

    def model_pred(cols):
        b, _ = lab2.fit(f, cols, fit_m)
        return lab2.design(f, cols) @ b

    r1, r2 = model_pred(ROUND1), model_pred(ROUND2)
    # Live rows use live coefficients; backtests use FIT-only ones.
    r3 = np.where(cur, fc.pred_live, fc.pred_fit)
    sig = lambda p: _sigma(p, y, fit_m)  # noqa: E731
    candidates = {
        "round3": (r3, fc.sigma_fit),
        "blend": (
            blend(line, r3, fc.blend_k),
            _sigma(blend(line, fc.pred_fit, fc.blend_k), y, fit_m),
        ),
        "vegas": (line, sig(line)),
        "round2": (r2, sig(r2)),
        "round1": (r1, sig(r1)),
    }
    comparison = {}
    for split, m in splits.items():
        mm = m & has_line
        comparison[split] = {name: metrics(p, s, f, mm) for name, (p, s) in candidates.items()}
        comparison[split]["round3_vs_vegas"] = paired(r3, line, y, mm)
        comparison[split]["round3_vs_round1"] = paired(r3, r1, y, mm)
        comparison[split]["blend_vs_vegas"] = paired(candidates["blend"][0], line, y, mm)

    by_season = []
    for s in sorted(set(f["season"].astype(int).tolist())):
        m = (f["season"] == s) & has_line
        row = {"season": s}
        for name in ("round3", "vegas", "round1"):
            mt = metrics(candidates[name][0], candidates[name][1], f, m)
            row[name] = mt.get("rmse")
        row["games"] = metrics(r3, fc.sigma_fit, f, m).get("games", 0)
        by_season.append(row)

    X = lab2.design(f, fc.cols)
    played = ~np.isnan(y)
    contrib_sd = {
        c: float(np.nanstd(X[(f["season"] < fc.current) & played, j] * fc.beta_live[j]))
        for j, c in enumerate(fc.cols)
    }
    coefficients = [
        {
            "feature": c,
            "label": LABELS.get(c, c),
            "beta": float(fc.beta_live[j]),
            "se": float(fc.se_live[j]),
            "typical_points": contrib_sd[c],
        }
        for j, c in enumerate(fc.cols)
    ]

    sim_rows = []
    for season, p in odds:
        sim_rows.append(
            {
                "season": season,
                "brier_playoffs": _brier(p, "p_playoffs", "made_playoffs"),
                "brier_division": _brier(p, "p_division", "won_division"),
                "v1_brier_playoffs": v1_brier.get(str(season), {}).get("brier_playoffs"),
                "v1_brier_division": v1_brier.get(str(season), {}).get("brier_division"),
            }
        )

    upcoming = []
    unplayed = np.flatnonzero(cur & ~played & ~np.isnan(fc.pred_live))
    if len(unplayed):
        nxt = min(games[i]["week"] for i in unplayed)
        for i in unplayed:
            g = games[i]
            if g["week"] != nxt:
                continue
            m = float(fc.pred_live[i])
            bl = float(blend(line[i : i + 1], np.array([m]), fc.blend_k)[0])
            upcoming.append(
                {
                    "game_id": g["game_id"],
                    "week": g["week"],
                    "home": g["home"],
                    "away": g["away"],
                    "vegas": None if np.isnan(line[i]) else float(line[i]),
                    "model": m,
                    "blend": bl,
                    "home_wp": float(normal_cdf(np.array([m / fc.sigma_live]))[0]),
                    "blend_wp": float(normal_cdf(np.array([bl / fc.sigma_live]))[0]),
                    "factors": [
                        {
                            "feature": c,
                            "label": LABELS.get(c, c),
                            "points": float(X[i, j] * fc.beta_live[j]),
                        }
                        for j, c in enumerate(fc.cols)
                    ],
                    "injuries": {
                        side: sorted(
                            inj.get((g["season"], g["week"], g[side]), {}).get("players", []),
                            key=lambda p: -p["impact"],
                        )
                        for side in ("home", "away")
                    },
                }
            )

    span = lambda r: [min(r), max(r)]  # noqa: E731
    return {
        "protocol": {
            "fit_seasons": span(FIT_SEASONS),
            "validate_seasons": span(VALIDATE_SEASONS),
            "test_seasons": span(TEST_SEASONS),
            "freeze_date": FREEZE_DATE,
            "live_season": fc.current,
        },
        "variants": VARIANTS,
        "labels": LABELS,
        "selection": selection,
        "chosen": frozen,
        "selection_agrees": chosen["variant"] == frozen["variant"],
        "sigma": fc.sigma_live,
        "blend_k": fc.blend_k,
        "coefficients": coefficients,
        "comparison": comparison,
        "by_season": by_season,
        "sim": {
            "b_epa": float(fc.sim_beta[0]),
            "b_mov": float(fc.sim_beta[1]),
            "b_home": float(fc.sim_beta[2]),
            "sigma": fc.sim_sigma,
            "seasons": sim_rows,
        },
        "upcoming": upcoming,
    }


def _brier(p: dict, key: str, field: str) -> float | None:
    if not p.get("actual"):
        return None
    errs = [
        (r[key] - float(p["actual"][r["team"]][field])) ** 2
        for r in p["rows"]
        if r["team"] in p["actual"] and field in p["actual"][r["team"]]
    ]
    return float(np.mean(errs)) if errs else None


def apply_to_predictions(preds: dict, games: list[dict], f, fc: Forecast) -> dict:
    """Make round 3 the site's forecast in predictions.json: per-game model margins and
    win probabilities, accuracy summaries, and the QB points rescaled to round 3's weight."""
    from .ratings import evaluate, win_prob

    cur = f["season"] == fc.current
    pred = np.where(cur, fc.pred_live, fc.pred_fit)
    by_id = {g["game_id"]: i for i, g in enumerate(games)}
    j_qb = fc.cols.index("qb_adj") if "qb_adj" in fc.cols else None
    old_qb = preds["params"]["qb_weight"]
    new_qb = float(fc.beta_live[j_qb]) if j_qb is not None else 0.0

    def update(row: dict, played: bool) -> dict:
        i = by_id.get(row["game_id"])
        if i is None or np.isnan(pred[i]):
            return row
        sigma = fc.sigma_fit if played else fc.sigma_live
        m = float(pred[i])
        line = f["vegas"][i]
        scale = new_qb / old_qb if old_qb else 0.0
        return row | {
            "model": m,
            "home_wp": win_prob(m, sigma),
            "blend": float(blend(np.array([line]), np.array([m]), fc.blend_k)[0]),
            "home_qb_pts": row["home_qb_pts"] * scale,
            "away_qb_pts": row["away_qb_pts"] * scale,
        }

    preds["games"] = [update(r, True) for r in preds["games"]]
    preds["upcoming"] = [update(r, False) for r in preds["upcoming"]]
    season = f["season"]
    summary = []
    for name, seasons in (
        ("fit", FIT_SEASONS),
        ("validate", VALIDATE_SEASONS),
        ("test", TEST_SEASONS),
    ):
        sel = np.isin(season, list(seasons))
        summary.append({"split": name} | evaluate(pred[sel], f["vegas"][sel], f["result"][sel]))
    preds["summary"] = summary
    preds["by_season"] = [
        {"season": int(s)}
        | evaluate(pred[season == s], f["vegas"][season == s], f["result"][season == s])
        for s in sorted(set(season.astype(int).tolist()))
        if np.any(~np.isnan(f["result"][season == s]))
    ]
    preds["params"] |= {
        "model": FROZEN["variant"] if FROZEN else None,
        "sigma": fc.sigma_live,
        "qb_weight": new_qb,
        "blend_k": fc.blend_k,
    }
    return preds
