"""Hosted MCP authentication and tenant context binding."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from openpasture.context import OpenPastureContext, bind_context

ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[dict[str, Any], ASGIReceive, ASGISend], Awaitable[None]]


def tenant_hash(api_key: str) -> str:
    """Return a filesystem-safe tenant identifier derived from an API key."""

    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TenantBinding:
    """Authenticated tenant context for one hosted MCP request."""

    context_id: str
    api_key: str


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
    """Authenticate hosted MCP URLs and bind a per-tenant context."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        data_root: str | Path | None = None,
    ) -> None:
        self.app = app
        self.auth_url = os.environ.get("OPENPASTURE_API_KEY_AUTH_URL", "").strip()
        if not self.auth_url:
            raise RuntimeError("OPENPASTURE_API_KEY_AUTH_URL is required for hosted MCP API key auth.")
        self.data_root = Path(
            data_root or os.environ.get("OPENPASTURE_HOSTED_DATA_DIR", "/data/openpasture")
        ).expanduser()
        self._contexts: dict[str, OpenPastureContext] = {}

    def _validate_with_cloud(self, api_key: str) -> TenantBinding | None:
        encoded_payload = json.dumps({"apiKey": api_key}).encode("utf-8")
        request = urllib_request.Request(
            self.auth_url,
            data=encoded_payload,
            headers={"content-type": "application/json"},
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None

        if result.get("ok") is True and result.get("tenantId"):
            return TenantBinding(context_id=str(result["tenantId"]), api_key=api_key)
        return None

    async def _resolve_tenant_binding(self, api_key: str) -> TenantBinding | None:
        import asyncio

        return await asyncio.to_thread(self._validate_with_cloud, api_key)

    def _tenant_context(self, binding: TenantBinding) -> OpenPastureContext:
        safe_context_id = hashlib.sha256(binding.context_id.encode("utf-8")).hexdigest()
        cache_id = hashlib.sha256(f"{binding.context_id}:{tenant_hash(binding.api_key)}".encode("utf-8")).hexdigest()
        context = self._contexts.get(cache_id)
        if context is not None:
            return context

        config = {
            "data_dir": self.data_root / "tenants" / safe_context_id,
            "store": os.environ.get("OPENPASTURE_STORE", "sqlite"),
            "convex_url": os.environ.get("OPENPASTURE_CONVEX_URL", ""),
        }
        if config["store"].lower() == "convex":
            config["convex_key"] = binding.api_key

        context = OpenPastureContext(config)
        context.initialize()
        self._contexts[cache_id] = context
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
        binding = await self._resolve_tenant_binding(api_key)
        if not binding:
            await send_text_response(send, status=401, body="Invalid openPasture API key")
            return

        rewritten_path = "/" + "/".join(parts[1:])
        rewritten_scope = dict(scope)
        rewritten_scope["path"] = rewritten_path
        rewritten_scope["raw_path"] = rewritten_path.encode("ascii")
        state = dict(rewritten_scope.get("state") or {})
        state["openpasture_api_key_hash"] = tenant_hash(api_key)
        state["openpasture_tenant_context_id"] = binding.context_id
        rewritten_scope["state"] = state

        context = self._tenant_context(binding)
        with bind_context(context):
            await self.app(rewritten_scope, receive, send)
