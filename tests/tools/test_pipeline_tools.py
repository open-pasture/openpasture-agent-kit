from __future__ import annotations

import json
from datetime import datetime

import pytest

from openpasture.domain import Observation
from openpasture.runtime import get_store, initialize
from openpasture.tools.farm import handle_register_farm
from openpasture.tools.pipeline import (
    handle_list_data_pipelines,
    handle_run_data_pipeline,
    handle_save_data_pipeline,
)

pytestmark = pytest.mark.alpha


def _register_farm() -> str:
    initialize()
    result = json.loads(
        handle_register_farm(
            {
                "name": "Pipeline Farm",
                "timezone": "America/Chicago",
            }
        )
    )
    return result["farm"]["id"]


def test_save_data_pipeline_writes_skill_and_persists_pipeline(tmp_path, monkeypatch):
    farm_id = _register_farm()

    monkeypatch.setenv("OPENPASTURE_SKILLS_DIR", str(tmp_path / "skills"))

    saved = json.loads(
        handle_save_data_pipeline(
            {
                "farm_id": farm_id,
                "vendor": "SPYPOINT",
                "login_url": "https://webapp.spypoint.com/",
                "profile_id": f"spypoint-{farm_id}",
                "pipeline_name": "spypoint-wsn-grass-height",
                "collection_goal": "Collect the best daily grass-height image from WSN.",
                "target_urls": ["https://webapp.spypoint.com/shared-cameras"],
                "extraction_prompts": [
                    "Pick the most representative daily image showing the measuring stick and summarize it as JSON."
                ],
                "observation_source": "spypoint",
                "observation_tags": ["trailcam", "grass-height"],
                "navigation_notes": [
                    "Open Shared with me.",
                    "Open the target camera gallery.",
                    "Review the most recent day first.",
                ],
                "known_gotchas": ["Some days may not show the measuring stick clearly."],
            }
        )
    )
    assert saved["status"] == "ok"
    assert saved["pipeline"]["name"] == "spypoint-wsn-grass-height"
    assert saved["pipeline"]["vendor_skill_version"].startswith("sha256:")

    skill_path = tmp_path / "skills" / "pipeline-spypoint" / "SKILL.md"
    assert skill_path.exists()
    skill_text = skill_path.read_text()
    assert "Pipeline SPYPOINT" in skill_text
    assert "Open Shared with me." in skill_text

    stored_pipelines = get_store().list_pipelines(farm_id)
    assert len(stored_pipelines) == 1
    assert stored_pipelines[0].profile_id == f"spypoint-{farm_id}"


def test_save_data_pipeline_can_infer_vendor_from_login_url(tmp_path, monkeypatch):
    farm_id = _register_farm()
    monkeypatch.setenv("OPENPASTURE_SKILLS_DIR", str(tmp_path / "skills"))

    saved = json.loads(
        handle_save_data_pipeline(
            {
                "farm_id": farm_id,
                "login_url": "https://webapp.spypoint.com/",
                "target_urls": ["https://webapp.spypoint.com/shared-cameras"],
                "extraction_prompts": ["Extract one observation as JSON."],
            }
        )
    )
    assert saved["status"] == "ok"
    assert saved["pipeline"]["profile_id"] == f"spypoint-{farm_id}"
    assert saved["pipeline"]["observation_source"] == "spypoint"


def test_list_data_pipelines_returns_saved_pipeline(tmp_path, monkeypatch):
    farm_id = _register_farm()
    monkeypatch.setenv("OPENPASTURE_SKILLS_DIR", str(tmp_path / "skills"))

    json.loads(
        handle_save_data_pipeline(
            {
                "farm_id": farm_id,
                "vendor": "SPYPOINT",
                "login_url": "https://webapp.spypoint.com/",
                "target_urls": ["https://webapp.spypoint.com/shared-cameras"],
                "extraction_prompts": ["Extract one observation as JSON."],
            }
        )
    )

    listed = json.loads(handle_list_data_pipelines({"farm_id": farm_id}))
    assert listed["status"] == "ok"
    assert listed["count"] == 1
    assert listed["pipelines"][0]["observation_source"] == "spypoint"


def test_run_data_pipeline_tool_returns_runner_output(tmp_path, monkeypatch):
    farm_id = _register_farm()
    store = get_store()
    monkeypatch.setenv("OPENPASTURE_SKILLS_DIR", str(tmp_path / "skills"))
    json.loads(
        handle_save_data_pipeline(
            {
                "farm_id": farm_id,
                "vendor": "SPYPOINT",
                "login_url": "https://webapp.spypoint.com/",
                "target_urls": ["https://webapp.spypoint.com/shared-cameras"],
                "extraction_prompts": ["Extract one observation as JSON."],
            }
        )
    )
    pipeline_id = store.list_pipelines(farm_id)[0].id

    def fake_collect(self, pipeline_id: str):
        return [
            Observation(
                id="obs_pipeline",
                farm_id=farm_id,
                source="spypoint",
                observed_at=datetime.utcnow(),
                content="Representative grass-height image selected for the day.",
                metrics={"candidate_count": 4},
                tags=["trailcam", "grass-height"],
            )
        ]

    monkeypatch.setattr("openpasture.tools.pipeline.DataPipelineRunner.collect", fake_collect)

    result = json.loads(handle_run_data_pipeline({"pipeline_id": pipeline_id}))
    assert result["status"] == "ok"
    assert result["observation_count"] == 1
    assert result["observations"][0]["source"] == "spypoint"
