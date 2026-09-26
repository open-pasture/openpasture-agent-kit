from __future__ import annotations

from openpasture.connectors import mcp
from openpasture.skills import list_skills, read_skill
from openpasture.toolkit import get_tool_spec, list_tool_specs, tool_names


def test_tool_catalog_contains_core_farm_capabilities():
    names = tool_names()

    assert "setup_initial_farm" in names
    assert "save_geo_onboarding_draft" in names
    assert "get_farm_geo_state" in names
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
    assert "geo-onboarding" in skills
    assert "Hermes" not in skills["morning-brief"].description
    assert "# Morning Brief" in read_skill("morning-brief")
    assert "Google Maps screenshot" in read_skill("geo-onboarding")


def test_mcp_payload_uses_tool_catalog():
    payload = mcp._tool_payload()

    assert len(payload) == len(list_tool_specs())
    assert any(tool["name"] == "record_observation" for tool in payload)
    assert all("schema" in tool for tool in payload)


DECISION_LOOP_TOOLS = (
    "get_land_report",
    "record_collar_report",
    "get_herd_positions",
    "compute_grazing_signals",
    "assemble_decision_context",
    "submit_grazing_decision",
    "respond_to_decision",
    "get_decision",
    "list_decisions",
    "get_boundary_status",
    "set_autonomy",
    "evaluate_decision_outcome",
    "run_decision_cycle",
)


def test_tool_catalog_exposes_the_decision_loop():
    names = tool_names()

    for name in DECISION_LOOP_TOOLS:
        assert name in names
        spec = get_tool_spec(name)
        assert spec.schema["type"] == "object"
        assert "daily-grazing-decision" in spec.related_skills
    assert "movement_decision" not in names
    assert "approve_plan" not in names


def test_plugin_manifest_lists_every_catalog_tool():
    from pathlib import Path

    manifest = (Path(__file__).resolve().parents[1] / "plugin.yaml").read_text()
    for name in tool_names():
        assert f"  - {name}\n" in manifest
