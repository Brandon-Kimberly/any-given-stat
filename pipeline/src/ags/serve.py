"""``ags up``: build what's missing, then serve the site locally with a Sync API.

- Data: ``web/static/data/meta.json`` missing -> run the full data build first.
- Web app: ``npm install`` if ``web/node_modules`` is missing; ``npm run build`` if
  ``web/build`` is missing or older than any source file.
- Server: stdlib ``ThreadingHTTPServer`` on 127.0.0.1. ``web/build`` is served with SvelteKit
  adapter-static routing (``/odds/`` -> ``odds/index.html``, ``/odds`` -> redirect, unknown
  routes -> the ``404.html`` SPA fallback with status 200). ``/data/*`` is served straight from
  ``web/static/data`` so a sync shows up without rebuilding the web app. ``/api/*`` is the sync
  API (``sync.py``), plus ``/api/espn/league``: a proxy for ESPN fantasy leagues, whose API
  has no CORS headers (the browser can't call it directly).
"""

from __future__ import annotations

import gzip
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .cli import default_seasons, parse_seasons, run_build
from .config import DATA_VERSION, OUT_DIR, REPO_ROOT
from .sync import SyncManager

WEB_DIR = REPO_ROOT / "web"
BUILD_DIR = WEB_DIR / "build"
DATA_DIR = OUT_DIR
PORT_TRIES = 10
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".map": "application/json",
    ".parquet": "application/vnd.apache.parquet",
    ".wasm": "application/wasm",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".csv": "text/csv; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}
COMPRESSIBLE = {".json", ".js", ".mjs", ".css", ".html", ".svg", ".csv", ".txt", ".map"}
GZIP_MIN_BYTES = 1024
GZIP_CACHE_BYTES = 256 * 1024 * 1024
MAX_BODY = 10_000


# ---------- Routing (pure) ----------


@dataclass(frozen=True)
class Route:
    kind: str  # 'file' | 'redirect' | 'fallback' | 'notfound'
    path: Path | None = None  # file to send (file / fallback)
    location: str | None = None  # redirect target path
    data: bool = False  # served from the data directory


def resolve(url_path: str, build_dir: Path = BUILD_DIR, data_dir: Path = DATA_DIR) -> Route:
    """Map a decoded-or-not URL path (no query string) to what to send."""
    path = urllib.parse.unquote(url_path)
    if not path.startswith("/") or "\x00" in path:
        return Route("notfound")
    parts = [p for p in path.split("/") if p]
    if any(p in (".", "..") or "\\" in p or ":" in p for p in parts):
        return Route("notfound")

    if parts and parts[0] == "data":
        f = data_dir.joinpath(*parts[1:])
        if len(parts) > 1 and f.is_file():
            return Route("file", f, data=True)
        return Route("notfound", data=True)

    f = build_dir.joinpath(*parts)
    if f.is_dir():
        index = f / "index.html"
        if index.is_file():
            if path.endswith("/"):
                return Route("file", index)
            return Route("redirect", location=path + "/")
    elif f.is_file():
        return Route("file", f)

    # Assets and anything that looks like a file are real 404s; routes get the SPA shell.
    last = parts[-1] if parts else ""
    fallback = build_dir / "404.html"
    if (parts and parts[0] == "_app") or "." in last or not fallback.is_file():
        return Route("notfound")
    return Route("fallback", fallback)


def content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in MIME:
        return MIME[suffix]
    guess, _ = mimetypes.guess_type(path.name)
    return guess or "application/octet-stream"


def cache_control(url_path: str, route: Route) -> str:
    if route.data or route.kind == "fallback" or (route.path and route.path.suffix == ".html"):
        return "no-store"
    if url_path.startswith("/_app/immutable/"):
        return "public, max-age=31536000, immutable"
    return "no-cache"


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """A single ``bytes=a-b`` range -> inclusive (start, end); None = whole file.
    Raises ValueError for an unsatisfiable range."""
    if not header or not header.startswith("bytes=") or "," in header:
        return None
    lo, _, hi = header[6:].strip().partition("-")
    try:
        if lo == "":
            n = int(hi)
            if n <= 0:
                raise ValueError("empty suffix range")
            return max(0, size - n), size - 1
        start = int(lo)
        end = int(hi) if hi else size - 1
    except ValueError:
        raise ValueError("bad range") from None
    if start >= size or end < start:
        raise ValueError("unsatisfiable range")
    return start, min(end, size - 1)


class GzipCache:
    """Compressed bodies keyed by (path, mtime, size); dropped wholesale when it gets big."""

    def __init__(self, limit: int = GZIP_CACHE_BYTES) -> None:
        self.limit = limit
        self._items: dict[str, tuple[int, int, bytes]] = {}
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, path: Path) -> bytes:
        st = path.stat()
        key = str(path)
        with self._lock:
            hit = self._items.get(key)
            if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
                return hit[2]
        body = gzip.compress(path.read_bytes(), compresslevel=6)
        with self._lock:
            if self._bytes + len(body) > self.limit:
                self._items.clear()
                self._bytes = 0
            old = self._items.pop(key, None)
            self._bytes -= len(old[2]) if old else 0
            self._items[key] = (st.st_mtime_ns, st.st_size, body)
            self._bytes += len(body)
        return body


def host_is_local(value: str | None) -> bool:
    """``Host`` header or ``Origin`` URL names this machine (CSRF / DNS-rebinding guard)."""
    if not value:
        return False
    if "://" in value:
        value = urllib.parse.urlsplit(value).netloc
    host = value.rsplit("@", 1)[-1]
    if host.startswith("["):
        host = host.split("]", 1)[0] + "]"
    else:
        host = host.split(":", 1)[0]
    return host.lower() in LOCAL_HOSTS


# ---------- ESPN fantasy proxy ----------

ESPN_LEAGUE_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
    "/segments/0/leagues/{league}?view=mSettings&view=mTeam&view=mRoster"
)
ESPN_TIMEOUT = 15
ESPN_MAX_BYTES = 32 * 1024 * 1024
# espn_s2 is URL-encoded base64 (sometimes pasted decoded); SWID is a {GUID}.
COOKIE_VALUE = re.compile(r"[A-Za-z0-9%{}+/=._-]{1,4096}")


class EspnError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = int(status)


def parse_espn_query(query: str) -> tuple[str, str]:
    """``id=<digits>&season=<4 digits>`` -> (league id, season); ValueError otherwise."""
    q = urllib.parse.parse_qs(query, keep_blank_values=True)
    ids, seasons = q.get("id", []), q.get("season", [])
    if len(ids) != 1 or not re.fullmatch(r"[0-9]{1,15}", ids[0]):
        raise ValueError("id must be an ESPN league id (digits)")
    if len(seasons) != 1 or not re.fullmatch(r"[0-9]{4}", seasons[0]):
        raise ValueError("season must be a 4-digit year")
    return ids[0], seasons[0]


def espn_cookie_header(espn_s2: str | None, swid: str | None) -> str | None:
    """``Cookie`` header for ESPN's private-league cookies; ValueError on unsafe characters."""
    parts = []
    for name, value in (("espn_s2", espn_s2), ("SWID", swid)):
        value = (value or "").strip()
        if not value:
            continue
        if not COOKIE_VALUE.fullmatch(value):
            raise ValueError(f"{name} contains characters a cookie can't have")
        parts.append(f"{name}={value}")
    return "; ".join(parts) or None


class _EspnRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects only within espn.com, so the cookies never go anywhere else."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urlsplit(newurl)
        host = (url.hostname or "").lower()
        if url.scheme != "https" or not (host == "espn.com" or host.endswith(".espn.com")):
            raise EspnError(HTTPStatus.BAD_GATEWAY, "ESPN redirected somewhere unexpected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_espn_opener = urllib.request.build_opener(_EspnRedirects)


def espn_urlopen(req: urllib.request.Request, timeout: float):
    """Seam for tests: they replace this to avoid the network."""
    return _espn_opener.open(req, timeout=timeout)


def fetch_espn_league(league: str, season: str, cookie: str | None) -> object:
    """ESPN's league JSON (settings, teams, rosters). Raises EspnError with the status to send:
    ESPN's own 401/403/404, else 502."""
    req = urllib.request.Request(
        ESPN_LEAGUE_URL.format(season=season, league=league),
        headers={"Accept": "application/json", "User-Agent": "any-given-stat"},
    )
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with espn_urlopen(req, ESPN_TIMEOUT) as r:
            body = r.read(ESPN_MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise EspnError(e.code, "this league is private: espn_s2 and SWID are needed") from None
        if e.code == 404:
            raise EspnError(404, "no ESPN league with that id and season") from None
        raise EspnError(HTTPStatus.BAD_GATEWAY, f"ESPN answered HTTP {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", None) or type(e).__name__
        raise EspnError(HTTPStatus.BAD_GATEWAY, f"couldn't reach ESPN ({reason})") from None
    if len(body) > ESPN_MAX_BYTES:
        raise EspnError(HTTPStatus.BAD_GATEWAY, "ESPN's response was too large")
    try:
        return json.loads(body)
    except ValueError:
        raise EspnError(HTTPStatus.BAD_GATEWAY, "ESPN sent something other than JSON") from None


# ---------- HTTP ----------


class SiteHandler(BaseHTTPRequestHandler):
    server_version = "ags"
    protocol_version = "HTTP/1.1"
    build_dir: Path = BUILD_DIR
    data_dir: Path = DATA_DIR
    manager: SyncManager | None = None
    gz = GzipCache()

    def log_message(self, format: str, *args: object) -> None:
        pass  # quiet; errors are reported via log_error

    def log_error(self, format: str, *args: object) -> None:
        sys.stderr.write("http: " + (format % args) + "\n")

    # --- dispatch ---

    def do_GET(self) -> None:
        self._dispatch(head=False)

    def do_HEAD(self) -> None:
        self._dispatch(head=True)

    def do_POST(self) -> None:
        # Always consume the body first: on a kept-alive connection an unread body would be
        # parsed as the next request.
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 <= n <= MAX_BODY:
            self.close_connection = True
            self._json(
                {"error": "bad or too large request body"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE
            )
            return
        self._body = self.rfile.read(n) if n else b""
        url = urllib.parse.urlsplit(self.path)
        if not url.path.startswith("/api/"):
            self._json({"error": "method not allowed"}, HTTPStatus.METHOD_NOT_ALLOWED)
            return
        self._api(url.path, post=True)

    def _dispatch(self, head: bool) -> None:
        url = urllib.parse.urlsplit(self.path)
        try:
            if url.path.startswith("/api/"):
                self._api(url.path, post=False)
                return
            route = resolve(url.path, self.build_dir, self.data_dir)
            if route.kind == "redirect":
                loc = route.location + (f"?{url.query}" if url.query else "")
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", loc)
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif route.kind == "notfound" or route.path is None:
                self._text("Not found", HTTPStatus.NOT_FOUND, head)
            else:
                self._file(url.path, route, head)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    # --- static files ---

    def _file(self, url_path: str, route: Route, head: bool) -> None:
        path = route.path
        assert path is not None
        ctype = content_type(path)
        size = path.stat().st_size
        range_header = self.headers.get("Range")
        accepts_gzip = "gzip" in (self.headers.get("Accept-Encoding") or "")
        gzip_it = (
            not head
            and not range_header
            and accepts_gzip
            and path.suffix.lower() in COMPRESSIBLE
            and size >= GZIP_MIN_BYTES
        )
        if gzip_it:
            body = self.gz.get(path)
            self.send_response(HTTPStatus.OK)
            self._common_headers(url_path, route, ctype)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        try:
            rng = parse_range(range_header, size)
        except ValueError:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start, end = rng if rng else (0, size - 1)
        length = max(0, end - start + 1)
        self.send_response(HTTPStatus.PARTIAL_CONTENT if rng else HTTPStatus.OK)
        self._common_headers(url_path, route, ctype)
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        if head or length == 0:
            return
        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1 << 20, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _common_headers(self, url_path: str, route: Route, ctype: str) -> None:
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cache_control(url_path, route))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _text(self, text: str, status: HTTPStatus, head: bool = False) -> None:
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    # --- API ---

    def _json(self, data: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self) -> object:
        raw = getattr(self, "_body", b"")
        return json.loads(raw) if raw.strip() else {}

    def _api(self, path: str, post: bool) -> None:
        if not host_is_local(self.headers.get("Host")):
            self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        origin = self.headers.get("Origin")
        if post and origin is not None and not host_is_local(origin):
            self._json({"error": "cross-origin request refused"}, HTTPStatus.FORBIDDEN)
            return
        if path == "/api/espn/league":
            self._espn_league(post)
            return
        m = self.manager
        if m is None:
            self._json({"available": False}, HTTPStatus.NOT_FOUND)
            return
        try:
            if path == "/api/status" and not post:
                self._json(m.status())
            elif path == "/api/sync" and post:
                body = self._read_json()
                force = bool(body.get("force")) if isinstance(body, dict) else False
                if not m.start(force=force):
                    self._json({"error": "a sync is already running", **m.status()}, 409)
                else:
                    self._json(m.status(), HTTPStatus.ACCEPTED)
            elif path == "/api/settings" and post:
                m.update_settings(self._read_json())
                self._json(m.status())
            elif path in ("/api/status", "/api/sync", "/api/settings"):
                self._json({"error": "method not allowed"}, HTTPStatus.METHOD_NOT_ALLOWED)
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as e:
            self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

    def _espn_league(self, post: bool) -> None:
        # GET only; also refused from other sites' pages (the proxy sends the user's cookies).
        if post or self.command != "GET":
            self._json({"error": "method not allowed"}, HTTPStatus.METHOD_NOT_ALLOWED)
            return
        origin = self.headers.get("Origin")
        if origin is not None and not host_is_local(origin):
            self._json({"error": "cross-origin request refused"}, HTTPStatus.FORBIDDEN)
            return
        try:
            league, season = parse_espn_query(urllib.parse.urlsplit(self.path).query)
            cookie = espn_cookie_header(
                self.headers.get("X-ESPN-S2"), self.headers.get("X-ESPN-SWID")
            )
        except ValueError as e:
            self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            return
        try:
            data = fetch_espn_league(league, season, cookie)
        except EspnError as e:
            # `source` tells the page this came from ESPN (vs. no proxy at all).
            self._json({"error": str(e), "source": "espn", "status": e.status}, e.status)
            return
        self._json(data)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets two servers share a port, which would defeat the
    # "port busy -> try the next one" logic.
    allow_reuse_address = os.name != "nt"


def make_server(
    port: int,
    *,
    manager: SyncManager | None,
    build_dir: Path = BUILD_DIR,
    data_dir: Path = DATA_DIR,
    tries: int = PORT_TRIES,
) -> LocalServer:
    handler = type(
        "BoundSiteHandler",
        (SiteHandler,),
        {"build_dir": build_dir, "data_dir": data_dir, "manager": manager},
    )
    last: OSError | None = None
    for p in range(port, port + tries):
        try:
            return LocalServer(("127.0.0.1", p), handler)
        except OSError as e:
            last = e
    raise SystemExit(f"Ports {port}-{port + tries - 1} are all busy ({last}). Try --port.")


# ---------- Web build ----------

WEB_INPUTS = ("package.json", "package-lock.json", "svelte.config.js")


def newest_input_mtime(web_dir: Path) -> float:
    paths = [web_dir / n for n in WEB_INPUTS] + list(web_dir.glob("vite.config.*"))
    newest = max((p.stat().st_mtime for p in paths if p.is_file()), default=0.0)
    skip = (web_dir / "static" / "data").resolve()
    for top in (web_dir / "src", web_dir / "static"):
        for root, dirs, files in os.walk(top):
            r = Path(root)
            dirs[:] = [d for d in dirs if (r / d).resolve() != skip]
            for name in files:
                try:
                    newest = max(newest, (r / name).stat().st_mtime)
                except OSError:
                    pass
    return newest


def web_build_stale(web_dir: Path = WEB_DIR) -> bool:
    index = web_dir / "build" / "index.html"
    if not index.is_file():
        return True
    return newest_input_mtime(web_dir) > index.stat().st_mtime


def deps_stale(web_dir: Path = WEB_DIR) -> bool:
    """True when node_modules is missing or older than package.json / package-lock.json.

    npm records each install in node_modules/.package-lock.json; a ``git pull`` that adds a
    dependency leaves the lockfile newer than that record, so the build would fail to
    resolve the new package without an install first.
    """
    stamp = web_dir / "node_modules" / ".package-lock.json"
    if not stamp.exists():
        return True
    manifests = [web_dir / n for n in ("package.json", "package-lock.json")]
    newest = max((m.stat().st_mtime for m in manifests if m.exists()), default=0.0)
    return newest > stamp.stat().st_mtime


def ensure_web_build(web_dir: Path = WEB_DIR) -> None:
    npm = shutil.which("npm")
    needs_install = deps_stale(web_dir)
    stale = web_build_stale(web_dir)
    if not (needs_install or stale):
        return
    if not npm:
        raise SystemExit("npm not found: install Node.js 22 (https://nodejs.org) and try again.")
    env = dict(os.environ)
    env.pop("BASE_PATH", None)  # served at the root locally
    if needs_install:
        print("Installing web dependencies (npm install)...", flush=True)
        _run([npm, "install"], web_dir, env)
        # npm may leave its record untouched when nothing changed; mark this install done.
        stamp = web_dir / "node_modules" / ".package-lock.json"
        if stamp.exists():
            os.utime(stamp)
    if stale or needs_install:
        print("Building the web app (npm run build, about a minute)...", flush=True)
        _run([npm, "run", "build"], web_dir, env)


def _run(cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
    code = subprocess.run(cmd, cwd=cwd, env=env).returncode
    if code != 0:
        shown = " ".join(["npm", *cmd[1:]])
        raise SystemExit(f"'{shown}' failed (exit {code}) in {cwd}.")


# ---------- Entry point ----------


def data_status(data_dir: Path = DATA_DIR) -> str:
    """'missing' (no build yet), 'outdated' (built by an older DATA_VERSION) or 'ok'."""
    meta = data_dir / "meta.json"
    if not meta.exists():
        return "missing"
    try:
        version = json.loads(meta.read_text(encoding="utf-8")).get("data_version", 1)
    except (OSError, ValueError):
        return "outdated"
    return "ok" if version >= DATA_VERSION else "outdated"


def up(
    port: int = 4173,
    open_browser: bool = True,
    build_web: bool = True,
    seasons: str | None = None,
) -> None:
    spec = seasons or default_seasons()
    manager = SyncManager(spec)

    status = data_status()
    if status != "ok":
        if status == "missing":
            print("No site data yet: downloading nflverse play-by-play and building the datasets.")
            print("The first run takes a while (about 200 MB, cached in data/raw).", flush=True)
        else:
            print("The site data is from an older version: rebuilding it (downloads are cached).")
        start = time.perf_counter()
        run_build(parse_seasons(spec))
        print(f"Data built in {time.perf_counter() - start:.0f}s.", flush=True)
        manager.record_manifest()

    if build_web:
        ensure_web_build()
    if not (BUILD_DIR / "index.html").is_file():
        raise SystemExit("web/build is missing: run without --no-build to build the web app.")

    server = make_server(port, manager=manager)
    actual = server.server_address[1]
    url = f"http://localhost:{actual}/"
    manager.start_scheduler()
    if actual != port:
        print(f"Port {port} is busy; using {actual}.")
    print(f"\nAny Given Stat is running at {url}")
    print(
        "Use the Sync button in the header to fetch new data. Press Ctrl+C to stop.\n", flush=True
    )
    if open_browser:
        threading.Timer(0.4, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        manager.stop()
        server.server_close()
