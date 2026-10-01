import datetime as dt

from ags.cli import current_nfl_season, parse_seasons


def test_parse_seasons():
    assert parse_seasons("2016-2018,2020,2017") == [2016, 2017, 2018, 2020]


def test_current_nfl_season_rolls_over_in_september():
    assert current_nfl_season(dt.date(2026, 8, 31)) == 2025
    assert current_nfl_season(dt.date(2026, 9, 1)) == 2026
    assert current_nfl_season(dt.date(2027, 2, 10)) == 2026
