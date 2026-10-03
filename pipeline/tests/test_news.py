"""news.py: ESPN articles -> items, injury-report items, news.json, the /api/news cache.

The ESPN responses in ``fixtures/espn_news.json`` are hand-built in the shape of
``site.api.espn.com/apis/site/v2/sports/football/nfl/news`` (no network in tests).
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import duckdb
import pytest

from ags import news, serve
from ags.config import NEWS_TEAM_URL, NEWS_URL

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "espn_news.json").read_text())
IDS = {"3912547": "00-0034869", "4426515": "00-0039075", "4426348": "00-0039910"}
NOW = dt.datetime(2026, 10, 3, 18, 0, tzinfo=dt.UTC)


def fake_fetch(fail_general=False, fail_teams=False, calls=None):
    def fetch(url):
        if calls is not None:
            calls.append(url)
        if url == NEWS_URL:
            if fail_general:
                raise news.NewsError("couldn't reach ESPN (blocked)")
            return FIXTURE["general"]
        if fail_teams:
            raise news.NewsError("HTTP 500")
        if url == NEWS_TEAM_URL.format(team=26):
            return FIXTURE["team_26"]
        return {"articles": []}

    return fetch


def test_team_codes():
    assert news.team_code(14) == "LA" and news.team_code("28") == "WAS"
    assert news.team_code("WSH") == "WAS" and news.team_code("LAR") == "LA"
    assert news.team_code("sea") == "SEA" and news.team_code("JAC") == "JAX"
    assert news.team_code(31) is None and news.team_code("XXX") is None
    assert news.team_code(None) is None
    assert len(set(news.ESPN_TEAMS.values())) == 32


def test_normalize_article():
    arts = FIXTURE["general"]["articles"]
    item = news.normalize_article(arts[0], IDS)
    assert item == {
        "id": "espn-46500001",
        "kind": "news",
        "headline": "Seahawks QB Sam Darnold practices fully, set to start Sunday",
        "description": arts[0]["description"],
        "published": "2026-10-02T23:58:40Z",
        "url": "https://www.espn.com/nfl/story/_/id/46500001/seahawks-qb-sam-darnold-practices-fully",
        "image": "https://a.espncdn.com/photo/2026/1002/r46500001_1296x729_16-9.jpg",
        "teams": ["SEA"],
        "players": ["00-0034869"],
        "athletes": [{"id": "00-0034869", "name": "Sam Darnold"}],
        "source": "ESPN",
        "byline": "ESPN News Services",
    }
    rankings = news.normalize_article(arts[1], IDS)
    assert rankings["teams"] == ["LA", "MIN"]
    # Unmapped athletes keep their name (a chip without a link).
    assert rankings["athletes"] == [
        {"id": "00-0039075", "name": "Puka Nacua"},
        {"id": None, "name": "Justin Jefferson"},
    ]
    assert rankings["players"] == ["00-0039075"]
    assert rankings["premium"] is True
    assert rankings["image"].endswith("r46500003_1296x729_16-9.jpg")  # header beats inline
    d = rankings["description"]
    assert len(d) <= news.DESCRIPTION_CHARS + 1 and d.endswith("…") and "\n" not in d
    assert d.startswith("Our analysts rank")
    video = news.normalize_article(arts[2], IDS)
    assert video["label"] == "Video" and video["teams"] == ["WAS"]
    recap = news.normalize_article(arts[3], IDS)
    assert recap["label"] == "Recap" and recap["teams"] == ["GB", "DET", "WAS"]
    assert recap["image"] is None and "byline" not in recap
    assert news.normalize_article(arts[4], IDS) is None  # no link
    assert news.normalize_article(arts[5], IDS) is None  # no headline
    last = news.normalize_article(arts[6], IDS)
    assert last["published"] == "2026-10-01T12:00:00Z" and last["image"] is None
    assert news.normalize_article("junk", IDS) is None


def test_espn_items_dedupes_and_tolerates_team_failures():
    calls: list[str] = []
    items = news.espn_items(IDS, fake_fetch(calls=calls))
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)) == 6  # 5 usable + 1 team-only, Darnold item once
    assert "espn-46500009" in ids
    assert calls[0] == NEWS_URL and len(calls) == 33
    assert NEWS_TEAM_URL.format(team=26) == NEWS_URL.replace("limit=50", "limit=8") + "&team=26"
    assert len(news.espn_items(IDS, fake_fetch(fail_teams=True))) == 5
    calls.clear()
    with pytest.raises(news.NewsError):
        news.espn_items(IDS, fake_fetch(fail_general=True, calls=calls))
    assert calls == [NEWS_URL]  # network down: team feeds aren't tried
    with pytest.raises(news.NewsError):
        news.espn_items(IDS, lambda url: {"unexpected": True})


def _item(n, teams, minute):
    return {"id": f"x{n}", "teams": teams, "published": f"2026-10-02T10:{minute:02d}:00Z"}


def test_select_news_keeps_each_team_newest():
    items = [_item(i, ["KC"], 50 - i) for i in range(10)] + [_item(99, ["SEA"], 1)]
    out = news.select_news(items, limit=4, per_team=1)
    assert [i["id"] for i in out] == ["x0", "x1", "x2", "x99"]  # SEA's only item survives
    assert [i["id"] for i in news.select_news(items, limit=3, per_team=0)] == ["x0", "x1", "x2"]


def test_fetch_json_errors(monkeypatch):
    def boom(req, timeout):
        raise urllib.error.URLError("blocked")

    monkeypatch.setattr(news, "urlopen", boom)
    with pytest.raises(news.NewsError, match="couldn't reach ESPN"):
        news.fetch_json(NEWS_URL)


# ---------- injury report ----------


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("""
        create table injuries (season int, game_type varchar, team varchar, week int,
            gsis_id varchar, position varchar, full_name varchar, report_status varchar,
            practice_status varchar, report_primary_injury varchar)
    """)
    full, ltd, dnp = (
        "Full Participation in Practice",
        "Limited Participation in Practice",
        "Did Not Participate In Practice",
    )
    nir = "Not injury related - personal"
    rows = [
        # last season: ignored
        (2025, "REG", "SEA", 18, "P9", "QB", "Old Guy", "Out", dnp, "Knee"),
        # week 3
        (2026, "REG", "SEA", 3, "P1", "QB", "Sam Darnold", "Out", dnp, "Knee"),
        (2026, "REG", "SEA", 3, "P2", "WR", "Wide Out", "Questionable", ltd, "Ankle"),
        (2026, "REG", "SEA", 3, "P3", "RB", "Run Back", "Questionable", ltd, "Hamstring"),
        (2026, "REG", "SEA", 3, "P4", "G", "Big Guard", "Out", dnp, "Back"),
        (2026, "REG", "SEA", 3, "P5", "TE", "Tight End", "Out", dnp, "Foot"),
        (2026, "REG", "KC", 2, "K1", "WR", "Chief Receiver", "Out", dnp, "Hip"),  # KC bye wk 3
        # week 4
        (2026, "REG", "SEA", 4, "P1", "QB", "Sam Darnold", None, full, "Knee"),  # cleared
        (2026, "REG", "SEA", 4, "P2", "WR", "Wide Out", "Out", dnp, "Ankle"),  # worse
        (2026, "REG", "SEA", 4, "P3", "RB", "Run Back", "Questionable", ltd, "Hamstring"),
        (2026, "REG", "SEA", 4, "P4", "G", "Big Guard", "Out", dnp, "Back"),  # same, line: skip
        (2026, "REG", "SEA", 4, "P5", "TE", "Tight End", "Questionable", ltd, "Foot"),  # better
        (2026, "REG", "SEA", 4, "P6", "CB", "New Corner", "Doubtful", dnp, nir),
        (2026, "REG", "SEA", 4, "P7", "WR", "Healthy Wr", None, full, None),  # nothing: skip
        (2026, "REG", "SEA", 4, "P8", "RB", "Sore Back", None, ltd, "Rest"),  # limited, no status
        (2026, "REG", "SEA", 4, "P10", "LB", "Line Backer", None, ltd, "Knee"),  # skip
        (2026, "REG", "KC", 4, "K1", "WR", "Chief Receiver", None, ltd, "Hip"),  # pre-final
        (2026, "REG", "KC", 4, "K2", "TE", "Chief End", None, dnp, "Toe"),
        (2026, "REG", "KC", 4, "K3", "T", "Chief Tackle", None, dnp, "Toe"),  # skip
    ]  # fmt: skip
    c.executemany("insert into injuries values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    c.execute(
        "create table schedule (season int, week int, home_team varchar, away_team varchar,"
        " gameday date)"
    )
    c.executemany(
        "insert into schedule values (?, ?, ?, ?, ?)",
        [(2026, 4, "SEA", "ARI", "2026-10-04"), (2026, 4, "LV", "KC", "2026-10-05")],
    )
    return c


def test_injury_items(con, tmp_path):
    items, report = news.injury_items(con, now=NOW, raw_dir=tmp_path)
    assert report == {"season": 2026, "week": 4}
    by = {i["players"][0]: i for i in items}
    assert set(by) == {"P1", "P2", "P3", "P5", "P6", "P8", "K1", "K2"}
    assert by["P2"]["change"] == "worse" and by["P2"]["status"] == "Out"
    assert by["P2"]["headline"] == "Wide Out ruled out (ankle)"
    assert by["P2"]["description"] == (
        "SEA WR · Ankle · Did not practice · was questionable in week 3 · Week 4 vs ARI"
    )
    assert by["P1"]["change"] == "cleared" and "status" not in by["P1"]
    assert by["P1"]["headline"] == "Sam Darnold has no game status"
    assert by["P1"]["description"].endswith("Full practice · was out in week 3 · Week 4 vs ARI")
    assert by["P3"]["change"] == "same" and "also questionable in week 3" in by["P3"]["description"]
    assert (
        by["P5"]["change"] == "better" and by["P5"]["headline"] == "Tight End questionable (foot)"
    )
    assert (
        by["P6"]["change"] == "new"
        and by["P6"]["headline"] == "New Corner doubtful (not injury: personal)"
    )
    assert by["P8"].get("change") is None and by["P8"]["headline"] == "Sore Back has no game status"
    # Statuses for SEA's Sunday game come out Friday 4 pm ET.
    assert by["P2"]["published"] == "2026-10-02T20:00:00Z"
    # KC plays Monday: Saturday's final report isn't out at NOW, so practice items only.
    assert (
        by["K1"]["preliminary"] is True
        and by["K1"]["headline"] == "Chief Receiver: limited in practice"
    )
    assert by["K1"]["description"] == (
        "KC WR · Hip · Limited in practice · was out in week 2 · Week 4 at LV"
        " · game status due Saturday"
    )
    assert by["K1"]["published"] == "2026-10-03T18:00:00Z"
    for i in items:
        assert i["kind"] == "injury" and i["url"] is None and i["source"] == "NFL injury report"
        assert i["athletes"] == [{"id": i["players"][0], "name": i["athletes"][0]["name"]}]
    # Newest first; within the same time, bigger changes first.
    times = [i["published"] for i in items]
    assert times == sorted(times, reverse=True)
    sea = [i["players"][0] for i in items if i["teams"] == ["SEA"]]
    assert sea[0] == "P2" and sea.index("P1") < sea.index("P3")
    # Once the release time passes, KC's empty statuses are final: nothing changed but K1.
    later, _ = news.injury_items(con, now=NOW + dt.timedelta(days=1), raw_dir=tmp_path)
    kc = {i["players"][0]: i for i in later if i["teams"] == ["KC"]}
    assert set(kc) == {"K1", "K2"} and kc["K1"]["change"] == "cleared"


def test_injury_items_body_part_from_raw_parquet(tmp_path):
    c = duckdb.connect()
    c.execute("""
        create table raw as select 2026 as season, 'SEA' as team, 4 as week, 'P1' as gsis_id,
            'QB' as position, 'Sam Darnold' as full_name, 'Questionable' as report_status,
            'Limited Participation in Practice' as practice_status,
            'Wrist' as report_primary_injury, null::varchar as practice_primary_injury
    """)
    c.execute(f"copy raw to '{(tmp_path / 'injuries_2026.parquet').as_posix()}' (format parquet)")
    c.execute(
        "create view injuries as select season, team, week, gsis_id, position, full_name,"
        " report_status, practice_status from raw"
    )
    items, _ = news.injury_items(c, now=NOW, raw_dir=tmp_path)
    assert items[0]["headline"] == "Sam Darnold questionable (wrist)"
    assert news.injury_items(duckdb.connect(), now=NOW) == ([], None)


# ---------- news.json ----------


def test_build_keeps_previous_news_when_espn_is_down(con, tmp_path, capsys):
    fresh = news.build(con, {}, fake_fetch(), now=NOW, raw_dir=tmp_path)
    assert fresh["news_fetched_at"] == "2026-10-03T18:00:00Z" and fresh["error"] is None
    assert fresh["injury_report"] == {"season": 2026, "week": 4}
    kinds = [i["kind"] for i in fresh["items"]]
    assert kinds.count("news") == 6 and kinds.count("injury") == 8
    times = [i["published"] for i in fresh["items"]]
    assert times == sorted(times, reverse=True)
    assert len(json.dumps(fresh)) < 20_000

    later = NOW + dt.timedelta(hours=3)
    stale = news.build(con, fresh, fake_fetch(fail_general=True), now=later, raw_dir=tmp_path)
    assert "ESPN news skipped" in capsys.readouterr().err
    assert stale["news_fetched_at"] == "2026-10-03T18:00:00Z"  # when the kept news was fetched
    assert stale["generated_at"] == "2026-10-03T21:00:00Z"
    assert "couldn't reach ESPN" in stale["error"]
    old_news = [i for i in fresh["items"] if i["kind"] == "news"]
    assert [i for i in stale["items"] if i["kind"] == "news"] == old_news
    # No previous file and no network: injuries only.
    bare = news.build(con, {}, fake_fetch(fail_general=True), now=NOW, raw_dir=tmp_path)
    assert bare["news_fetched_at"] is None and {i["kind"] for i in bare["items"]} == {"injury"}


def test_read_previous(tmp_path):
    assert news.read_previous(tmp_path / "missing.json") == {}
    (tmp_path / "bad.json").write_text("{nope")
    assert news.read_previous(tmp_path / "bad.json") == {}
    (tmp_path / "ok.json").write_text(json.dumps({"items": []}))
    assert news.read_previous(tmp_path / "ok.json") == {"items": []}


# ---------- /api/news ----------


def _data_dir(tmp_path, con):
    built = news.build(con, {}, fake_fetch(fail_general=True), now=NOW, raw_dir=tmp_path)
    built["items"].append(
        {"id": "espn-old", "kind": "news", "headline": "Old", "published": "2026-09-01T00:00:00Z",
         "teams": [], "players": [], "athletes": [], "url": "https://www.espn.com/x"}
    )  # fmt: skip
    built["news_fetched_at"] = "2026-09-01T00:00:00Z"
    (tmp_path / "news.json").write_text(json.dumps(built))
    (tmp_path / "fantasy_ids.json").write_text(json.dumps({"espn": IDS, "sleeper": {}}))
    return tmp_path


def test_live_news_caches_and_falls_back(con, tmp_path):
    data = _data_dir(tmp_path, con)
    clock = {"t": 1_000_000.0}
    calls: list[str] = []
    state = {"down": True}

    def fetch(url):
        return fake_fetch(fail_general=state["down"], calls=calls)(url)

    feed = news.LiveNews(fetch=fetch, clock=lambda: clock["t"])
    first = feed.get(data)
    # ESPN down: the build's news and injuries, flagged not live.
    assert first["live"] is False and "couldn't reach ESPN" in first["error"]
    assert [i["id"] for i in first["items"] if i["kind"] == "news"] == ["espn-old"]
    assert first["news_fetched_at"] == "2026-09-01T00:00:00Z"
    assert sum(i["kind"] == "injury" for i in first["items"]) == 8
    # Within the retry window nothing is fetched again.
    feed.get(data)
    assert len(calls) == 1
    state["down"] = False
    clock["t"] += news.RETRY_AFTER
    live = feed.get(data)
    assert live["live"] is True and live["error"] is None
    assert live["news_fetched_at"] == news.iso(dt.datetime.fromtimestamp(clock["t"], dt.UTC))
    ids = [i["id"] for i in live["items"]]
    assert "espn-46500001" in ids and "espn-old" not in ids
    assert sum(i["kind"] == "injury" for i in live["items"]) == 8
    darnold = next(i for i in live["items"] if i["id"] == "espn-46500001")
    assert darnold["players"] == ["00-0034869"]  # ESPN ids mapped via fantasy_ids.json
    n = len(calls)
    clock["t"] += news.LIVE_TTL - 1
    feed.get(data)
    assert len(calls) == n  # cached for ten minutes
    clock["t"] += 1
    state["down"] = True
    after = feed.get(data)
    # A later failure keeps serving the last live news.
    assert after["live"] is True and "espn-46500001" in [i["id"] for i in after["items"]]


def test_api_news_endpoint(con, tmp_path, monkeypatch):
    data = _data_dir(tmp_path, con)
    monkeypatch.setattr(serve.SiteHandler, "news_feed", news.LiveNews(fetch=fake_fetch()))
    server = serve.make_server(0, manager=None, build_dir=tmp_path, data_dir=data, tries=1)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def get(path, headers=None, method="GET"):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", headers=headers or {}, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    try:
        status, h, body = get("/api/news")
        assert status == 200 and h["Cache-Control"] == "no-store"
        payload = json.loads(body)
        assert payload["live"] is True and payload["injury_report"]["week"] == 4
        assert get("/api/news", method="POST")[0] == 405
        assert get("/api/news", {"Host": "evil.example"})[0] == 403
    finally:
        server.shutdown()
        server.server_close()
