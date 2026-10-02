"""Player directory (nflverse players.parquet) joined onto the player datasets.

Play-by-play only carries abbreviated names ("P.Mahomes") and no positions, so the
build looks players up by gsis_id after the pbp-only datasets are computed.
"""

from __future__ import annotations

from collections.abc import Iterable

import duckdb

from .db import has_relation, records


def players(con: duckdb.DuckDBPyConnection, ids: Iterable[str]) -> list[dict]:
    """Directory rows for the given gsis ids. Requires the ``players`` view; else []."""
    ids = sorted({i for i in ids if i})
    if not ids or not has_relation(con, "players"):
        return []
    return records(
        con,
        """
        select gsis_id as player_id, display_name as name, position, position_group,
               rookie_season, draft_year, draft_round, draft_pick, college_name as college
        from players
        where gsis_id in (select unnest(?::varchar[]))
        order by gsis_id
        """,
        [ids],
    )


def enrich(rows: list[dict], directory: list[dict], fields: dict[str, str]) -> None:
    """Add directory fields to rows in place, matched on ``player_id``.

    ``fields`` maps output field -> directory field; unknown players get None.
    """
    by_id = {p["player_id"]: p for p in directory}
    for r in rows:
        p = by_id.get(r["player_id"], {})
        for out, src in fields.items():
            r[out] = p.get(src)
