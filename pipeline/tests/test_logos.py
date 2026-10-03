from ags import fetch


def test_fetch_logos_gets_the_full_logo_and_the_tile_and_survives_failures(tmp_path, monkeypatch):
    teams = tmp_path / "teams.csv"
    teams.write_text(
        "team_abbr,team_logo_espn,team_logo_squared\n"
        "DET,https://a.espncdn.com/det.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/DET.png\n"
        "SEA,https://a.espncdn.com/sea.png,\n"
    )
    fetched = []

    def fake_download(url, dest):
        if "sea" in url:
            raise OSError("blocked")
        fetched.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"png")

    monkeypatch.setattr(fetch, "_download", fake_download)
    assert fetch.fetch_logos(teams, raw_dir=tmp_path) == tmp_path / "logos"
    assert (tmp_path / "logos_full" / "DET.png").exists()
    assert (tmp_path / "logos" / "DET.png").exists()
    assert not (tmp_path / "logos_full" / "SEA.png").exists()
    assert any("raw.githubusercontent.com" in u for u in fetched)  # tile URL rewritten
    fetch.fetch_logos(teams, raw_dir=tmp_path)  # cached: nothing re-downloaded
    assert len(fetched) == 2
