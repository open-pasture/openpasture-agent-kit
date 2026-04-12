"""Weather observation pipeline."""

from __future__ import annotations

import json
from datetime import datetime
from logging import getLogger
from urllib.parse import urlencode
from urllib.request import urlopen

from openpasture.domain import Observation
from openpasture.store.protocol import FarmStore

logger = getLogger(__name__)


class WeatherObservationPipeline:
    """Produces observations from forecast and historical weather APIs."""

    def __init__(self, store: FarmStore, base_url: str = "https://api.open-meteo.com/v1/forecast"):
        self.store = store
        self.base_url = base_url

    def collect(self, farm_id: str) -> list[Observation]:
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
