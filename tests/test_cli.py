from __future__ import annotations

import json

from openpasture.cli import main


def test_cli_lists_tools(capsys):
    exit_code = main(["tools", "list"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    names = {tool["name"] for tool in payload["tools"]}
    assert "setup_initial_farm" in names
    assert "generate_morning_brief" in names


def test_cli_runs_tool_with_json(capsys):
    exit_code = main(
        [
            "tool",
            "run",
            "setup_initial_farm",
            "--json",
            json.dumps(
                {
                    "name": "CLI Farm",
                    "timezone": "America/Chicago",
                    "herd": {"id": "herd_cli", "species": "cattle", "count": 12},
                    "paddocks": [{"id": "paddock_cli", "name": "CLI Paddock", "status": "grazing"}],
                }
            ),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["farm"]["name"] == "CLI Farm"


def test_cli_lists_skills(capsys):
    exit_code = main(["skills", "list"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    names = {skill["name"] for skill in payload["skills"]}
    assert "rotation-planning" in names
