"""Hosted Streamable HTTP MCP server for openPasture."""

from __future__ import annotations

import os
from typing import Any

from openpasture.connectors.mcp import build_mcp_server
from openpasture.connectors.mcp_auth import (
    APIKeyTenantMiddleware,
    ASGIApp,
    ASGIReceive,
    ASGISend,
    send_text_response,
)


class HealthCheckApp:
    """Serve liveness checks before delegating to the MCP ASGI app."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: ASGIReceive, send: ASGISend) -> None:
        if scope.get("type") == "http" and scope.get("path") == "/health":
            await send_text_response(send, status=200, body="ok")
            return
        await self.app(scope, receive, send)


def _no_rebind_security() -> Any:
    """Disable MCP SDK DNS rebinding protection for cloud deployments."""
    try:
        from mcp.server.transport_security import TransportSecuritySettings
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    except ImportError:
        return None


def _streamable_http_app(server: Any, transport_security: Any = None) -> ASGIApp:
    try:
        method = server.streamable_http_app
    except AttributeError as exc:
        raise RuntimeError(
            "The hosted openPasture MCP server requires an MCP FastMCP version "
            "with streamable_http_app() support."
        ) from exc

    if transport_security is not None:
        try:
            return method(transport_security=transport_security)
        except TypeError:
            pass
    return method()


def build_hosted_app() -> ASGIApp:
    """Build the hosted MCP ASGI application."""

    security = _no_rebind_security()

    # v1.x: transport_security on FastMCP constructor
    # v2.x: transport_security on streamable_http_app()
    try:
        server = build_mcp_server(transport_security=security) if security else build_mcp_server()
    except TypeError:
        server = build_mcp_server()

    mcp_app = _streamable_http_app(server, transport_security=security)
    tenant_app = APIKeyTenantMiddleware(mcp_app)
    return HealthCheckApp(tenant_app)


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "The hosted openPasture MCP server requires uvicorn. "
            "Install with `pip install openpasture-agent-kit[mcp]`."
        ) from exc

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(build_hosted_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
