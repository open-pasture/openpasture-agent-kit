from __future__ import annotations

import asyncio
import json
from typing import Any

from openpasture.connectors import mcp_auth
from openpasture.context import get_default_context, get_store
from openpasture.domain import Farm


async def _receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _call_middleware(middleware: mcp_auth.APIKeyTenantMiddleware, path: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await middleware(
        {"type": "http", "path": path, "raw_path": path.encode("ascii"), "state": {}},
        _receive,
        send,
    )
    return messages


class FakeContext:
    instances: list["FakeContext"] = []

    def __init__(self, config: dict[str, object]) -> None:
        self.config = config
        self.initialized = False
        FakeContext.instances.append(self)

    def initialize(self) -> None:
        self.initialized = True


class FakeCloudResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeCloudResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_valid_path_rewrites_and_binds_context(monkeypatch, tmp_path):
    FakeContext.instances = []
    monkeypatch.setattr(mcp_auth, "OpenPastureContext", FakeContext)
    monkeypatch.setenv("OPENPASTURE_API_KEY_AUTH_URL", "https://example.convex.site/api-key/auth")
    monkeypatch.setenv("OPENPASTURE_STORE", "convex")
    monkeypatch.setenv("OPENPASTURE_CONVEX_URL", "https://example.convex.cloud")

    seen: dict[str, object] = {}

    async def app(scope: dict[str, Any], _receive, send) -> None:
        seen["path"] = scope["path"]
        seen["state"] = scope["state"]
        seen["context"] = get_default_context()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    def fake_urlopen(request, timeout):
        assert timeout == 10
        assert json.loads(request.data.decode("utf-8")) == {"apiKey": "opk_live_valid"}
        return FakeCloudResponse({"ok": True, "tenantId": "tenant_valid"})

    monkeypatch.setattr(mcp_auth.urllib_request, "urlopen", fake_urlopen)
    middleware = mcp_auth.APIKeyTenantMiddleware(app, data_root=tmp_path)

    messages = asyncio.run(_call_middleware(middleware, "/opk_live_valid/mcp"))

    assert messages[0]["status"] == 200
    assert seen["path"] == "/mcp"
    assert seen["context"] is FakeContext.instances[0]
    assert seen["state"]["openpasture_tenant_context_id"] == "tenant_valid"
    assert FakeContext.instances[0].config["convex_key"] == "opk_live_valid"
    assert FakeContext.instances[0].initialized is True


def test_invalid_api_key_returns_401(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENPASTURE_API_KEY_AUTH_URL", "https://example.convex.site/api-key/auth")

    async def app(_scope, _receive, _send) -> None:
        raise AssertionError("app should not run")

    def fake_urlopen(_request, timeout):
        assert timeout == 10
        return FakeCloudResponse({"ok": False})

    monkeypatch.setattr(mcp_auth.urllib_request, "urlopen", fake_urlopen)
    middleware = mcp_auth.APIKeyTenantMiddleware(app, data_root=tmp_path)

    messages = asyncio.run(_call_middleware(middleware, "/opk_live_wrong/mcp"))

    assert messages[0]["status"] == 401


def test_cloud_auth_uses_only_openpasture_api_key(monkeypatch, tmp_path):
    FakeContext.instances = []
    monkeypatch.setattr(mcp_auth, "OpenPastureContext", FakeContext)
    monkeypatch.setenv("OPENPASTURE_API_KEY_AUTH_URL", "https://example.convex.site/api-key/auth")
    monkeypatch.setenv("OPENPASTURE_STORE", "convex")
    monkeypatch.setenv("OPENPASTURE_CONVEX_URL", "https://example.convex.cloud")
    payloads: list[dict[str, str]] = []

    def fake_urlopen(request, timeout):
        assert timeout == 10
        payload = json.loads(request.data.decode("utf-8"))
        payloads.append(payload)
        return FakeCloudResponse({"ok": True, "tenantId": "tenant_shared"})

    monkeypatch.setattr(mcp_auth.urllib_request, "urlopen", fake_urlopen)

    async def app(_scope, _receive, send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = mcp_auth.APIKeyTenantMiddleware(app, data_root=tmp_path)

    messages = asyncio.run(_call_middleware(middleware, "/opk_live_cloud/mcp"))

    assert messages[0]["status"] == 200
    assert payloads == [{"apiKey": "opk_live_cloud"}]
    assert FakeContext.instances[0].config["convex_key"] == "opk_live_cloud"


def test_shared_mcp_request_reaches_convex_store_with_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENPASTURE_API_KEY_AUTH_URL", "https://example.convex.site/api-key/auth")
    monkeypatch.setenv("OPENPASTURE_STORE", "convex")
    monkeypatch.setenv("OPENPASTURE_CONVEX_URL", "https://example.convex.cloud")

    def fake_urlopen(_request, timeout):
        assert timeout == 10
        return FakeCloudResponse({"ok": True, "tenantId": "tenant_e2e"})

    monkeypatch.setattr(mcp_auth.urllib_request, "urlopen", fake_urlopen)

    def initialize_store_only(self) -> None:
        self.get_store()

    monkeypatch.setattr(mcp_auth.OpenPastureContext, "initialize", initialize_store_only)

    calls: list[dict[str, object]] = []

    class FakeStoreResponse:
        def __init__(self, result: object) -> None:
            self.result = result

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"ok": True, "result": self.result}

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        assert headers["authorization"] == "Bearer opk_live_e2e"
        assert json["operation"] == "farms.create"
        return FakeStoreResponse(json["args"]["record"]["farmId"])

    monkeypatch.setattr("openpasture.store.convex.httpx.post", fake_post)

    async def app(_scope, _receive, send) -> None:
        farm_id = get_store().create_farm(Farm(id="farm_e2e", name="E2E Farm", timezone="UTC"))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": farm_id.encode("utf-8")})

    middleware = mcp_auth.APIKeyTenantMiddleware(app, data_root=tmp_path)

    messages = asyncio.run(_call_middleware(middleware, "/opk_live_e2e/mcp"))

    assert messages[0]["status"] == 200
    assert messages[1]["body"] == b"farm_e2e"
    assert calls[0]["url"] == "https://example.convex.site/store"
