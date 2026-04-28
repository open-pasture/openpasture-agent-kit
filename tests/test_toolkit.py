from __future__ import annotations

from openpasture.connectors import mcp
from openpasture.skills import list_skills, read_skill
from openpasture.toolkit import get_tool_spec, list_tool_specs, tool_names


def test_tool_catalog_contains_core_farm_capabilities():
    names = tool_names()

    assert "setup_initial_farm" in names
    assert "get_farm_state" in names
    assert "generate_morning_brief" in names
    assert "search_knowledge" in names

    spec = get_tool_spec("generate_morning_brief")
    assert spec.schema["type"] == "object"
    assert "morning-brief" in spec.related_skills


def test_skills_are_discoverable_as_portable_documents():
    skills = {skill.name: skill for skill in list_skills()}

    assert "morning-brief" in skills
    assert "farm-onboarding" in skills
    assert "Hermes" not in skills["morning-brief"].description
    assert "# Morning Brief" in read_skill("morning-brief")


def test_mcp_payload_uses_tool_catalog():
    payload = mcp._tool_payload()

    assert len(payload) == len(list_tool_specs())
    assert any(tool["name"] == "record_observation" for tool in payload)
    assert all("schema" in tool for tool in payload)
