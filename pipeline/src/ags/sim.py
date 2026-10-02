"""Monte Carlo playoff odds: simulate the rest of the regular season and the bracket.

For each "as of" state w of a season (0 = preseason, then after each completed week),
team strengths are fit on games before week w + 1 (EPA ratings, ``ratings.fit_before``,
and points ratings, ``strength.fit_mov``) and every unplayed game's home margin is

    expected = b_epa * epa_gap + b_mov * points_gap + b_home * home_ind
    margin   = expected + delta[home] - delta[away] + Normal(0, sigma_game)

with the round-3 forecast's coefficients (``lab3.py``, fit on FIT seasons only). Next
week's games use a better number when one exists: the market blend (betting line plus the
model's small correction) or the full model with the starting QB and injuries.

``delta`` is one draw per team per simulated season, Normal(0, tau): how wrong our
strength estimate might be. It makes a team's games move together, as they do in
reality (a team that is better than we think wins more of all its games). The per-game
noise shrinks to keep each single game's spread at the calibrated sigma:
sigma_game^2 = sigma^2 - 2 tau^2. ``tau`` falls from ``TAU_PRESEASON`` to ``TAU_LATE``
over the season and was tuned on FIT seasons by the Brier score of playoff odds.

Seeding follows the NFL's order where it can be computed from game results: win
percentage, head-to-head among the tied clubs, division record (division ties) or
conference record (wild cards), strength of victory, strength of schedule, then a coin
flip. Common-games records and the NFL's multi-club wild-card procedure are approximated.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np

from . import ratings, strength
from .db import has_relation, records

SIMS = 10_000
SEED = 2016
# Bump when simulation logic changes: cached states are keyed by it and by every input.
SIM_VERSION = 2
TIEBREAK_EPS = 1e-6  # far below the smallest win-percentage gap (0.5 / (17 * 16))
DIVISION_BONUS = 2.0  # > any win percentage: puts division winners ahead of wild cards
# Rating uncertainty in points (sd of one team's true strength around our estimate),
# tuned on FIT seasons 2017-2021 by playoff Brier (see tune_tau; grid TAU_GRID, 2,000 sims):
# 0.1193 vs 0.1199 with no uncertainty. Preseason -> after the last regular-season week.
TAU_PRESEASON = 4.5
TAU_LATE = 2.0
# Lexicographic tiebreak weights: each step can only reorder clubs equal on the previous.
KEY_WEIGHTS = (1.0, 1e-2, 1e-4, 1e-6, 1e-8, 1e-10, 1e-12)


@dataclass(frozen=True)
class SimModel:
    """Game model for simulated games (points), from lab3's frozen forecast."""

    epa_lam: float
    epa_half_life: float
    mov_lam: float
    mov_half_life: float
    b_epa: float  # points per EPA/play of net rating gap
    b_mov: float  # points per point of points-rating gap
    b_home: float
    sigma: float
    tau_preseason: float = TAU_PRESEASON
    tau_late: float = TAU_LATE

    def tau(self, week: int) -> float:
        k = min(1.0, max(0.0, week / 18))
        return self.tau_preseason * (1 - k) + self.tau_late * k


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


@dataclass
class Standings:
    """Per-sim records the tiebreakers need. Arrays are (sims, teams) unless noted."""

    win_pct: np.ndarray
    home: np.ndarray  # (games,) team ids
    away: np.ndarray
    home_win: np.ndarray  # (sims, games) in {0, 0.5, 1}
    div_pct: np.ndarray
    conf_pct: np.ndarray
    sov: np.ndarray  # strength of victory: mean win pct of teams beaten
    sos: np.ndarray  # strength of schedule: mean win pct of opponents


def _pct(won: np.ndarray, games: np.ndarray) -> np.ndarray:
    return np.where(games > 0, won / np.maximum(games, 1), 0.5)


def _onehot(ids: np.ndarray, n: int) -> np.ndarray:
    m = np.zeros((len(ids), n))
    m[np.arange(len(ids)), ids] = 1.0
    return m


def standings(
    n_teams: int, home, away, home_win: np.ndarray, div_id: np.ndarray, conf_id: np.ndarray
) -> Standings:
    home = np.asarray(home, dtype=int)
    away = np.asarray(away, dtype=int)
    H, A = _onehot(home, n_teams), _onehot(away, n_teams)
    wins = home_win @ H + (1.0 - home_win) @ A
    n_games = H.sum(axis=0) + A.sum(axis=0)
    win_pct = _pct(wins, n_games)

    def record(mask):
        w = home_win[:, mask] @ H[mask] + (1.0 - home_win[:, mask]) @ A[mask]
        return _pct(w, H[mask].sum(axis=0) + A[mask].sum(axis=0))

    # Strength of victory: the beaten opponents' win pct, summed per winner (ties count half).
    sov_num = (home_win * win_pct[:, away]) @ H + ((1.0 - home_win) * win_pct[:, home]) @ A
    sov = np.where(wins > 0, sov_num / np.maximum(wins, 1e-9), 0.0)
    opp_sum = win_pct[:, away] @ H + win_pct[:, home] @ A
    sos = opp_sum / np.maximum(n_games, 1)
    return Standings(
        win_pct=win_pct,
        home=home,
        away=away,
        home_win=home_win,
        div_pct=record(div_id[home] == div_id[away]),
        conf_pct=record(conf_id[home] == conf_id[away]),
        sov=sov,
        sos=sos,
    )


def tiebreak_key(
    st: Standings, cols: np.ndarray, group: np.ndarray, stage: str, rng: np.random.Generator
) -> np.ndarray:
    """Sort key (higher = better) for teams ``cols``, comparing teams within the same
    ``group`` label (per sim, shape (sims, len(cols))). ``stage``: 'division' or 'wildcard'.

    Head-to-head is the record in games among the clubs tied on win percentage within the
    group; then division record (division stage) or conference record (wild card), then
    strength of victory, strength of schedule, and a random draw.
    """
    cols = np.asarray(cols)
    k = len(cols)
    pos = np.full(len(st.win_pct[0]), -1)
    pos[cols] = np.arange(k)
    hp, ap = pos[st.home], pos[st.away]
    inside = (hp >= 0) & (ap >= 0)
    hp, ap, hw = hp[inside], ap[inside], st.home_win[:, inside]
    wp = st.win_pct[:, cols]
    rows = np.arange(len(wp))[:, None]
    tied = (np.abs(wp[:, hp] - wp[:, ap]) < 1e-9) & (group[rows, hp] == group[rows, ap])
    tied = tied.astype(float)
    Hc, Ac = _onehot(hp, k), _onehot(ap, k)
    won = (hw * tied) @ Hc + ((1.0 - hw) * tied) @ Ac
    played = tied @ (Hc + Ac)
    h2h = np.where(played > 0, won / np.maximum(played, 1), 0.5)
    record = st.div_pct[:, cols] if stage == "division" else st.conf_pct[:, cols]
    parts = [wp, h2h, record]
    if stage == "division":
        parts.append(st.conf_pct[:, cols])
    parts += [st.sov[:, cols], st.sos[:, cols], rng.random(wp.shape)]
    return sum(wgt * x for wgt, x in zip(KEY_WEIGHTS, parts, strict=False))


def seed_conference(
    win_pct: np.ndarray,
    divisions: list[np.ndarray],
    n_seeds: int,
    rng: np.random.Generator,
    st: Standings | None = None,
    members: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Seed one conference in every sim.

    ``win_pct`` is (sims, teams) for the conference's teams; ``divisions`` lists column
    indices. Returns (seeds, div_winner): seeds is (sims, n_seeds) column indices in seed
    order (division winners 1-4, then wild cards); div_winner is a (sims, teams) bool mask.
    With ``st`` (league standings) and ``members`` (the conference's league team ids),
    ties follow the NFL tiebreakers; without them ties are broken at random.
    """
    n, k = win_pct.shape
    rows = np.arange(n)
    div_of = np.zeros(k, dtype=int)
    for d, cols in enumerate(divisions):
        div_of[np.asarray(cols)] = d
    if st is None:
        key_div = key_wc = win_pct + rng.random(win_pct.shape) * TIEBREAK_EPS
    else:
        key_div = tiebreak_key(st, members, np.broadcast_to(div_of, (n, k)), "division", rng)
    div_winner = np.zeros(win_pct.shape, dtype=bool)
    for cols in divisions:
        cols = np.asarray(cols)
        div_winner[rows, cols[np.argmax(key_div[:, cols], axis=1)]] = True
    if st is not None:
        # Winners are compared with winners (seeds 1-4), the rest with the rest.
        key_wc = tiebreak_key(st, members, div_winner.astype(int), "wildcard", rng)
    order = np.argsort(-(key_wc + DIVISION_BONUS * div_winner), axis=1, kind="stable")
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
    fixed: np.ndarray,
    expected: np.ndarray,
    team_strength: np.ndarray,
    model: SimModel,
    season: int,
    sims: int,
    rng: np.random.Generator,
    tau: float = 0.0,
) -> list[dict]:
    """Simulate one state. Per game: ``fixed`` = home wins (1, 0.5, 0) or nan to simulate;
    ``expected`` = expected home margin (points, home field included). ``team_strength``
    is each team's rating in points (for playoff games). ``tau``: rating uncertainty.
    Returns one row per team.
    """
    n_teams = len(league.teams)
    delta = rng.normal(0.0, tau, (sims, n_teams)) if tau > 0 else np.zeros((sims, n_teams))
    sigma_game = float(np.sqrt(max(model.sigma**2 - 2 * tau**2, 1.0)))
    todo = np.isnan(fixed)
    home_win = np.broadcast_to(np.nan_to_num(fixed), (sims, len(fixed))).copy()
    if todo.any():
        h, a = home[todo], away[todo]
        z = rng.standard_normal((sims, int(todo.sum())))
        margin = expected[todo] + delta[:, h] - delta[:, a] + sigma_game * z
        home_win[:, todo] = np.where(margin > 0, 1.0, 0.0)
    div_id = np.zeros(n_teams, dtype=int)
    conf_id = np.zeros(n_teams, dtype=int)
    for c, (members, divisions) in enumerate(league.conferences):
        conf_id[members] = c
        for d, cols in enumerate(divisions):
            div_id[members[np.asarray(cols)]] = c * 10 + d
    st = standings(n_teams, home, away, home_win, div_id, conf_id)
    wins = season_wins(n_teams, home, away, home_win)
    rows = np.arange(sims)

    def higher_seed_wins(h, a, home_ind=1.0):
        mean = team_strength[h] - team_strength[a] + model.b_home * home_ind
        noise = delta[rows, h] - delta[rows, a] + sigma_game * rng.standard_normal(len(h))
        return mean + noise > 0

    n_seeds, byes = playoff_format(season)
    seed_num = np.zeros((sims, n_teams), dtype=int)  # 0 = missed the playoffs
    div_win = np.zeros((sims, n_teams), dtype=bool)
    champs = []
    col = rows[:, None]
    for members, divisions in league.conferences:
        seeds, dw = seed_conference(
            st.win_pct[:, members], divisions, n_seeds, rng, st=st, members=members
        )
        team_seeds = members[seeds]
        seed_num[col, team_seeds] = np.arange(1, n_seeds + 1)
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


def _alignment(con: duckdb.DuckDBPyConnection) -> dict[str, tuple[str, str]]:
    return {
        r["team"]: (r["conf"], r["division"])
        for r in records(
            con,
            """
            select team_abbr as team, team_conf as conf, team_division as division
            from team_colors where team_conf is not null and team_division is not null
            """,
        )
    }


def playoff_odds(
    con: duckdb.DuckDBPyConnection,
    model: SimModel,
    sims: int = SIMS,
    overrides: dict[str, float] | None = None,
    seasons: list[int] | None = None,
    cache_dir: Path | None = None,
) -> list[tuple[int, dict]]:
    """[(season, payload)] for every loaded season after the first (or ``seasons``).

    ``overrides``: game_id -> expected home margin for a better-informed number (market
    blend or full model), used only for the week right after each state.
    Needs the ``schedule`` and ``team_colors`` views (alignment); returns [] without them.
    """
    if not (has_relation(con, "schedule") and has_relation(con, "team_colors")):
        return []
    overrides = overrides or {}
    alignment = _alignment(con)
    rows = ratings.load_rows(con)
    rating_idx = {t: i for i, t in enumerate(rows.teams)}
    mov_rows = strength.load_mov_rows(con, rows.teams)
    loaded = sorted(set(rows.season.tolist()))[1:]  # first season: no prior-year ratings
    out = []
    for season in seasons or loaded:
        if season not in loaded:
            continue
        sched = records(
            con,
            """
            select game_id, game_type, week, home_team as home, away_team as away, result,
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
        ids = [g["game_id"] for g in reg]
        outcome = np.where(result > 0, 1.0, np.where(result < 0, 0.0, 0.5))
        r_idx = np.array([rating_idx.get(t, -1) for t in league.teams])
        states = []
        for w in range(last + 1):
            t_now = int(ratings.time_index(season, w + 1))
            f = ratings.fit_before(rows, t_now, model.epa_lam, model.epa_half_life)
            s_mov = strength.fit_mov(mov_rows, t_now, model.mov_lam, model.mov_half_life)
            net = np.where(r_idx >= 0, f.net[r_idx], 0.0)
            mov = np.where(r_idx >= 0, s_mov[r_idx], 0.0)
            team_strength = model.b_epa * net + model.b_mov * mov
            expected = (
                team_strength[home_all] - team_strength[away_all] + model.b_home * home_ind_all
            )
            nxt = week == w + 1
            for i in np.flatnonzero(nxt):
                if ids[i] in overrides:
                    expected[i] = overrides[ids[i]]
            latest = w == last and not reg_over
            # Fix results as of the state; the live state also fixes games already played
            # in the week in progress (e.g. Thursday night).
            fixed_mask = played & ((week <= w) | latest)
            keep = ~(reg_over & (week <= w) & ~played)
            fixed = np.where(fixed_mask, outcome, np.nan)[keep]
            key = _state_key(
                season, w, sims, model, home_all[keep], away_all[keep], fixed, expected[keep],
                team_strength, league.teams,
            )  # fmt: skip
            cached = _cache_read(cache_dir, key)
            if cached is None:
                rng = np.random.default_rng([SEED, season, w])
                cached = simulate(
                    league,
                    home_all[keep],
                    away_all[keep],
                    fixed,
                    expected[keep],
                    team_strength,
                    model,
                    season,
                    sims,
                    rng,
                    tau=model.tau(w),
                )
                _cache_write(cache_dir, key, cached)
            for r in cached:
                r = dict(r)
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
                    "model": {
                        "b_epa": model.b_epa,
                        "b_mov": model.b_mov,
                        "b_home": model.b_home,
                        "sigma": model.sigma,
                        "tau_preseason": model.tau_preseason,
                        "tau_late": model.tau_late,
                    },
                },
            )
        )
    return out


def _state_key(season, w, sims, model, home, away, fixed, expected, strength_, teams) -> str:
    """Hash of everything a simulated state depends on (inputs rounded to kill float noise)."""
    h = hashlib.sha256()
    # Fitted coefficients wobble in the last digits between runs (summation order), so
    # model parameters are rounded too.
    params = [round(float(v), 6) for v in vars(model).values()]
    h.update(json.dumps([SIM_VERSION, season, w, sims, list(teams), params]).encode())
    for arr in (home, away, np.nan_to_num(fixed, nan=-1), expected, strength_):
        h.update(np.round(np.asarray(arr, dtype=float), 6).tobytes())
    return f"{season}_{w:02d}_{h.hexdigest()[:20]}"


def _cache_read(cache_dir: Path | None, key: str) -> list[dict] | None:
    if cache_dir is None:
        return None
    path = cache_dir / f"{key}.json"
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except (OSError, ValueError):
        return None


def _cache_write(cache_dir: Path | None, key: str, rows: list[dict]) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    season_w = key.rsplit("_", 1)[0]
    for old in cache_dir.glob(f"{season_w}_*.json"):  # one entry per (season, state)
        old.unlink(missing_ok=True)
    (cache_dir / f"{key}.json").write_text(json.dumps(rows))


def brier(payloads: list[tuple[int, dict]], key: str = "p_playoffs") -> float | None:
    """Mean Brier score of make-the-playoffs (or division) odds over every state."""
    field = {"p_playoffs": "made_playoffs", "p_division": "won_division"}[key]
    errs = []
    for _, p in payloads:
        if not p["actual"]:
            continue
        for r in p["rows"]:
            out = p["actual"].get(r["team"])
            if out is not None and field in out:
                errs.append((r[key] - float(out[field])) ** 2)
    return float(np.mean(errs)) if errs else None


TAU_GRID = ((0.0, 0.0), (1.5, 0.0), (3.0, 0.0), (3.0, 1.0), (4.5, 1.0), (4.5, 2.0), (6.0, 2.0))


def tune_tau(
    con: duckdb.DuckDBPyConnection,
    model: SimModel,
    seasons: list[int],
    sims: int = 2000,
    overrides: dict[str, float] | None = None,
) -> list[dict]:
    """Brier score of playoff odds on ``seasons`` for each (preseason, late) tau pair."""
    from dataclasses import replace

    out = []
    for pre, late in TAU_GRID:
        m = replace(model, tau_preseason=pre, tau_late=late)
        payloads = playoff_odds(con, m, sims=sims, overrides=overrides, seasons=seasons)
        out.append(
            {
                "tau_preseason": pre,
                "tau_late": late,
                "brier_playoffs": brier(payloads),
                "brier_division": brier(payloads, "p_division"),
            }
        )
    return out
