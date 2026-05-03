from __future__ import annotations

from openpasture.connectors import cloud_sync, mcp_chatgpt_app


def test_chatgpt_app_tool_surface_is_narrow_and_annotated():
    tools = {tool["name"]: tool for tool in mcp_chatgpt_app.app_tool_payload()}

    assert list(tools) == [
        "get_onboarding_status",
        "save_farm_onboarding",
        "record_starting_observation",
        "render_onboarding_summary",
    ]
    assert tools["get_onboarding_status"]["annotations"]["readOnlyHint"] is True
    assert tools["save_farm_onboarding"]["annotations"]["readOnlyHint"] is False
    assert tools["record_starting_observation"]["annotations"]["openWorldHint"] is False

    render_tool = tools["render_onboarding_summary"]
    assert render_tool["annotations"]["readOnlyHint"] is True
    assert render_tool["_meta"]["openai/outputTemplate"] == mcp_chatgpt_app.TEMPLATE_URI
    assert render_tool["_meta"]["ui"]["resourceUri"] == mcp_chatgpt_app.TEMPLATE_URI


def test_chatgpt_app_registers_onboarding_widget_resource():
    resource = mcp_chatgpt_app.app_resource_payload()

    assert resource["uri"] == mcp_chatgpt_app.TEMPLATE_URI
    assert resource["mimeType"] == mcp_chatgpt_app.RESOURCE_MIME_TYPE
    assert 'method, params }, "*"' in resource["text"]
    assert 'rpcRequest("ui/initialize", {})' in resource["text"]
    assert 'rpcRequest("tools/call"' in resource["text"]
    assert 'method: "ui/message"' in resource["text"]
    assert "ui/notifications/tool-result" in resource["text"]
    assert "ui/notifications/tool-input" in resource["text"]
    assert "OpenPasture farm onboarding" in resource["text"]


def test_onboarding_status_before_setup_prompts_for_minimum_details():
    status = mcp_chatgpt_app.handle_get_onboarding_status({})

    assert status["status"] == "needs_setup"
    assert status["onboarding_status"]["complete"] is False
    assert status["missing"] == ["farm", "timezone", "herd", "paddocks", "current_paddock"]
    assert "farm name and timezone" in status["next_question"]


def test_save_onboarding_and_render_summary_returns_ui_ready_payload():
    status = mcp_chatgpt_app.handle_save_farm_onboarding(
        {
            "name": "Willow Creek",
            "timezone": "America/Chicago",
            "herd": {"id": "herd_1", "species": "cattle", "count": 28},
            "paddocks": [
                {"id": "paddock_home", "name": "Home", "status": "grazing"},
                {"id": "paddock_north", "name": "North", "status": "resting"},
            ],
            "current_paddock_id": "paddock_home",
        }
    )

    assert status["status"] == "ok"
    assert status["onboarding_status"]["complete"] is True
    assert status["farm"]["name"] == "Willow Creek"
    assert len(status["herds"]) == 1
    assert len(status["paddocks"]) == 2

    rendered = mcp_chatgpt_app.handle_render_onboarding_summary(status)
    assert rendered["workflow"] == "farm_onboarding"
    assert rendered["onboarding_status"]["complete"] is True
    assert "field note" in rendered["next_question"]


def test_save_onboarding_with_maps_pin_location_syncs_cloud_batches(monkeypatch):
    monkeypatch.setenv("CONVEX_SYNC_URL", "https://openpasture.example/sync")
    monkeypatch.setenv("CONVEX_SYNC_KEY", "tenant_sync_key")
    captured_batches = []

    def fake_post_sync_batch(sync_url, tenant_key, table, records):
        captured_batches.append(
            {
                "sync_url": sync_url,
                "tenant_key": tenant_key,
                "table": table,
                "records": records,
            }
        )

    monkeypatch.setattr(cloud_sync, "_post_sync_batch", fake_post_sync_batch)

    status = mcp_chatgpt_app.handle_save_farm_onboarding(
        {
            "name": "Pinned Pastures",
            "timezone": "America/Chicago",
            "location": {"type": "Point", "coordinates": [-95.2345, 36.4567]},
            "location_hint": "Google Maps screenshot with a dropped pin at 36.4567, -95.2345.",
            "herd": {"id": "herd_maps", "species": "cattle", "count": 18},
            "paddocks": [
                {
                    "id": "paddock_home",
                    "name": "Home",
                    "status": "grazing",
                    "geometry": [
                        {"longitude": -95.235, "latitude": 36.456},
                        {"longitude": -95.234, "latitude": 36.456},
                        {"longitude": -95.234, "latitude": 36.457},
                    ],
                }
            ],
            "current_paddock_id": "paddock_home",
        }
    )

    assert status["onboarding_status"]["complete"] is True
    assert status["farm"]["location"] == {"type": "Point", "coordinates": [-95.2345, 36.4567]}
    assert "Google Maps screenshot" in status["farm"]["notes"]
    assert status["cloud_sync"]["status"] == "ok"

    assert [batch["table"] for batch in captured_batches] == ["farms", "landUnits", "herds"]
    farm_record = captured_batches[0]["records"][0]
    assert farm_record["agentFarmId"] == status["farm"]["id"]
    assert farm_record["location"] == {"type": "Point", "coordinates": [-95.2345, 36.4567]}
    assert farm_record["notes"] == status["farm"]["notes"]

    paddock_record = captured_batches[1]["records"][0]
    assert paddock_record["agentLandUnitId"] == "paddock_home"
    assert paddock_record["unitType"] == "paddock"
    assert paddock_record["geometry"]["type"] == "Feature"
    assert paddock_record["geometry"]["geometry"]["type"] == "Polygon"

    herd_record = captured_batches[2]["records"][0]
    assert herd_record["agentHerdId"] == "herd_maps"
    assert herd_record["currentPaddockId"] == "paddock_home"



def test_save_onboarding_refines_existing_farm_without_duplicate_herds():
    first = mcp_chatgpt_app.handle_save_farm_onboarding(
        {
            "name": "Elm Spring",
            "timezone": "America/Chicago",
            "location": {"type": "Point", "coordinates": [-95.1, 36.1]},
            "herd": {"id": "herd_existing", "species": "cattle", "count": 18},
            "paddocks": [{"id": "paddock_home", "name": "Home", "status": "grazing"}],
        }
    )

    refined = mcp_chatgpt_app.handle_save_farm_onboarding(
        {
            "name": "Elm Spring Pastures",
            "timezone": "America/Chicago",
            "location_hint": "Screenshot shows the farm, but the coordinates are not visible.",
            "herd": {"id": "herd_new", "species": "cattle", "count": 20},
            "paddocks": [{"id": "paddock_home", "name": "Home", "status": "grazing"}],
            "current_paddock_id": "paddock_home",
        }
    )

    assert refined["status"] == "ok"
    assert refined["farm"]["id"] == first["farm"]["id"]
    assert refined["farm"]["name"] == "Elm Spring Pastures"
    assert refined["farm"]["location"] == {"type": "Point", "coordinates": [-95.1, 36.1]}
    assert [herd["id"] for herd in refined["herds"]] == ["herd_existing"]
    assert refined["herds"][0]["current_paddock_id"] == "paddock_home"

def test_record_starting_observation_refreshes_onboarding_summary():
    status = mcp_chatgpt_app.handle_save_farm_onboarding(
        {
            "name": "Willow Creek",
            "timezone": "America/Chicago",
            "herd": {"id": "herd_1", "species": "cattle", "count": 28},
            "paddocks": [{"id": "paddock_home", "name": "Home", "status": "grazing"}],
            "current_paddock_id": "paddock_home",
        }
    )

    refreshed = mcp_chatgpt_app.handle_record_starting_observation(
        {
            "farm_id": status["farm"]["id"],
            "source": "field",
            "content": "Grass is knee high in Home paddock.",
            "paddock_id": "paddock_home",
            "herd_id": "herd_1",
        }
    )

    assert refreshed["onboarding_status"]["complete"] is True
    assert len(refreshed["recent_observations"]) == 1
    assert refreshed["recent_observations"][0]["content"] == "Grass is knee high in Home paddock."
