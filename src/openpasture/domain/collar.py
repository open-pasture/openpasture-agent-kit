"""Collar primitives: boundary commands going down, positions and acks coming up.

Field names follow ``docs/contracts.md``. The collar gateway translates these to
and from the OpenCollar wire protocol, which is narrower (one ring, no
exclusions, no transitions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

from .clock import iso_or_none, parse_datetime, utc_now

BoundaryTransitionType = Literal["open_then_close", "immediate"]
BoundaryCommandStatus = Literal["pending", "sent", "active", "rejected", "failed"]
AckStatus = Literal["received", "applied", "rejected"]

TRANSITION_TYPES: tuple[str, ...] = ("open_then_close", "immediate")
ACK_STATUSES: tuple[str, ...] = ("received", "applied", "rejected")
DEFAULT_CLOSE_AFTER_MINUTES = 90


@dataclass(slots=True)
class BoundaryTransition:
    """How the herd gets from the old boundary to the new one."""

    type: BoundaryTransitionType = "immediate"
    corridor: dict[str, object] | None = None
    close_after_minutes: int | None = None

    def __post_init__(self) -> None:
        if self.type not in TRANSITION_TYPES:
            raise ValueError(f"Unsupported boundary transition: {self.type}")
        if self.type == "open_then_close" and self.close_after_minutes is None:
            self.close_after_minutes = DEFAULT_CLOSE_AFTER_MINUTES

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"type": self.type}
        if self.type == "open_then_close":
            payload["corridor"] = self.corridor
            payload["close_after_minutes"] = self.close_after_minutes
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, object] | None) -> "BoundaryTransition":
        if not data:
            return cls()
        corridor = data.get("corridor")
        minutes = data.get("close_after_minutes")
        return cls(
            type=str(data.get("type") or "immediate"),  # type: ignore[arg-type]
            corridor=dict(corridor) if isinstance(corridor, Mapping) else None,
            close_after_minutes=int(minutes) if isinstance(minutes, (int, float)) else None,
        )


@dataclass(slots=True)
class BoundaryCommand:
    """A versioned boundary for one herd's collars."""

    command_id: str
    decision_id: str | None
    farm_id: str
    herd_id: str
    collar_ids: list[str]
    version: int
    effective_at: datetime
    boundary: dict[str, object]
    exclusions: list[dict[str, object]] = field(default_factory=list)
    transition: BoundaryTransition = field(default_factory=BoundaryTransition)
    # The last wire version this command uses. An open_then_close transition is
    # two wire boundaries, so it uses ``version`` and ``version + 1``.
    final_version: int | None = None
    status: BoundaryCommandStatus = "pending"
    activation_threshold: float = 1.0
    land_unit_id: str | None = None
    activated_at: datetime | None = None
    sent_at: datetime | None = None
    gateway: str = ""
    error: str | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.final_version is None:
            self.final_version = self.version

    @property
    def versions(self) -> list[int]:
        return list(range(self.version, int(self.final_version or self.version) + 1))

    def to_dict(self) -> dict[str, object]:
        return {
            "command_id": self.command_id,
            "decision_id": self.decision_id,
            "farm_id": self.farm_id,
            "herd_id": self.herd_id,
            "collar_ids": list(self.collar_ids),
            "version": self.version,
            "effective_at": self.effective_at.isoformat(),
            "boundary": self.boundary,
            "exclusions": list(self.exclusions),
            "transition": self.transition.to_dict(),
            "final_version": self.final_version,
            "status": self.status,
            "activation_threshold": self.activation_threshold,
            "land_unit_id": self.land_unit_id,
            "activated_at": iso_or_none(self.activated_at),
            "sent_at": iso_or_none(self.sent_at),
            "gateway": self.gateway,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "BoundaryCommand":
        final_version = data.get("final_version")
        threshold = data.get("activation_threshold")
        return cls(
            command_id=str(data["command_id"]),
            decision_id=str(data["decision_id"]) if data.get("decision_id") else None,
            farm_id=str(data["farm_id"]),
            herd_id=str(data["herd_id"]),
            collar_ids=[str(item) for item in data.get("collar_ids") or []],
            version=int(data["version"]),  # type: ignore[arg-type]
            effective_at=parse_datetime(data.get("effective_at")) or utc_now(),
            boundary=dict(data.get("boundary") or {}),  # type: ignore[arg-type]
            exclusions=[dict(item) for item in data.get("exclusions") or [] if isinstance(item, Mapping)],
            transition=BoundaryTransition.from_dict(
                data.get("transition") if isinstance(data.get("transition"), Mapping) else None
            ),
            final_version=int(final_version) if isinstance(final_version, (int, float)) else None,
            status=str(data.get("status") or "pending"),  # type: ignore[arg-type]
            activation_threshold=float(threshold) if isinstance(threshold, (int, float)) else 1.0,
            land_unit_id=str(data["land_unit_id"]) if data.get("land_unit_id") else None,
            activated_at=parse_datetime(data.get("activated_at")),
            sent_at=parse_datetime(data.get("sent_at")),
            gateway=str(data.get("gateway") or ""),
            error=str(data["error"]) if data.get("error") else None,
            created_at=parse_datetime(data.get("created_at")) or utc_now(),
        )


@dataclass(slots=True)
class BoundaryAck:
    """One collar's report about one boundary version."""

    command_id: str
    collar_id: str
    version: int
    status: AckStatus
    received_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ACK_STATUSES:
            raise ValueError(f"Unsupported acknowledgement status: {self.status}")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "command_id": self.command_id,
            "collar_id": self.collar_id,
            "version": self.version,
            "status": self.status,
            "received_at": self.received_at.isoformat(),
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "BoundaryAck":
        received_at = parse_datetime(data.get("received_at") or data.get("at")) or utc_now()
        reason = data.get("reason")
        return cls(
            command_id=str(data["command_id"]),
            collar_id=str(data["collar_id"]),
            version=int(data["version"]),  # type: ignore[arg-type]
            status=str(data["status"]),  # type: ignore[arg-type]
            received_at=received_at,
            reason=str(reason) if reason else None,
        )


@dataclass(slots=True)
class PositionFix:
    """One GNSS fix from one collar."""

    collar_id: str
    at: datetime
    point: list[float]
    accuracy_meters: float | None = None
    activity: str | None = None
    sats: int | None = None
    farm_id: str | None = None
    herd_id: str | None = None
    land_unit_id: str | None = None
    boundary_version: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "collar_id": self.collar_id,
            "at": self.at.isoformat(),
            "point": list(self.point),
            "accuracy_meters": self.accuracy_meters,
            "activity": self.activity,
            "sats": self.sats,
            "farm_id": self.farm_id,
            "herd_id": self.herd_id,
            "land_unit_id": self.land_unit_id,
            "boundary_version": self.boundary_version,
        }


@dataclass(slots=True)
class CueEvent:
    """A sound or stimulus the collar gave an animal at the line."""

    collar_id: str
    at: datetime
    type: str = "audio"
    point: list[float] | None = None
    level: int | None = None
    # Negative means past the line; positive means short of it.
    margin_meters: float | None = None
    farm_id: str | None = None
    herd_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "collar_id": self.collar_id,
            "at": self.at.isoformat(),
            "type": self.type,
            "point": list(self.point) if self.point else None,
            "level": self.level,
            "margin_meters": self.margin_meters,
            "farm_id": self.farm_id,
            "herd_id": self.herd_id,
        }


@dataclass(slots=True)
class PositionReport:
    """What one collar sends between commands."""

    collar_id: str
    fixes: list[PositionFix] = field(default_factory=list)
    cues: list[CueEvent] = field(default_factory=list)
    battery: float | None = None
    boundary_version: int | None = None


@dataclass(slots=True)
class Collar:
    """A collar and the herd it belongs to."""

    collar_id: str
    farm_id: str
    herd_id: str | None = None
    animal_id: str | None = None
    battery: float | None = None
    boundary_version: int | None = None
    last_seen_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "collar_id": self.collar_id,
            "farm_id": self.farm_id,
            "herd_id": self.herd_id,
            "animal_id": self.animal_id,
            "battery": self.battery,
            "boundary_version": self.boundary_version,
            "last_seen_at": iso_or_none(self.last_seen_at),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Collar":
        battery = data.get("battery")
        version = data.get("boundary_version")
        return cls(
            collar_id=str(data["collar_id"]),
            farm_id=str(data["farm_id"]),
            herd_id=str(data["herd_id"]) if data.get("herd_id") else None,
            animal_id=str(data["animal_id"]) if data.get("animal_id") else None,
            battery=float(battery) if isinstance(battery, (int, float)) else None,
            boundary_version=int(version) if isinstance(version, (int, float)) else None,
            last_seen_at=parse_datetime(data.get("last_seen_at")),
            created_at=parse_datetime(data.get("created_at")) or utc_now(),
        )


@dataclass(slots=True)
class CollarSummary:
    """Collar data for one herd rolled up over one window. Kept indefinitely."""

    summary_id: str
    farm_id: str
    herd_id: str
    window_starts_at: datetime
    window_ends_at: datetime
    collar_ids: list[str] = field(default_factory=list)
    fix_count: int = 0
    cue_count: int = 0
    land_unit_fix_counts: dict[str, int] = field(default_factory=dict)
    dominant_land_unit_id: str | None = None
    # Share of fixes inside the boundary the herd was supposed to hold.
    share_inside_boundary: float | None = None
    boundary_version: int | None = None
    activity_counts: dict[str, int] = field(default_factory=dict)
    last_fix_at: datetime | None = None
    centroid: list[float] | None = None
    battery_by_collar: dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "summary_id": self.summary_id,
            "farm_id": self.farm_id,
            "herd_id": self.herd_id,
            "window_starts_at": self.window_starts_at.isoformat(),
            "window_ends_at": self.window_ends_at.isoformat(),
            "collar_ids": list(self.collar_ids),
            "fix_count": self.fix_count,
            "cue_count": self.cue_count,
            "land_unit_fix_counts": dict(self.land_unit_fix_counts),
            "dominant_land_unit_id": self.dominant_land_unit_id,
            "share_inside_boundary": self.share_inside_boundary,
            "boundary_version": self.boundary_version,
            "activity_counts": dict(self.activity_counts),
            "last_fix_at": iso_or_none(self.last_fix_at),
            "centroid": list(self.centroid) if self.centroid else None,
            "battery_by_collar": dict(self.battery_by_collar),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "CollarSummary":
        share = data.get("share_inside_boundary")
        version = data.get("boundary_version")
        centroid = data.get("centroid")
        return cls(
            summary_id=str(data["summary_id"]),
            farm_id=str(data["farm_id"]),
            herd_id=str(data["herd_id"]),
            window_starts_at=parse_datetime(data.get("window_starts_at")) or utc_now(),
            window_ends_at=parse_datetime(data.get("window_ends_at")) or utc_now(),
            collar_ids=[str(item) for item in data.get("collar_ids") or []],
            fix_count=int(data.get("fix_count") or 0),  # type: ignore[arg-type]
            cue_count=int(data.get("cue_count") or 0),  # type: ignore[arg-type]
            land_unit_fix_counts={
                str(key): int(value)  # type: ignore[arg-type]
                for key, value in (data.get("land_unit_fix_counts") or {}).items()  # type: ignore[union-attr]
            },
            dominant_land_unit_id=str(data["dominant_land_unit_id"]) if data.get("dominant_land_unit_id") else None,
            share_inside_boundary=float(share) if isinstance(share, (int, float)) else None,
            boundary_version=int(version) if isinstance(version, (int, float)) else None,
            activity_counts={
                str(key): int(value)  # type: ignore[arg-type]
                for key, value in (data.get("activity_counts") or {}).items()  # type: ignore[union-attr]
            },
            last_fix_at=parse_datetime(data.get("last_fix_at")),
            centroid=[float(item) for item in centroid] if isinstance(centroid, list) else None,
            battery_by_collar={
                str(key): float(value)  # type: ignore[arg-type]
                for key, value in (data.get("battery_by_collar") or {}).items()  # type: ignore[union-attr]
            },
            created_at=parse_datetime(data.get("created_at")) or utc_now(),
        )


@dataclass(frozen=True, slots=True)
class BoundaryActivation:
    """Which collars confirmed a command, and whether that is enough."""

    command_id: str
    active: bool
    threshold: float
    confirmed_share: float
    confirmed_collar_ids: list[str]
    unconfirmed_collar_ids: list[str]
    rejected: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "command_id": self.command_id,
            "active": self.active,
            "threshold": self.threshold,
            "confirmed_share": self.confirmed_share,
            "confirmed_collar_ids": list(self.confirmed_collar_ids),
            "unconfirmed_collar_ids": list(self.unconfirmed_collar_ids),
            "rejected": dict(self.rejected),
        }


def boundary_activation(command: BoundaryCommand, acks: list[BoundaryAck]) -> BoundaryActivation:
    """Decide whether a command is active from its acknowledgements.

    A collar confirms the command once it reports ``applied`` for any of the
    command's wire versions and has not rejected any of them. ``received`` alone
    does not count: the collar has stored the boundary but is not enforcing it.
    The command is active once the confirmed share of the herd's collars reaches
    the activation threshold. A herd with no collars can never be active.
    """

    versions = set(command.versions)
    applied: set[str] = set()
    rejected: dict[str, str] = {}
    for ack in acks:
        if ack.command_id != command.command_id or ack.version not in versions:
            continue
        if ack.status == "rejected":
            rejected[ack.collar_id] = ack.reason or "Collar rejected the boundary."
        elif ack.status == "applied":
            applied.add(ack.collar_id)
    confirmed = [collar_id for collar_id in command.collar_ids if collar_id in applied and collar_id not in rejected]
    unconfirmed = [collar_id for collar_id in command.collar_ids if collar_id not in confirmed]
    total = len(command.collar_ids)
    share = round(len(confirmed) / total, 4) if total else 0.0
    return BoundaryActivation(
        command_id=command.command_id,
        active=bool(total) and share + 1e-9 >= command.activation_threshold,
        threshold=command.activation_threshold,
        confirmed_share=share,
        confirmed_collar_ids=confirmed,
        unconfirmed_collar_ids=unconfirmed,
        rejected=rejected,
    )
