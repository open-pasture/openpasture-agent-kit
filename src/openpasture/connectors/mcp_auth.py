"""Hosted MCP authentication and tenant context binding."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from openpasture.context import OpenPastureContext, bind_context

ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[dict[str, Any], ASGIReceive, ASGISend], Awaitable[None]]


def parse_api_keys(value: str | None = None) -> frozenset[str]:
    """Parse comma-separated hosted API keys from an environment value."""

    raw_value = os.environ.get("OPENPASTURE_API_KEYS", "") if value is None else value
    return frozenset(key.strip() for key in raw_value.split(",") if key.strip())


def tenant_hash(api_key: str) -> str:
    """Return a filesystem-safe tenant identifier derived from an API key."""

    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


async def send_text_response(
    send: ASGISend,
    *,
    status: int,
    body: str,
) -> None:
    encoded = body.encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(encoded)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": encoded})


class APIKeyTenantMiddleware:
    """Authenticate Firecrawl-style MCP URLs and bind a per-tenant context."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        api_keys: frozenset[str] | None = None,
        data_root: str | Path | None = None,
    ) -> None:
        self.app = app
        self.api_keys = parse_api_keys() if api_keys is None else api_keys
        if not self.api_keys:
            raise RuntimeError("OPENPASTURE_API_KEYS must include at least one hosted MCP API key.")
        self.data_root = Path(
            data_root or os.environ.get("OPENPASTURE_HOSTED_DATA_DIR", "/data/openpasture")
        ).expanduser()
        self._contexts: dict[str, OpenPastureContext] = {}

    def _is_allowed(self, api_key: str) -> bool:
        return any(hmac.compare_digest(api_key, allowed_key) for allowed_key in self.api_keys)

    def _tenant_context(self, api_key: str) -> OpenPastureContext:
        hashed_key = tenant_hash(api_key)
        context = self._contexts.get(hashed_key)
        if context is not None:
            return context

        context = OpenPastureContext({"data_dir": self.data_root / "tenants" / hashed_key})
        context.initialize()
        self._contexts[hashed_key] = context
        return context

    async def __call__(self, scope: dict[str, Any], receive: ASGIReceive, send: ASGISend) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        parts = [part for part in str(scope.get("path", "")).split("/") if part]
        if len(parts) < 2 or parts[1] != "mcp":
            await send_text_response(send, status=404, body="Not found")
            return

        api_key = parts[0]
        if not self._is_allowed(api_key):
            await send_text_response(send, status=401, body="Invalid openPasture API key")
            return

        rewritten_path = "/" + "/".join(parts[1:])
        rewritten_scope = dict(scope)
        rewritten_scope["path"] = rewritten_path
        rewritten_scope["raw_path"] = rewritten_path.encode("ascii")
        state = dict(rewritten_scope.get("state") or {})
        state["openpasture_api_key_hash"] = tenant_hash(api_key)
        rewritten_scope["state"] = state

        context = self._tenant_context(api_key)
        with bind_context(context):
            await self.app(rewritten_scope, receive, send)
