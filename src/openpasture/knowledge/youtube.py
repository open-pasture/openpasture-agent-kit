"""Transcript acquisition helpers for curated video sources."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


class YouTubeTranscriptFetcher:
    """Fetches transcript content and source metadata for a YouTube URL."""

    def _extract_video_id(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.hostname in {"youtu.be"}:
            return parsed.path.strip("/")
        if parsed.hostname and "youtube" in parsed.hostname:
            query = parse_qs(parsed.query)
            if "v" in query:
                return query["v"][0]
        raise ValueError("Could not determine a YouTube video ID from the provided URL.")

    def fetch(self, url: str) -> dict[str, object]:
        video_id = self._extract_video_id(url)
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError as exc:
            raise RuntimeError(
                "youtube-transcript-api is not installed. Install project dependencies to use ingest_youtube."
            ) from exc

        transcript_fragments = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = "\n".join(fragment["text"] for fragment in transcript_fragments)
        return {
            "url": url,
            "video_id": video_id,
            "title": f"YouTube video {video_id}",
            "author": "Unknown",
            "transcript": transcript,
        }
