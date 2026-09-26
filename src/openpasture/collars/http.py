"""HTTP collar gateway: posts boundary commands to a collar backend."""

from __future__ import annotations

import os

import httpx

from openpasture.collars.gateway import CollarGatewayError, OpenCollarGateway
from openpasture.domain import BoundaryAck, BoundaryCommand


class HttpCollarGateway(OpenCollarGateway):
    """Sends wire boundaries to ``{url}/boundaries``.

    The request body is ``{command_id, farm_id, herd_id, collar_ids,
    boundaries}`` where ``boundaries`` are OpenCollar V0 wire boundaries. The
    backend may answer with ``{"acks": [...]}``; later acks arrive through
    ``record_collar_report``.
    """

    name = "http"

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not url.strip():
            raise ValueError("HttpCollarGateway needs OPENPASTURE_COLLAR_GATEWAY_URL.")
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.client = client

    @classmethod
    def from_env(cls) -> "HttpCollarGateway":
        return cls(
            os.environ.get("OPENPASTURE_COLLAR_GATEWAY_URL", ""),
            token=os.environ.get("OPENPASTURE_COLLAR_GATEWAY_TOKEN") or None,
        )

    def send_boundary(self, command: BoundaryCommand, wire_boundaries: list[dict[str, object]]) -> list[BoundaryAck]:
        body = {
            "command_id": command.command_id,
            "farm_id": command.farm_id,
            "herd_id": command.herd_id,
            "collar_ids": command.collar_ids,
            "boundaries": wire_boundaries,
        }
        headers = {"content-type": "application/json"}
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        try:
            poster = self.client.post if self.client is not None else httpx.post
            response = poster(f"{self.url}/boundaries", json=body, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json() if response.content else {}
        except Exception as exc:
            raise CollarGatewayError(f"Collar gateway request failed: {exc}") from exc
        acks = payload.get("acks") if isinstance(payload, dict) else None
        return [self.parse_ack(item) for item in acks or [] if isinstance(item, dict)]
