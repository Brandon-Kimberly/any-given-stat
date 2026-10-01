"""Run every SQL explorer preset against the real exported play-by-play.

Skipped when the pipeline hasn't been run (no web/static/data/pbp files).
"""

from __future__ import annotations

import re

import duckdb
import pytest

from ags.config import OUT_DIR, REPO_ROOT

PRESETS_TS = REPO_ROOT / "web" / "src" / "lib" / "presets.ts"
PBP_FILES = sorted((OUT_DIR / "pbp").glob("pbp_*.parquet"))


def preset_sql() -> list[tuple[str, str]]:
    text = PRESETS_TS.read_text()
    titles = re.findall(r"title: '([^']+)'", text)
    sqls = re.findall(r"sql: `([^`]+)`", text)
    assert titles and len(titles) == len(sqls)
    return list(zip(titles, sqls, strict=True))


@pytest.mark.skipif(not PBP_FILES, reason="run `uv run ags build` first")
@pytest.mark.parametrize(("title", "sql"), preset_sql())
def test_preset_runs_and_returns_rows(title, sql):
    con = duckdb.connect()
    # Mirror the explorer: `pbp` is the most recent complete season.
    files = [p for p in PBP_FILES if p.stat().st_size > 2_000_000][-1:]
    con.execute(f"create view pbp as select * from read_parquet('{files[0].as_posix()}')")
    rows = con.execute(sql).fetchall()
    assert rows, f"{title} returned no rows"
