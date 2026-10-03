import duckdb

from ags.build import season_status


def test_past_seasons_are_complete_even_short_a_game():
    """2022 lost BUF-CIN (271 games): it is still over. Only the latest season can be live."""
    con = duckdb.connect()
    con.execute("create table games (season int, season_type varchar, week int, home_score int)")
    rows = [(2022, "REG", 18, 20)] * 271 + [(2023, "REG", 18, 20)] * 272
    rows += [(2024, "REG", 3, 20)] * 48 + [(2024, "REG", 4, 20)]
    con.executemany("insert into games values (?, ?, ?, ?)", rows)
    status = {s["season"]: s for s in season_status(con)}
    assert status[2022]["complete"] and status[2023]["complete"]
    assert not status[2024]["complete"]
    assert status[2022]["reg_games"] == 271
