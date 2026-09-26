"""Weather observation pipeline."""

from __future__ import annotations

import json
from datetime import datetime
from logging import getLogger
from urllib.parse import urlencode
from urllib.request import urlopen

from openpasture.domain import Observation
from openpasture.domain.clock import utc_now
from openpasture.store.protocol import FarmStore

logger = getLogger(__name__)


class WeatherObservationPipeline:
    """Produces observations from forecast and historical weather APIs.

    Also fills the land report ``weather`` section when Alexandria is not
    configured (see ``openpasture.land.open_data``).
    """

    def __init__(self, store: FarmStore | None = None, base_url: str = "https://api.open-meteo.com/v1/forecast"):
        self.store = store
        self.base_url = base_url

    def fetch_section(
        self,
        longitude: float,
        latitude: float,
        *,
        history_days: int = 30,
        forecast_days: int = 7,
    ) -> dict[str, object]:
        """Return a contract-shaped weather section from Open-Meteo. Raises on failure."""

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "precipitation_probability_max,et0_fao_evapotranspiration",
            "past_days": max(0, min(int(history_days), 92)),
            "forecast_days": max(1, min(int(forecast_days), 16)),
            "timezone": "UTC",
        }
        with urlopen(f"{self.base_url}?{urlencode(params)}", timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        current = payload.get("current", {})
        daily = payload.get("daily", {})
        today = utc_now().date().isoformat()
        history: list[dict[str, object]] = []
        forecast: list[dict[str, object]] = []
        dates = daily.get("time", []) or []
        def pick(key: str, index: int) -> object:
            values = daily.get(key) or []
            return values[index] if index < len(values) else None

        for index, day in enumerate(dates):
            row = {
                "date": day,
                "precip_mm": pick("precipitation_sum", index),
                "temp_max_c": pick("temperature_2m_max", index),
                "temp_min_c": pick("temperature_2m_min", index),
            }
            if day < today:
                history.append({**row, "et0_mm": pick("et0_fao_evapotranspiration", index)})
            else:
                forecast.append({**row, "precip_probability": _fraction(pick("precipitation_probability_max", index))})
        humidity = current.get("relative_humidity_2m")
        return {
            "current": {
                "air_temp_c": current.get("temperature_2m"),
                "precip_mm_24h": history[-1]["precip_mm"] if history else current.get("precipitation"),
                "wind_kph": current.get("wind_speed_10m"),
                "relative_humidity": _fraction(humidity),
            },
            "history": history,
            "forecast": forecast,
            "sources": [
                {
                    "provider": "open-meteo",
                    "retrieved_at": utc_now().isoformat(),
                    "resolution": "~11 km",
                    "license": "CC BY 4.0",
                }
            ],
        }

    def collect(self, farm_id: str) -> list[Observation]:
        if self.store is None:
            raise ValueError("WeatherObservationPipeline.collect needs a store.")
        farm = self.store.get_farm(farm_id)
        if farm is None:
            raise ValueError(f"Farm '{farm_id}' does not exist.")
        if farm.location is None:
            return []

        params = {
            "latitude": farm.location.latitude,
            "longitude": farm.location.longitude,
            "current": "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": 3,
            "timezone": farm.timezone,
        }
        try:
            with urlopen(f"{self.base_url}?{urlencode(params)}", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            logger.warning("Weather collection failed for farm '%s'. Continuing without weather context.", farm_id)
            return []

        current = payload.get("current", {})
        daily = payload.get("daily", {})
        content = (
            "Weather outlook: "
            f"{current.get('temperature_2m', 'unknown')}C now, "
            f"{current.get('precipitation', 0)}mm precipitation, "
            f"{current.get('wind_speed_10m', 'unknown')} km/h wind."
        )

        observation = Observation(
            id=f"weather_{farm_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            farm_id=farm_id,
            source="weather",
            observed_at=datetime.utcnow(),
            content=content,
            metrics={
                "temperature_c": current.get("temperature_2m"),
                "precipitation_mm": current.get("precipitation"),
                "wind_kph": current.get("wind_speed_10m"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "forecast_dates": daily.get("time", []),
                "forecast_highs_c": daily.get("temperature_2m_max", []),
                "forecast_lows_c": daily.get("temperature_2m_min", []),
                "forecast_precip_mm": daily.get("precipitation_sum", []),
            },
            tags=["weather", "forecast"],
        )
        return [observation]


def _fraction(value: object) -> float | None:
    """Open-Meteo reports percentages; the land report contract uses 0-1."""

    if isinstance(value, (int, float)):
        return round(float(value) / 100.0, 3)
    return None
