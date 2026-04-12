from __future__ import annotations

from openpasture.runtime import build_session_context, initialize


def test_session_context_surfaces_missing_firecrawl_notice(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    initialize()

    context = build_session_context()

    assert "FIRECRAWL_API_KEY" in context
    assert "No active farm is loaded yet." in context
