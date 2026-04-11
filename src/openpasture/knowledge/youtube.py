"""Transcript acquisition helpers for curated video sources."""

from __future__ import annotations


class YouTubeTranscriptFetcher:
    """Fetches transcript content and source metadata for a YouTube URL."""

    def fetch(self, url: str) -> dict[str, object]:
        raise NotImplementedError("YouTube transcript fetching is not implemented yet.")
