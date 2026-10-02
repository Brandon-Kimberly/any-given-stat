"""Team names, divisions and colors (nflverse teams_colors_logos.csv), with readable picks.

Team primaries are often too dark for a dark page or too light for a light one, so
for each theme we pick the first team color that clears a WCAG contrast floor
against the page background.
"""

from __future__ import annotations

import duckdb

from .db import has_relation, records

LIGHT_BG = "#fcfcfb"
DARK_BG = "#1a1a19"
MIN_CONTRAST = 2.0
BADGE_LIGHT_FG = "#ffffff"
BADGE_DARK_FG = "#0b0b0b"


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def luminance(hex_color: str) -> float:
    """WCAG 2 relative luminance of an sRGB hex color (0 = black, 1 = white)."""

    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colors, from 1 (same) to 21 (black on white)."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def pick_color(candidates: list[str | None], background: str, floor: float = MIN_CONTRAST) -> str:
    """First candidate with contrast >= ``floor`` against ``background``; else the best one."""
    colors = [c for c in candidates if c]
    for c in colors:
        if contrast(c, background) >= floor:
            return c
    return max(colors, key=lambda c: contrast(c, background))


def badge_fg(color: str) -> str:
    """White or near-black text, whichever reads better on ``color``."""
    light = contrast(BADGE_LIGHT_FG, color)
    dark = contrast(BADGE_DARK_FG, color)
    return BADGE_LIGHT_FG if light >= dark else BADGE_DARK_FG


def teams_meta(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """One row per team that appears as an offense in the loaded play-by-play.

    Requires the ``team_colors`` view; returns [] without it. Legacy codes in the
    CSV (OAK, SD, STL, LAR) drop out because play-by-play uses current codes.
    """
    if not has_relation(con, "team_colors"):
        return []
    rows = records(
        con,
        """
        select team_abbr as team, team_name as name, team_nick as nick,
               team_conf as conf, team_division as division,
               lower(team_color::varchar) as color, lower(team_color2::varchar) as color2,
               lower(team_color3::varchar) as color3, lower(team_color4::varchar) as color4
        from team_colors
        where team_abbr in (select distinct posteam from pbp where posteam is not null)
        order by team_abbr
        """,
    )
    for r in rows:
        candidates = [r["color"], r["color2"], r.pop("color3"), r.pop("color4")]
        r["color_light"] = pick_color(candidates, LIGHT_BG)
        r["color_dark"] = pick_color(candidates, DARK_BG)
        r["badge_fg"] = badge_fg(r["color"])
    return rows
