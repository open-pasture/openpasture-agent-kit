"""In-memory collar gateway for tests, demos, and farms without collars yet."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Mapping

from openpasture.collars.gateway import OpenCollarGateway
from openpasture.domain import BoundaryAck, BoundaryCommand
from openpasture.domain.clock import as_utc, parse_datetime, utc_now
from openpasture.domain.geo import geometry_bbox, geometry_centroid, point_in_geometry


class SimulatedCollarGateway(OpenCollarGateway):
    """Acts like a herd of V0 collars that are always in range.

    Each simulated collar keeps the version it holds and ignores anything not
    newer, like the firmware. Boundaries effective now are ``applied`` at once;
    staged ones are ``received`` and applied by ``poll_acks`` once due.
    ``offline_collar_ids`` never answer; ``rejecting_collar_ids`` always reject.
    """

    name = "simulated"

    def __init__(
        self,
        *,
        offline_collar_ids: set[str] | None = None,
        rejecting_collar_ids: dict[str, str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.offline_collar_ids = set(offline_collar_ids or ())
        self.rejecting_collar_ids = dict(rejecting_collar_ids or {})
        self.clock = clock or utc_now
        self.sent: list[dict[str, object]] = []
        self.held_versions: dict[str, int] = {}
        self._staged: list[tuple[str, dict[str, object]]] = []

    def send_boundary(self, command: BoundaryCommand, wire_boundaries: list[dict[str, object]]) -> list[BoundaryAck]:
        now = self.clock()
        acks: list[BoundaryAck] = []
        for collar_id in command.collar_ids:
            if collar_id in self.offline_collar_ids:
                continue
            for wire in wire_boundaries:
                self.sent.append({"collar_id": collar_id, **wire})
                acks.append(self._receive(collar_id, wire, now))
        return acks

    def _receive(self, collar_id: str, wire: Mapping[str, object], now: datetime) -> BoundaryAck:
        version = int(wire["version"])  # type: ignore[arg-type]
        command_id = str(wire["command_id"])
        if collar_id in self.rejecting_collar_ids:
            return BoundaryAck(command_id, collar_id, version, "rejected", now, self.rejecting_collar_ids[collar_id])
        held = max([self.held_versions.get(collar_id, 0)] + [
            int(staged["version"]) for staged_collar, staged in self._staged if staged_collar == collar_id  # type: ignore[arg-type]
        ])
        if version <= held:
            return BoundaryAck(
                command_id, collar_id, version, "rejected", now, f"Version {version} is not newer than {held}."
            )
        effective_at = parse_datetime(wire.get("effective_at")) or now
        if as_utc(effective_at) <= as_utc(now):
            self.held_versions[collar_id] = version
            return BoundaryAck(command_id, collar_id, version, "applied", now)
        self._staged.append((collar_id, dict(wire)))
        return BoundaryAck(command_id, collar_id, version, "received", now)

    def poll_acks(self) -> list[BoundaryAck]:
        now = self.clock()
        acks: list[BoundaryAck] = []
        waiting: list[tuple[str, dict[str, object]]] = []
        for collar_id, wire in self._staged:
            effective_at = parse_datetime(wire.get("effective_at")) or now
            if as_utc(effective_at) <= as_utc(now):
                version = int(wire["version"])  # type: ignore[arg-type]
                self.held_versions[collar_id] = max(self.held_versions.get(collar_id, 0), version)
                acks.append(BoundaryAck(str(wire["command_id"]), collar_id, version, "applied", now))
            else:
                waiting.append((collar_id, wire))
        self._staged = waiting
        return acks

    def simulate_report(
        self,
        collar_id: str,
        boundary: Mapping[str, object],
        *,
        start: datetime | None = None,
        count: int = 6,
        interval_minutes: int = 10,
        seed: int | None = None,
        cues: int = 0,
    ) -> dict[str, object]:
        """A wire-shaped position report with fixes inside ``boundary``."""

        rng = random.Random(seed if seed is not None else collar_id)
        box = geometry_bbox(boundary)
        begin = start or self.clock() - timedelta(minutes=interval_minutes * count)
        fixes = []
        for index in range(count):
            point = None
            for _ in range(200):
                candidate = [
                    rng.uniform(box.min_longitude, box.max_longitude),
                    rng.uniform(box.min_latitude, box.max_latitude),
                ]
                if point_in_geometry(candidate, boundary):
                    point = candidate
                    break
            point = point or geometry_centroid(boundary)
            fixes.append(
                {
                    "at": (begin + timedelta(minutes=interval_minutes * index)).isoformat(),
                    "point": [round(point[0], 7), round(point[1], 7)],
                    "accuracy_m": 1.8,
                    "sats": 9,
                    "activity": "grazing" if index % 3 else "resting",
                }
            )
        return {
            "collar_id": collar_id,
            "boundary_version": self.held_versions.get(collar_id),
            "fixes": fixes,
            "cues": [
                {"at": (begin + timedelta(minutes=interval_minutes * index)).isoformat(), "level": 1, "margin_m": 1.2}
                for index in range(cues)
            ],
            "battery": 0.81,
        }
