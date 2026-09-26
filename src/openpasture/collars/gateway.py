"""The collar gateway protocol and the shared wire-speaking base."""

from __future__ import annotations

from typing import Mapping, Protocol

from openpasture.collars.wire import parse_position_report, parse_wire_ack, to_wire_boundaries
from openpasture.domain import BoundaryAck, BoundaryCommand, PositionReport


class CollarGatewayError(RuntimeError):
    """The gateway could not deliver a command."""


class CollarGateway(Protocol):
    """How the engine talks to a herd's collars.

    Other virtual-fence vendors can be supported by implementing this.
    """

    name: str

    def translate(
        self, command: BoundaryCommand, previous_boundary: Mapping[str, object] | None
    ) -> list[dict[str, object]]: ...
    def send_boundary(self, command: BoundaryCommand, wire_boundaries: list[dict[str, object]]) -> list[BoundaryAck]: ...
    def poll_acks(self) -> list[BoundaryAck]: ...
    def parse_position_report(self, payload: Mapping[str, object]) -> PositionReport: ...
    def parse_ack(self, payload: Mapping[str, object], *, collar_id: str | None = None) -> BoundaryAck: ...


class OpenCollarGateway:
    """Base for gateways that speak the OpenCollar V0 protocol."""

    name = "opencollar"

    def translate(
        self, command: BoundaryCommand, previous_boundary: Mapping[str, object] | None
    ) -> list[dict[str, object]]:
        return to_wire_boundaries(command, previous_boundary)

    def poll_acks(self) -> list[BoundaryAck]:
        return []

    def parse_position_report(self, payload: Mapping[str, object]) -> PositionReport:
        return parse_position_report(payload)

    def parse_ack(self, payload: Mapping[str, object], *, collar_id: str | None = None) -> BoundaryAck:
        return parse_wire_ack(payload, collar_id=collar_id)
