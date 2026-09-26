"""Time helpers shared by the decision record, land reports, and collar data.

Older records use naive UTC datetimes. Newer records carry a timezone. These
helpers let both compare safely: a naive value is always treated as UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current time as an aware UTC datetime."""

    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime, treating naive values as UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_text(value: datetime) -> str:
    """Return a sortable UTC ISO string for storage indexes and range filters."""

    return as_utc(value).isoformat(timespec="seconds")


def parse_datetime(value: object) -> datetime | None:
    """Parse an ISO 8601 string (``Z`` allowed) or pass a datetime through."""

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.strip())
    raise ValueError("Datetime must be an ISO 8601 string.")


def iso_or_none(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()
