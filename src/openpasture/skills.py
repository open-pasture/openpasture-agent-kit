"""Portable skill discovery for openPasture connectors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpasture.context import get_skills_dir


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    version: str | None
    path: Path


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    try:
        _, raw, _ = text.split("---", maxsplit=2)
    except ValueError:
        return {}
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", maxsplit=1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def list_skills(skills_dir: Path | None = None) -> list[SkillSpec]:
    root = skills_dir or get_skills_dir()
    specs: list[SkillSpec] = []
    if not root.exists():
        return specs
    for path in sorted(root.glob("*/SKILL.md")):
        text = path.read_text()
        fields = _parse_frontmatter(text)
        specs.append(
            SkillSpec(
                name=fields.get("name") or path.parent.name,
                description=fields.get("description") or "",
                version=fields.get("version"),
                path=path,
            )
        )
    return specs


def get_skill(name: str, skills_dir: Path | None = None) -> SkillSpec:
    for spec in list_skills(skills_dir):
        if spec.name == name:
            return spec
    raise KeyError(f"Unknown openPasture skill '{name}'.")


def read_skill(name: str, skills_dir: Path | None = None) -> str:
    return get_skill(name, skills_dir).path.read_text()
