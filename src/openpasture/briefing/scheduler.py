"""Scheduling for the decision cycle: one job per herd per decision window."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from logging import getLogger
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from openpasture.domain import DailyBrief
from openpasture.domain.settings import parse_clock_time
from openpasture.store.protocol import FarmStore

if TYPE_CHECKING:
    from openpasture.briefing.engine import DecisionEngine

logger = getLogger(__name__)

DUE_JOB_ID = "decision-due"
DUE_INTERVAL_MINUTES = 5


def parse_brief_time(value: str, *, default: tuple[int, int] = (6, 0)) -> tuple[int, int]:
    """Parse an ``HH:MM`` wall-clock time for the default decision window start."""

    text = value.strip()
    if not text:
        return default
    try:
        return parse_clock_time(text)
    except ValueError as exc:
        raise ValueError("OPENPASTURE_BRIEF_TIME must use HH:MM format as a valid 24-hour clock time.") from exc


def format_scheduled_brief_message(brief: DailyBrief) -> str:
    """Render a concise scheduled message for connector delivery."""

    herd = f" herd `{brief.decision.herd_id}`" if brief.decision.herd_id else ""
    lines = [
        f"Scheduled grazing decision for farm `{brief.farm_id}`{herd}.",
        brief.summary,
    ]
    if brief.highlights:
        lines.append("Highlights:")
        lines.extend(f"- {highlight}" for highlight in brief.highlights[:3])
    if brief.uncertainty_request:
        lines.append(f"Next observation: {brief.uncertainty_request}")
    return "\n".join(lines)


class DecisionScheduler:
    """Runs the decision cycle for each herd at the start of each window.

    A second job every few minutes sends apply_unless_stopped moves whose
    deadline passed and picks up collar confirmations.
    """

    def __init__(
        self,
        store: FarmStore,
        *,
        engine_factory: Callable[[], DecisionEngine],
        deliver_fn: Callable[[str], bool] | None = None,
        default_hour: int = 6,
        default_minute: int = 0,
    ) -> None:
        self.store = store
        self.engine_factory = engine_factory
        self.deliver_fn = deliver_fn
        self.default_hour = default_hour
        self.default_minute = default_minute
        self._scheduler = BackgroundScheduler(timezone="UTC")

    def set_delivery_handler(self, deliver_fn: Callable[[str], bool] | None) -> None:
        self.deliver_fn = deliver_fn

    @staticmethod
    def job_id(farm_id: str, herd_id: str) -> str:
        return f"decision-cycle:{farm_id}:{herd_id}"

    def _ensure_started(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
        if self._scheduler.get_job(DUE_JOB_ID) is None:
            self._scheduler.add_job(
                self.process_due,
                trigger=IntervalTrigger(minutes=DUE_INTERVAL_MINUTES),
                id=DUE_JOB_ID,
                replace_existing=True,
                misfire_grace_time=600,
            )

    def schedule(self, farm_id: str, timezone: str, hour: int | None = None, minute: int | None = None) -> None:
        """(Re)schedule every herd on the farm from its decision settings."""

        self._ensure_started()
        engine = self.engine_factory()
        try:
            zone = ZoneInfo(timezone)
        except Exception:
            zone = ZoneInfo("UTC")
        for herd in self.store.get_herds(farm_id):
            settings = engine.settings_for(farm_id, herd.id)
            start_hour, start_minute = parse_clock_time(settings.window_start_time)
            if hour is not None:
                start_hour, start_minute = hour, self.default_minute if minute is None else minute
            window_hours = settings.window_hours
            if window_hours <= 24 and 24 % window_hours == 0:
                hours = sorted({(start_hour + step * window_hours) % 24 for step in range(24 // window_hours)})
                trigger = CronTrigger(hour=",".join(str(item) for item in hours), minute=start_minute, timezone=zone)
            else:
                trigger = IntervalTrigger(hours=window_hours, timezone=zone)
            self._scheduler.add_job(
                self.run_cycle_now,
                trigger=trigger,
                id=self.job_id(farm_id, herd.id),
                replace_existing=True,
                kwargs={"farm_id": farm_id, "herd_id": herd.id},
                misfire_grace_time=3600,
            )

    def run_cycle_now(
        self,
        farm_id: str,
        herd_id: str | None = None,
        *,
        for_date: date | None = None,
    ) -> DailyBrief:
        engine = self.engine_factory()
        now = None
        if for_date is not None:
            farm = self.store.get_farm(farm_id)
            if farm is not None:
                now = engine.moment_for_date(farm, herd_id, for_date)
        result, context = engine.run_cycle(farm_id, herd_id, now=now)
        brief = engine.build_brief(result.decision, context)
        self.store.save_daily_brief(brief)
        self._deliver(brief)
        return brief

    def run_brief_now(self, farm_id: str, *, for_date: date | None = None) -> DailyBrief:
        """Run the cycle for the farm's first herd and deliver the brief."""

        return self.run_cycle_now(farm_id, None, for_date=for_date)

    def process_due(self) -> None:
        try:
            self.engine_factory().process_due()
        except Exception:
            logger.exception("Processing due grazing decisions failed.")

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
