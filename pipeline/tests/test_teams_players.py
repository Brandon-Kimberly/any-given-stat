import pytest

from ags import players
from ags.teams import badge_fg, contrast, luminance, pick_color, teams_meta


def test_contrast_matches_wcag_reference_values():
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#fff", "#000") == pytest.approx(21.0)
    assert contrast("#777777", "#777777") == pytest.approx(1.0)
    assert luminance("#ffffff") == pytest.approx(1.0)
    assert luminance("#000000") == pytest.approx(0.0)
    # WCAG's well-known example: #767676 on white is just over 4.5:1.
    assert contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


def test_pick_color_takes_first_readable_else_best():
    light, dark = "#fcfcfb", "#1a1a19"
    # Navy is fine on light, unreadable on dark; gold then wins on dark.
    assert pick_color(["#0b162a", "#c83803"], light) == "#0b162a"
    assert pick_color(["#0b162a", "#ffb612"], dark) == "#ffb612"
    # Nothing clears 2.0 on light: the higher-contrast candidate wins.
    assert pick_color(["#ffffff", "#eeeeee", None], light) == "#eeeeee"


def test_badge_fg_picks_readable_text():
    assert badge_fg("#ffb612") == "#0b0b0b"
    assert badge_fg("#0b162a") == "#ffffff"


def _team_colors(con):
    con.execute("""
        create table team_colors as select * from (values
            ('AAA', 'Alpha As', 'As', 'AFC', 'AFC East', '#0B162A', '#FFB612', '#ffffff', null),
            ('BBB', 'Beta Bs', 'Bs', 'NFC', 'NFC West', '#FFB612', '#000000', null, null),
            ('OLD', 'Old Name', 'Olds', 'NFC', 'NFC West', '#000000', '#ffffff', null, null)
        ) t(team_abbr, team_name, team_nick, team_conf, team_division,
            team_color, team_color2, team_color3, team_color4)
    """)


def test_teams_meta_keeps_only_pbp_teams(make_pbp):
    con = make_pbp([{"posteam": "AAA"}, {"posteam": "BBB", "defteam": "AAA"}])
    assert teams_meta(con) == []  # no team_colors view: degrade to empty
    _team_colors(con)
    rows = {r["team"]: r for r in teams_meta(con)}
    assert set(rows) == {"AAA", "BBB"}
    a = rows["AAA"]
    assert a["color"] == "#0b162a" and a["color2"] == "#ffb612"
    assert a["color_light"] == "#0b162a" and a["color_dark"] == "#ffb612"
    assert a["badge_fg"] == "#ffffff"
    assert rows["BBB"]["color_light"] == "#000000"  # gold fails 2.0 on the light page
    assert rows["BBB"]["badge_fg"] == "#0b0b0b"
    assert set(a) == {
        "team",
        "name",
        "nick",
        "conf",
        "division",
        "color",
        "color2",
        "color_light",
        "color_dark",
        "badge_fg",
    }


def test_players_directory_and_enrich(make_pbp):
    con = make_pbp([{}])
    assert players.players(con, ["P1"]) == []  # no players view
    con.execute("""
        create table players as select * from (values
            ('P1', 'Pat Passer', 'QB', 'QB', 2018, 2018, 1, 10, 'State'),
            ('P2', 'Will Wide', 'WR', 'WR', 2020, null, null, null, null)
        ) t(gsis_id, display_name, position, position_group, rookie_season, draft_year,
            draft_round, draft_pick, college_name)
    """)
    directory = players.players(con, ["P2", "P1", "P1", None, "P9"])
    assert [p["player_id"] for p in directory] == ["P1", "P2"]
    assert directory[0]["name"] == "Pat Passer" and directory[0]["college"] == "State"
    rows = [{"player_id": "P2", "name": "W.Wide"}, {"player_id": "P9", "name": "X.Unknown"}]
    players.enrich(rows, directory, {"position": "position", "full_name": "name"})
    assert rows[0] == {
        "player_id": "P2",
        "name": "W.Wide",
        "position": "WR",
        "full_name": "Will Wide",
    }
    assert rows[1]["position"] is None and rows[1]["full_name"] is None
