from __future__ import annotations

import json

import pytest

from openpasture.runtime import build_session_context, initialize, pre_llm_call, set_active_farm_id
from openpasture.tools.onboarding import handle_setup_initial_farm

pytestmark = pytest.mark.alpha


def test_session_context_surfaces_missing_firecrawl_notice(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    initialize()

    context = build_session_context()

    assert "FIRECRAWL_API_KEY" in context
    assert "Workflow mode: onboarding" in context
    assert "Do not call setup_initial_farm with empty args." in context
    assert "Preferred setup_initial_farm payload shape:" in context
    assert "No active farm is loaded yet." in context


def test_session_context_switches_to_daily_operations_after_setup():
    initialize()

    json.loads(
        handle_setup_initial_farm(
            {
                "name": "Runtime Farm",
                "timezone": "America/Chicago",
                "herd": {"id": "herd_1", "species": "cattle", "count": 20},
                "paddocks": [
                    {
                        "id": "paddock_home",
                        "name": "Home",
                        "status": "grazing",
                    }
                ],
            }
        )
    )

    context = build_session_context()

    assert "Workflow mode: daily-operations" in context
    assert "Active farm: Runtime Farm" in context
    assert "Active farm id:" in context
    assert "Primary herd id: herd_1" in context
    assert "Known paddocks: paddock_home (Home)" in context


def test_session_context_rehydrates_single_farm_when_active_id_is_cleared():
    initialize()

    json.loads(
        handle_setup_initial_farm(
            {
                "name": "Rehydrate Farm",
                "timezone": "America/Chicago",
                "herd": {"id": "herd_2", "species": "cattle", "count": 12},
                "paddocks": [
                    {
                        "id": "paddock_south",
                        "name": "South",
                        "status": "grazing",
                    }
                ],
            }
        )
    )
    set_active_farm_id(None)

    context = build_session_context()

    assert "Active farm: Rehydrate Farm" in context
    assert "Active farm id:" in context
    assert "Known paddocks: paddock_south (South)" in context


def test_pre_llm_call_keeps_explicit_setup_guardrails_on_first_run():
    initialize()

    prompt = pre_llm_call()

    assert "Live tool guardrails:" in prompt
    assert "call setup_initial_farm immediately" in prompt
    assert "Never probe setup_initial_farm with empty args or {}." in prompt


def test_pre_llm_call_switches_to_daily_guardrails_after_setup():
    initialize()

    json.loads(
        handle_setup_initial_farm(
            {
                "name": "Guardrail Farm",
                "timezone": "America/Chicago",
                "herd": {"id": "herd_guard", "species": "cattle", "count": 15},
                "paddocks": [
                    {
                        "id": "paddock_guard",
                        "name": "Guard",
                        "status": "grazing",
                    }
                ],
            }
        )
    )

    prompt = pre_llm_call()

    assert "For daily operations, prefer the active farm context" in prompt
    assert "Never probe setup_initial_farm with empty args or {}." not in prompt
