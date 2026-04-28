"""MCP connector for openPasture.

The MCP package is optional so the agent kit and Hermes adapter remain
installable without MCP runtime dependencies.
"""

from __future__ import annotations

import json
from typing import Any

from openpasture.skills import list_skills, read_skill
from openpasture.toolkit import list_tool_specs, run_tool


def _require_fastmcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The openPasture MCP connector requires the optional 'mcp' dependency. "
            "Install with `pip install openpasture[mcp]`."
        ) from exc
    return FastMCP


def _tool_payload() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "schema": spec.schema,
            "tags": list(spec.tags),
            "related_skills": list(spec.related_skills),
        }
        for spec in list_tool_specs()
    ]


def build_mcp_server(name: str = "openPasture"):
    """Build an MCP server exposing openPasture tools and skill resources."""

    FastMCP = _require_fastmcp()
    server = FastMCP(name)

    @server.tool()
    def list_openpasture_tools() -> str:
        """List available openPasture farm operating tools."""

        return json.dumps({"tools": _tool_payload()}, indent=2, sort_keys=True)

    @server.tool()
    def run_openpasture_tool(tool_name: str, arguments_json: str = "{}") -> str:
        """Run one openPasture tool with a JSON argument object."""

        args = json.loads(arguments_json)
        if not isinstance(args, dict):
            raise ValueError("arguments_json must decode to a JSON object.")
        return run_tool(tool_name, args)

    @server.tool()
    def list_openpasture_skills() -> str:
        """List portable openPasture skills available to this agent."""

        skills = [
            {
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "resource_uri": f"openpasture://skills/{skill.name}",
            }
            for skill in list_skills()
        ]
        return json.dumps({"skills": skills}, indent=2, sort_keys=True)

    @server.tool()
    def read_openpasture_skill(skill_name: str) -> str:
        """Read one portable openPasture skill by name."""

        return read_skill(skill_name)

    @server.resource("openpasture://tools")
    def openpasture_tools_resource() -> str:
        return json.dumps({"tools": _tool_payload()}, indent=2, sort_keys=True)

    @server.resource("openpasture://skills/{skill_name}")
    def openpasture_skill_resource(skill_name: str) -> str:
        return read_skill(skill_name)

    return server


def main() -> None:
    build_mcp_server().run()


if __name__ == "__main__":
    main()
