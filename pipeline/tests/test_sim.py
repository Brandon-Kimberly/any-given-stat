import numpy as np
import pytest

from ags import sim

MODEL = sim.GameModel(lam=1000, half_life=16, points_per_epa=200, home_points=2, sigma=13)


def test_playoff_format_by_era():
    assert sim.playoff_format(2019) == (6, 2)
    assert sim.playoff_format(2020) == (7, 1)


def test_last_completed_week_handles_partial_and_cancelled():
    weeks = [1, 1, 2, 2, 3, 3]
    assert sim.last_completed_week(weeks, [0, 0, 0, 0, 0, 0]) == 0
    assert sim.last_completed_week(weeks, [1, 1, 1, 0, 0, 0]) == 1  # week 2 in progress
    assert sim.last_completed_week(weeks, [1, 1, 1, 1, 1, 0]) == 2
    # A cancelled week-2 game doesn't freeze the season once week 3 has results.
    assert sim.last_completed_week(weeks, [1, 1, 1, 0, 1, 1]) == 3


def test_season_wins_counts_home_away_and_ties():
    # Two sims, three games among three teams: 0 hosts 1, 1 hosts 2, 2 hosts 0.
    home, away = [0, 1, 2], [1, 2, 0]
    home_win = np.array([[1.0, 1.0, 1.0], [0.0, 0.5, 1.0]])
    wins = sim.season_wins(3, home, away, home_win)
    assert wins.tolist() == [[1, 1, 1], [0, 1.5, 1.5]]


# One 16-team conference, four divisions of four (columns 0-3, 4-7, 8-11, 12-15).
DIVISIONS = [np.arange(d * 4, d * 4 + 4) for d in range(4)]


def test_seed_conference_division_winners_then_wild_cards():
    wins = np.array([[10, 9, 3, 2, 8, 7, 6, 5, 12, 11, 1, 0, 4, 4.5, 3.5, 2.5]])
    seeds, div_winner = sim.seed_conference(wins / 17, DIVISIONS, 7, np.random.default_rng(0))
    # Division winners 8 (12 wins), 0 (10), 4 (8), 13 (4.5) are seeds 1-4 by record even
    # though 13 has fewer wins than several wild cards; then 9 (11), 1 (9), 5 (7).
    assert seeds.tolist() == [[8, 0, 4, 13, 9, 1, 5]]
    assert np.flatnonzero(div_winner[0]).tolist() == [0, 4, 8, 13]


def test_seed_conference_breaks_ties_at_random():
    wins = np.zeros((4000, 16))
    wins[:, 0] = wins[:, 1] = 10  # tied for the division
    seeds, div_winner = sim.seed_conference(wins / 17, DIVISIONS, 7, np.random.default_rng(1))
    share = div_winner[:, 0].mean()
    assert 0.45 < share < 0.55
    assert (div_winner[:, 0] ^ div_winner[:, 1]).all()  # exactly one of them
    # The loser of the tie is the best wild card (seed 5).
    loser = np.where(div_winner[:, 0], 1, 0)
    assert (seeds[:, 4] == loser).all()


def _bracket(seeds, byes, beats):
    """Run play_bracket with team ids 101.. and a deterministic rule; log the matchups."""
    log = []

    def higher_seed_wins(h, a):
        log.append((int(h[0]) - 100, int(a[0]) - 100))
        return np.array([beats(int(h[0]) - 100, int(a[0]) - 100)])

    champ = sim.play_bracket(np.array([[100 + s for s in seeds]]), byes, higher_seed_wins)
    return int(champ[0]) - 100, log


def test_bracket_seven_seeds_reseeds_after_wild_card_round():
    seeds = list(range(1, 8))
    champ, log = _bracket(seeds, 1, lambda h, a: h <= a)
    assert champ == 1
    assert log == [(2, 7), (3, 6), (4, 5), (1, 4), (2, 3), (1, 2)]
    # The 7 seed upsets the 2: the 1 seed then gets the lowest remaining seed (7).
    champ, log = _bracket(seeds, 1, lambda h, a: a != 7)
    assert log[3:5] == [(1, 7), (3, 4)]
    assert champ == 7


def test_bracket_six_seeds_two_byes():
    champ, log = _bracket(list(range(1, 7)), 2, lambda h, a: False)  # lower seed always wins
    assert log[:2] == [(3, 6), (4, 5)]
    assert log[2:4] == [(1, 6), (2, 5)]
    assert log[4] == (5, 6)
    assert champ == 6


def _league(n_div_teams=4):
    alignment = {}
    for conf in ("AFC", "NFC"):
        for d in ("East", "North", "South", "West"):
            for i in range(n_div_teams):
                alignment[f"{conf[0]}{d[0]}{i}"] = (conf, f"{conf} {d}")
    return sim.League.from_alignment(alignment)


def test_simulate_with_every_game_played_is_deterministic():
    league = _league()
    n = len(league.teams)
    # Team i hosts team i+1 (mod n) and loses; team 0 also gets a tie with team 2.
    home = np.array([*range(n), 0])
    away = np.array([*((i + 1) % n for i in range(n)), 2])
    fixed = np.array([0.0] * n + [0.5])
    net = np.zeros(n)
    rows = sim.simulate(
        league, home, away, np.ones(n + 1), fixed, net, MODEL, 2024, 200, np.random.default_rng(3)
    )
    by = {r["team"]: r for r in rows}
    assert sum(r["p_playoffs"] for r in rows) == pytest.approx(14)
    assert sum(r["p_division"] for r in rows) == pytest.approx(8)
    assert sum(r["p_bye"] for r in rows) == pytest.approx(2)
    assert sum(r["p_conf"] for r in rows) == pytest.approx(2)
    assert sum(r["p_sb"] for r in rows) == pytest.approx(1)
    t0 = by[league.teams[0]]
    assert (t0["mean_wins"], t0["wins_p10"], t0["wins_p90"]) == (1.5, 1.5, 1.5)
    for r in rows:
        if r["p_playoffs"] == 0:
            assert r["mean_seed_if_in"] is None and r["p_sb"] == 0


def test_simulate_dominant_team_wins_everything():
    league = _league()
    n = len(league.teams)
    home, away = np.triu_indices(n, 1)  # everyone plays everyone once
    net = np.zeros(n)
    net[5] = 1.0  # +200 points per game
    rows = sim.simulate(
        league,
        home,
        away,
        np.ones(len(home)),
        np.full(len(home), np.nan),
        net,
        MODEL,
        2024,
        500,
        np.random.default_rng(4),
    )
    star = rows[5]
    assert star["p_playoffs"] == 1.0 and star["p_bye"] == 1.0 and star["p_sb"] == 1.0
    assert star["mean_seed_if_in"] == 1.0


def test_actual_outcomes_from_postseason_games():
    post = [
        {"game_type": "WC", "home": "A", "away": "B", "result": 3},
        {"game_type": "WC", "home": "C", "away": "D", "result": -7},
        {"game_type": "DIV", "home": "E", "away": "A", "result": 10},  # E had a bye
        {"game_type": "DIV", "home": "F", "away": "D", "result": -1},
        {"game_type": "CON", "home": "E", "away": "D", "result": -3},
        {"game_type": "SB", "home": "D", "away": "G", "result": 4},
    ]
    out = sim.actual_outcomes(["A", "B", "C", "D", "E", "F", "G", "H"], post)
    assert out["D"] == {"made_playoffs": True, "sb_winner": True, "won_division": False}
    assert out["E"]["won_division"] and out["F"]["won_division"] and out["C"]["won_division"]
    assert not out["B"]["won_division"]
    assert out["H"] == {"made_playoffs": False, "sb_winner": False, "won_division": False}
    assert sim.actual_outcomes(["A"], post[:-1]) is None  # no Super Bowl yet


def test_playoff_odds_skips_without_reference_views(make_pbp):
    params = {"lambda": 1000.0, "half_life_weeks": None, "points_per_epa": 200.0}
    params |= {"home_points": 2.0, "sigma": 13.0}
    assert sim.playoff_odds(make_pbp([{}]), params) == []
