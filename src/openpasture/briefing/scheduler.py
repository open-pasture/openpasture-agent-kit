"""Scheduling helpers for recurring agent-driven workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from logging import getLogger
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from openpasture.briefing.assembler import MorningBriefAssembler
from openpasture.domain import DailyBrief
from openpasture.store.protocol import FarmStore

logger = getLogger(__name__)


def parse_brief_time(value: str, *, default: tuple[int, int] = (6, 0)) -> tuple[int, int]:
    """Parse an ``HH:MM`` wall-clock time for recurring brief delivery."""

    text = value.strip()
    if not text:
        return default
    try:
        hour_text, minute_text = text.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise ValueError("OPENPASTURE_BRIEF_TIME must use HH:MM format.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("OPENPASTURE_BRIEF_TIME must be a valid 24-hour clock time.")
    return hour, minute


def format_scheduled_brief_message(brief: DailyBrief) -> str:
    """Render a concise scheduled message for Hermes delivery."""

    lines = [
        f"Scheduled morning brief for farm `{brief.farm_id}`.",
        brief.summary,
    ]
    if brief.highlights:
        lines.append("Highlights:")
        lines.extend(f"- {highlight}" for highlight in brief.highlights[:3])
    if brief.uncertainty_request:
        lines.append(f"Next observation: {brief.uncertainty_request}")
    return "\n".join(lines)


class MorningBriefScheduler:
    """Schedules recurring morning brief jobs for one or more farms."""

    def __init__(
        self,
        store: FarmStore,
        *,
        deliver_fn: Callable[[str], bool] | None = None,
        default_hour: int = 6,
        default_minute: int = 0,
    ) -> None:
        self.store = store
        self.deliver_fn = deliver_fn
        self.default_hour = default_hour
        self.default_minute = default_minute
        self._scheduler = BackgroundScheduler(timezone="UTC")

    def set_delivery_handler(self, deliver_fn: Callable[[str], bool] | None) -> None:
        self.deliver_fn = deliver_fn

    def schedule(self, farm_id: str, timezone: str, hour: int | None = None, minute: int | None = None) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
        trigger = CronTrigger(
            hour=self.default_hour if hour is None else hour,
            minute=self.default_minute if minute is None else minute,
            timezone=ZoneInfo(timezone),
        )
        self._scheduler.add_job(
            self.run_brief_now,
            trigger=trigger,
            id=self._job_id(farm_id),
            replace_existing=True,
            kwargs={"farm_id": farm_id},
            misfire_grace_time=3600,
        )

    def run_brief_now(self, farm_id: str, *, for_date: date | None = None) -> DailyBrief:
        brief = MorningBriefAssembler(store=self.store).assemble(farm_id=farm_id, for_date=for_date)
        self.store.create_plan(brief.recommendation)
        self.store.save_daily_brief(brief)
        self._deliver(brief)
        return brief

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def _deliver(self, brief: DailyBrief) -> None:
        if self.deliver_fn is None:
            return
        message = format_scheduled_brief_message(brief)
        try:
            delivered = self.deliver_fn(message)
        except Exception:
            logger.exception("Failed to deliver scheduled brief for farm '%s'.", brief.farm_id)
            return
        if not delivered:
            logger.info("Scheduled brief for farm '%s' was saved but not delivered.", brief.farm_id)

    @staticmethod
    def _job_id(farm_id: str) -> str:
        return f"morning-brief:{farm_id}"
