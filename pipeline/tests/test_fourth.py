import pytest

from ags import fourth


def _row(season, team, dist, field, decision, epa):
    # dist/field are (label, ord) pairs.
    return {
        "season": season,
        "team": team,
        "distance": dist[0],
        "dist_ord": dist[1],
        "field": field[0],
        "field_ord": field[1],
        "decision": decision,
        "epa": epa,
    }


SHORT_RZ = (("1", 1), ("Opp 1-10", 9))  # bucket A
LONG_DEEP = (("6-10", 5), ("Own 1-20", 1))  # bucket B
MID = (("3", 3), ("Opp 41-50", 5))  # bucket C


def test_recommend():
    assert fourth.recommend({"go": 0.8, "punt": None, "fg": 0.3}) == ("go", pytest.approx(0.5))
    assert fourth.recommend({"go": 0.1, "punt": None, "fg": None}) == ("go", None)
    assert fourth.recommend({"go": None, "punt": None, "fg": None}) == (None, None)


def test_buckets_and_epa_lost_by_hand():
    ref = [
        # Bucket A: go mean 0.8, fg mean 0.3, punt n=1 (< min_n) -> best go, margin 0.5.
        _row(2024, "T1", *SHORT_RZ, "go", 1.0),
        _row(2024, "T1", *SHORT_RZ, "fg", 0.2),
        _row(2024, "T2", *SHORT_RZ, "go", 0.6),
        _row(2024, "T2", *SHORT_RZ, "fg", 0.4),
        _row(2024, "T2", *SHORT_RZ, "punt", 5.0),
        # Bucket B: punt mean -0.2, go mean -1.5 -> best punt, margin 1.3.
        _row(2024, "T1", *LONG_DEEP, "go", -1.0),
        _row(2024, "T1", *LONG_DEEP, "punt", -0.1),
        _row(2024, "T2", *LONG_DEEP, "go", -2.0),
        _row(2024, "T2", *LONG_DEEP, "punt", -0.3),
        # Bucket C: only go has a mean -> best go, no margin.
        _row(2024, "T3", *MID, "go", 0.1),
        _row(2024, "T3", *MID, "go", 0.3),
    ]
    buckets = {b["distance"]: b for b in fourth.bucket_table(ref, min_n=2)}
    a, b, c = buckets["1"], buckets["6-10"], buckets["3"]
    assert (a["best"], a["punt_epa"]) == ("go", None)
    assert (a["go_epa"], a["fg_epa"]) == (pytest.approx(0.8), pytest.approx(0.3))
    assert a["margin"] == pytest.approx(0.5)
    assert (a["go_n"], a["fg_n"], a["punt_n"]) == (2, 2, 1)
    assert b["best"] == "punt" and b["margin"] == pytest.approx(1.3)
    assert c["best"] == "go" and c["margin"] is None and c["go_epa"] == pytest.approx(0.2)

    extra = [
        # 2025 T1: fg in A loses 0.5, go in B loses 1.3, punt in A has no mean -> skipped.
        _row(2025, "T1", *SHORT_RZ, "fg", 9.9),
        _row(2025, "T1", *LONG_DEEP, "go", 9.9),
        _row(2025, "T1", *SHORT_RZ, "punt", 9.9),
        # 2025 T2: followed the recommendation; punting in C (no punt mean) is skipped.
        _row(2025, "T2", *SHORT_RZ, "go", -9.9),
        _row(2025, "T2", *MID, "punt", 0.0),
    ]
    teams = {
        (t["season"], t["team"]): t
        for t in fourth.grade_teams(ref + extra, list(buckets.values()), clear_margin=0.3)
    }
    t1 = teams[(2024, "T1")]
    # A go 0 + A fg 0.5 + B go 1.3 + B punt 0.
    assert t1["epa_lost"] == pytest.approx(1.8)
    assert t1["fourth_downs"] == 4 and t1["go_rate"] == pytest.approx(0.5)
    assert (t1["clear_go"], t1["went_when_clear_go"]) == (2, 1)
    assert teams[(2024, "T2")]["epa_lost"] == pytest.approx(1.8)
    # T3 lost nothing (rank 1); T1 and T2 tie at 1.8 and share rank 2.
    assert teams[(2024, "T3")]["rank"] == 1
    assert teams[(2024, "T1")]["rank"] == teams[(2024, "T2")]["rank"] == 2
    assert teams[(2025, "T1")]["epa_lost"] == pytest.approx(1.8)
    assert teams[(2025, "T1")]["clear_go"] == 2
    assert teams[(2025, "T1")]["went_when_clear_go"] == 0
    assert teams[(2025, "T2")]["epa_lost"] == 0.0
    assert (teams[(2025, "T2")]["rank"], teams[(2025, "T1")]["rank"]) == (1, 2)


def test_population_and_bucket_edges(make_pbp):
    fourth_down = {"down": 4.0, "play_type": "run", "pass": 0.0, "rush": 1.0, "epa": 0.5}
    con = make_pbp(
        [
            fourth_down | {"ydstogo": 4.0, "yardline_100": 51.0},
            fourth_down | {"ydstogo": 11.0, "yardline_100": 50.0},
            fourth_down | {"play_type": "punt", "ydstogo": 1.0, "yardline_100": 80.0},
            fourth_down | {"play_type": "field_goal", "ydstogo": 6.0, "yardline_100": 10.0},
            fourth_down | {"play_type": "no_play"},
            fourth_down | {"wp": 0.97},
            fourth_down | {"qtr": 5.0},
            fourth_down | {"season_type": "POST"},
            {"down": 3.0},
        ]
    )
    out = fourth.fourth_downs(con, [2024])
    got = sorted((b["distance"], b["field"]) for b in out["buckets"])
    assert got == [
        ("1", "Own 1-20"),
        ("11+", "Opp 41-50"),
        ("4-5", "Own 41-49"),
        ("6-10", "Opp 1-10"),
    ]
    decisions = {b["distance"]: b for b in out["buckets"]}
    assert decisions["1"]["punt_n"] == 1 and decisions["6-10"]["fg_n"] == 1
    assert all(b["best"] is None for b in out["buckets"])  # all n < 25
    (team,) = out["teams"]
    assert team["fourth_downs"] == 4 and team["go_rate"] == pytest.approx(0.5)
    assert out["meta"]["reference_seasons"] == [2024, 2024]
