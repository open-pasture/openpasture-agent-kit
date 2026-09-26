"""Alexandria land source over the Firecrawl API.

Alexandria runs tools through Firecrawl's scrape endpoint: the request carries an
``alexandria`` parameter naming the provider and capability, with the land
report request as options. Base URL, provider, and capability are configurable
because the tool catalog is still settling.
"""

from __future__ import annotations

import os
from logging import getLogger
from typing import Mapping

import httpx

from openpasture.domain import LandReport, LandReportRequest, LandReportSection
from openpasture.domain.clock import utc_now
from openpasture.land.source import build_report

logger = getLogger(__name__)

DEFAULT_BASE_URL = "https://api.firecrawl.dev"
DEFAULT_SCRAPE_PATH = "/v2/scrape"
DEFAULT_PROVIDER = "alexandria"
DEFAULT_CAPABILITY = "land_report"


class AlexandriaLandSource:
    """Fetches land reports from Alexandria and maps them into ``LandReport``."""

    name = "alexandria"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        provider: str | None = None,
        capability: str | None = None,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("AlexandriaLandSource needs a Firecrawl API key.")
        self.api_key = api_key.strip()
        self.base_url = (base_url or os.environ.get("OPENPASTURE_ALEXANDRIA_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.provider = provider or os.environ.get("OPENPASTURE_ALEXANDRIA_LAND_PROVIDER") or DEFAULT_PROVIDER
        self.capability = (
            capability or os.environ.get("OPENPASTURE_ALEXANDRIA_LAND_CAPABILITY") or DEFAULT_CAPABILITY
        )
        self.timeout = timeout
        self.client = client

    @classmethod
    def from_env(cls) -> "AlexandriaLandSource | None":
        api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
        return cls(api_key) if api_key else None

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}{DEFAULT_SCRAPE_PATH}"

    def request_body(self, request: LandReportRequest) -> dict[str, object]:
        return {
            "alexandria": {
                "provider": self.provider,
                "capability": self.capability,
                "options": request.to_contract(),
            }
        }

    def fetch(self, request: LandReportRequest) -> LandReport:
        try:
            payload = self._post(self.request_body(request))
        except Exception as exc:  # network, HTTP status, or JSON errors
            logger.warning("Alexandria land report failed: %s", exc)
            reason = f"Alexandria request failed: {exc}"
            return build_report(
                request,
                {name: LandReportSection.unavailable(reason) for name in request.sections},
                source=self.name,
            )
        return self.map_response(request, payload)

    def _post(self, body: dict[str, object]) -> object:
        headers = {"authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        if self.client is not None:
            response = self.client.post(self.endpoint, json=body, headers=headers, timeout=self.timeout)
        else:
            response = httpx.post(self.endpoint, json=body, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def map_response(self, request: LandReportRequest, payload: object) -> LandReport:
        """Map an Alexandria response into a report with only the requested sections."""

        report = _find_report(payload)
        raw_sections = report.get("sections") if isinstance(report.get("sections"), Mapping) else report
        default_sources = report.get("sources") if isinstance(report.get("sources"), list) else None
        sections: dict[str, LandReportSection] = {}
        for name in request.sections:
            raw = raw_sections.get(name) if isinstance(raw_sections, Mapping) else None
            if not isinstance(raw, Mapping):
                sections[name] = LandReportSection.unavailable("Alexandria returned no data for this section.")
                continue
            section = LandReportSection.from_contract(raw)
            if section.ok and not section.sources:
                section.sources = list(default_sources or [
                    {"provider": f"alexandria:{self.provider}/{self.capability}", "retrieved_at": utc_now().isoformat()}
                ])
            sections[name] = section
        built = build_report(request, sections, source=self.name)
        if isinstance(report.get("report_id"), str):
            built.report_id = str(report["report_id"])
        return built


def _find_report(payload: object) -> Mapping[str, object]:
    """Find the report object inside a Firecrawl envelope."""

    if not isinstance(payload, Mapping):
        return {}
    candidates: list[object] = [payload]
    data = payload.get("data")
    if isinstance(data, Mapping):
        candidates = [data.get("alexandria"), data.get("result"), data.get("json"), data, payload]
    for candidate in candidates:
        if isinstance(candidate, Mapping) and (
            "sections" in candidate or any(key in candidate for key in ("weather", "imagery", "soil"))
        ):
            return candidate
    return {}
