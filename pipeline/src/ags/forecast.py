"""Kickoff weather forecasts for upcoming outdoor games (Open-Meteo, free, no key).

Backtests use nflverse's recorded game-time weather; live predictions need a forecast. If
the service can't be reached, games get no forecast and weather adds nothing to their line.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Home stadium coordinates (shared stadiums repeat). Neutral-site games get no forecast.
STADIUMS = {
    "ARI": (33.528, -112.263), "ATL": (33.755, -84.401), "BAL": (39.278, -76.623),
    "BUF": (42.774, -78.787), "CAR": (35.226, -80.853), "CHI": (41.862, -87.617),
    "CIN": (39.095, -84.516), "CLE": (41.506, -81.700), "DAL": (32.748, -97.093),
    "DEN": (39.744, -105.020), "DET": (42.340, -83.046), "GB": (44.501, -88.062),
    "HOU": (29.685, -95.411), "IND": (39.760, -86.164), "JAX": (30.324, -81.637),
    "KC": (39.049, -94.484), "LA": (33.953, -118.339), "LAC": (33.953, -118.339),
    "LV": (36.091, -115.184), "MIA": (25.958, -80.239), "MIN": (44.974, -93.258),
    "NE": (42.091, -71.264), "NO": (29.951, -90.081), "NYG": (40.814, -74.074),
    "NYJ": (40.814, -74.074), "PHI": (39.901, -75.168), "PIT": (40.447, -80.016),
    "SEA": (47.595, -122.332), "SF": (37.403, -121.970), "TB": (27.976, -82.503),
    "TEN": (36.166, -86.771), "WAS": (38.908, -76.864),
}  # fmt: skip


def kickoff_reading(payload: dict, gameday: str, gametime: str) -> tuple[float, float] | None:
    """(temp F, wind mph) at the kickoff hour from an Open-Meteo hourly payload (Eastern)."""
    hourly = payload.get("hourly") or {}
    stamp = f"{gameday}T{str(gametime)[:2]}:00"
    try:
        i = hourly["time"].index(stamp)
        return float(hourly["temperature_2m"][i]), float(hourly["wind_speed_10m"][i])
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def fetch_forecast(team: str, gameday: str, gametime: str) -> tuple[float, float] | None:
    if team not in STADIUMS or not gameday or not gametime:
        return None
    lat, lon = STADIUMS[team]
    query = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,wind_speed_10m",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "America/New_York",
            "start_date": gameday,
            "end_date": gameday,
        }
    )
    try:
        with urllib.request.urlopen(f"{FORECAST_URL}?{query}", timeout=20) as resp:
            return kickoff_reading(json.load(resp), gameday, gametime)
    except (OSError, ValueError) as e:
        print(f"no forecast for {team} {gameday}: {e}", file=sys.stderr)
        return None
