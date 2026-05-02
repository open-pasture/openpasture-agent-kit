"""Hosted Streamable HTTP server for the OpenPasture ChatGPT onboarding app."""

from __future__ import annotations

import os

from openpasture.connectors.mcp_auth import APIKeyTenantMiddleware, ASGIApp
from openpasture.connectors.mcp_chatgpt_app import build_chatgpt_app_server
from openpasture.connectors.mcp_hosted import HealthCheckApp, _no_rebind_security, _streamable_http_app


def build_hosted_chatgpt_app() -> ASGIApp:
    """Build the Railway-hosted ChatGPT onboarding app."""

    security = _no_rebind_security()
    try:
        server = build_chatgpt_app_server(transport_security=security) if security else build_chatgpt_app_server()
    except TypeError:
        server = build_chatgpt_app_server()

    mcp_app = _streamable_http_app(server, transport_security=security)
    tenant_app = APIKeyTenantMiddleware(mcp_app)
    return HealthCheckApp(tenant_app)


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "The hosted OpenPasture ChatGPT app requires uvicorn. "
            "Install with `pip install openpasture-agent-kit[mcp]`."
        ) from exc

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(build_hosted_chatgpt_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
