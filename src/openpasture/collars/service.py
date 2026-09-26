"""Collar service: boundary versions, delivery, confirmation, and position data."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Mapping
from uuid import uuid4

from openpasture.collars.gateway import CollarGateway
from openpasture.collars.wire import BoundaryTranslationError
from openpasture.domain import (
    BoundaryActivation,
    BoundaryAck,
    BoundaryCommand,
    BoundaryTransition,
    Collar,
    CollarSummary,
    LandUnit,
    PositionReport,
    boundary_activation,
)
from openpasture.domain.clock import as_utc, utc_now
from openpasture.domain.geo import point_in_geometry
from openpasture.store.protocol import FarmStore

DEFAULT_RETENTION_DAYS = 30
POSITION_UNIT_TYPES = {"paddock", "section"}


def new_command_id() -> str:
    return f"bc_{uuid4().hex[:20]}"


class CollarService:
    """Owns everything that touches the herd's collars."""

    def __init__(
        self,
        store: FarmStore,
        gateway: CollarGateway,
        *,
        activation_threshold: float = 1.0,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.gateway = gateway
        self.activation_threshold = activation_threshold
        self.retention_days = retention_days
        self.clock = clock or utc_now

    # -- boundaries -------------------------------------------------------

    def collar_ids_for_herd(self, farm_id: str, herd_id: str) -> list[str]:
        return [collar.collar_id for collar in self.store.list_collars(farm_id, herd_id)]

    def next_version(self, herd_id: str) -> int:
        """Versions only go up per herd, across every command ever issued."""

        commands = self.store.list_boundary_commands(herd_id, limit=1)
        highest = max((int(command.final_version or command.version) for command in commands), default=0)
        return highest + 1

    def active_command(self, herd_id: str) -> BoundaryCommand | None:
        for command in self.store.list_boundary_commands(herd_id, limit=20):
            if command.status == "active":
                return command
        return None

    def latest_command(self, herd_id: str) -> BoundaryCommand | None:
        commands = self.store.list_boundary_commands(herd_id, limit=1)
        return commands[0] if commands else None

    def issue_boundary(
        self,
        *,
        farm_id: str,
        herd_id: str,
        boundary: Mapping[str, object],
        decision_id: str | None = None,
        land_unit_id: str | None = None,
        exclusions: list[dict[str, object]] | None = None,
        transition: BoundaryTransition | None = None,
        effective_at: datetime | None = None,
        previous_boundary: Mapping[str, object] | None = None,
        activation_threshold: float | None = None,
    ) -> tuple[BoundaryCommand, BoundaryActivation]:
        """Create, translate, and send a command. Never raises for delivery problems.

        A command the collars cannot express is saved as ``rejected``; a
        transport failure is saved as ``failed``. Either way ``error`` says why.
        """

        collar_ids = self.collar_ids_for_herd(farm_id, herd_id)
        if not collar_ids:
            raise ValueError(f"Herd '{herd_id}' has no collars registered.")
        if previous_boundary is None:
            current = self.active_command(herd_id)
            previous_boundary = current.boundary if current else None
        command = BoundaryCommand(
            command_id=new_command_id(),
            decision_id=decision_id,
            farm_id=farm_id,
            herd_id=herd_id,
            collar_ids=collar_ids,
            version=self.next_version(herd_id),
            effective_at=effective_at or self.clock(),
            boundary=dict(boundary),
            exclusions=list(exclusions or []),
            transition=transition or BoundaryTransition(),
            activation_threshold=self.activation_threshold if activation_threshold is None else activation_threshold,
            land_unit_id=land_unit_id,
            gateway=self.gateway.name,
        )
        try:
            wire = self.gateway.translate(command, previous_boundary)
        except BoundaryTranslationError as exc:
            command.status = "rejected"
            command.error = str(exc)
            self.store.save_boundary_command(command)
            return command, boundary_activation(command, [])
        command.final_version = command.version + len(wire) - 1
        self.store.save_boundary_command(command)
        try:
            acks = self.gateway.send_boundary(command, wire)
        except Exception as exc:
            command.status = "failed"
            command.error = str(exc)
            self.store.save_boundary_command(command)
            return command, boundary_activation(command, [])
        command.status = "sent"
        command.sent_at = self.clock()
        for ack in acks:
            self.store.record_boundary_ack(ack)
        return command, self._update_activation(command)

    def _update_activation(self, command: BoundaryCommand) -> BoundaryActivation:
        activation = boundary_activation(command, self.store.list_boundary_acks(command.command_id))
        if command.status == "sent" and activation.active:
            command.status = "active"
            command.activated_at = self.clock()
        elif command.status == "sent" and activation.rejected and len(activation.rejected) == len(command.collar_ids):
            command.status = "rejected"
            command.error = "Every collar rejected the boundary."
        self.store.save_boundary_command(command)
        return activation

    def record_acks(self, acks: list[BoundaryAck]) -> list[tuple[BoundaryCommand, BoundaryActivation]]:
        """Store acks and recompute activation for every command they touch."""

        touched: dict[str, BoundaryCommand] = {}
        for ack in acks:
            command = touched.get(ack.command_id) or self.store.get_boundary_command(ack.command_id)
            if command is None:
                continue
            self.store.record_boundary_ack(ack)
            touched[command.command_id] = command
        return [(command, self._update_activation(command)) for command in touched.values()]

    def refresh(self, command: BoundaryCommand) -> BoundaryActivation:
        """Pull any pending acks from the gateway, then recompute activation."""

        self.record_acks(self.gateway.poll_acks())
        fresh = self.store.get_boundary_command(command.command_id) or command
        return self._update_activation(fresh)

    def boundary_status(self, command: BoundaryCommand) -> dict[str, object]:
        activation = self.refresh(command)
        command = self.store.get_boundary_command(command.command_id) or command
        acks = self.store.list_boundary_acks(command.command_id)
        unconfirmed = []
        for collar_id in activation.unconfirmed_collar_ids:
            collar = self.store.get_collar(collar_id)
            unconfirmed.append(
                {
                    "collar_id": collar_id,
                    "reason": activation.rejected.get(collar_id) or "No applied acknowledgement yet.",
                    "last_seen_at": collar.last_seen_at.isoformat() if collar and collar.last_seen_at else None,
                    "battery": collar.battery if collar else None,
                }
            )
        return {
            "command": command,
            "acks": acks,
            "activation": activation.to_dict(),
            "unconfirmed_collars": unconfirmed,
            "wire_versions": command.versions,
        }

    # -- positions --------------------------------------------------------

    def _position_units(self, farm_id: str) -> list[LandUnit]:
        units = [unit for unit in self.store.list_land_units(farm_id) if unit.unit_type in POSITION_UNIT_TYPES]
        return sorted(units, key=lambda unit: unit.area_hectares or 0.0)

    def land_unit_for_point(self, point: list[float], units: list[LandUnit]) -> str | None:
        """The smallest paddock or section containing the point."""

        for unit in units:
            if point_in_geometry(point, unit.geometry.geometry):
                return unit.id
        return None

    def ingest_report(
        self,
        report: PositionReport,
        *,
        farm_id: str,
        herd_id: str | None = None,
    ) -> dict[str, object]:
        collar = self.store.get_collar(report.collar_id)
        resolved_herd = herd_id or (collar.herd_id if collar else None)
        if resolved_herd is None:
            raise ValueError(
                f"Collar '{report.collar_id}' is not registered to a herd. Pass herd_id to register it."
            )
        if collar is None or collar.herd_id != resolved_herd or collar.farm_id != farm_id:
            collar = Collar(
                collar_id=report.collar_id,
                farm_id=farm_id,
                herd_id=resolved_herd,
                created_at=collar.created_at if collar else self.clock(),
            )

        units = self._position_units(farm_id)
        for fix in report.fixes:
            fix.farm_id = farm_id
            fix.herd_id = resolved_herd
            fix.land_unit_id = self.land_unit_for_point(fix.point, units)
        for cue in report.cues:
            cue.farm_id = farm_id
            cue.herd_id = resolved_herd
        fixes_recorded = self.store.record_position_fixes(report.fixes)
        cues_recorded = self.store.record_cue_events(report.cues)

        latest = max((fix.at for fix in report.fixes), default=None, key=as_utc)
        if latest is not None and (collar.last_seen_at is None or as_utc(latest) > as_utc(collar.last_seen_at)):
            collar.last_seen_at = latest
        if report.battery is not None:
            collar.battery = report.battery
        if report.boundary_version is not None:
            collar.boundary_version = report.boundary_version
        self.store.upsert_collar(collar)

        pruned = self.store.prune_position_fixes(self.clock() - timedelta(days=self.retention_days))
        counts = Counter(fix.land_unit_id for fix in report.fixes if fix.land_unit_id)
        return {
            "collar": collar,
            "herd_id": resolved_herd,
            "fixes_recorded": fixes_recorded,
            "cues_recorded": cues_recorded,
            "pruned_raw_records": pruned,
            "land_unit_fix_counts": dict(counts),
        }

    def summarize(
        self,
        farm_id: str,
        herd_id: str,
        starts_at: datetime,
        ends_at: datetime,
        *,
        boundary: Mapping[str, object] | None = None,
        save: bool = False,
    ) -> CollarSummary | None:
        """Roll the herd's fixes and cues in a window into one summary.

        Returns None when the herd has no collars and no fixes in the window.
        """

        fixes = self.store.list_position_fixes(herd_id, starts_at, ends_at)
        cues = self.store.list_cue_events(herd_id, starts_at, ends_at)
        collars = self.store.list_collars(farm_id, herd_id)
        if not fixes and not collars:
            return None
        if boundary is None:
            active = self.active_command(herd_id)
            boundary = active.boundary if active else None
        unit_counts = Counter(fix.land_unit_id for fix in fixes if fix.land_unit_id)
        activity_counts = Counter(fix.activity for fix in fixes if fix.activity)
        inside = sum(1 for fix in fixes if boundary and point_in_geometry(fix.point, boundary))
        versions = [fix.boundary_version for fix in fixes if fix.boundary_version is not None]
        summary = CollarSummary(
            summary_id=f"cs_{uuid4().hex[:20]}",
            farm_id=farm_id,
            herd_id=herd_id,
            window_starts_at=starts_at,
            window_ends_at=ends_at,
            collar_ids=sorted({collar.collar_id for collar in collars} | {fix.collar_id for fix in fixes}),
            fix_count=len(fixes),
            cue_count=len(cues),
            land_unit_fix_counts=dict(unit_counts),
            dominant_land_unit_id=unit_counts.most_common(1)[0][0] if unit_counts else None,
            share_inside_boundary=round(inside / len(fixes), 4) if fixes and boundary else None,
            boundary_version=max(versions) if versions else None,
            activity_counts=dict(activity_counts),
            last_fix_at=max((fix.at for fix in fixes), key=as_utc) if fixes else None,
            centroid=(
                [
                    round(sum(fix.point[0] for fix in fixes) / len(fixes), 7),
                    round(sum(fix.point[1] for fix in fixes) / len(fixes), 7),
                ]
                if fixes
                else None
            ),
            battery_by_collar={collar.collar_id: collar.battery for collar in collars if collar.battery is not None},
            created_at=self.clock(),
        )
        if save:
            self.store.save_collar_summary(summary)
        return summary

    def latest_fixes(self, herd_id: str, *, since: datetime) -> list[dict[str, object]]:
        """The most recent fix per collar since ``since``."""

        latest: dict[str, object] = {}
        for fix in self.store.list_position_fixes(herd_id, since):
            latest[fix.collar_id] = fix
        return [latest[key] for key in sorted(latest)]  # type: ignore[misc]
