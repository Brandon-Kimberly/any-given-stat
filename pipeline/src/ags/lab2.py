"""Round 2 of beating the closing line: everything public data can say about a game.

Round 1 (``market.py``) used team ratings, the starting QB and rest. Round 2 adds what its
page said the market still knew: other injuries, travel, weather, division familiarity and
late-season motivation (``context.py``), plus known betting-market biases.

Protocol, written before any round-2 result was looked at:

- Same splits and rule as round 1: coefficients fit on FIT, variant and bet threshold
  chosen on VALIDATE (best win rate with 100+ bets), nothing tuned on anything else.
- TEST (2024-2025) is reported but labeled reused: its round-1 results were seen before
  round 2 was designed, so it is not a clean test any more.
- The clean test is live: the choice is frozen in ``FROZEN`` (committed on ``FREEZE_DATE``)
  and only games played after that date count as sealed. Live coefficients are refit on
  every completed season before the current one, a fixed rule with no choices in it.
"""

from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np

from . import context, ratings
from .db import has_relation, records
from .forecast import fetch_forecast
from .market import BREAKEVEN, MIN_VALIDATE_BETS, THRESHOLDS, binom_p_value
from .qb import qb_adjustments
from .ratings import FIT_SEASONS, TEST_SEASONS, VALIDATE_SEASONS

FREEZE_DATE = "2026-10-02"
# From run_selection() on FREEZE_DATE, committed before any TEST or live result was
# computed (validate: 78-65, 54.5% on 143 bets). Later builds re-run the selection and
# report whether it still agrees; the frozen choice is what gets scored either way.
FROZEN: dict | None = {"variant": "Ratings + QB + injuries", "threshold": 3.0}

BASE = ["epa_margin", "qb_adj", "home_ind"]
INJ_TOTAL = ["inj_total"]
INJ_GROUPS = [f"inj_{g}" for g in context.INJURY_GROUPS]
SPOTS = ["rest_diff", "bye_diff", "tz_crossed", "west_early", "stakes_diff"]
WEATHER_DIV = ["wind_x_margin", "cold_x_margin", "dome_cold", "div_x_margin"]

VARIANTS: dict[str, list[str]] = {
    "Ratings + QB + injuries": BASE + INJ_TOTAL,
    "Ratings + QB + injuries by position": BASE + INJ_GROUPS,
    "+ schedule spots": BASE + INJ_TOTAL + SPOTS,
    "+ weather and division": BASE + INJ_TOTAL + SPOTS + WEATHER_DIV,
    "Everything": BASE + INJ_GROUPS + SPOTS + WEATHER_DIV,
    "Market + injuries": ["vegas", "inj_total"],
    "Market + everything": ["vegas", "epa_margin", "qb_adj"] + INJ_GROUPS + SPOTS + WEATHER_DIV,
    "Market + known biases": ["vegas", "home_dog", "stakes_diff", "west_early", "bye_diff"],
}

LABELS = {
    "vegas": "Closing line",
    "epa_margin": "Team ratings",
    "qb_adj": "Starting QB",
    "home_ind": "Home field",
    "inj_total": "Injuries (all)",
    "inj_ol": "Injuries: offensive line",
    "inj_wr_te": "Injuries: WR/TE",
    "inj_rb": "Injuries: RB",
    "inj_front": "Injuries: DL/LB",
    "inj_db": "Injuries: secondary",
    "rest_diff": "Rest days",
    "bye_diff": "Off a bye",
    "tz_crossed": "Time zones traveled",
    "west_early": "West coast team, early kickoff",
    "stakes_diff": "Late-season stakes",
    "wind_x_margin": "Wind (shrinks the margin)",
    "cold_x_margin": "Cold (shrinks the margin)",
    "dome_cold": "Dome team in the cold",
    "div_x_margin": "Division game (shrinks the margin)",
    "home_dog": "Home underdog",
}


def build_frame(
    con: duckdb.DuckDBPyConnection,
    lam: float,
    half_life: float,
    odds: dict[int, dict],
    forecasts: bool = True,
) -> tuple[list[dict], dict[str, np.ndarray], dict]:
    """(games, features, injury details). Features are home-minus-away or interactions."""
    games = records(
        con,
        """
        select game_id, season, week, gameday, gametime, home_team as home, away_team as away,
               case when location = 'Neutral' then 0 else 1 end as home_ind,
               result, spread_line as vegas, home_qb_id as home_qb, away_qb_id as away_qb,
               home_rest, away_rest, div_game, roof, temp, wind
        from schedule
        where game_type = 'REG' and season >= 2017
        order by season, week, game_id
        """,
    )
    rows = ratings.load_rows(con)
    loaded = set(rows.season.tolist())
    games = [g for g in games if g["season"] in loaded]
    num = lambda k: np.array(  # noqa: E731
        [np.nan if g[k] is None else float(g[k]) for g in games]
    )
    n = len(games)
    f: dict[str, np.ndarray] = {
        "vegas": num("vegas"),
        "result": num("result"),
        "home_ind": num("home_ind"),
        "epa_margin": ratings.walk_forward(rows, games, lam, half_life),
    }
    home_qb, away_qb = qb_adjustments(con, games)
    f["qb_adj"] = home_qb - away_qb

    keys = [(g["season"], g["week"], t) for g in games for t in (g["home"], g["away"])]
    inj = context.injury_impacts(con, keys)
    for grp in context.INJURY_GROUPS:
        f[f"inj_{grp}"] = np.array(
            [
                inj.get((g["season"], g["week"], g["home"]), {}).get(grp, 0.0)
                - inj.get((g["season"], g["week"], g["away"]), {}).get(grp, 0.0)
                for g in games
            ]
        )
    f["inj_total"] = sum(f[f"inj_{grp}"] for grp in context.INJURY_GROUPS)

    rest_h, rest_a = np.nan_to_num(num("home_rest"), nan=7), np.nan_to_num(num("away_rest"), nan=7)
    f["rest_diff"] = rest_h - rest_a
    f["bye_diff"] = (rest_h >= 13).astype(float) - (rest_a >= 13).astype(float)
    trav = [context.travel(g["home"], g["away"], g["home_ind"], g["gametime"]) for g in games]
    f["tz_crossed"] = np.array([t[0] for t in trav])
    f["west_early"] = np.array([t[1] for t in trav])

    set_stakes(games, f, odds)

    domes = context.dome_teams(con)
    today = dt.date.today().isoformat()
    wind = np.zeros(n)
    cold = np.zeros(n)
    dome_cold = np.zeros(n)
    weather_src = [None] * n
    for i, g in enumerate(games):
        temp, wnd = g["temp"], g["wind"]
        if temp is None and wnd is None and g["result"] is None and forecasts:
            soon = g["gameday"] and today <= str(g["gameday"]) <= _days_ahead(7)
            if soon and g["home_ind"] and g["roof"] in ("outdoors", "open"):
                fc = fetch_forecast(g["home"], str(g["gameday"]), g["gametime"])
                if fc:
                    temp, wnd = fc
                    weather_src[i] = "forecast"
        elif temp is not None or wnd is not None:
            weather_src[i] = "recorded"
        w, c, outdoors = context.weather(g["roof"], temp, wnd)
        wind[i], cold[i] = w, c
        away_dome = domes.get((g["season"], g["away"]), False)
        home_dome = domes.get((g["season"], g["home"]), False)
        dome_cold[i] = float(outdoors and c > 0 and away_dome and not home_dome)
        g["temp_used"], g["wind_used"], g["weather_src"] = temp, wnd, weather_src[i]
    f["wind_x_margin"] = wind * f["epa_margin"]
    f["cold_x_margin"] = cold / 10 * f["epa_margin"]
    f["dome_cold"] = dome_cold
    f["div_x_margin"] = np.nan_to_num(num("div_game")) * f["epa_margin"]
    f["home_dog"] = ((f["vegas"] < 0) & (f["home_ind"] == 1)).astype(float)
    f["season"] = np.array([g["season"] for g in games], dtype=float)
    return games, f, inj


def set_stakes(games: list[dict], f: dict[str, np.ndarray], odds: dict[int, dict]) -> None:
    """(Re)compute the late-season stakes feature from playoff-odds payloads."""
    indexed = context.index_odds(odds)
    f["stakes_diff"] = np.array(
        [
            context.stakes(indexed, g["season"], g["week"], g["home"])
            - context.stakes(indexed, g["season"], g["week"], g["away"])
            for g in games
        ]
    )


def _days_ahead(days: int) -> str:
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


def design(f: dict[str, np.ndarray], cols: list[str]) -> np.ndarray:
    return np.column_stack([f[c] for c in cols])


def ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Coefficients and their standard errors."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(1, len(y) - X.shape[1])
    s2 = float(resid @ resid) / dof
    cov = s2 * np.linalg.pinv(X.T @ X)
    return beta, np.sqrt(np.clip(np.diag(cov), 0, None))


def fit(f: dict[str, np.ndarray], cols: list[str], mask: np.ndarray):
    X = design(f, cols)
    ok = mask & ~np.isnan(f["result"]) & ~np.isnan(X).any(axis=1)
    return ols(X[ok], f["result"][ok])


def score(pred: np.ndarray, f: dict[str, np.ndarray], mask: np.ndarray, threshold: float) -> dict:
    """ATS record betting the model's side when |pred - line| >= threshold, plus MAE."""
    v, r = f["vegas"], f["result"]
    ok = mask & ~np.isnan(pred) & ~np.isnan(v) & ~np.isnan(r)
    p, v, r = pred[ok], v[ok], r[ok]
    side = np.sign(p - v)
    actual = np.sign(r - v)
    bet = (np.abs(p - v) >= max(threshold, 1e-9)) & (side != 0) & (actual != 0)
    w = int(np.sum(bet & (side == actual)))
    n = int(bet.sum())
    return {
        "games": int(ok.sum()),
        "mae": float(np.mean(np.abs(p - r))) if ok.any() else None,
        "vegas_mae": float(np.mean(np.abs(v - r))) if ok.any() else None,
        "bets": n,
        "wins": w,
        "win_rate": w / n if n else None,
        "p_value": binom_p_value(w, n, BREAKEVEN) if n else None,
    }


def seasons_mask(f: dict[str, np.ndarray], seasons) -> np.ndarray:
    return np.isin(f["season"], list(seasons))


def run_selection(f: dict[str, np.ndarray]) -> list[dict]:
    """Fit on FIT, score every variant x threshold on VALIDATE. Nothing else is computed."""
    fit_m = seasons_mask(f, FIT_SEASONS)
    val_m = seasons_mask(f, VALIDATE_SEASONS)
    out = []
    for name, cols in VARIANTS.items():
        beta, _ = fit(f, cols, fit_m)
        pred = design(f, cols) @ beta
        for th in THRESHOLDS:
            out.append(
                {"variant": name, "threshold": th}
                | {f"fit_{k}": v for k, v in score(pred, f, fit_m, th).items()}
                | {f"val_{k}": v for k, v in score(pred, f, val_m, th).items()}
            )
    return out


def choose(selection: list[dict]) -> dict | None:
    eligible = [r for r in selection if r["val_bets"] >= MIN_VALIDATE_BETS]
    return max(eligible, key=lambda r: r["val_win_rate"]) if eligible else None


def lab(
    con: duckdb.DuckDBPyConnection,
    lam: float,
    half_life: float,
    odds: dict[int, dict],
    frame: tuple[list[dict], dict[str, np.ndarray], dict] | None = None,
) -> dict | None:
    games, f, inj = frame or build_frame(con, lam, half_life, odds)
    seasons = set(f["season"].astype(int).tolist())
    if not set(TEST_SEASONS) <= seasons:
        return None
    selection = run_selection(f)
    chosen = choose(selection)
    frozen = FROZEN or (
        None if chosen is None else {"variant": chosen["variant"], "threshold": chosen["threshold"]}
    )
    if frozen is None:
        return None
    agrees = chosen is not None and (chosen["variant"], chosen["threshold"]) == (
        frozen["variant"],
        frozen["threshold"],
    )
    cols = VARIANTS[frozen["variant"]]
    th = frozen["threshold"]

    # Reused test: FIT-only coefficients, as in round 1.
    b_fit, _ = fit(f, cols, seasons_mask(f, FIT_SEASONS))
    test = score(design(f, cols) @ b_fit, f, seasons_mask(f, TEST_SEASONS), th)

    # Live: refit on every completed season before the current one.
    current = max(seasons)
    before = f["season"] < current
    b_live, se_live = fit(f, cols, before)
    X = design(f, cols)
    pred = X @ b_live
    played = ~np.isnan(f["result"])
    cur = f["season"] == current
    days = np.array([str(g["gameday"]) for g in games])
    pre_m = cur & (days <= FREEZE_DATE)
    sealed_m = cur & (days > FREEZE_DATE)

    def ledger_row(i: int) -> dict:
        g = games[i]
        v, p, r = f["vegas"][i], pred[i], f["result"][i]
        side = (
            None
            if np.isnan(v) or abs(p - v) < max(th, 1e-9)
            else (g["home"] if p > v else g["away"])
        )
        won = None
        if side and not np.isnan(r) and r != v:
            won = bool((r > v) == (side == g["home"]))
        return {
            "game_id": g["game_id"],
            "week": g["week"],
            "gameday": str(g["gameday"]),
            "home": g["home"],
            "away": g["away"],
            "vegas": None if np.isnan(v) else float(v),
            "model": float(p),
            "result": None if np.isnan(r) else float(r),
            "bet": side,
            "won": won,
            "sealed": bool(days[i] > FREEZE_DATE),
        }

    ledger = [ledger_row(i) for i in np.flatnonzero(cur & played & ~np.isnan(pred))]

    # How much each factor typically moves a line, on completed games.
    contrib_sd = {
        c: float(np.nanstd(X[before & played, j] * b_live[j])) for j, c in enumerate(cols)
    }
    coefficients = [
        {
            "feature": c,
            "label": LABELS.get(c, c),
            "beta": float(b_live[j]),
            "se": float(se_live[j]),
            "typical_points": contrib_sd[c],
        }
        for j, c in enumerate(cols)
    ]

    upcoming = []
    unplayed = np.flatnonzero(cur & ~played & ~np.isnan(pred))
    if len(unplayed):
        next_week = min(games[i]["week"] for i in unplayed)
        for i in unplayed:
            g = games[i]
            if g["week"] != next_week:
                continue
            row = ledger_row(i)
            row["factors"] = [
                {"feature": c, "label": LABELS.get(c, c), "points": float(X[i, j] * b_live[j])}
                for j, c in enumerate(cols)
            ]
            row["injuries"] = {
                side: sorted(
                    inj.get((g["season"], g["week"], g[side]), {}).get("players", []),
                    key=lambda p: -p["impact"],
                )
                for side in ("home", "away")
            }
            row["weather"] = {
                "roof": g["roof"],
                "temp": g["temp_used"],
                "wind": g["wind_used"],
                "source": g["weather_src"],
            }
            upcoming.append(row)

    # Does the closing line already price each factor? Regress the line's miss
    # (result - line) on the factor over every completed season: a coefficient near 0 means
    # the market prices it. Descriptive, all seasons, no betting decision rides on it.
    miss = f["result"] - f["vegas"]
    done = before & played & ~np.isnan(f["vegas"])
    market_check = []
    for c in INJ_TOTAL + INJ_GROUPS + SPOTS + WEATHER_DIV + ["home_dog"]:
        x = f[c][done]
        if np.std(x) == 0:
            continue
        X1 = np.column_stack([np.ones_like(x), x])
        b_m, se_m = ols(X1, miss[done])
        X2 = np.column_stack([f[k][done] for k in BASE] + [x])
        b_r, se_r = ols(X2, f["result"][done])
        market_check.append(
            {
                "feature": c,
                "label": LABELS.get(c, c),
                "vs_ratings": float(b_r[-1]),
                "vs_ratings_se": float(se_r[-1]),
                "vs_line": float(b_m[1]),
                "vs_line_se": float(se_m[1]),
                "share_nonzero": float(np.mean(x != 0)),
            }
        )

    # How much of the upcoming week's injury report has final game statuses yet.
    statuses_posted = None
    if upcoming and has_relation(con, "injuries"):
        wk = upcoming[0]["week"]
        statuses_posted = con.execute(
            """
            select count(distinct team) from injuries
            where season = ? and week = ? and game_type = 'REG' and report_status is not null
            """,
            [current, wk],
        ).fetchone()[0]

    span = lambda r: [min(r), max(r)]  # noqa: E731
    return {
        "protocol": {
            "fit_seasons": span(FIT_SEASONS),
            "validate_seasons": span(VALIDATE_SEASONS),
            "test_seasons": span(TEST_SEASONS),
            "breakeven": BREAKEVEN,
            "thresholds": list(THRESHOLDS),
            "min_validate_bets": MIN_VALIDATE_BETS,
            "freeze_date": FREEZE_DATE,
            "live_season": current,
            "status_weights": context.STATUS_WEIGHT,
            "role_games": context.ROLE_GAMES,
            "has_injuries": has_relation(con, "injuries") and has_relation(con, "snaps"),
            "teams_with_final_statuses": statuses_posted,
            "teams_playing": 2 * len(upcoming),
        },
        "market_check": market_check,
        "variants": VARIANTS,
        "labels": LABELS,
        "selection": selection,
        "chosen": frozen,
        "selection_agrees": agrees,
        "test": test,
        "coefficients": coefficients,
        "live": {
            "pre_freeze": score(pred, f, pre_m, th),
            "sealed": score(pred, f, sealed_m, th),
            "games": ledger,
        },
        "upcoming": upcoming,
    }
