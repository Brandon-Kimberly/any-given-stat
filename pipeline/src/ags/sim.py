"""Monte Carlo playoff odds: simulate the rest of the regular season and the bracket.

For each "as of" state w of a season (0 = preseason, then after each completed week),
team ratings are fit on games before week w + 1 (``ratings.fit_before``) and every
unplayed game's home margin is drawn from

    Normal(points_per_epa * epa_margin + home_points * home_ind, sigma)

with the calibration the spread model publishes (predictions.json ``params``; the
starting-QB adjustment is left out because future starters are unknown). Games already
played keep their result; an actual tie counts half a win. The same rating snapshot
plays the postseason.

Seeding is simplified: division winners by win percentage, then wild cards by win
percentage, and every tie is broken at random per simulation (the NFL's head-to-head,
division and common-games tiebreakers are not modeled).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

import duckdb
import numpy as np

from . import ratings
from .db import has_relation, records

SIMS = 10_000
SEED = 2016
TIEBREAK_EPS = 1e-6  # far below the smallest win-percentage gap (0.5 / (17 * 16))
DIVISION_BONUS = 2.0  # > any win percentage: puts division winners ahead of wild cards


@dataclass(frozen=True)
class GameModel:
    lam: float
    half_life: float
    points_per_epa: float
    home_points: float
    sigma: float

    @classmethod
    def from_params(cls, params: dict) -> GameModel:
        """From the ``params`` block of predictions.json (ratings.predictions)."""
        return cls(
            lam=params["lambda"],
            half_life=params["half_life_weeks"] or 1e9,
            points_per_epa=params["points_per_epa"],
            home_points=params["home_points"],
            sigma=params["sigma"],
        )

    def margin(self, net_home, net_away, home_ind):
        """Expected home margin in points."""
        return self.points_per_epa * (net_home - net_away) + self.home_points * home_ind


def playoff_format(season: int) -> tuple[int, int]:
    """(seeds per conference, first-round byes): 6 and 2 through 2019, 7 and 1 since."""
    return (6, 2) if season <= 2019 else (7, 1)


def last_completed_week(weeks, has_result) -> int:
    """Last week w such that weeks 1..w are done (0 if week 1 isn't).

    A week is done when every game in it has a result, or when a later week already
    has one (a cancelled game, e.g. BUF-CIN in 2022, must not freeze the season).
    """
    weeks = np.asarray(weeks)
    has = np.asarray(has_result, dtype=bool)
    if not has.any():
        return 0
    latest = weeks[has].max()
    done = 0
    for wk in sorted(set(weeks.tolist())):
        if has[weeks == wk].all() or wk < latest:
            done = wk
        else:
            break
    return int(done)


def season_wins(n_teams: int, home, away, home_win: np.ndarray) -> np.ndarray:
    """Wins per sim per team. ``home_win`` is (sims, games) in {0, 0.5, 1}."""
    home = np.asarray(home, dtype=int)
    away = np.asarray(away, dtype=int)
    g = np.arange(len(home))
    H = np.zeros((len(home), n_teams))
    A = np.zeros((len(home), n_teams))
    H[g, home] = 1.0
    A[g, away] = 1.0
    return home_win @ H + (1.0 - home_win) @ A


def seed_conference(
    win_pct: np.ndarray, divisions: list[np.ndarray], n_seeds: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Seed one conference in every sim.

    ``win_pct`` is (sims, teams) for the conference's teams; ``divisions`` lists column
    indices. Returns (seeds, div_winner): seeds is (sims, n_seeds) column indices in seed
    order (division winners 1-4 by record, then wild cards by record); div_winner is a
    (sims, teams) bool mask. Ties are broken at random, independently per sim.
    """
    n, _ = win_pct.shape
    key = win_pct + rng.random(win_pct.shape) * TIEBREAK_EPS
    div_winner = np.zeros(win_pct.shape, dtype=bool)
    rows = np.arange(n)
    for cols in divisions:
        cols = np.asarray(cols)
        div_winner[rows, cols[np.argmax(key[:, cols], axis=1)]] = True
    order = np.argsort(-(key + DIVISION_BONUS * div_winner), axis=1, kind="stable")
    return order[:, :n_seeds], div_winner


def play_bracket(
    seeds: np.ndarray, byes: int, higher_seed_wins: Callable[[np.ndarray, np.ndarray], np.ndarray]
) -> np.ndarray:
    """Conference champion per sim for an NFL bracket with reseeding.

    ``seeds`` is (sims, k) team ids in seed order. Each round the top ``byes`` seeds sit
    out (first round only) and the rest pair best vs worst remaining seed.
    ``higher_seed_wins(home, away)`` gets team id arrays (the higher seed is home) and
    returns a bool array per sim.
    """
    n, k = seeds.shape
    rows = np.arange(n)
    alive = np.tile(np.arange(k), (n, 1))  # seed positions, ascending = best first
    b = byes
    while alive.shape[1] > 1:
        bye, playing = alive[:, :b], alive[:, b:]
        m = playing.shape[1]
        if m % 2:
            raise ValueError(f"odd number of teams in a round: {m}")
        winners = np.empty((n, m // 2), dtype=int)
        for j in range(m // 2):
            hi, lo = playing[:, j], playing[:, m - 1 - j]
            won = higher_seed_wins(seeds[rows, hi], seeds[rows, lo])
            winners[:, j] = np.where(won, hi, lo)
        alive = np.sort(np.concatenate([bye, winners], axis=1), axis=1)
        b = 0
    return seeds[rows, alive[:, 0]]


@dataclass(frozen=True)
class League:
    """One season's teams and alignment; team ids index ``teams``."""

    teams: list[str]
    conferences: list[tuple[np.ndarray, list[np.ndarray]]]  # (team ids, divisions as ids)

    @classmethod
    def from_alignment(cls, alignment: dict[str, tuple[str, str]]) -> League:
        """``alignment``: team -> (conference, division)."""
        teams = sorted(alignment)
        idx = {t: i for i, t in enumerate(teams)}
        confs = []
        for conf in sorted({c for c, _ in alignment.values()}):
            members = [t for t in teams if alignment[t][0] == conf]
            divisions = sorted({alignment[t][1] for t in members})
            confs.append(
                (
                    np.array([idx[t] for t in members]),
                    [
                        np.array([members.index(t) for t in members if alignment[t][1] == d])
                        for d in divisions
                    ],
                )
            )
        return cls(teams, confs)


def simulate(
    league: League,
    home: np.ndarray,
    away: np.ndarray,
    home_ind: np.ndarray,
    fixed: np.ndarray,
    net: np.ndarray,
    model: GameModel,
    season: int,
    sims: int,
    rng: np.random.Generator,
) -> list[dict]:
    """Simulate one state. Per game: ``fixed`` = home wins (1, 0.5, 0) or nan to simulate.

    ``net`` is each team's net EPA/play rating. Returns one row per team.
    """
    n_teams = len(league.teams)
    pred = model.margin(net[home], net[away], home_ind)
    todo = np.isnan(fixed)
    home_win = np.broadcast_to(np.nan_to_num(fixed), (sims, len(fixed))).copy()
    if todo.any():
        z = rng.standard_normal((sims, int(todo.sum())))
        home_win[:, todo] = (pred[todo] + model.sigma * z > 0).astype(float)
    wins = season_wins(n_teams, home, away, home_win)
    n_games = np.bincount(home, minlength=n_teams) + np.bincount(away, minlength=n_teams)
    win_pct = wins / np.maximum(n_games, 1)

    def higher_seed_wins(h, a, home_ind=1.0):
        margin = model.margin(net[h], net[a], home_ind)
        return margin + model.sigma * rng.standard_normal(len(h)) > 0

    n_seeds, byes = playoff_format(season)
    seed_num = np.zeros((sims, n_teams), dtype=int)  # 0 = missed the playoffs
    div_win = np.zeros((sims, n_teams), dtype=bool)
    champs = []
    rows = np.arange(sims)[:, None]
    for members, divisions in league.conferences:
        seeds, dw = seed_conference(win_pct[:, members], divisions, n_seeds, rng)
        team_seeds = members[seeds]
        seed_num[rows, team_seeds] = np.arange(1, n_seeds + 1)
        div_win[:, members] = dw
        champs.append(play_bracket(team_seeds, byes, higher_seed_wins))
    if len(champs) == 2:
        sb_home_wins = higher_seed_wins(champs[0], champs[1], home_ind=0.0)
        sb = np.where(sb_home_wins, champs[0], champs[1])
    else:
        sb = np.full(sims, -1)

    q10, q90 = np.quantile(wins, [0.1, 0.9], axis=0, method="inverted_cdf")
    made = seed_num > 0
    out = []
    for t, team in enumerate(league.teams):
        in_t = made[:, t]
        out.append(
            {
                "team": team,
                "mean_wins": float(wins[:, t].mean()),
                "wins_p10": float(q10[t]),
                "wins_p90": float(q90[t]),
                "p_playoffs": float(in_t.mean()),
                "p_division": float(div_win[:, t].mean()),
                "p_bye": float((in_t & (seed_num[:, t] <= byes)).mean()),
                "p_conf": float(sum((c == t).mean() for c in champs)),
                "p_sb": float((sb == t).mean()),
                "mean_seed_if_in": float(seed_num[in_t, t].mean()) if in_t.any() else None,
            }
        )
    return out


def actual_outcomes(teams: list[str], post: list[dict]) -> dict[str, dict] | None:
    """Who made the playoffs, won the division and won the Super Bowl, from POST games.

    ``post`` rows: game_type (WC/DIV/CON/SB), home, away, result (home margin). Division
    winners host wild-card games or skip them (byes); wild cards always travel. Returns
    None when the Super Bowl hasn't been played.
    """
    sb = [g for g in post if g["game_type"] == "SB" and g["result"] is not None]
    if not sb:
        return None
    g = sb[0]
    champ = g["home"] if g["result"] > 0 else g["away"]
    made = {t for p in post for t in (p["home"], p["away"])}
    wc = [p for p in post if p["game_type"] == "WC"]
    wc_teams = {t for p in wc for t in (p["home"], p["away"])}
    division = ({p["home"] for p in wc} | (made - wc_teams)) if wc else None
    out = {}
    for t in teams:
        row = {"made_playoffs": t in made, "sb_winner": t == champ}
        if division is not None:
            row["won_division"] = t in division
        out[t] = row
    return out


def playoff_odds(
    con: duckdb.DuckDBPyConnection, params: dict, sims: int = SIMS
) -> list[tuple[int, dict]]:
    """[(season, payload)] for every loaded season after the first.

    Needs the ``schedule`` and ``team_colors`` views (alignment); returns [] without them.
    """
    if not (has_relation(con, "schedule") and has_relation(con, "team_colors")):
        return []
    model = GameModel.from_params(params)
    alignment = {
        r["team"]: (r["conf"], r["division"])
        for r in records(
            con,
            """
            select team_abbr as team, team_conf as conf, team_division as division
            from team_colors where team_conf is not null and team_division is not null
            """,
        )
    }
    rows = ratings.load_rows(con)
    rating_idx = {t: i for i, t in enumerate(rows.teams)}
    seasons = sorted(set(rows.season.tolist()))[1:]  # first season: no prior-year ratings
    out = []
    for season in seasons:
        sched = records(
            con,
            """
            select game_type, week, home_team as home, away_team as away, result,
                   case when location = 'Neutral' then 0 else 1 end as home_ind
            from schedule where season = ?
            order by week, game_id
            """,
            [season],
        )
        reg = [g for g in sched if g["game_type"] == "REG"]
        teams = sorted({g["home"] for g in reg} | {g["away"] for g in reg})
        missing = [t for t in teams if t not in alignment]
        if not reg or missing:
            print(f"skip playoff odds {season}: no alignment for {missing}", file=sys.stderr)
            continue
        league = League.from_alignment({t: alignment[t] for t in teams})
        tid = {t: i for i, t in enumerate(league.teams)}
        week = np.array([g["week"] for g in reg])
        result = np.array([np.nan if g["result"] is None else float(g["result"]) for g in reg])
        played = ~np.isnan(result)
        last = last_completed_week(week, played)
        # Unplayed games inside completed weeks: cancelled once the season is over
        # (dropped), postponed while it is in progress (simulated).
        reg_over = bool(played[week == week.max()].all())
        home_all = np.array([tid[g["home"]] for g in reg])
        away_all = np.array([tid[g["away"]] for g in reg])
        home_ind_all = np.array([float(g["home_ind"]) for g in reg])
        outcome = np.where(result > 0, 1.0, np.where(result < 0, 0.0, 0.5))
        states = []
        for w in range(last + 1):
            keep = ~(reg_over & (week <= w) & ~played)
            fixed = np.where((week <= w) & played, outcome, np.nan)[keep]
            f = ratings.fit_before(
                rows, int(ratings.time_index(season, w + 1)), model.lam, model.half_life
            )
            net = np.array([f.net[rating_idx[t]] if t in rating_idx else 0.0 for t in teams])
            rng = np.random.default_rng([SEED, season, w])
            for r in simulate(
                league,
                home_all[keep],
                away_all[keep],
                home_ind_all[keep],
                fixed,
                net,
                model,
                season,
                sims,
                rng,
            ):
                states.append({"team": r.pop("team"), "week": w} | r)
        post = [g for g in sched if g["game_type"] != "REG"]
        n_seeds, byes = playoff_format(season)
        out.append(
            (
                season,
                {
                    "season": season,
                    "sims": sims,
                    "seeds": n_seeds,
                    "byes": byes,
                    "weeks": list(range(last + 1)),
                    "rows": states,
                    "actual": actual_outcomes(teams, post),
                },
            )
        )
    return out
