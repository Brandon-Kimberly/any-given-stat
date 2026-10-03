"""The ESPN league proxy in ``ags up`` (no network: ``serve.espn_urlopen`` is faked)."""

from __future__ import annotations

import email.message
import io
import json
import threading
import urllib.error
import urllib.request

import pytest

from ags import serve

LEAGUE = {"id": 336358, "seasonId": 2025, "settings": {"name": "Office League"}, "teams": []}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", code, "err", email.message.Message(), None)


@pytest.fixture
def espn(monkeypatch):
    """Fake ESPN: records requests; `reply` is bytes to return or an exception to raise."""
    state = {"reply": json.dumps(LEAGUE).encode(), "requests": []}

    def fake(req, timeout):
        state["requests"].append((req, timeout))
        reply = state["reply"]
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(reply)

    monkeypatch.setattr(serve, "espn_urlopen", fake)
    return state


def test_parse_espn_query():
    assert serve.parse_espn_query("id=336358&season=2025") == ("336358", "2025")
    for bad in (
        "",
        "id=336358",
        "season=2025",
        "id=33a&season=2025",
        "id=1/../2&season=2025",
        "id=1&season=25",
        "id=1&season=2025x",
        "id=1&id=2&season=2025",
        "id=%2F1&season=2025",
        "id=1234567890123456&season=2025",
    ):
        with pytest.raises(ValueError):
            serve.parse_espn_query(bad)


def test_espn_cookie_header():
    assert serve.espn_cookie_header(None, None) is None
    assert serve.espn_cookie_header(" ", "") is None
    assert serve.espn_cookie_header("AEB%2Fx%3D", "{AB-12}") == "espn_s2=AEB%2Fx%3D; SWID={AB-12}"
    assert serve.espn_cookie_header("AEB+x/y==", None) == "espn_s2=AEB+x/y=="
    for bad in ("a;b=c", "a\r\nX-Evil: 1", "a b", 'a"b', "x" * 5000):
        with pytest.raises(ValueError):
            serve.espn_cookie_header(bad, None)


def test_fetch_espn_league(espn):
    assert serve.fetch_espn_league("336358", "2025", "espn_s2=s; SWID={W}") == LEAGUE
    req, timeout = espn["requests"][0]
    assert timeout == 15
    assert req.full_url == (
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/segments/0"
        "/leagues/336358?view=mSettings&view=mTeam&view=mRoster"
    )
    assert req.get_header("Cookie") == "espn_s2=s; SWID={W}"
    serve.fetch_espn_league("1", "2024", None)
    assert espn["requests"][1][0].get_header("Cookie") is None


@pytest.mark.parametrize(
    ("reply", "status"),
    [
        (http_error(401), 401),
        (http_error(403), 403),
        (http_error(404), 404),
        (http_error(500), 502),
        (urllib.error.URLError("no route"), 502),
        (TimeoutError(), 502),
        (b"<html>maintenance</html>", 502),
    ],
)
def test_fetch_espn_league_errors(espn, reply, status):
    espn["reply"] = reply
    with pytest.raises(serve.EspnError) as e:
        serve.fetch_espn_league("1", "2025", "espn_s2=secret")
    assert e.value.status == status
    assert "secret" not in str(e.value)


def test_redirects_stay_on_espn():
    handler = serve._EspnRedirects()
    req = urllib.request.Request("https://lm-api-reads.fantasy.espn.com/x")
    req.add_header("Cookie", "espn_s2=s")
    ok = handler.redirect_request(req, None, 302, "Found", {}, "https://fantasy.espn.com/y")
    assert ok is not None and ok.full_url == "https://fantasy.espn.com/y"
    for bad in ("https://evil.example/", "http://fantasy.espn.com/", "https://espn.com.evil.io/"):
        with pytest.raises(serve.EspnError):
            handler.redirect_request(req, None, 302, "Found", {}, bad)


def test_server_proxy(espn, tmp_path, capsys):
    server = serve.make_server(0, manager=None, build_dir=tmp_path, data_dir=tmp_path, tries=1)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def get(path, headers=None, method="GET"):
        req = urllib.request.Request(base + path, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    path = "/api/espn/league?id=336358&season=2025"
    cookies = {"X-ESPN-S2": "AEB%2Fsecret", "X-ESPN-SWID": "{SW-1D}"}
    try:
        status, h, body = get(path, cookies)
        assert status == 200 and json.loads(body) == LEAGUE
        assert h["Cache-Control"] == "no-store" and h["Content-Type"] == "application/json"
        sent = espn["requests"][-1][0]
        assert sent.get_header("Cookie") == "espn_s2=AEB%2Fsecret; SWID={SW-1D}"
        assert "336358" in sent.full_url and "/seasons/2025/" in sent.full_url

        # Same-origin pages may call it; other sites and other Host names may not.
        assert get(path, {"Origin": f"http://localhost:{port}"})[0] == 200
        n = len(espn["requests"])
        assert get(path, {"Origin": "https://evil.example"})[0] == 403
        assert get(path, {"Host": "evil.example"})[0] == 403
        assert get(path, method="POST")[0] == 405
        assert get(path, method="HEAD")[0] == 405
        # Bad parameters never reach ESPN.
        assert get("/api/espn/league?id=1;rm&season=2025")[0] == 400
        assert get("/api/espn/league?id=1&season=20255")[0] == 400
        assert get(path, {"X-ESPN-S2": "a;b"})[0] == 400
        assert len(espn["requests"]) == n

        # ESPN's errors come back with ESPN's status and source 'espn'.
        espn["reply"] = http_error(401)
        status, _, body = get(path, cookies)
        assert status == 401
        assert json.loads(body)["source"] == "espn" and json.loads(body)["status"] == 401
        espn["reply"] = urllib.error.URLError("down")
        status, _, body = get(path)
        assert status == 502 and json.loads(body)["source"] == "espn"
        # Other API paths still say not found (no sync manager here).
        assert get("/api/espn/other")[0] == 404
    finally:
        server.shutdown()
        server.server_close()
    out = capsys.readouterr()
    assert "secret" not in out.out + out.err


def test_data_status_rebuilds_older_data(tmp_path):
    import json

    from ags.config import DATA_VERSION
    from ags.serve import data_status

    assert data_status(tmp_path) == "missing"
    (tmp_path / "meta.json").write_text(json.dumps({"seasons": []}))
    assert data_status(tmp_path) == "outdated"  # built before data_version existed
    (tmp_path / "meta.json").write_text(json.dumps({"data_version": DATA_VERSION}))
    assert data_status(tmp_path) == "ok"
