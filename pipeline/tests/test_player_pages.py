"""Player index + profile files (players.directory_pages, players.season_lines cache)."""

from ags import players


def _directory(con):
    con.execute("""
        create table players as select * from (values
            ('K1', 'Kim Kicker', 'K', 'SPEC', '4', 'State',
             'https://static.www.nfl.com/image/private/f_auto,q_auto/league/abc123'),
            ('LB1', 'Lee Backer', 'OLB', 'LB', '55', null, null),
            ('WR1', 'Will Wide', 'WR', 'WR', '11', null,
             'https://example.com/other/photo.png'),
            ('CB1', 'Two Way', 'CB', 'DB', '12', null, null)
        ) t(gsis_id, display_name, position, position_group, jersey_number, college_name,
            headshot)
    """)


def _seasons():
    games = {
        "2024_01_AAA_BBB": [1, "REG", "BBB", "AAA"],
        "2024_02_BBB_CCC": [2, "REG", "CCC", "BBB"],
        "2024_19_CCC_AAA": [19, "POST", "AAA", "CCC"],
    }
    games25 = {"2025_01_AAA_CCC": [1, "REG", "CCC", "AAA"]}
    names = {
        "K1": ["K.Kicker", "K"],
        "LB1": ["L.Backer", "LB"],
        "WR1": ["W.Wide", "WR"],
        "CB1": ["T.Way", "DB"],
        "OL9": ["O.Lineman", "?"],
        "AAA": ["AAA", "DEF"],
    }
    return {
        2024: {
            "games": games,
            "players": names,
            "lines": [
                ["2024_01_AAA_BBB", "K1", "AAA", {"fga": 2, "fgm": 1, "fgm_dists": [45]}],
                ["2024_01_AAA_BBB", "LB1", "BBB", {"tkl_solo": 5, "sack": 0.5}],
                ["2024_02_BBB_CCC", "LB1", "CCC", {"tkl_solo": 2}],  # traded mid-season
                ["2024_19_CCC_AAA", "LB1", "CCC", {"tkl_ast": 1}],  # playoffs, still CCC
                ["2024_01_AAA_BBB", "AAA", "AAA", {"sack": 1}],  # team defense: no page
                ["2024_01_AAA_BBB", "OL9", "AAA", {}],  # empty line: no page
                ["2024_01_AAA_BBB", "CB1", "AAA", {"def_pd": 1}],
            ],
        },
        2025: {
            "games": games25,
            "players": names,
            "lines": [["2025_01_AAA_CCC", "K1", "AAA", {"xpa": 1, "xpm": 1}]],
        },
    }


def test_directory_pages(make_pbp):
    con = make_pbp([{}])
    _directory(con)
    efficiency = [
        {"player_id": "WR1", "season": 2023, "team": "BBB", "name": "W.Wide", "position": "WR"},
        {"player_id": "WR1", "season": 2024, "team": "AAA", "name": "W.Wide", "position": "WR"},
        {"player_id": "CB1", "season": 2024, "team": "AAA", "name": "T.Way", "position": "CB"},
    ]
    index, pages = players.directory_pages(con, _seasons(), efficiency)
    rows = {r[0]: dict(zip(players.INDEX_COLUMNS, r, strict=True)) for r in index}
    # Team defenses and players without a stat never get a page.
    assert set(rows) == {"K1", "LB1", "WR1", "CB1"}
    assert rows["K1"] == {
        "id": "K1",
        "name": "Kim Kicker",
        "pos": "K",
        "team": "AAA",
        "season": 2025,
        "headshot": "p:abc123",
        "efficiency": 0,
    }
    # Efficiency players keep their page; a two-way player also gets a profile file.
    assert rows["WR1"]["efficiency"] == 1 and rows["WR1"]["season"] == 2024
    assert rows["WR1"]["headshot"] == "https://example.com/other/photo.png"
    assert rows["CB1"]["efficiency"] == 2
    assert set(pages) == {"K1", "LB1", "CB1"}

    lb = pages["LB1"]
    assert lb["name"] == "Lee Backer" and lb["position"] == "OLB" and lb["group"] == "LB"
    assert lb["jersey"] == "55"
    # 2024: one game for BBB, two for CCC (the playoff game counts).
    assert lb["teams"] == [[2024, "CCC"]]
    assert lb["games"] == [
        ["2024_01_AAA_BBB", 1, 0, "BBB", "AAA", 1, {"tkl_solo": 5, "sack": 0.5}],
        ["2024_02_BBB_CCC", 2, 0, "CCC", "BBB", 1, {"tkl_solo": 2}],
        ["2024_19_CCC_AAA", 19, 1, "CCC", "AAA", 0, {"tkl_ast": 1}],
    ]
    k = pages["K1"]
    assert k["teams"] == [[2024, "AAA"], [2025, "AAA"]]
    assert k["headshot"].endswith("/abc123") and k["college"] == "State"
    assert [g[0] for g in k["games"]] == ["2024_01_AAA_BBB", "2025_01_AAA_CCC"]
    assert k["games"][0][4:6] == ["BBB", 0]  # away at BBB


def test_team_tie_goes_to_latest(make_pbp):
    con = make_pbp([{}])
    seasons = {
        2024: {
            "games": {"g1": [1, "REG", "AAA", "BBB"], "g2": [2, "REG", "CCC", "DDD"]},
            "players": {"LB1": ["L.Backer", "LB"]},
            "lines": [
                ["g1", "LB1", "AAA", {"tkl_solo": 1}],
                ["g2", "LB1", "DDD", {"tkl_solo": 1}],
            ],
        }
    }
    index, pages = players.directory_pages(con, seasons, [])
    assert pages["LB1"]["teams"] == [[2024, "DDD"]]
    assert index[0][3] == "DDD"
    # No players view: names and the site position come from the stat lines.
    assert index[0][1:3] == ["L.Backer", "LB"] and pages["LB1"]["group"] == "LB"


def test_short_headshot():
    assert players.short_headshot(None) is None
    url = "https://static.www.nfl.com/image/upload/f_auto,q_auto/league/xyz"
    assert players.short_headshot(url) == "u:xyz"
    odd = "https://static.www.nfl.com/image/upload/f_auto,q_auto/v1/league/xyz"
    assert players.short_headshot(odd) == odd


def test_season_lines_cache(make_pbp, tmp_path):
    con = make_pbp([{}])
    lines = _seasons()[2025] | {"teams": {}}
    first = players.season_lines(con, 2025, tmp_path, 7, lines)
    assert "teams" not in first and first["version"] == "7"
    # A later build that skips the season reads the cache back.
    assert players.season_lines(con, 2025, tmp_path, 7) == first
