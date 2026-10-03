"""Sync: check nflverse for new files, rebuild the datasets when something changed.

Used by ``ags up`` (``serve.py``): the site's Sync button calls ``POST /api/sync`` and polls
``GET /api/status``; auto-sync runs on a schedule set from the same panel.

A sync is
1. a change check: HTTP HEAD on the files that change in-season (latest season play-by-play,
   injuries and snap counts, the schedule, the player directory), compared with the ETag /
   Last-Modified / Content-Length recorded in ``data/raw/sync_manifest.json`` after the last
   successful build. Nothing new = done in a couple of seconds.
2. otherwise a full ``ags build`` in a subprocess (it re-downloads the latest season), with its
   output streamed into the status log. The manifest is only updated when the build succeeds.

Auto-sync modes (``data/sync_settings.json``):
- ``off``.
- ``interval``: every ``interval_minutes``.
- ``gameday``: every ``interval_minutes`` inside NFL game windows (US Eastern, September to
  February only): Thursday and Monday 19:00-24:00, Sunday 12:00-24:00, Saturday 12:00-24:00
  from December 10 through January, and 12:00-24:00 on Thanksgiving and Christmas. Outside the
  windows it checks every 6 hours (and once when the next window opens).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shlex
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from pathlib import Path

from .cli import parse_seasons
from .config import (
    DEPTH_URL,
    INJURIES_URL,
    OUT_DIR,
    PBP_URL,
    PLAYERS_URL,
    RAW_DIR,
    REPO_ROOT,
    SCHEDULE_URL,
    SNAPS_URL,
)

AUTO_MODES = ("off", "interval", "gameday")
INTERVALS = (5, 10, 15, 30, 60, 180)
DEFAULT_SETTINGS = {"auto": "off", "interval_minutes": 15}
OFF_WINDOW_EVERY = dt.timedelta(hours=6)
SETTINGS_PATH = REPO_ROOT / "data" / "sync_settings.json"
MANIFEST_NAME = "sync_manifest.json"
# Test hook: run this shell-style command instead of the real build (e.g. a script that
# prints a few lines and exits), so a smoke test never rebuilds the real data.
SYNC_COMMAND_ENV = "AGS_SYNC_COMMAND"
LOG_KEEP = 200
LOG_TAIL = 20

Signature = dict[str, object]
HeadFn = Callable[[str], Signature]


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def iso(t: dt.datetime | None) -> str | None:
    return t.astimezone(dt.UTC).isoformat(timespec="seconds") if t else None


def parse_iso(s: object) -> dt.datetime | None:
    if not isinstance(s, str):
        return None
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


# ---------- Settings ----------


def validate_settings(update: object, current: dict | None = None) -> dict:
    """Merge a (partial) settings update into ``current``; ValueError if anything is invalid."""
    out = dict(current or DEFAULT_SETTINGS)
    if not isinstance(update, dict):
        raise ValueError("settings must be a JSON object")
    unknown = set(update) - {"auto", "interval_minutes"}
    if unknown:
        raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")
    if "auto" in update:
        if update["auto"] not in AUTO_MODES:
            raise ValueError(f"auto must be one of {', '.join(AUTO_MODES)}")
        out["auto"] = update["auto"]
    if "interval_minutes" in update:
        m = update["interval_minutes"]
        if isinstance(m, bool) or not isinstance(m, int) or m not in INTERVALS:
            raise ValueError(f"interval_minutes must be one of {', '.join(map(str, INTERVALS))}")
        out["interval_minutes"] = m
    return out


def load_settings(path: Path = SETTINGS_PATH) -> dict:
    try:
        return validate_settings(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


# ---------- Game windows (US Eastern) ----------


def _eastern_zone() -> dt.tzinfo | None:
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/New_York")
    except Exception:  # no tz database (Windows without tzdata)
        return None


_ET = _eastern_zone()


def _nth_sunday(year: int, month: int, n: int) -> dt.date:
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def to_eastern(t: dt.datetime) -> dt.datetime:
    """US Eastern wall time; without a tz database, a fixed UTC-4/-5 by the US DST rule."""
    if _ET is not None:
        return t.astimezone(_ET)
    u = t.astimezone(dt.UTC)
    dst_start = dt.datetime.combine(_nth_sunday(u.year, 3, 2), dt.time(7), dt.UTC)
    dst_end = dt.datetime.combine(_nth_sunday(u.year, 11, 1), dt.time(6), dt.UTC)
    hours = -4 if dst_start <= u < dst_end else -5
    return u.astimezone(dt.timezone(dt.timedelta(hours=hours)))


def thanksgiving(year: int) -> dt.date:
    first = dt.date(year, 11, 1)
    return first + dt.timedelta(days=(3 - first.weekday()) % 7 + 21)


def in_game_window(t: dt.datetime) -> bool:
    """True while NFL games are (typically) being played: see the module docstring."""
    et = to_eastern(t)
    d, hour = et.date(), et.hour
    if d.month not in (9, 10, 11, 12, 1, 2):
        return False
    if d == thanksgiving(d.year) or (d.month == 12 and d.day == 25):
        return hour >= 12
    weekday = d.weekday()  # Monday = 0
    if weekday == 6:
        return hour >= 12
    if weekday in (0, 3):
        return hour >= 19
    if weekday == 5:
        late = (d.month == 12 and d.day >= 10) or d.month == 1
        return late and hour >= 12
    return False


def next_window_start(now: dt.datetime, horizon_days: int = 8) -> dt.datetime | None:
    """First top of the hour after ``now`` inside a game window (windows open on the hour)."""
    t = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    for _ in range(horizon_days * 24):
        if in_game_window(t):
            return t
        t += dt.timedelta(hours=1)
    return None


def next_auto_at(settings: dict, last: dt.datetime | None, now: dt.datetime) -> dt.datetime | None:
    """When the next automatic sync is due (may be in the past = due now)."""
    mode = settings.get("auto", "off")
    if mode not in ("interval", "gameday"):
        return None
    base = last or now
    step = dt.timedelta(minutes=int(settings.get("interval_minutes", 15)))
    if mode == "interval" or in_game_window(now):
        return base + step
    due = base + OFF_WINDOW_EVERY
    opens = next_window_start(now)
    return min(due, opens) if opens else due


# ---------- Change detection ----------


def tracked_sources(season: int) -> list[tuple[str, str]]:
    """(file name in data/raw, URL) for the files that change during a season."""
    return [
        (f"play_by_play_{season}.parquet", PBP_URL.format(season=season)),
        ("games.csv", SCHEDULE_URL),
        (f"injuries_{season}.parquet", INJURIES_URL.format(season=season)),
        (f"snap_counts_{season}.parquet", SNAPS_URL.format(season=season)),
        (f"depth_charts_{season}.parquet", DEPTH_URL.format(season=season)),
        ("players.parquet", PLAYERS_URL),
    ]


def head(url: str, timeout: float = 20) -> Signature:
    """HEAD a URL (redirects followed: release assets live on githubusercontent.com).

    A 404 is a valid answer ("not published yet"), not an error.
    """
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "any-given-stat"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            h = resp.headers
            length = h.get("Content-Length")
            return {
                "etag": h.get("ETag"),
                "last_modified": h.get("Last-Modified"),
                "length": int(length) if length and length.isdigit() else None,
            }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"missing": True}
        raise


def same_file(prev: Signature, cur: Signature) -> bool:
    if prev.get("missing") or cur.get("missing"):
        return bool(prev.get("missing")) and bool(cur.get("missing"))
    if prev.get("length") is not None and cur.get("length") is not None:
        if prev["length"] != cur["length"]:
            return False
    if prev.get("etag") and cur.get("etag"):
        return prev["etag"] == cur["etag"]
    if prev.get("last_modified") and cur.get("last_modified"):
        return prev["last_modified"] == cur["last_modified"]
    return False


def _older_than_local(sig: Signature, local: Path) -> bool:
    """No manifest entry: the remote file is unchanged if our copy was downloaded after it."""
    if sig.get("missing"):
        return not local.exists()
    lm = sig.get("last_modified")
    if not isinstance(lm, str) or not local.exists():
        return False
    try:
        remote = parsedate_to_datetime(lm)
    except (TypeError, ValueError):
        return False
    return remote.timestamp() <= local.stat().st_mtime


def detect_changes(
    sources: list[tuple[str, str]],
    manifest: dict,
    raw_dir: Path = RAW_DIR,
    head_fn: HeadFn = head,
) -> tuple[list[str], dict[str, Signature], list[str]]:
    """Returns (changed file names, current signatures, errors). Unreachable files count as
    changed (we can't tell), and get no signature."""
    known = manifest.get("files", {}) if isinstance(manifest, dict) else {}
    changed: list[str] = []
    current: dict[str, Signature] = {}
    errors: list[str] = []
    for name, url in sources:
        try:
            sig = head_fn(url)
        except (OSError, ValueError) as e:
            errors.append(f"{name}: {e}")
            changed.append(name)
            continue
        current[name] = sig
        prev = known.get(name)
        unchanged = same_file(prev, sig) if prev else _older_than_local(sig, raw_dir / name)
        if not unchanged:
            changed.append(name)
    return changed, current, errors


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


# ---------- Build output -> progress ----------


def classify(line: str) -> tuple[str, str] | None:
    """Map a build log line to (state, stage text), or None to keep the current stage."""
    line = line.strip()
    if line.startswith("fetch "):
        url = line[6:].strip()
        return "downloading", f"Downloading {url.rstrip('/').rsplit('/', 1)[-1]}"
    if line.startswith("wrote "):
        path = line[6:].split(" (", 1)[0].strip().rstrip("/\\")
        return "building", f"Writing {Path(path).name}"
    if line.startswith("[time] "):
        label = line[7:].rsplit(":", 1)[0].strip()
        return "building", f"Built {label}"
    return None


def default_command(seasons: str) -> list[str]:
    override = os.environ.get(SYNC_COMMAND_ENV)
    if override:
        return shlex.split(override, posix=os.name != "nt")
    return [sys.executable, "-u", "-m", "ags.cli", "build", "--seasons", seasons]


# ---------- The manager ----------


class SyncManager:
    """Runs syncs in a background thread and keeps the state ``/api/status`` reports."""

    def __init__(
        self,
        seasons: str,
        *,
        raw_dir: Path = RAW_DIR,
        out_dir: Path = OUT_DIR,
        settings_path: Path = SETTINGS_PATH,
        manifest_path: Path | None = None,
        command: list[str] | None = None,
        head_fn: HeadFn = head,
        clock: Callable[[], dt.datetime] = utcnow,
    ) -> None:
        self.seasons = seasons
        self.latest = max(parse_seasons(seasons))
        self.raw_dir = raw_dir
        self.out_dir = out_dir
        self.settings_path = settings_path
        self.manifest_path = manifest_path or raw_dir / MANIFEST_NAME
        self.command = command or default_command(seasons)
        self.head_fn = head_fn
        self.clock = clock
        self.settings = load_settings(settings_path)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._log: deque[str] = deque(maxlen=LOG_KEEP)
        self.started = clock()
        self.state = "idle"
        self.stage = ""
        self.message = ""
        self.trigger: str | None = None
        self.started_at: dt.datetime | None = None
        self.finished_at: dt.datetime | None = None
        self.last_result: str | None = None
        self.last_success_at = parse_iso(load_manifest(self.manifest_path).get("last_success_at"))

    # --- status / settings ---

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def next_auto(self) -> dt.datetime | None:
        bases = [t for t in (self.finished_at, self.last_success_at) if t]
        last = max(bases) if bases else self.started
        return next_auto_at(self.settings, last, self.clock())

    def status(self) -> dict:
        with self._lock:
            nxt = None if self.running else self.next_auto()
            return {
                "available": True,
                "state": self.state,
                "stage": self.stage,
                "trigger": self.trigger,
                "started_at": iso(self.started_at),
                "finished_at": iso(self.finished_at),
                "last_success_at": iso(self.last_success_at),
                "last_result": self.last_result,
                "message": self.message,
                "log_tail": list(self._log)[-LOG_TAIL:],
                "settings": dict(self.settings),
                "next_auto_at": iso(nxt),
                "seasons": self.seasons,
            }

    def update_settings(self, update: object) -> dict:
        with self._lock:
            self.settings = validate_settings(update, self.settings)
            save_settings(self.settings, self.settings_path)
            return dict(self.settings)

    # --- running ---

    def start(self, force: bool = False, trigger: str = "manual") -> bool:
        """Start a sync in the background; False if one is already running."""
        with self._lock:
            if self.running:
                return False
            self.state, self.stage, self.message = "checking", "Checking nflverse for new data", ""
            self.trigger = trigger
            self.started_at, self.finished_at = self.clock(), None
            self._log.clear()
            self._thread = threading.Thread(
                target=self._run, args=(force,), name="ags-sync", daemon=True
            )
            self._thread.start()
            return True

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def _set(self, **fields: object) -> None:
        with self._lock:
            for k, v in fields.items():
                setattr(self, k, v)

    def _append(self, line: str) -> None:
        with self._lock:
            self._log.append(line)
            mapped = classify(line)
            if mapped:
                self.state, self.stage = mapped

    def _finish(self, result: str, message: str) -> None:
        with self._lock:
            now = self.clock()
            self.state = "error" if result == "error" else "idle"
            self.stage = ""
            self.last_result = result
            self.message = message
            self.finished_at = now
            if result != "error":
                self.last_success_at = now

    def _run(self, force: bool) -> None:
        try:
            self._sync(force)
        except Exception as e:  # never leave the state stuck on "building"
            self._append(f"error: {e!r}")
            self._finish("error", f"Sync failed: {e}")

    def _sync(self, force: bool) -> None:
        manifest = load_manifest(self.manifest_path)
        sources = tracked_sources(self.latest)
        changed, current, errors = detect_changes(sources, manifest, self.raw_dir, self.head_fn)
        for e in errors:
            self._append(f"check failed: {e}")
        if len(errors) == len(sources) and not force:
            self._finish("error", "Couldn't reach nflverse. Check your internet connection.")
            return
        have_data = (self.out_dir / "meta.json").exists()
        if not changed and have_data and not force:
            manifest["last_success_at"] = iso(self.clock())
            save_manifest(manifest, self.manifest_path)
            self._append(f"no changes in {len(sources)} files")
            self._finish("up_to_date", "Already up to date")
            return

        self._append("changed: " + (", ".join(changed) or "none (forced rebuild)"))
        self._set(state="building", stage="Starting the build")
        code = self._run_command()
        if self._stop.is_set():
            self._finish("error", "Sync stopped")
            return
        if code != 0:
            last = next((ln for ln in reversed(self._log) if ln.strip()), "")
            self._finish("error", f"Build failed (exit {code}). {last}".strip())
            return
        files = dict(manifest.get("files", {}))
        files.update(current)
        for name in errors:  # unknown remote state: re-check next time
            files.pop(name.split(":", 1)[0], None)
        now = iso(self.clock())
        save_manifest(
            {"files": files, "updated_at": now, "last_success_at": now, "seasons": self.seasons},
            self.manifest_path,
        )
        what = ", ".join(changed) if changed else "forced rebuild"
        self._finish("updated", f"Data updated ({what})")

    def _run_command(self) -> int:
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        self._append("$ " + " ".join(self.command))
        try:
            proc = subprocess.Popen(
                self.command,
                cwd=REPO_ROOT / "pipeline",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
        except OSError as e:
            self._append(f"could not start the build: {e}")
            return 127
        self._proc = proc
        assert proc.stdout is not None
        for line in proc.stdout:
            self._append(line.rstrip())
        code = proc.wait()
        self._proc = None
        return code

    def record_manifest(self) -> None:
        """After a build outside the manager (``ags up``'s first run): remember what we have."""
        try:
            _, current, _ = detect_changes(
                tracked_sources(self.latest), {}, self.raw_dir, self.head_fn
            )
        except Exception:
            return
        now = self.clock()
        save_manifest(
            {"files": current, "updated_at": iso(now), "last_success_at": iso(now)},
            self.manifest_path,
        )
        self.last_success_at = now

    # --- auto-sync ---

    def tick(self) -> bool:
        """Start an automatic sync if one is due. Returns whether it started one."""
        if self.running:
            return False
        due = self.next_auto()
        if due is None or due > self.clock():
            return False
        return self.start(force=False, trigger="auto")

    def start_scheduler(self, every: float = 15.0) -> None:
        def loop() -> None:
            while not self._stop.wait(every):
                try:
                    self.tick()
                except Exception as e:  # keep the scheduler alive
                    print(f"auto-sync: {e}", file=sys.stderr)

        threading.Thread(target=loop, name="ags-sync-scheduler", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
