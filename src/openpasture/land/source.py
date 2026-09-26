"""The land source protocol: where land reports come from."""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from openpasture.domain import LandReport, LandReportRequest, LandReportSection
from openpasture.domain.clock import utc_now


class LandSource(Protocol):
    """Anything that can answer a land report request.

    Implementations fetch only the requested sections and return every requested
    section, marking the ones they could not fill as unavailable with a reason.
    They should not raise for ordinary provider failures.
    """

    name: str

    def fetch(self, request: LandReportRequest) -> LandReport: ...


def new_report_id() -> str:
    return f"lr_{uuid4().hex[:20]}"


def build_report(
    request: LandReportRequest,
    sections: dict[str, LandReportSection],
    *,
    source: str,
) -> LandReport:
    """Assemble a report, keeping only requested sections and filling gaps."""

    filled = {
        name: sections.get(name) or LandReportSection.unavailable(f"{source} returned no data for this section.")
        for name in request.sections
    }
    return LandReport(
        report_id=new_report_id(),
        geometry=request.geometry,
        as_of=request.as_of or utc_now(),
        sections=filled,
        buffer_meters=request.buffer_meters,
        requested_sections=request.sections,
        cache_key=request.cache_key(),
        source=source,
    )
