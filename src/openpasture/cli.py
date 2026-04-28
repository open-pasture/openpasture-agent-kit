"""Agent-friendly command line interface for openPasture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from openpasture.context import OpenPastureContext, initialize
from openpasture.skills import list_skills, read_skill
from openpasture.toolkit import list_tool_specs, run_tool


def _emit(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _load_json(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("--json must decode to a JSON object.")
    return payload


def _context_from_args(args: argparse.Namespace) -> OpenPastureContext:
    config: dict[str, object] = {}
    if getattr(args, "data_dir", None):
        config["data_dir"] = Path(args.data_dir)
    if getattr(args, "store", None):
        config["store"] = args.store
    return initialize(config or None)


def _tool_records() -> list[dict[str, Any]]:
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


def _skills_records() -> list[dict[str, object]]:
    return [
        {
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "path": str(skill.path),
        }
        for skill in list_skills()
    ]


def _cmd_tools_list(args: argparse.Namespace) -> int:
    _context_from_args(args)
    _emit({"tools": _tool_records()})
    return 0


def _cmd_tool_run(args: argparse.Namespace) -> int:
    _context_from_args(args)
    print(run_tool(args.tool_name, _load_json(args.json)))
    return 0


def _cmd_skills_list(args: argparse.Namespace) -> int:
    _context_from_args(args)
    _emit({"skills": _skills_records()})
    return 0


def _cmd_skills_show(args: argparse.Namespace) -> int:
    _context_from_args(args)
    print(read_skill(args.skill_name))
    return 0


def _cmd_knowledge_search(args: argparse.Namespace) -> int:
    _context_from_args(args)
    payload: dict[str, object] = {"query": args.query}
    if args.limit is not None:
        payload["limit"] = args.limit
    if args.author:
        payload["author"] = args.author
    if args.category:
        payload["category"] = args.category
    print(run_tool("search_knowledge", payload))
    return 0


def _cmd_validate_alpha(args: argparse.Namespace) -> int:
    _context_from_args(args)
    from openpasture.validation.alpha import main as alpha_main

    argv = ["automated" if args.mode is None else args.mode]
    return alpha_main(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openpasture",
        description="Agent kit for the openPasture farm operating toolkit.",
    )
    parser.add_argument("--data-dir", help="Override OPENPASTURE_DATA_DIR for this invocation.")
    parser.add_argument("--store", choices=["sqlite", "convex"], help="Override OPENPASTURE_STORE.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    tools = subparsers.add_parser("tools", help="Inspect available tool capabilities.")
    tools_subparsers = tools.add_subparsers(dest="tools_command", required=True)
    tools_list = tools_subparsers.add_parser("list", help="List tool specs as JSON.")
    tools_list.set_defaults(func=_cmd_tools_list)

    tool = subparsers.add_parser("tool", help="Run one tool.")
    tool_subparsers = tool.add_subparsers(dest="tool_command", required=True)
    tool_run = tool_subparsers.add_parser("run", help="Run one tool with JSON args.")
    tool_run.add_argument("tool_name")
    tool_run.add_argument("--json", default="{}", help="JSON object passed to the tool.")
    tool_run.set_defaults(func=_cmd_tool_run)

    skills = subparsers.add_parser("skills", help="Inspect portable openPasture skills.")
    skills_subparsers = skills.add_subparsers(dest="skills_command", required=True)
    skills_list = skills_subparsers.add_parser("list", help="List skills as JSON.")
    skills_list.set_defaults(func=_cmd_skills_list)
    skills_show = skills_subparsers.add_parser("show", help="Print one skill document.")
    skills_show.add_argument("skill_name")
    skills_show.set_defaults(func=_cmd_skills_show)

    knowledge = subparsers.add_parser("knowledge", help="Knowledge base helpers.")
    knowledge_subparsers = knowledge.add_subparsers(dest="knowledge_command", required=True)
    knowledge_search = knowledge_subparsers.add_parser("search", help="Search stored grazing knowledge.")
    knowledge_search.add_argument("query")
    knowledge_search.add_argument("--limit", type=int)
    knowledge_search.add_argument("--author")
    knowledge_search.add_argument("--category")
    knowledge_search.set_defaults(func=_cmd_knowledge_search)

    validate = subparsers.add_parser("validate", help="Maintainer validation commands.")
    validate_subparsers = validate.add_subparsers(dest="validate_command", required=True)
    validate_alpha = validate_subparsers.add_parser("alpha", help="Run alpha validation.")
    validate_alpha.add_argument("mode", nargs="?", choices=["automated", "docker", "show-target"])
    validate_alpha.set_defaults(func=_cmd_validate_alpha)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        _emit({"status": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
