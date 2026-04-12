from pathlib import Path

from openpasture.knowledge.chunker import LessonExtractor


def test_lesson_extractor_parses_seed_markdown():
    path = Path(__file__).resolve().parents[2] / "seed" / "principles" / "universal.md"
    entries = LessonExtractor().extract(
        transcript=path.read_text(),
        source_title="Universal Grazing Principles",
        source_author="openPasture",
        source_url=str(path),
        source_kind="seed",
    )

    assert entries
    assert any(entry.entry_type == "principle" for entry in entries)
    assert any("move animals daily" in entry.content.lower() for entry in entries)
    assert all(entry.sources for entry in entries)
    assert all(entry.category == "grazing-management" for entry in entries)
