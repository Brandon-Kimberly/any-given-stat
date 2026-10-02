"""`ags up` / sync: change detection, game windows, settings, routing, sync runs (offline)."""

from __future__ import annotations

import datetime as dt
import gzip
import http.client
import json
import os
import sys
import threading
import time
import urllib.request

import pytest

from ags import serve, sync
from ags.serve import Route, parse_range, resolve
from ags.sync import (
    SyncManager,
    classify,
    detect_changes,
    in_game_window,
    next_auto_at,
    tracked_sources,
    validate_settings,
)

ET = dt.timezone(dt.timedelta(hours=-4))  # EDT, for readable fixed datetimes


def et(y, mo, d, h, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=ET)


# ---------- Settings ----------


def test_settings_validation():
    assert validate_settings({}) == {"auto": "off", "interval_minutes": 15}
    s = validate_settings({"auto": "gameday", "interval_minutes": 5})
    assert s == {"auto": "gameday", "interval_minutes": 5}
    assert validate_settings({"interval_minutes": 60}, s) == {
        "auto": "gameday",
        "interval_minutes": 60,
    }
    for bad in (
        {"auto": "sometimes"},
        {"interval_minutes": 7},
        {"interval_minutes": "15"},
        {"interval_minutes": True},
        {"other": 1},
        [],
    ):
        with pytest.raises(ValueError):
            validate_settings(bad)


def test_settings_persist(tmp_path):
    path = tmp_path / "sync_settings.json"
    assert sync.load_settings(path) == sync.DEFAULT_SETTINGS
    sync.save_settings({"auto": "interval", "interval_minutes": 30}, path)
    assert sync.load_settings(path) == {"auto": "interval", "interval_minutes": 30}
    path.write_text("{not json")
    assert sync.load_settings(path) == sync.DEFAULT_SETTINGS


# ---------- Game windows ----------


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        (et(2026, 10, 4, 13), True),  # Sunday afternoon
        (et(2026, 10, 4, 11), False),  # Sunday morning
        (et(2026, 10, 4, 23, 59), True),  # SNF
        (et(2026, 10, 5, 20), True),  # MNF
        (et(2026, 10, 5, 18), False),  # Monday before kickoff
        (et(2026, 10, 8, 20), True),  # TNF
        (et(2026, 10, 7, 20), False),  # Wednesday
        (et(2026, 10, 10, 14), False),  # Saturday in October
        (et(2026, 12, 12, 14), True),  # Saturday after Dec 10
        (et(2027, 1, 9, 16), True),  # wild-card Saturday
        (et(2026, 11, 26, 13), True),  # Thanksgiving (4th Thursday)
        (et(2026, 11, 19, 13), False),  # a normal Thursday afternoon
        (et(2026, 12, 25, 13), True),  # Christmas (a Friday in 2026)
        (et(2026, 7, 12, 14), False),  # Sunday in the off-season
    ],
)
def test_game_window(when, expected):
    assert in_game_window(when) is expected


def test_thanksgiving():
    assert sync.thanksgiving(2026) == dt.date(2026, 11, 26)
    assert sync.thanksgiving(2025) == dt.date(2025, 11, 27)


def test_fixed_offset_fallback(monkeypatch):
    monkeypatch.setattr(sync, "_ET", None)
    summer = dt.datetime(2026, 10, 4, 17, tzinfo=dt.UTC)  # 13:00 EDT
    winter = dt.datetime(2026, 12, 13, 17, tzinfo=dt.UTC)  # 12:00 EST
    assert sync.to_eastern(summer).hour == 13
    assert sync.to_eastern(winter).hour == 12
    assert in_game_window(summer) and in_game_window(winter)


def test_next_auto_at():
    now = et(2026, 10, 4, 13)  # inside a window
    last = et(2026, 10, 4, 12, 50)
    off = {"auto": "off", "interval_minutes": 15}
    assert next_auto_at(off, last, now) is None
    every = {"auto": "interval", "interval_minutes": 15}
    assert next_auto_at(every, last, now) == last + dt.timedelta(minutes=15)
    gd = {"auto": "gameday", "interval_minutes": 5}
    assert next_auto_at(gd, last, now) == last + dt.timedelta(minutes=5)
    # Wednesday: every 6 hours...
    wed = et(2026, 10, 7, 9)
    assert next_auto_at(gd, wed, wed) == wed + dt.timedelta(hours=6)
    # ...but no later than the moment the Thursday night window opens.
    thu = et(2026, 10, 8, 16)
    assert next_auto_at(gd, thu, thu) == et(2026, 10, 8, 19)


# ---------- Change detection ----------


def sig(etag, length=100, lm="Fri, 02 Oct 2026 15:46:33 GMT"):
    return {"etag": etag, "last_modified": lm, "length": length}


def fake_head(table):
    def head(url):
        value = table[url.rsplit("/", 1)[-1]]
        if isinstance(value, Exception):
            raise value
        return value

    return head


def test_detect_changes(tmp_path):
    sources = tracked_sources(2026)
    names = [n for n, _ in sources]
    remote = {n: sig(f'"{n}-v1"') for n in names}
    manifest = {"files": dict(remote)}

    changed, current, errors = detect_changes(sources, manifest, tmp_path, fake_head(remote))
    assert changed == [] and errors == [] and current == remote

    remote2 = dict(remote, **{"games.csv": sig('"games-v2"')})
    changed, _, _ = detect_changes(sources, manifest, tmp_path, fake_head(remote2))
    assert changed == ["games.csv"]

    remote3 = dict(remote, **{"players.parquet": OSError("timed out")})
    changed, current, errors = detect_changes(sources, manifest, tmp_path, fake_head(remote3))
    assert changed == ["players.parquet"] and "players.parquet" not in current
    assert errors and errors[0].startswith("players.parquet")


def test_detect_changes_without_manifest(tmp_path):
    """No manifest entry: compare the remote Last-Modified with our download time."""
    sources = [("play_by_play_2026.parquet", "https://x/play_by_play_2026.parquet")]
    local = tmp_path / "play_by_play_2026.parquet"
    local.write_bytes(b"x")
    published = dt.datetime(2026, 10, 2, 15, tzinfo=dt.UTC)
    os.utime(local, (published.timestamp() + 60,) * 2)  # downloaded a minute after
    old = {"play_by_play_2026.parquet": sig('"a"', lm="Fri, 02 Oct 2026 15:00:00 GMT")}
    new = {"play_by_play_2026.parquet": sig('"b"', lm="Fri, 02 Oct 2026 16:00:00 GMT")}
    assert detect_changes(sources, {}, tmp_path, fake_head(old))[0] == []
    assert detect_changes(sources, {}, tmp_path, fake_head(new))[0] == [sources[0][0]]
    # Not published upstream and not here either: nothing to do.
    missing = [("snap_counts_2026.parquet", "https://x/snap_counts_2026.parquet")]
    gone = {"snap_counts_2026.parquet": {"missing": True}}
    assert detect_changes(missing, {}, tmp_path, fake_head(gone))[0] == []


def test_same_file():
    assert sync.same_file(sig('"a"'), sig('"a"'))
    assert not sync.same_file(sig('"a"'), sig('"b"'))
    assert not sync.same_file(sig('"a"', 100), sig('"a"', 101))
    assert sync.same_file({"last_modified": "x", "length": 1}, {"last_modified": "x", "length": 1})
    assert sync.same_file({"missing": True}, {"missing": True})
    assert not sync.same_file({"missing": True}, sig('"a"'))


def test_classify():
    assert classify("fetch https://github.com/x/play_by_play_2026.parquet") == (
        "downloading",
        "Downloading play_by_play_2026.parquet",
    )
    assert classify("wrote /repo/web/static/data/teams.json (120 KB)") == (
        "building",
        "Writing teams.json",
    )
    assert classify("wrote /repo/web/static/data/ratings/ (11 seasons)")[1] == "Writing ratings"
    assert classify("[time] playoff odds: 12.3s") == ("building", "Built playoff odds")
    assert classify("warning: something") is None


# ---------- Sync runs ----------


def make_manager(tmp_path, command, remote):
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    (out / "meta.json").write_text("{}")
    return SyncManager(
        "2025-2026",
        raw_dir=tmp_path / "raw",
        out_dir=out,
        settings_path=tmp_path / "settings.json",
        command=command,
        head_fn=fake_head(remote),
    )


def remote_files(version):
    return {n: sig(f'"{n}-{version}"') for n, _ in tracked_sources(2026)}


PY = sys.executable
OK_BUILD = [PY, "-c", "print('fetch https://x/play_by_play_2026.parquet'); print('wrote a.json')"]
BAD_BUILD = [PY, "-c", "import sys; print('boom'); sys.exit(3)"]


def test_sync_success_then_up_to_date(tmp_path):
    m = make_manager(tmp_path, OK_BUILD, remote_files("v1"))
    assert m.start()
    m.wait(30)
    st = m.status()
    assert st["state"] == "idle" and st["last_result"] == "updated", st
    assert any("wrote a.json" in ln for ln in st["log_tail"])
    manifest = json.loads(m.manifest_path.read_text())
    assert manifest["files"]["games.csv"]["etag"] == '"games.csv-v1"'
    assert st["last_success_at"]

    # Same remote files: no build, done quickly.
    m.command = BAD_BUILD  # would fail if it ran
    assert m.start()
    m.wait(30)
    st = m.status()
    assert st["last_result"] == "up_to_date", st


def test_sync_failure_keeps_manifest(tmp_path):
    m = make_manager(tmp_path, BAD_BUILD, remote_files("v2"))
    sync.save_manifest({"files": remote_files("v1")}, m.manifest_path)
    assert m.start()
    m.wait(30)
    st = m.status()
    assert st["state"] == "error" and st["last_result"] == "error"
    assert "exit 3" in st["message"] and "boom" in st["message"]
    manifest = json.loads(m.manifest_path.read_text())
    assert manifest["files"]["games.csv"]["etag"] == '"games.csv-v1"'  # unchanged


def test_sync_force_and_unreachable(tmp_path):
    down = {n: OSError("offline") for n, _ in tracked_sources(2026)}
    m = make_manager(tmp_path, OK_BUILD, down)
    m.start()
    m.wait(30)
    assert m.status()["last_result"] == "error"
    assert "Couldn't reach" in m.status()["message"]
    m.start(force=True)  # force builds anyway
    m.wait(30)
    assert m.status()["last_result"] == "updated"


def test_sync_rejects_concurrent_start(tmp_path):
    slow = [PY, "-c", "import time; time.sleep(1)"]
    m = make_manager(tmp_path, slow, remote_files("v1"))
    assert m.start()
    assert not m.start()
    m.wait(30)


def test_auto_tick(tmp_path):
    m = make_manager(tmp_path, OK_BUILD, remote_files("v1"))
    m.update_settings({"auto": "interval", "interval_minutes": 5})
    assert json.loads((tmp_path / "settings.json").read_text())["auto"] == "interval"
    assert not m.tick()  # just started
    m.started -= dt.timedelta(minutes=6)
    assert m.tick()
    m.wait(30)
    assert m.status()["last_result"] == "updated"
    assert not m.tick()  # just synced


# ---------- Static routing ----------


@pytest.fixture
def site(tmp_path):
    build = tmp_path / "build"
    data = tmp_path / "data"
    (build / "odds").mkdir(parents=True)
    (build / "_app" / "immutable").mkdir(parents=True)
    (build / "index.html").write_text("<p>home</p>")
    (build / "404.html").write_text("<p>spa</p>")
    (build / "odds" / "index.html").write_text("<p>odds</p>")
    (build / "_app" / "immutable" / "a.js").write_text("export {}")
    (build / "favicon.svg").write_text("<svg/>")
    (data / "games").mkdir(parents=True)
    (data / "meta.json").write_text(json.dumps({"generated_at": "x", "pad": "y" * 5000}))
    (data / "games" / "g.json").write_text("{}")
    (tmp_path / "secret.txt").write_text("no")
    return build, data


def test_resolve(site):
    build, data = site
    assert resolve("/", build, data) == Route("file", build / "index.html")
    assert resolve("/odds/", build, data) == Route("file", build / "odds" / "index.html")
    assert resolve("/odds", build, data) == Route("redirect", location="/odds/")
    assert resolve("/favicon.svg", build, data) == Route("file", build / "favicon.svg")
    assert resolve("/_app/immutable/a.js", build, data).kind == "file"
    assert resolve("/data/meta.json", build, data) == Route("file", data / "meta.json", data=True)
    assert resolve("/data/games/g.json", build, data).path == data / "games" / "g.json"
    # Client-side routes get the SPA shell; missing assets and data are real 404s.
    assert resolve("/team/KC/", build, data) == Route("fallback", build / "404.html")
    assert resolve("/_app/immutable/missing.js", build, data).kind == "notfound"
    assert resolve("/missing.png", build, data).kind == "notfound"
    assert resolve("/data/missing.json", build, data).kind == "notfound"
    assert resolve("/data/", build, data).kind == "notfound"
    # No escaping the roots.
    assert resolve("/../secret.txt", build, data).kind == "notfound"
    assert resolve("/%2e%2e/secret.txt", build, data).kind == "notfound"
    assert resolve("/data/..%2fsecret.txt", build, data).kind == "notfound"
    assert resolve("/C:/x", build, data).kind == "notfound"


def test_parse_range():
    assert parse_range(None, 100) is None
    assert parse_range("bytes=0-9", 100) == (0, 9)
    assert parse_range("bytes=90-", 100) == (90, 99)
    assert parse_range("bytes=-10", 100) == (90, 99)
    assert parse_range("bytes=50-500", 100) == (50, 99)
    with pytest.raises(ValueError):
        parse_range("bytes=100-", 100)


def test_host_is_local():
    assert serve.host_is_local("localhost:4173")
    assert serve.host_is_local("127.0.0.1")
    assert serve.host_is_local("http://localhost:4173")
    assert serve.host_is_local("[::1]:4173")
    assert not serve.host_is_local("evil.example")
    assert not serve.host_is_local("http://localhost.evil.example")
    assert not serve.host_is_local(None)


def test_web_build_stale(tmp_path):
    web = tmp_path / "web"
    (web / "src").mkdir(parents=True)
    (web / "static" / "data").mkdir(parents=True)
    (web / "src" / "app.ts").write_text("x")
    assert serve.web_build_stale(web)  # no build yet
    (web / "build").mkdir()
    (web / "build" / "index.html").write_text("x")
    old = time.time() - 100
    os.utime(web / "src" / "app.ts", (old, old))
    assert not serve.web_build_stale(web)
    (web / "static" / "data" / "meta.json").write_text("{}")  # data doesn't count
    assert not serve.web_build_stale(web)
    (web / "src" / "app.ts").write_text("y")
    os.utime(web / "src" / "app.ts", (time.time() + 10,) * 2)
    assert serve.web_build_stale(web)


# ---------- The server end to end ----------


def test_server(site, tmp_path):
    build, data = site
    m = make_manager(tmp_path, OK_BUILD, remote_files("v1"))
    server = serve.make_server(0, manager=m, build_dir=build, data_dir=data, tries=1)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)

    def get(path, headers=None, method="GET", body=None):
        req = urllib.request.Request(base + path, headers=headers or {}, method=method, data=body)
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    try:
        status, h, body = get("/odds/")
        assert status == 200 and body == b"<p>odds</p>" and h["Cache-Control"] == "no-store"
        status, h, _ = get("/odds?season=2025")
        assert status == 302 and h["Location"] == "/odds/?season=2025"
        status, _, body = get("/team/KC/")
        assert status == 200 and body == b"<p>spa</p>"
        status, h, _ = get("/_app/immutable/a.js")
        assert "immutable" in h["Cache-Control"] and h["Content-Type"].startswith("text/javascript")
        status, h, body = get("/data/meta.json", {"Accept-Encoding": "gzip"})
        assert h["Content-Encoding"] == "gzip" and h["Cache-Control"] == "no-store"
        assert json.loads(gzip.decompress(body))["generated_at"] == "x"
        status, h, body = get("/data/meta.json", {"Range": "bytes=0-1"})
        assert (
            status == 206
            and body == b'{"'
            and h["Content-Range"].endswith(f"/{(data / 'meta.json').stat().st_size}")
        )
        status, _, body = get("/api/status")
        assert status == 200 and json.loads(body)["available"] is True
        js = {"Content-Type": "application/json"}
        payload = json.dumps({"auto": "gameday"}).encode()
        status, _, body = get("/api/settings", js, "POST", payload)
        assert status == 200 and json.loads(body)["settings"]["auto"] == "gameday"
        status, _, _ = get("/api/settings", js, "POST", b'{"interval_minutes": 2}')
        assert status == 400
        evil = {**js, "Origin": "https://evil.example"}
        status, _, _ = get("/api/sync", evil, "POST", b"{}")
        assert status == 403
        # A refused POST's body must not leak into the next request on a kept-alive connection.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("POST", "/api/sync", body=b"{}", headers=evil)
        refused = conn.getresponse()
        assert refused.status == 403 and refused.read()
        conn.request("GET", "/api/status")
        assert conn.getresponse().status == 200
        conn.close()
        status, _, body = get("/api/sync", js, "POST", b"{}")
        assert status == 202
        m.wait(30)
        assert m.status()["last_result"] == "updated"
    finally:
        server.shutdown()
        server.server_close()
