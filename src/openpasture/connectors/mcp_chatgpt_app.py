"""ChatGPT Apps SDK connector for the OpenPasture farm onboarding app."""

from __future__ import annotations

import inspect
import json
import os
from collections.abc import Callable
from importlib.resources import files
from typing import Any

from openpasture.connectors.mcp import _require_fastmcp
from openpasture.context import initialize, resolve_farm_id
from openpasture.toolkit import run_tool
from openpasture.tools import observe, onboarding

TEMPLATE_URI = "ui://openpasture/onboarding-summary-v2.html"
RESOURCE_MIME_TYPE = "text/html;profile=mcp-app"

ONBOARDING_FIELDS = (
    "farm",
    "timezone",
    "herd",
    "paddocks",
    "current_paddock",
)

_FALLBACK_ONBOARDING_SUMMARY_WIDGET_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>OpenPasture onboarding summary</title>
    <style>
      :root {
        color: #e8e8e6;
        background: #000000;
        font-family: "JetBrains Mono", "SF Mono", ui-monospace, Menlo, Monaco, Consolas, monospace;
      }
      * {
        box-sizing: border-box;
      }
      html {
        min-height: 100%;
        background: #000000;
      }
      body {
        display: grid;
        min-height: 100vh;
        margin: 0;
        place-items: center;
        background:
          linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px),
          #000000;
        background-size: 28px 28px;
        color: #e8e8e6;
        font-weight: 300;
        padding: 18px;
      }
      main {
        display: grid;
        gap: 2px;
        justify-items: stretch;
        margin: 0 auto;
        max-width: 680px;
        width: min(100%, 680px);
      }
      .card {
        background: #080a08;
        border: 0;
        border-radius: 0;
        box-shadow: none;
        padding: 18px;
        text-align: center;
      }
      h1 {
        margin: 0;
        color: #ffffff;
        font-size: clamp(21px, 4vw, 30px);
        font-weight: 400;
        letter-spacing: -0.03em;
        line-height: 1.2;
      }
      h2 {
        margin: 0 0 12px;
        color: #6a6e68;
        font-size: 11px;
        font-weight: 400;
        letter-spacing: 0.14em;
        text-transform: uppercase;
      }
      p {
        margin: 8px auto 0;
        max-width: 54ch;
        line-height: 1.55;
      }
      ul {
        display: inline-grid;
        gap: 7px;
        list-style-position: inside;
        margin: 10px auto 0;
        padding: 0;
        text-align: left;
      }
      .status-grid {
        display: grid;
        gap: 2px;
        grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
        justify-content: center;
        margin: 0 auto;
        max-width: 560px;
      }
      .pill {
        background: rgba(255, 255, 255, 0.03);
        border: 0;
        border-radius: 0;
        color: #6a6e68;
        font-size: 11px;
        letter-spacing: 0.07em;
        padding: 12px 10px;
        text-align: center;
        text-transform: uppercase;
      }
      .ready {
        background: rgba(255, 255, 255, 0.06);
        color: #ffffff;
      }
      .missing {
        background: rgba(224, 80, 64, 0.14);
        color: #e05040;
      }
      .muted {
        color: #8a8e88;
      }
      button {
        border: 0;
        border-radius: 0;
        background: #ffffff;
        color: #000000;
        cursor: pointer;
        font: inherit;
        font-size: 12px;
        letter-spacing: 0.08em;
        padding: 11px 14px;
        text-transform: uppercase;
      }
      button:disabled {
        cursor: default;
        opacity: 0.6;
      }
      button + button {
        background: rgba(255, 255, 255, 0.06);
        color: #e8e8e6;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 2px;
        justify-content: center;
        margin-top: 16px;
      }
    </style>
  </head>
  <body>
    <main>
      <section class="card">
        <h1 id="title">OpenPasture farm onboarding</h1>
        <p id="summary" class="muted">Waiting for onboarding details from ChatGPT.</p>
      </section>
      <section class="card">
        <h2>Setup checklist</h2>
        <div id="status-grid" class="status-grid"></div>
      </section>
      <section class="card">
        <h2>Captured so far</h2>
        <div id="captured"></div>
      </section>
      <section class="card">
        <h2>Next useful question</h2>
        <p id="next-question">Ask for the smallest missing detail.</p>
        <div class="actions">
          <button id="ask-button" type="button">Ask this in chat</button>
          <button id="refresh-button" type="button">Refresh status</button>
        </div>
      </section>
    </main>
    <script>
      const fields = ["farm", "timezone", "herd", "paddocks", "current_paddock"];
      const openai = typeof window !== "undefined" ? window.openai : undefined;
      let latestQuestion = "";
      let requestId = 0;

      function asArray(value) {
        return Array.isArray(value) ? value : [];
      }

      function rpcRequest(method, params) {
        const id = `openpasture-${++requestId}`;
        return new Promise((resolve, reject) => {
          const timeout = window.setTimeout(() => {
            window.removeEventListener("message", onMessage);
            reject(new Error(`${method} timed out`));
          }, 10000);

          function onMessage(event) {
            if (event.source !== window.parent) return;
            const message = event.data;
            if (!message || message.jsonrpc !== "2.0" || message.id !== id) return;
            window.clearTimeout(timeout);
            window.removeEventListener("message", onMessage);
            if (message.error) {
              reject(new Error(message.error.message || "Host request failed"));
              return;
            }
            resolve(message.result);
          }

          window.addEventListener("message", onMessage, { passive: true });
          window.parent.postMessage({ jsonrpc: "2.0", id, method, params }, "*");
        });
      }

      function render(data) {
        const payload = data && typeof data === "object" ? data : {};
        const status = payload.onboarding_status || {};
        const farm = payload.farm || null;
        const herds = asArray(payload.herds);
        const paddocks = asArray(payload.paddocks);
        const observations = asArray(payload.recent_observations);
        const missing = asArray(payload.missing);
        latestQuestion = String(payload.next_question || "What is the smallest missing setup detail?");

        document.getElementById("title").textContent = farm?.name
          ? `${farm.name} onboarding`
          : "OpenPasture farm onboarding";
        document.getElementById("summary").textContent = status.complete
          ? "Core setup is ready. The farmer can add observations or move into daily planning."
          : "ChatGPT is collecting the basic farm, herd, paddock, and current-location details.";

        const grid = document.getElementById("status-grid");
        grid.replaceChildren(
          ...fields.map((field) => {
            const item = document.createElement("div");
            const ready = !missing.includes(field);
            item.className = `pill ${ready ? "ready" : "missing"}`;
            item.textContent = `${field.replace("_", " ")}: ${ready ? "ready" : "missing"}`;
            return item;
          })
        );

        const captured = document.getElementById("captured");
        captured.replaceChildren();
        const list = document.createElement("ul");
        [
          `Farm: ${farm?.name || "not set"}`,
          `Timezone: ${farm?.timezone || "not set"}`,
          `Herds: ${herds.length}`,
          `Paddocks: ${paddocks.length}`,
          `Starting observations: ${observations.length}`,
        ].forEach((text) => {
          const item = document.createElement("li");
          item.textContent = text;
          list.appendChild(item);
        });
        captured.appendChild(list);

        document.getElementById("next-question").textContent = latestQuestion;
      }

      function receiveToolResult(event) {
        if (event.source !== window.parent) return;
        const message = event.data;
        if (!message || message.jsonrpc !== "2.0") return;
        if (message.method === "ui/notifications/tool-result") {
          render(message.params?.structuredContent);
          return;
        }
        if (message.method === "ui/notifications/tool-input") {
          render(message.params?.structuredContent || message.params);
        }
      }

      document.getElementById("ask-button").addEventListener("click", () => {
        if (!latestQuestion) return;
        window.parent.postMessage(
          {
            jsonrpc: "2.0",
            method: "ui/message",
            params: {
              role: "user",
              content: [{ type: "text", text: latestQuestion }],
            },
          },
          "*"
        );
      });

      document.getElementById("refresh-button").addEventListener("click", async () => {
        const button = document.getElementById("refresh-button");
        button.disabled = true;
        try {
          const result = await rpcRequest("tools/call", {
            name: "get_onboarding_status",
            arguments: {},
          });
          render(result?.structuredContent || result);
        } catch (error) {
          latestQuestion = "Ask ChatGPT to check OpenPasture onboarding status again.";
          document.getElementById("next-question").textContent = latestQuestion;
        } finally {
          button.disabled = false;
        }
      });

      rpcRequest("ui/initialize", {})
        .then((result) => render(result?.toolOutput || result?.structuredContent || openai?.toolOutput))
        .catch(() => render(openai?.toolOutput));

      window.addEventListener("message", receiveToolResult, { passive: true });
      if (openai) {
        window.addEventListener(
          "openai:set_globals",
          (event) => render(event.detail?.globals?.toolOutput || openai.toolOutput),
          { passive: true }
        );
      }
    </script>
  </body>
</html>
""".strip()


def _load_widget_html() -> str:
    try:
        return (
            files("openpasture.connectors")
            .joinpath("assets/onboarding-summary.html")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError):
        return _FALLBACK_ONBOARDING_SUMMARY_WIDGET_HTML


ONBOARDING_SUMMARY_WIDGET_HTML = _load_widget_html()


def _load_json_tool_result(tool_name: str, args: dict[str, object] | None = None) -> dict[str, Any]:
    result = json.loads(run_tool(tool_name, args or {}))
    if not isinstance(result, dict):
        raise ValueError(f"{tool_name} returned an unexpected response.")
    return result


def _missing_from_state(state: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    farm = state.get("farm") if isinstance(state.get("farm"), dict) else None
    herds = state.get("herds") if isinstance(state.get("herds"), list) else []
    paddocks = state.get("paddocks") if isinstance(state.get("paddocks"), list) else []

    if not farm or not farm.get("name"):
        missing.append("farm")
    if not farm or not farm.get("timezone"):
        missing.append("timezone")
    if not herds:
        missing.append("herd")
    if not paddocks:
        missing.append("paddocks")
    if not herds or not all(isinstance(herd, dict) and herd.get("current_paddock_id") for herd in herds):
        missing.append("current_paddock")
    return missing


def _next_question(missing: list[str]) -> str:
    if "farm" in missing or "timezone" in missing:
        return "What is the farm name and timezone you want OpenPasture to use?"
    if "herd" in missing:
        return "What livestock group should we start with, and how many head are in it?"
    if "paddocks" in missing:
        return "What are the main paddocks or grazing areas you want to track first?"
    if "current_paddock" in missing:
        return "Which paddock is the herd in right now?"
    return "Is there one recent field note I should save before we finish setup?"


def _summary_from_state(state: dict[str, Any]) -> dict[str, Any]:
    missing = _missing_from_state(state)
    farm = state.get("farm") if isinstance(state.get("farm"), dict) else None
    herds = state.get("herds") if isinstance(state.get("herds"), list) else []
    paddocks = state.get("paddocks") if isinstance(state.get("paddocks"), list) else []
    land_units = state.get("land_units") if isinstance(state.get("land_units"), list) else []
    recent_observations = (
        state.get("recent_observations") if isinstance(state.get("recent_observations"), list) else []
    )
    onboarding_status = {
        "farm_ready": "farm" not in missing and "timezone" not in missing,
        "herd_ready": "herd" not in missing,
        "paddocks_ready": "paddocks" not in missing,
        "herd_position_ready": "current_paddock" not in missing,
        "complete": not missing,
    }
    return {
        "status": "ok",
        "workflow": "farm_onboarding",
        "onboarding_status": onboarding_status,
        "farm": farm,
        "herds": herds,
        "land_units": land_units,
        "paddocks": paddocks,
        "latest_plan": state.get("latest_plan"),
        "recent_observations": recent_observations,
        "missing": missing,
        "next_question": _next_question(missing),
    }


def handle_get_onboarding_status(args: dict[str, object] | None = None) -> dict[str, Any]:
    """Return a compact, UI-ready view of the current onboarding state."""

    payload = dict(args or {})
    try:
        farm_id = resolve_farm_id(payload) if payload.get("farm_id") else None
        state = _load_json_tool_result("get_farm_state", {"farm_id": farm_id} if farm_id else {})
    except ValueError as exc:
        if "No farm is loaded yet" not in str(exc):
            raise
        return {
            "status": "needs_setup",
            "workflow": "farm_onboarding",
            "onboarding_status": {
                "farm_ready": False,
                "herd_ready": False,
                "paddocks_ready": False,
                "herd_position_ready": False,
                "complete": False,
            },
            "farm": None,
            "herds": [],
            "land_units": [],
            "paddocks": [],
            "latest_plan": None,
            "recent_observations": [],
            "missing": list(ONBOARDING_FIELDS),
            "next_question": _next_question(list(ONBOARDING_FIELDS)),
        }
    return _summary_from_state(state)


def handle_save_farm_onboarding(args: dict[str, object]) -> dict[str, Any]:
    """Save first-run farm setup through the canonical onboarding tool."""

    result = _load_json_tool_result("setup_initial_farm", args)
    return _summary_from_state(result)


def handle_record_starting_observation(args: dict[str, object]) -> dict[str, Any]:
    """Record one field note during onboarding and return refreshed status."""

    _load_json_tool_result("record_observation", args)
    farm_id = args.get("farm_id")
    return handle_get_onboarding_status({"farm_id": farm_id} if isinstance(farm_id, str) else {})


def handle_render_onboarding_summary(args: dict[str, object]) -> dict[str, Any]:
    """Return the final structured content the onboarding widget renders."""

    payload = dict(args)
    if "onboarding_status" not in payload:
        payload = handle_get_onboarding_status(payload)
    else:
        missing = payload.get("missing") if isinstance(payload.get("missing"), list) else []
        payload.setdefault("status", "ok")
        payload.setdefault("workflow", "farm_onboarding")
        payload.setdefault("next_question", _next_question([str(item) for item in missing]))
    return payload


def app_tool_payload() -> list[dict[str, Any]]:
    """Return ChatGPT app tool descriptors for review and tests."""

    return [
        {
            "name": "get_onboarding_status",
            "title": "Get onboarding status",
            "description": "Check which farm onboarding details are present or missing. Read-only.",
            "schema": {
                "type": "object",
                "properties": {
                    "farm_id": {
                        "type": "string",
                        "description": "Optional farm id when more than one farm is present.",
                    }
                },
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "openWorldHint": False,
            },
            "_meta": {
                "openai/toolInvocation/invoking": "Checking farm setup...",
                "openai/toolInvocation/invoked": "Checked farm setup.",
            },
        },
        {
            "name": "save_farm_onboarding",
            "title": "Save farm onboarding",
            "description": (
                "Save the initial farm, first herd, paddocks, and current paddock after the farmer "
                "has provided enough setup detail."
            ),
            "schema": onboarding.SETUP_INITIAL_FARM_SCHEMA,
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": False,
                "openWorldHint": False,
            },
            "_meta": {
                "openai/toolInvocation/invoking": "Saving farm setup...",
                "openai/toolInvocation/invoked": "Saved farm setup.",
            },
        },
        {
            "name": "record_starting_observation",
            "title": "Record starting observation",
            "description": (
                "Record one farmer-provided field note during onboarding. Use only when the farmer "
                "explicitly gives an observation to save."
            ),
            "schema": observe.RECORD_OBSERVATION_SCHEMA,
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": False,
                "openWorldHint": False,
            },
            "_meta": {
                "openai/toolInvocation/invoking": "Recording field note...",
                "openai/toolInvocation/invoked": "Recorded field note.",
            },
        },
        {
            "name": "render_onboarding_summary",
            "title": "Render onboarding summary",
            "description": (
                "Render the OpenPasture onboarding summary widget. First call the onboarding data "
                "tools, then pass their structured content to this render tool."
            ),
            "schema": {
                "type": "object",
                "description": "Structured onboarding content returned by the data tools.",
                "properties": {
                    "onboarding_status": {"type": "object"},
                    "farm": {"type": ["object", "null"]},
                    "herds": {"type": "array"},
                    "land_units": {"type": "array"},
                    "paddocks": {"type": "array"},
                    "recent_observations": {"type": "array"},
                    "missing": {"type": "array", "items": {"type": "string"}},
                    "next_question": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "openWorldHint": False,
            },
            "_meta": {
                "ui": {"resourceUri": TEMPLATE_URI},
                "openai/outputTemplate": TEMPLATE_URI,
                "openai/toolInvocation/invoking": "Rendering onboarding summary...",
                "openai/toolInvocation/invoked": "Rendered onboarding summary.",
            },
        },
    ]


def app_resource_payload() -> dict[str, Any]:
    """Return the widget resource descriptor used by the render tool."""

    return {
        "uri": TEMPLATE_URI,
        "mimeType": RESOURCE_MIME_TYPE,
        "text": ONBOARDING_SUMMARY_WIDGET_HTML,
        "_meta": {"ui": {"prefersBorder": True}},
    }


def _supported_kwargs(method: Callable[..., Any], options: dict[str, Any]) -> dict[str, Any]:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return {key: value for key, value in options.items() if key in {"name", "description"}}

    params = signature.parameters
    accepts_extra = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values())
    if accepts_extra:
        return {key: value for key, value in options.items() if key != "_meta"}
    return {key: value for key, value in options.items() if key in params}


def _register_tool(server: Any, descriptor: dict[str, Any], func: Callable[..., Any]) -> None:
    options = {
        "name": descriptor["name"],
        "title": descriptor.get("title"),
        "description": descriptor["description"],
        "annotations": descriptor.get("annotations"),
        "meta": descriptor.get("_meta"),
        "_meta": descriptor.get("_meta"),
        "structured_output": True,
    }
    decorator = server.tool(**_supported_kwargs(server.tool, options))
    decorator(func)


def _register_resource(server: Any) -> None:
    payload = app_resource_payload()
    options = {
        "name": "openpasture-onboarding-summary",
        "title": "OpenPasture onboarding summary",
        "description": "Inline ChatGPT component for farm onboarding progress.",
        "mime_type": RESOURCE_MIME_TYPE,
        "meta": payload["_meta"],
        "_meta": payload["_meta"],
    }
    decorator = server.resource(TEMPLATE_URI, **_supported_kwargs(server.resource, options))

    @decorator
    def openpasture_onboarding_summary_resource() -> str:
        return ONBOARDING_SUMMARY_WIDGET_HTML


def build_chatgpt_app_server(name: str = "OpenPasture Farm Onboarding", **settings: Any):
    """Build the narrow ChatGPT Apps SDK MCP server for farm onboarding."""

    FastMCP = _require_fastmcp()
    server = FastMCP(name, **settings)
    _register_resource(server)

    def get_onboarding_status(farm_id: str | None = None) -> dict[str, Any]:
        return handle_get_onboarding_status({"farm_id": farm_id} if farm_id else {})

    def save_farm_onboarding(
        name: str,
        timezone: str,
        herd: dict[str, Any] | None = None,
        herd_id: str | None = None,
        herd_species: str | None = None,
        herd_count: int | str | None = None,
        paddocks: list[dict[str, Any]] | None = None,
        current_paddock_id: str | None = None,
        current_paddock_name: str | None = None,
        location: dict[str, Any] | None = None,
        boundary: dict[str, Any] | list[Any] | None = None,
        location_hint: str | None = None,
        boundary_hint: str | None = None,
        notes: str | None = None,
        allow_additional_farm: bool = False,
    ) -> dict[str, Any]:
        args = {
            "name": name,
            "timezone": timezone,
            "herd": herd,
            "herd_id": herd_id,
            "herd_species": herd_species,
            "herd_count": herd_count,
            "paddocks": paddocks,
            "current_paddock_id": current_paddock_id,
            "current_paddock_name": current_paddock_name,
            "location": location,
            "boundary": boundary,
            "location_hint": location_hint,
            "boundary_hint": boundary_hint,
            "notes": notes,
            "allow_additional_farm": allow_additional_farm,
        }
        return handle_save_farm_onboarding({key: value for key, value in args.items() if value not in (None, "")})

    def record_starting_observation(
        content: str,
        source: str = "field",
        farm_id: str | None = None,
        paddock_id: str | None = None,
        herd_id: str | None = None,
        observed_at: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        args = {
            "content": content,
            "source": source,
            "farm_id": farm_id,
            "paddock_id": paddock_id,
            "herd_id": herd_id,
            "observed_at": observed_at,
            "tags": tags,
        }
        return handle_record_starting_observation(
            {key: value for key, value in args.items() if value not in (None, "")}
        )

    def render_onboarding_summary(
        onboarding_status: dict[str, Any] | None = None,
        farm: dict[str, Any] | None = None,
        herds: list[dict[str, Any]] | None = None,
        land_units: list[dict[str, Any]] | None = None,
        paddocks: list[dict[str, Any]] | None = None,
        recent_observations: list[dict[str, Any]] | None = None,
        missing: list[str] | None = None,
        next_question: str | None = None,
    ) -> dict[str, Any]:
        args = {
            "onboarding_status": onboarding_status,
            "farm": farm,
            "herds": herds,
            "land_units": land_units,
            "paddocks": paddocks,
            "recent_observations": recent_observations,
            "missing": missing,
            "next_question": next_question,
        }
        return handle_render_onboarding_summary(
            {key: value for key, value in args.items() if value not in (None, "")}
        )

    handlers = {
        "get_onboarding_status": get_onboarding_status,
        "save_farm_onboarding": save_farm_onboarding,
        "record_starting_observation": record_starting_observation,
        "render_onboarding_summary": render_onboarding_summary,
    }
    for descriptor in app_tool_payload():
        _register_tool(server, descriptor, handlers[descriptor["name"]])
    return server


def main() -> None:
    initialize()
    transport = os.environ.get("OPENPASTURE_MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        port = int(os.environ.get("PORT", "8000"))
        server = build_chatgpt_app_server(host="0.0.0.0", port=port)
        server.run(transport="streamable-http")
        return
    server = build_chatgpt_app_server()
    server.run()


if __name__ == "__main__":
    main()
