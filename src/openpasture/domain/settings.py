"""Per-farm and per-herd decision settings: autonomy and the decision window.

A farm-level row (``herd_id`` None) sets defaults for every herd. A herd-level
row overrides only the fields it sets. Anything left unset falls back to the
kit defaults below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from .clock import parse_datetime, utc_now
from .decision import AUTONOMY_MODES, Autonomy

DEFAULT_AUTONOMY: Autonomy = "propose"
DEFAULT_HOLD_MINUTES = 120
DEFAULT_WINDOW_HOURS = 24
DEFAULT_WINDOW_START_TIME = "06:00"
# Share of a herd's collars that must confirm a boundary before it is active.
DEFAULT_ACTIVATION_THRESHOLD = 1.0


@dataclass(slots=True)
class DecisionSettings:
    """Stored settings for a farm (herd_id None) or one herd."""

    farm_id: str
    herd_id: str | None = None
    autonomy: Autonomy | None = None
    # apply_unless_stopped: send at this local "HH:MM" unless stopped first...
    send_time: str | None = None
    # ...or, when no send_time is set, this many minutes after the decision.
    hold_minutes: int | None = None
    window_hours: int | None = None
    window_start_time: str | None = None
    activation_threshold: float | None = None
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.autonomy is not None and self.autonomy not in AUTONOMY_MODES:
            raise ValueError(
                f"Unsupported autonomy mode '{self.autonomy}'. Use one of: {', '.join(AUTONOMY_MODES)}."
            )
        for key in ("send_time", "window_start_time"):
            value = getattr(self, key)
            if value is not None:
                parse_clock_time(value)
        if self.window_hours is not None and not 1 <= self.window_hours <= 24 * 14:
            raise ValueError("window_hours must be between 1 and 336.")
        if self.activation_threshold is not None and not 0 < self.activation_threshold <= 1:
            raise ValueError("activation_threshold must be greater than 0 and at most 1.")

    def to_dict(self) -> dict[str, object]:
        return {
            "farm_id": self.farm_id,
            "herd_id": self.herd_id,
            "autonomy": self.autonomy,
            "send_time": self.send_time,
            "hold_minutes": self.hold_minutes,
            "window_hours": self.window_hours,
            "window_start_time": self.window_start_time,
            "activation_threshold": self.activation_threshold,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DecisionSettings":
        def _int(value: object) -> int | None:
            return int(value) if isinstance(value, (int, float)) else None

        herd_id = data.get("herd_id")
        return cls(
            farm_id=str(data["farm_id"]),
            herd_id=str(herd_id) if herd_id else None,
            autonomy=data.get("autonomy") or None,  # type: ignore[arg-type]
            send_time=str(data["send_time"]) if data.get("send_time") else None,
            hold_minutes=_int(data.get("hold_minutes")),
            window_hours=_int(data.get("window_hours")),
            window_start_time=str(data["window_start_time"]) if data.get("window_start_time") else None,
            activation_threshold=(
                float(data["activation_threshold"])
                if isinstance(data.get("activation_threshold"), (int, float))
                else None
            ),
            updated_at=parse_datetime(data.get("updated_at")) or utc_now(),
        )


@dataclass(frozen=True, slots=True)
class EffectiveDecisionSettings:
    """Resolved settings for one herd, with the level each value came from."""

    farm_id: str
    herd_id: str | None
    autonomy: Autonomy
    send_time: str | None
    hold_minutes: int
    window_hours: int
    window_start_time: str
    activation_threshold: float
    autonomy_level: str

    def to_dict(self) -> dict[str, object]:
        return {
            "farm_id": self.farm_id,
            "herd_id": self.herd_id,
            "autonomy": self.autonomy,
            "autonomy_level": self.autonomy_level,
            "send_time": self.send_time,
            "hold_minutes": self.hold_minutes,
            "window_hours": self.window_hours,
            "window_start_time": self.window_start_time,
            "activation_threshold": self.activation_threshold,
        }


def resolve_decision_settings(
    farm_id: str,
    herd_id: str | None,
    farm_settings: DecisionSettings | None,
    herd_settings: DecisionSettings | None,
    *,
    default_window_start_time: str = DEFAULT_WINDOW_START_TIME,
    default_activation_threshold: float = DEFAULT_ACTIVATION_THRESHOLD,
) -> EffectiveDecisionSettings:
    """Merge herd over farm over kit defaults."""

    def pick(name: str, default: object) -> object:
        for layer in (herd_settings, farm_settings):
            if layer is not None and getattr(layer, name) is not None:
                return getattr(layer, name)
        return default

    if herd_settings is not None and herd_settings.autonomy is not None:
        autonomy_level = "herd"
    elif farm_settings is not None and farm_settings.autonomy is not None:
        autonomy_level = "farm"
    else:
        autonomy_level = "default"

    return EffectiveDecisionSettings(
        farm_id=farm_id,
        herd_id=herd_id,
        autonomy=pick("autonomy", DEFAULT_AUTONOMY),  # type: ignore[arg-type]
        send_time=pick("send_time", None),  # type: ignore[arg-type]
        hold_minutes=int(pick("hold_minutes", DEFAULT_HOLD_MINUTES)),  # type: ignore[arg-type]
        window_hours=int(pick("window_hours", DEFAULT_WINDOW_HOURS)),  # type: ignore[arg-type]
        window_start_time=str(pick("window_start_time", default_window_start_time)),
        activation_threshold=float(pick("activation_threshold", default_activation_threshold)),  # type: ignore[arg-type]
        autonomy_level=autonomy_level,
    )


def parse_clock_time(value: str) -> tuple[int, int]:
    """Parse an ``HH:MM`` wall-clock time."""

    try:
        hour_text, minute_text = value.strip().split(":", maxsplit=1)
        hour, minute = int(hour_text), int(minute_text)
    except ValueError as exc:
        raise ValueError(f"'{value}' must use HH:MM format.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"'{value}' must be a valid 24-hour clock time.")
    return hour, minute
