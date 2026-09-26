"""Translation between the engine's collar contracts and the OpenCollar V0 wire.

The engine's ``BoundaryCommand`` carries exclusions and transitions. V0 collars
hold one ring of 3 to 64 vertices and a version, and nothing else (see
``opencollar/protocol/README.md``). So the gateway:

- cuts exclusions out of the ring where the shape allows, else refuses,
- expands ``open_then_close`` into two wire boundaries: version N is the old
  paddock, corridor, and new paddock merged; version N+1 is the new paddock
  alone, effective ``close_after_minutes`` later,
- checks the vertex budget and that the ring does not cross itself.

Inbound, it maps wire acks (``at``) and position reports (``accuracy_m``,
``margin_m``) onto the contract field names.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping

from openpasture.collars.rings import RingOperationError, clean_ring, ring_is_simple, subtract_ring, union_rings
from openpasture.domain import BoundaryAck, BoundaryCommand, CueEvent, PositionFix, PositionReport
from openpasture.domain.clock import as_utc, parse_datetime, utc_now

MIN_VERTICES = 3
MAX_VERTICES = 64  # firmware GEOFENCE_MAX_VERTICES


class BoundaryTranslationError(ValueError):
    """The command cannot be expressed as V0 collar boundaries."""


def outer_ring(geometry: Mapping[str, object], *, label: str = "boundary") -> list[list[float]]:
    """The single outer ring of a Polygon (or one-part MultiPolygon)."""

    if geometry.get("type") == "Feature":
        inner = geometry.get("geometry")
        if not isinstance(inner, Mapping):
            raise BoundaryTranslationError(f"The {label} Feature has no geometry.")
        geometry = inner
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        if len(coordinates) != 1:
            raise BoundaryTranslationError(f"The {label} has {len(coordinates)} separate parts. A collar holds one ring.")
        geometry_type, coordinates = "Polygon", coordinates[0]
    if geometry_type != "Polygon" or not isinstance(coordinates, list) or not coordinates:
        raise BoundaryTranslationError(f"The {label} must be a GeoJSON Polygon.")
    if len(coordinates) > 1:
        raise BoundaryTranslationError(
            f"The {label} has holes. V0 collars cannot enforce holes; send them as exclusions that touch the edge."
        )
    ring = coordinates[0]
    if not isinstance(ring, list):
        raise BoundaryTranslationError(f"The {label} ring is malformed.")
    return [[float(point[0]), float(point[1])] for point in ring]


def validate_ring(ring: list[list[float]], *, label: str = "boundary") -> list[list[float]]:
    """Return the ring unclosed, or raise with a farmer-readable reason."""

    points = [[round(x, 7), round(y, 7)] for x, y in clean_ring(ring)]
    if len(points) < MIN_VERTICES:
        raise BoundaryTranslationError(f"The {label} needs at least {MIN_VERTICES} corners.")
    if len(points) > MAX_VERTICES:
        raise BoundaryTranslationError(
            f"The {label} has {len(points)} corners. V0 collars hold at most {MAX_VERTICES}; simplify the shape."
        )
    for longitude, latitude in points:
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise BoundaryTranslationError(f"The {label} has a coordinate out of range.")
    if not ring_is_simple(points):
        raise BoundaryTranslationError(f"The {label} crosses itself.")
    return points


def _apply_exclusions(ring: list[list[float]], exclusions: list[dict[str, object]]) -> list[list[float]]:
    for index, exclusion in enumerate(exclusions, start=1):
        exclusion_ring = outer_ring(exclusion, label=f"exclusion {index}")
        try:
            cut = subtract_ring(ring, exclusion_ring)
        except RingOperationError as exc:
            raise BoundaryTranslationError(f"Exclusion {index} cannot be cut out of the boundary: {exc}") from exc
        if cut is not None:
            ring = cut
    return ring


def _wire_time(value: datetime) -> str:
    return as_utc(value).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def to_wire_boundaries(
    command: BoundaryCommand,
    previous_boundary: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    """Expand one command into the wire boundaries a V0 collar understands."""

    final_ring = validate_ring(_apply_exclusions(outer_ring(command.boundary), command.exclusions))
    first_effective = command.effective_at
    boundaries: list[dict[str, object]] = []

    transition = command.transition
    if transition.type == "open_then_close" and previous_boundary is not None:
        rings = [outer_ring(previous_boundary, label="previous boundary")]
        if transition.corridor:
            rings.append(outer_ring(transition.corridor, label="corridor"))
        rings.append(outer_ring(command.boundary))
        try:
            combined = union_rings(rings)
        except RingOperationError as exc:
            raise BoundaryTranslationError(
                f"The old paddock, corridor, and new paddock do not form one area: {exc} "
                "Draw a corridor that touches both, or send the move as immediate."
            ) from exc
        combined = validate_ring(_apply_exclusions(combined, command.exclusions), label="transition area")
        close_after = timedelta(minutes=int(transition.close_after_minutes or 0))
        boundaries.append(
            {
                "command_id": command.command_id,
                "version": command.version,
                "effective_at": _wire_time(first_effective),
                "boundary": combined,
            }
        )
        boundaries.append(
            {
                "command_id": command.command_id,
                "version": command.version + 1,
                "effective_at": _wire_time(first_effective + close_after),
                "boundary": final_ring,
            }
        )
        return boundaries

    boundaries.append(
        {
            "command_id": command.command_id,
            "version": command.version,
            "effective_at": _wire_time(first_effective),
            "boundary": final_ring,
        }
    )
    return boundaries


def parse_wire_ack(payload: Mapping[str, object], *, collar_id: str | None = None) -> BoundaryAck:
    """Map a wire ack (``at``) or a contract ack (``received_at``) to a BoundaryAck."""

    resolved_collar = payload.get("collar_id") or collar_id
    if not resolved_collar:
        raise ValueError("An acknowledgement needs a collar_id.")
    for key in ("command_id", "version", "status"):
        if payload.get(key) in (None, ""):
            raise ValueError(f"An acknowledgement needs '{key}'.")
    reason = payload.get("reason")
    return BoundaryAck(
        command_id=str(payload["command_id"]),
        collar_id=str(resolved_collar),
        version=int(payload["version"]),  # type: ignore[arg-type]
        status=str(payload["status"]),  # type: ignore[arg-type]
        received_at=parse_datetime(payload.get("received_at") or payload.get("at")) or utc_now(),
        reason=str(reason) if reason else None,
    )


def _point(value: object) -> list[float] | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [float(value[0]), float(value[1])]
    if isinstance(value, Mapping):
        if value.get("type") == "Point":
            return _point(value.get("coordinates"))
        if "longitude" in value and "latitude" in value:
            return [float(value["longitude"]), float(value["latitude"])]  # type: ignore[arg-type]
    return None


def _number(payload: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def parse_position_report(payload: Mapping[str, object]) -> PositionReport:
    """Map a wire or contract position report to a PositionReport."""

    collar_id = payload.get("collar_id")
    if not isinstance(collar_id, str) or not collar_id.strip():
        raise ValueError("A position report needs a collar_id.")
    boundary_version = payload.get("boundary_version")
    version = int(boundary_version) if isinstance(boundary_version, (int, float)) else None

    fixes: list[PositionFix] = []
    for raw in payload.get("fixes") or []:  # type: ignore[union-attr]
        if not isinstance(raw, Mapping):
            continue
        at = parse_datetime(raw.get("at"))
        point = _point(raw.get("point"))
        if at is None or point is None:
            raise ValueError("Each fix needs 'at' and 'point' [longitude, latitude].")
        sats = raw.get("sats")
        activity = raw.get("activity")
        fixes.append(
            PositionFix(
                collar_id=collar_id,
                at=at,
                point=point,
                accuracy_meters=_number(raw, "accuracy_meters", "accuracy_m"),
                activity=str(activity) if activity else None,
                sats=int(sats) if isinstance(sats, (int, float)) else None,
                boundary_version=version,
            )
        )

    cues: list[CueEvent] = []
    for raw in payload.get("cues") or []:  # type: ignore[union-attr]
        if not isinstance(raw, Mapping):
            continue
        at = parse_datetime(raw.get("at"))
        if at is None:
            raise ValueError("Each cue needs 'at'.")
        level = raw.get("level")
        cues.append(
            CueEvent(
                collar_id=collar_id,
                at=at,
                type=str(raw.get("type") or "cue"),
                point=_point(raw.get("point")),
                level=int(level) if isinstance(level, (int, float)) else None,
                margin_meters=_number(raw, "margin_meters", "margin_m"),
            )
        )

    return PositionReport(
        collar_id=collar_id,
        fixes=fixes,
        cues=cues,
        battery=_number(payload, "battery"),
        boundary_version=version,
    )
