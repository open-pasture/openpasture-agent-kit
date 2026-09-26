"""Collar connector: OpenCollar boundary commands, acknowledgements, and positions."""

from __future__ import annotations

import os

from .gateway import CollarGateway, CollarGatewayError, OpenCollarGateway
from .http import HttpCollarGateway
from .service import CollarService
from .simulated import SimulatedCollarGateway
from .wire import BoundaryTranslationError

COLLAR_GATEWAY_CHOICES = ("simulated", "http")


def collar_gateway_from_env(choice: str | None = None) -> CollarGateway:
    selected = (choice or os.environ.get("OPENPASTURE_COLLAR_GATEWAY") or "simulated").strip().lower()
    if selected == "simulated":
        return SimulatedCollarGateway()
    if selected == "http":
        return HttpCollarGateway.from_env()
    raise ValueError(
        f"Unsupported OPENPASTURE_COLLAR_GATEWAY '{selected}'. Use one of: {', '.join(COLLAR_GATEWAY_CHOICES)}."
    )


__all__ = [
    "BoundaryTranslationError",
    "COLLAR_GATEWAY_CHOICES",
    "CollarGateway",
    "CollarGatewayError",
    "CollarService",
    "HttpCollarGateway",
    "OpenCollarGateway",
    "SimulatedCollarGateway",
    "collar_gateway_from_env",
]
