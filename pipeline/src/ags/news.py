"""NFL news: ESPN headlines plus injury-report items, for ``news.json`` and ``/api/news``.

Two kinds of item, one shape (``kind`` tells them apart):

- ``news``: ESPN's public news API (``config.NEWS_URL`` and the per-team feed). Teams and
  players come from each article's ``categories``: ESPN team ids map to our team codes
  (``ESPN_TEAMS``; ESPN's WSH and LAR are our WAS and LA), ESPN athlete ids to gsis ids via
  the players directory / dynastyprocess id map (``espn_ids``).
- ``injury``: the latest week of the official injury report (nflverse ``injuries`` view).
  Every player with a game status (Out / Doubtful / Questionable), players whose status
  cleared since their previous report, and skill players listed without a status. Each item
  says what changed against the team's previous report. Reports carry no timestamp, so
  ``published`` is an estimate: 4 pm ET on the day game statuses come out (two days before
  the game; one for Thursday games), never later than the build.

ESPN is optional: any network failure keeps the previous ``news.json``'s ESPN items and logs
one line, and injury items are always rebuilt offline.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from .config import NEWS_TEAM_URL, NEWS_URL, RAW_DIR

if TYPE_CHECKING:  # `ags up` imports this module: keep duckdb out of its startup
    import duckdb


def has_relation(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    from .db import has_relation

    return has_relation(con, name)


TIMEOUT = 8
MAX_BYTES = 4 * 1024 * 1024
MAX_NEWS = 150
PER_TEAM = 3  # newest items per team kept even when the league-wide feed is busier
MAX_INJURY = 220
DESCRIPTION_CHARS = 240
LIVE_TTL = 600  # /api/news: seconds between ESPN fetches
RETRY_AFTER = 120  # ... and after a failed one
ET = ZoneInfo("America/New_York")

# ESPN team id -> our code (pbp abbreviations: LA = Rams, WAS = Commanders).
ESPN_TEAMS: dict[int, str] = {
    1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET",
    9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LA", 15: "MIA", 16: "MIN",
    17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC",
    25: "SF", 26: "SEA", 27: "TB", 28: "WAS", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}  # fmt: skip
# ESPN abbreviations that differ from ours (plus historical ones).
ESPN_ABBR = {"WSH": "WAS", "LAR": "LA", "OAK": "LV", "SD": "LAC", "STL": "LA", "JAC": "JAX"}
OUR_TEAMS = set(ESPN_TEAMS.values())

STATUS_RANK = {"Out": 3, "Doubtful": 2, "Questionable": 1}
FANTASY_POS = {"QB", "RB", "WR", "TE", "K", "FB"}
PRACTICE = {
    "Full Participation in Practice": "full practice",
    "Limited Participation in Practice": "limited in practice",
    "Did Not Participate In Practice": "did not practice",
}


class NewsError(Exception):
    """ESPN could not be reached or sent something unusable."""


def log(msg: str) -> None:
    print(f"news: {msg}", file=sys.stderr)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(microsecond=0)


# ---------- ESPN ----------


def urlopen(req: urllib.request.Request, timeout: float):
    """Seam for tests: they replace this to avoid the network."""
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_json(url: str, timeout: float = TIMEOUT) -> object:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "any-given-stat"}
    )
    try:
        with urlopen(req, timeout) as r:
            body = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise NewsError(f"ESPN answered HTTP {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", None) or type(e).__name__
        raise NewsError(f"couldn't reach ESPN ({reason})") from None
    if len(body) > MAX_BYTES:
        raise NewsError("ESPN's response was too large")
    try:
        return json.loads(body)
    except ValueError:
        raise NewsError("ESPN sent something other than JSON") from None


def team_code(value: object) -> str | None:
    """ESPN team id (int or digits) or abbreviation -> our code."""
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return ESPN_TEAMS.get(int(value))
    if isinstance(value, str):
        v = value.upper()
        v = ESPN_ABBR.get(v, v)
        return v if v in OUR_TEAMS else None
    return None


def parse_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def clip(text: object, n: int = DESCRIPTION_CHARS) -> str:
    s = re.sub(r"\s+", " ", text).strip() if isinstance(text, str) else ""
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(",;:—-")
    return cut + "…"


def _https(url: object) -> str | None:
    return url if isinstance(url, str) and url.startswith("https://") else None


def _image(article: dict) -> str | None:
    images = [
        i for i in article.get("images") or [] if isinstance(i, dict) and _https(i.get("url"))
    ]
    # Prefer a landscape header photo; any image otherwise.
    images.sort(
        key=lambda i: (i.get("type") != "header", (i.get("width") or 0) < (i.get("height") or 0))
    )
    return images[0]["url"] if images else None


def normalize_article(article: object, espn_ids: dict[str, str]) -> dict | None:
    """One ESPN news article -> a news item (None when it has no headline or link)."""
    if not isinstance(article, dict):
        return None
    headline = clip(article.get("headline"), 200)
    links = article.get("links") or {}
    url = _https(((links.get("web") or {}) if isinstance(links, dict) else {}).get("href"))
    published = parse_time(article.get("published")) or parse_time(article.get("lastModified"))
    raw_id = article.get("id") or article.get("nowId")
    if not headline or not url or published is None or raw_id is None:
        return None
    teams: list[str] = []
    athletes: list[dict] = []
    for c in article.get("categories") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "team":
            team = c.get("team") if isinstance(c.get("team"), dict) else {}
            code = team_code(c.get("teamId") or team.get("id")) or team_code(
                team.get("abbreviation")
            )
            if code and code not in teams:
                teams.append(code)
        elif c.get("type") == "athlete":
            athlete = c.get("athlete") if isinstance(c.get("athlete"), dict) else {}
            espn_id = str(c.get("athleteId") or athlete.get("id") or "")
            name = clip(c.get("description") or athlete.get("description"), 60)
            gsis = espn_ids.get(espn_id)
            if name and all(a["name"] != name for a in athletes):
                athletes.append({"id": gsis, "name": name})
    kind = article.get("type")
    item = {
        "id": f"espn-{raw_id}",
        "kind": "news",
        "headline": headline,
        "description": clip(article.get("description")),
        "published": iso(published),
        "url": url,
        "image": _image(article),
        "teams": teams,
        "players": [a["id"] for a in athletes if a["id"]],
        "athletes": athletes,
        "source": "ESPN",
    }
    if kind == "Media":
        item["label"] = "Video"
    elif kind == "Recap":
        item["label"] = "Recap"
    if article.get("premium") is True:
        item["premium"] = True
    byline = clip(article.get("byline"), 60)
    if byline:
        item["byline"] = byline
    return item


def articles(payload: object) -> list:
    if isinstance(payload, dict) and isinstance(payload.get("articles"), list):
        return payload["articles"]
    raise NewsError("ESPN's news response has no articles")


def espn_items(
    espn_ids: dict[str, str],
    fetch: Callable[[str], object] = fetch_json,
    teams: Iterable[int] = ESPN_TEAMS,
) -> list[dict]:
    """League-wide feed plus each team's feed, deduplicated. Raises NewsError when the
    league-wide feed fails (the network is down; team feeds aren't tried). A failed team
    feed is skipped."""
    raw = list(articles(fetch(NEWS_URL)))

    def one(team_id: int) -> list:
        try:
            return articles(fetch(NEWS_TEAM_URL.format(team=team_id)))
        except NewsError:
            return []

    with ThreadPoolExecutor(max_workers=8) as pool:
        for batch in pool.map(one, list(teams)):
            raw.extend(batch)
    out: dict[str, dict] = {}
    for a in raw:
        item = normalize_article(a, espn_ids)
        if item and item["id"] not in out:
            out[item["id"]] = item
    return list(out.values())


def select_news(items: Iterable[dict], limit: int = MAX_NEWS, per_team: int = PER_TEAM) -> list:
    """Newest ``limit`` items, but each team's ``per_team`` newest are always kept (so team
    pages have something even when the league-wide feed is busy). Newest first."""
    by_time = sorted(items, key=lambda i: i["published"], reverse=True)
    keep: dict[str, dict] = {}
    count: dict[str, int] = {}
    for i in by_time:
        for t in i["teams"]:
            if count.get(t, 0) < per_team:
                keep[i["id"]] = i
                for t2 in i["teams"]:
                    count[t2] = count.get(t2, 0) + 1
                break
    for i in by_time:
        if len(keep) >= limit:
            break
        keep.setdefault(i["id"], i)
    return sorted(keep.values(), key=lambda i: i["published"], reverse=True)


def espn_ids(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """ESPN athlete id -> gsis id, from the players directory and the dynastyprocess map."""
    out: dict[str, str] = {}
    if has_relation(con, "player_ids"):
        for espn, gsis in con.execute(
            "select espn_id, gsis_id from player_ids "
            "where gsis_id is not null and espn_id is not null"
        ).fetchall():
            out[str(espn).removesuffix(".0")] = gsis
    if has_relation(con, "players"):
        cols = {r[0] for r in con.execute("describe players").fetchall()}
        if "espn_id" in cols:
            for espn, gsis in con.execute(
                "select cast(espn_id as varchar), gsis_id from players "
                "where espn_id is not null and gsis_id is not null"
            ).fetchall():
                out[espn.removesuffix(".0")] = gsis
    return out


# ---------- injury report ----------


def _detail(text: object) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return None
    s = text.strip()
    m = re.match(r"(?i)not injury related\s*-\s*(.+)", s)
    if m:
        why = m.group(1).strip().lower()
        return "not injury: " + ("rest" if why.startswith("rest") else why)
    return s.lower()


def _report_time(gameday: object) -> dt.datetime | None:
    """When game statuses come out: 4 pm ET two days before the game (one day before a
    Thursday game)."""
    if isinstance(gameday, str):
        try:
            gameday = dt.date.fromisoformat(gameday[:10])
        except ValueError:
            return None
    if not isinstance(gameday, dt.date):
        return None
    day = gameday - dt.timedelta(days=1 if gameday.weekday() == 3 else 2)
    return dt.datetime(day.year, day.month, day.day, 16, 0, tzinfo=ET).astimezone(dt.UTC)


def _injury_rows(con: duckdb.DuckDBPyConnection, season: int, raw_dir: Path) -> list[tuple]:
    """(week, team, gsis, position, name, report_status, practice_status, injury) for one
    season. The body part isn't in the ``injuries`` view; without it, it comes from the raw
    parquet (matched on week and gsis id)."""
    cols = {r[0] for r in con.execute("describe injuries").fetchall()}
    part = [c for c in ("report_primary_injury", "practice_primary_injury") if c in cols]
    rows = con.execute(
        f"""
        select week, team, gsis_id, position, full_name, report_status, practice_status,
               {f"coalesce({', '.join(part)}, null)" if part else "null"}
        from injuries where season = ? and gsis_id is not null
        """,
        [season],
    ).fetchall()
    path = raw_dir / f"injuries_{season}.parquet"
    if not part and path.exists():
        parts = dict(
            ((w, g), p)
            for w, g, p in con.execute(
                "select week, gsis_id, coalesce(report_primary_injury, practice_primary_injury) "
                "from read_parquet(?)",
                [path.as_posix()],
            ).fetchall()
        )
        rows = [(*r[:7], parts.get((r[0], r[2]))) for r in rows]
    return rows


def injury_items(
    con: duckdb.DuckDBPyConnection,
    now: dt.datetime | None = None,
    raw_dir: Path = RAW_DIR,
    limit: int = MAX_INJURY,
) -> tuple[list[dict], dict | None]:
    """Items for the latest week of the latest season's injury report, plus
    ``{"season", "week"}`` (None when there's no report)."""
    if not has_relation(con, "injuries"):
        return [], None
    now = now or now_utc()
    latest = con.execute(
        "select season, max(week) from injuries where season = (select max(season) from injuries)"
        " group by season"
    ).fetchone()
    if not latest or latest[1] is None:
        return [], None
    season, week = int(latest[0]), int(latest[1])
    rows = _injury_rows(con, season, raw_dir)

    # Each team's game this week (opponent, home?, when statuses come out).
    games: dict[str, tuple[str, bool, dt.datetime | None]] = {}
    if has_relation(con, "schedule"):
        for home, away, gameday in con.execute(
            "select home_team, away_team, gameday from schedule where season = ? and week = ?",
            [season, week],
        ).fetchall():
            t = _report_time(gameday)
            games[home] = (away, True, t)
            games[away] = (home, False, t)

    current = [r for r in rows if r[0] == week]
    # The previous report for each player = his team's latest earlier report (bye weeks skip).
    prev_week: dict[str, int] = {}
    for w, team, *_ in rows:
        if w < week:
            prev_week[team] = max(prev_week.get(team, 0), w)
    previous = {(r[1], r[2]): r for r in rows if r[0] < week and prev_week.get(r[1]) == r[0]}
    # A team's report is final once it has game statuses or its release time has passed;
    # before that, nflverse holds the practice reports only (no status != cleared).
    with_status = {r[1] for r in current if r[5] in STATUS_RANK}

    items = []
    for _, team, gsis, pos, name, status, practice, injury in current:
        status = status if status in STATUS_RANK else None
        before = previous.get((team, gsis))
        was = before[5] if before and before[5] in STATUS_RANK else None
        pos = (pos or "").strip()
        fantasy_pos = pos in FANTASY_POS
        game = games.get(team)
        release = game[2] if game else None
        final = team in with_status or release is None or release <= now
        prac = PRACTICE.get(practice or "")
        if not final:
            if not (was or (fantasy_pos and practice in PRACTICE)):
                continue
            change = None
        elif status:
            if was is None:
                change = "new"
            elif STATUS_RANK[status] > STATUS_RANK[was]:
                change = "worse"
            elif STATUS_RANK[status] < STATUS_RANK[was]:
                change = "better"
            else:
                change = "same"
                if not fantasy_pos:
                    continue
        elif was:
            change = "cleared"
        elif fantasy_pos and prac and prac != "full practice":
            change = None
        else:
            continue
        what = _detail(injury)
        verb = {"Out": "ruled out", "Doubtful": "doubtful", "Questionable": "questionable"}
        if status:
            headline = f"{name} {verb[status]}" + (f" ({what})" if what else "")
        elif not final:
            headline = f"{name}: {prac or 'on the practice report'}"
        else:
            headline = f"{name} has no game status"
        bits = [f"{team} {pos}".strip()]
        if what:
            bits.append(what[0].upper() + what[1:])
        if prac:
            bits.append(prac[0].upper() + prac[1:])
        if was:
            bits.append(
                f"{'also' if change == 'same' else 'was'} {was.lower()} in week {prev_week[team]}"
            )
        if game:
            bits.append(f"Week {week} {'vs' if game[1] else 'at'} {game[0]}")
        if not final and release:
            bits.append(f"game status due {release.astimezone(ET):%A}")
        item = {
            "id": f"inj-{season}-{week}-{gsis}",
            "kind": "injury",
            "headline": headline,
            "description": " · ".join(bits),
            "published": iso(min(release, now) if release and final else now),
            "url": None,
            "image": None,
            "teams": [team],
            "players": [gsis],
            "athletes": [{"id": gsis, "name": name}],
            "source": "NFL injury report",
            "week": week,
        }
        for key, value in (("status", status), ("change", change), ("position", pos or None)):
            if value:
                item[key] = value
        if not final:
            item["preliminary"] = True
        priority = (
            {"worse": 0, "new": 1, "cleared": 2, "better": 3, "same": 4}.get(change or "", 5),
            -STATUS_RANK.get(status or "", 0),
            not fantasy_pos,
        )
        items.append((priority, item))
    items.sort(key=lambda p: p[0])
    kept = [i for _, i in items[:limit]]
    kept.sort(key=lambda i: i["published"], reverse=True)  # stable: priority within a time
    return kept, {"season": season, "week": week}


# ---------- payload ----------


def merge(news: list[dict], injuries: list[dict]) -> list[dict]:
    """News and injury items, newest first (injuries after news at the same minute)."""
    tagged = [(i["published"], 1, n, i) for n, i in enumerate(news)]
    tagged += [(i["published"], 0, -n, i) for n, i in enumerate(injuries)]
    tagged.sort(key=lambda t: t[:3], reverse=True)
    return [t[3] for t in tagged]


def payload(
    news: list[dict],
    injuries: list[dict],
    report: dict | None,
    *,
    generated_at: str,
    news_fetched_at: str | None,
    live: bool = False,
    error: str | None = None,
) -> dict:
    return {
        "generated_at": generated_at,
        "news_fetched_at": news_fetched_at,
        "live": live,
        "error": error,
        "injury_report": report,
        "items": merge(news, injuries),
    }


def read_previous(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("items"), list) else {}
    except (OSError, ValueError):
        return {}


def build(
    con: duckdb.DuckDBPyConnection,
    previous: dict | None = None,
    fetch: Callable[[str], object] = fetch_json,
    now: dt.datetime | None = None,
    raw_dir: Path = RAW_DIR,
) -> dict:
    """news.json: fresh ESPN items, or the previous file's when ESPN can't be reached."""
    now = now or now_utc()
    previous = previous or {}
    injuries, report = injury_items(con, now=now, raw_dir=raw_dir)
    error = None
    try:
        news = select_news(espn_items(espn_ids(con), fetch))
        fetched_at = iso(now)
    except NewsError as e:
        error = str(e)
        log(f"ESPN news skipped: {e}; keeping the previous news items")
        news = [i for i in previous.get("items", []) if i.get("kind") == "news"]
        fetched_at = previous.get("news_fetched_at")
    return payload(
        news, injuries, report, generated_at=iso(now), news_fetched_at=fetched_at, error=error
    )


# ---------- live feed for `ags up` ----------


class LiveNews:
    """``/api/news``: ESPN fetched at most every ``LIVE_TTL`` seconds, merged with the
    injury items (and, if ESPN is down, the news items) of the last build's news.json."""

    def __init__(
        self,
        fetch: Callable[[str], object] = fetch_json,
        clock: Callable[[], float] = time.time,
        ttl: float = LIVE_TTL,
    ) -> None:
        self.fetch = fetch
        self.clock = clock
        self.ttl = ttl
        self._lock = threading.Lock()
        self._news: list[dict] | None = None
        self._fetched_at: str | None = None
        self._next_try = 0.0
        self._error: str | None = None
        self._ids: tuple[float, dict[str, str]] = (-1.0, {})

    def _espn_ids(self, data_dir: Path) -> dict[str, str]:
        """ESPN -> gsis from the build's fantasy_ids.json (re-read when it changes)."""
        path = data_dir / "fantasy_ids.json"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return {}
        if mtime != self._ids[0]:
            try:
                ids = json.loads(path.read_text(encoding="utf-8")).get("espn", {})
            except (OSError, ValueError, AttributeError):
                ids = {}
            self._ids = (mtime, ids if isinstance(ids, dict) else {})
        return self._ids[1]

    def get(self, data_dir: Path) -> dict:
        base = read_previous(data_dir / "news.json")
        with self._lock:
            now = self.clock()
            if now >= self._next_try:
                try:
                    self._news = select_news(espn_items(self._espn_ids(data_dir), self.fetch))
                    self._fetched_at = iso(dt.datetime.fromtimestamp(now, dt.UTC))
                    self._error = None
                    self._next_try = now + self.ttl
                except NewsError as e:
                    if self._error is None:
                        log(f"live ESPN news unavailable: {e}")
                    self._error = str(e)
                    self._next_try = now + min(self.ttl, RETRY_AFTER)
            items = base.get("items", [])
            injuries = [i for i in items if i.get("kind") == "injury"]
            if self._news is not None:
                news, fetched = self._news, self._fetched_at
            else:
                news = [i for i in items if i.get("kind") == "news"]
                fetched = base.get("news_fetched_at")
            return payload(
                news,
                injuries,
                base.get("injury_report"),
                generated_at=base.get("generated_at") or iso(now_utc()),
                news_fetched_at=fetched,
                live=self._news is not None,
                error=self._error,
            )
