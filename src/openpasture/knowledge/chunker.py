"""Lesson extraction for practitioner knowledge sources."""

from __future__ import annotations

import re
from datetime import datetime

from openpasture.domain import KnowledgeEntry, SourceRecord


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


class LessonExtractor:
    """Turns raw transcript text into structured knowledge entries."""

    def _split_sections(self, transcript: str) -> list[tuple[str, str]]:
        lines = transcript.splitlines()
        sections: list[tuple[str, list[str]]] = []
        current_heading = "Overview"
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                if current_lines:
                    sections.append((current_heading, current_lines))
                current_heading = stripped.removeprefix("## ").strip()
                current_lines = []
                continue
            if stripped.startswith("# "):
                continue
            current_lines.append(stripped)

        if current_lines:
            sections.append((current_heading, current_lines))

        return [
            (heading, "\n".join(line for line in body if line).strip())
            for heading, body in sections
            if any(line for line in body)
        ]

    def _classify(self, heading: str, content: str) -> str:
        sample = f"{heading} {content}".lower()
        if any(word in sample for word in ("mistake", "avoid", "don't", "do not", "never")):
            return "mistake"
        if any(word in sample for word in ("signal", "look for", "watch", "behavior", "indicates")):
            return "signal"
        if any(word in sample for word in ("rule", "principle", "bias", "matters", "philosophy")):
            return "principle"
        return "technique"

    def _tags(self, heading: str, content: str) -> list[str]:
        sample = f"{heading} {content}".lower()
        tags: list[str] = []
        if "rest" in sample or "recovery" in sample:
            tags.append("recovery")
        if "move" in sample or "rotation" in sample:
            tags.append("movement")
        if "animal" in sample or "rumen" in sample or "behavior" in sample:
            tags.append("animal-signals")
        if "residual" in sample or "top-third" in sample or "forage" in sample:
            tags.append("forage")
        return tags

    def extract(
        self,
        transcript: str,
        source_title: str,
        source_author: str,
        source_url: str = "",
        source_kind: str = "youtube",
    ) -> list[KnowledgeEntry]:
        sections = self._split_sections(transcript)
        if not sections and transcript.strip():
            sections = [(source_title, transcript.strip())]

        entries: list[KnowledgeEntry] = []
        for index, (heading, content) in enumerate(sections, start=1):
            normalized = " ".join(content.split())
            if len(normalized) < 24:
                continue
            entry_id = f"knowledge_{_slugify(source_title)}_{index:02d}_{_slugify(heading)[:32]}"
            entries.append(
                KnowledgeEntry(
                    id=entry_id,
                    farm_id=None,
                    entry_type=self._classify(heading, normalized),
                    content=normalized,
                    sources=[
                        SourceRecord(
                            source_url=source_url,
                            source_title=source_title,
                            source_author=source_author,
                            source_kind=source_kind,
                            segment=heading,
                        )
                    ],
                    created_at=datetime.utcnow(),
                    tags=self._tags(heading, normalized),
                    category="grazing-management",
                )
            )
        return entries
