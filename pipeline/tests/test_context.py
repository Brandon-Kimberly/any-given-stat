import math

import pytest

from ags import context
from ags.forecast import kickoff_reading


def test_player_impact_is_role_times_presence():
    # Team played at t = 1..8; the player played 1-6 at 80% and missed 7-8.
    team = list(range(1, 9))
    hist = [(t, 0.8) for t in range(1, 7)]
    # Before t=9: role 0.8 over his last 6 games; presence = 4 of the team's last 6 (3..8).
    assert context.player_impact(hist, team, 9) == pytest.approx(0.8 * 4 / 6)
    # Before t=4: role over games 1-3, presence 3/3.
    assert context.player_impact(hist, team, 4) == pytest.approx(0.8)


def test_player_impact_ignores_later_games_and_unknowns():
    team = [1, 2, 3]
    hist = [(1, 0.5), (2, 1.0), (3, 1.0)]
    assert context.player_impact(hist, team, 2) == pytest.approx(0.5)
    assert context.player_impact([], team, 3) == 0.0
    assert context.player_impact(hist, [], 3) == 0.0


def test_travel():
    # Seattle at Miami, 1 PM Eastern: three zones and the early body-clock spot.
    assert context.travel("MIA", "SEA", 1, "13:00") == (3.0, 1.0)
    # Same trip at night: no early spot.
    assert context.travel("MIA", "SEA", 1, "20:15") == (3.0, 0.0)
    # Eastern team going west, and neutral sites.
    assert context.travel("SF", "NYJ", 1, "16:25") == (3.0, 0.0)
    assert context.travel("MIA", "SEA", 0, "09:30") == (0.0, 0.0)


def test_weather():
    assert context.weather("outdoors", 20.0, 25.0) == (15.0, 20.0, True)
    assert context.weather("outdoors", 70.0, 5.0) == (0.0, 0.0, True)
    assert context.weather("dome", 0.0, 40.0) == (0.0, 0.0, False)
    assert context.weather("open", None, None) == (0.0, 0.0, True)


def test_dead_teams_and_stakes():
    assert context.is_dead(0.01, 0.0, 0.0)  # eliminated
    assert context.is_dead(1.0, 1.0, 1.0)  # everything clinched
    assert not context.is_dead(1.0, 1.0, 0.5)  # still playing for the bye
    assert not context.is_dead(0.4, 0.1, 0.0)
    odds = context.index_odds(
        {
            2020: {
                "rows": [
                    {"team": "NYJ", "week": 15, "p_playoffs": 0.0, "p_division": 0, "p_bye": 0},
                    {"team": "BUF", "week": 15, "p_playoffs": 0.9, "p_division": 0.8, "p_bye": 0},
                ]
            }
        }
    )
    assert context.stakes(odds, 2020, 16, "NYJ") == 0.0
    assert context.stakes(odds, 2020, 16, "BUF") == 1.0
    assert context.stakes(odds, 2020, 10, "NYJ") == 1.0  # before week 15
    assert context.stakes(odds, 2019, 16, "NYJ") == 1.0  # no odds that season


def test_kickoff_reading():
    payload = {
        "hourly": {
            "time": ["2026-10-04T12:00", "2026-10-04T13:00"],
            "temperature_2m": [51.0, 53.5],
            "wind_speed_10m": [9.0, 12.0],
        }
    }
    assert kickoff_reading(payload, "2026-10-04", "13:00") == (53.5, 12.0)
    assert kickoff_reading(payload, "2026-10-04", "20:15") is None
    assert kickoff_reading({}, "2026-10-04", "13:00") is None
    assert not math.isnan(kickoff_reading(payload, "2026-10-04", "12:00")[0])
