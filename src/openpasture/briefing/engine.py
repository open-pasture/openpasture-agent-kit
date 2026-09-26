"""The decision engine: one decision per herd per decision window.

For each window the engine assembles context, derives grazing signals, takes a
decision (from the agent through ``submit``, or from the fallback heuristic in
``run_cycle``), applies the farmer's autonomy setting, sends the boundary to the
collars, tracks acknowledgements, and evaluates the outcome on later cycles.

Nothing reaches a collar without a recorded decision and the autonomy setting
(or the farmer) allowing it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from logging import getLogger
from typing import Mapping
from zoneinfo import ZoneInfo

from openpasture import calculations
from openpasture.briefing.advisor import HeuristicAdvisor, new_decision_id
from openpasture.briefing.attention_director import AttentionDirector
from openpasture.collars.service import CollarService
from openpasture.domain import (
    BoundaryActivation,
    BoundaryCommand,
    BoundaryTransition,
    CollarSummary,
    DailyBrief,
    DecisionInputs,
    DecisionOutcome,
    DecisionSettings,
    DecisionWindow,
    EffectiveDecisionSettings,
    Farm,
    FarmerResponse,
    GrazingDecision,
    Herd,
    KnowledgeEntry,
    LandReport,
    LandUnit,
    Observation,
    resolve_decision_settings,
)
from openpasture.domain.clock import as_utc, utc_now
from openpasture.domain.geo import point_in_geometry
from openpasture.domain.observation import is_field_observation_source
from openpasture.domain.settings import parse_clock_time
from openpasture.land.service import LandReportService
from openpasture.store.protocol import FarmStore

logger = getLogger(__name__)

DECISION_UNIT_TYPES = {"paddock", "section"}
DEFAULT_DECISION_SECTIONS: dict[str, dict[str, object]] = {
    "weather": {"history_days": 30, "forecast_days": 7},
    "imagery": {"latest": True, "history_days": 90, "products": ["ndvi"]},
    "climate": {"include": ["drought"]},
    "water": {"include": ["floodplain"]},
}
MAX_LAND_REPORTS_PER_CYCLE = 8
# Share of fixes that must fall inside the boundary for "held the line".
HELD_BOUNDARY_SHARE = 0.95
RESIDUAL_KEYS = ("residual_inches", "residual", "height_inches", "forage_height_inches")
RESPONSE_ALIASES = {
    "approve": "approved",
    "approved": "approved",
    "yes": "approved",
    "modify": "modified",
    "modified": "modified",
    "change": "modified",
    "reject": "rejected",
    "rejected": "rejected",
    "stop": "rejected",
    "no": "rejected",
}


def has_real_geometry(unit: LandUnit) -> bool:
    """False for the tiny placeholder shape onboarding uses when no map was given."""

    try:
        box = unit.geometry.bbox()
    except ValueError:
        return False
    placeholder = abs(box.min_longitude) < 1e-9 and abs(box.min_latitude) < 1e-9
    return not placeholder and (unit.area_hectares or 0.0) >= 0.05


@dataclass
class DecisionContext:
    """What the engine (and the agent) sees before deciding."""

    farm: Farm
    herd: Herd | None
    window: DecisionWindow
    settings: EffectiveDecisionSettings
    current_land_unit_id: str | None
    # Where the herd location came from: collar, farm_record, observation, or unknown.
    position_source: str
    land_units: list[LandUnit]
    candidates: list[LandUnit]
    collar_summary: CollarSummary | None
    land_reports: dict[str, LandReport]
    land_report_notes: dict[str, str]
    recent_observations: list[Observation]
    history: list[GrazingDecision]
    relevant_knowledge: list[KnowledgeEntry]
    active_command: BoundaryCommand | None
    signals: dict[str, object] = field(default_factory=dict)

    @property
    def weather_observations(self) -> list[Observation]:
        return [obs for obs in self.recent_observations if obs.source == "weather"]

    def to_dict(self) -> dict[str, object]:
        return {
            "farm_id": self.farm.id,
            "farm_name": self.farm.name,
            "herd": self.herd,
            "window": self.window.to_dict(),
            "settings": self.settings.to_dict(),
            "current_land_unit_id": self.current_land_unit_id,
            "position_source": self.position_source,
            "land_units": [
                {
                    "id": unit.id,
                    "name": unit.name,
                    "unit_type": unit.unit_type,
                    "status": unit.status,
                    "area_hectares": unit.area_hectares,
                    "geometry": unit.geometry.geometry,
                }
                for unit in self.land_units
            ],
            "candidate_land_unit_ids": [unit.id for unit in self.candidates],
            "collar_summary": self.collar_summary,
            "land_reports": {unit_id: report for unit_id, report in self.land_reports.items()},
            "land_report_notes": dict(self.land_report_notes),
            "recent_observations": [obs for obs in self.recent_observations if "land-report" not in obs.tags],
            "history": [
                {
                    "decision_id": item.decision_id,
                    "window": item.window.to_dict(),
                    "action": item.action,
                    "from_land_unit_id": item.from_land_unit_id,
                    "to_land_unit_id": item.land_unit_to_send(),
                    "status": item.status,
                    "farmer_response": item.farmer_response.to_dict() if item.farmer_response else None,
                    "outcome": item.outcome.to_dict() if item.outcome else None,
                }
                for item in self.history
            ],
            "relevant_knowledge": self.relevant_knowledge,
            "active_boundary": self.active_command,
            "signals": self.signals,
        }


@dataclass
class DecisionResult:
    """What happened when a decision was submitted, answered, or sent."""

    decision: GrazingDecision
    command: BoundaryCommand | None = None
    activation: BoundaryActivation | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "boundary_command": self.command,
            "activation": self.activation.to_dict() if self.activation else None,
            "message": self.message,
        }


class DecisionEngine:
    """Owns the decision cycle for every herd on the farm."""

    def __init__(
        self,
        store: FarmStore,
        *,
        land: LandReportService | None,
        collars: CollarService,
        retriever: object | None = None,
        advisor: HeuristicAdvisor | None = None,
        attention_director: AttentionDirector | None = None,
        clock: Callable[[], datetime] | None = None,
        default_window_start_time: str = "06:00",
        default_activation_threshold: float = 1.0,
    ) -> None:
        self.store = store
        self.land = land
        self.collars = collars
        self.retriever = retriever
        self.advisor = advisor or HeuristicAdvisor()
        self.attention_director = attention_director or AttentionDirector(store)
        self.clock = clock or utc_now
        self.default_window_start_time = default_window_start_time
        self.default_activation_threshold = default_activation_threshold

    # -- settings and windows --------------------------------------------

    def settings_for(self, farm_id: str, herd_id: str | None) -> EffectiveDecisionSettings:
        farm_settings = self.store.get_decision_settings(farm_id, None)
        herd_settings = self.store.get_decision_settings(farm_id, herd_id) if herd_id else None
        return resolve_decision_settings(
            farm_id,
            herd_id,
            farm_settings,
            herd_settings,
            default_window_start_time=self.default_window_start_time,
            default_activation_threshold=self.default_activation_threshold,
        )

    def save_settings(self, settings: DecisionSettings) -> EffectiveDecisionSettings:
        existing = self.store.get_decision_settings(settings.farm_id, settings.herd_id)
        if existing is not None:
            for name in (
                "autonomy",
                "send_time",
                "hold_minutes",
                "window_hours",
                "window_start_time",
                "activation_threshold",
            ):
                if getattr(settings, name) is None:
                    setattr(settings, name, getattr(existing, name))
        self.store.save_decision_settings(settings)
        return self.settings_for(settings.farm_id, settings.herd_id)

    @staticmethod
    def _zone(farm: Farm) -> ZoneInfo:
        try:
            return ZoneInfo(farm.timezone)
        except Exception:
            return ZoneInfo("UTC")

    def window_for(self, farm: Farm, settings: EffectiveDecisionSettings, moment: datetime) -> DecisionWindow:
        """The window containing ``moment``. Windows start at the configured local time."""

        zone = self._zone(farm)
        local = as_utc(moment).astimezone(zone)
        hour, minute = parse_clock_time(settings.window_start_time)
        base = datetime.combine(local.date(), time(hour, minute), tzinfo=zone)
        if local < base:
            base -= timedelta(days=1)
        length = timedelta(hours=settings.window_hours)
        if settings.window_hours < 24:
            steps = int((local - base) / length)
            base += steps * length
        return DecisionWindow(starts_at=base, ends_at=base + length)

    def moment_for_date(self, farm: Farm, herd_id: str | None, for_date: date) -> datetime:
        """A time inside the window that starts on ``for_date`` (for date-based callers)."""

        now = self.clock()
        zone = self._zone(farm)
        if as_utc(now).astimezone(zone).date() == for_date:
            return now
        settings = self.settings_for(farm.id, herd_id)
        hour, minute = parse_clock_time(settings.window_start_time)
        return datetime.combine(for_date, time(hour, minute), tzinfo=zone) + timedelta(minutes=1)

    # -- context and signals ---------------------------------------------

    def _farm(self, farm_id: str) -> Farm:
        farm = self.store.get_farm(farm_id)
        if farm is None:
            raise ValueError(f"Farm '{farm_id}' does not exist.")
        return farm

    def resolve_herd(self, farm_id: str, herd_id: str | None) -> Herd | None:
        herds = self.store.get_herds(farm_id)
        if herd_id is None:
            return herds[0] if herds else None
        herd = next((item for item in herds if item.id == herd_id), None)
        if herd is None:
            raise ValueError(f"Herd '{herd_id}' does not exist on farm '{farm_id}'.")
        return herd

    @staticmethod
    def _infer_from_observations(observations: list[Observation], herd_id: str | None) -> str | None:
        for observation in observations:
            if observation.paddock_id and herd_id and observation.herd_id == herd_id:
                return observation.paddock_id
        for observation in observations:
            if observation.paddock_id and "land-report" not in observation.tags:
                return observation.paddock_id
        return None

    def assemble_context(
        self,
        farm_id: str,
        herd_id: str | None = None,
        *,
        now: datetime | None = None,
        fetch_land: bool = True,
        save_summary: bool = False,
        land_unit_ids: list[str] | None = None,
    ) -> DecisionContext:
        now = now or self.clock()
        farm = self._farm(farm_id)
        herd = self.resolve_herd(farm_id, herd_id)
        settings = self.settings_for(farm_id, herd.id if herd else None)
        window = self.window_for(farm, settings, now)
        land_units = [unit for unit in self.store.list_land_units(farm_id) if unit.unit_type in DECISION_UNIT_TYPES]

        collar_summary = None
        if herd is not None:
            lookback = timedelta(hours=settings.window_hours)
            collar_summary = self.collars.summarize(farm_id, herd.id, now - lookback, now, save=save_summary)

        recent_observations = self.store.get_recent_observations(farm_id, days=7)
        if collar_summary is not None and collar_summary.dominant_land_unit_id:
            current_id, position_source = collar_summary.dominant_land_unit_id, "collar"
        elif herd is not None and herd.current_paddock_id:
            current_id, position_source = herd.current_paddock_id, "farm_record"
        elif (inferred := self._infer_from_observations(recent_observations, herd.id if herd else None)) is not None:
            current_id, position_source = inferred, "observation"
        else:
            current_id, position_source = None, "unknown"

        candidates = [unit for unit in land_units if unit.id != current_id]
        land_reports: dict[str, LandReport] = {}
        notes: dict[str, str] = {}
        if fetch_land and self.land is not None:
            wanted = [unit for unit in land_units if unit.id == current_id] + candidates
            if land_unit_ids:
                wanted = [unit for unit in land_units if unit.id in set(land_unit_ids)]
            for unit in wanted[:MAX_LAND_REPORTS_PER_CYCLE]:
                if not has_real_geometry(unit):
                    notes[unit.id] = "No mapped boundary yet, so no land report."
                    continue
                try:
                    report, _cached = self.land.report_for_land_unit(unit, DEFAULT_DECISION_SECTIONS, as_of=now)
                except Exception as exc:
                    logger.warning("Land report failed for '%s': %s", unit.id, exc)
                    notes[unit.id] = f"Land report failed: {exc}"
                    continue
                land_reports[unit.id] = report
            if land_reports:
                # Land report sections were stored as observations; include them.
                recent_observations = self.store.get_recent_observations(farm_id, days=7)

        history = self.store.list_decisions(farm_id, herd_id=herd.id, limit=10) if herd else []
        context = DecisionContext(
            farm=farm,
            herd=herd,
            window=window,
            settings=settings,
            current_land_unit_id=current_id,
            position_source=position_source,
            land_units=land_units,
            candidates=candidates,
            collar_summary=collar_summary,
            land_reports=land_reports,
            land_report_notes=notes,
            recent_observations=recent_observations,
            history=history,
            relevant_knowledge=[],
            active_command=self.collars.active_command(herd.id) if herd else None,
        )
        context.signals = self.compute_signals(context, now=now)
        context.relevant_knowledge = self._knowledge(context)
        return context

    def _knowledge(self, context: DecisionContext) -> list[KnowledgeEntry]:
        if self.retriever is None:
            return []
        flags = " ".join(flag["type"] for flag in context.signals.get("risk_flags", []))  # type: ignore[union-attr]
        field_text = " ".join(
            obs.content.lower() for obs in context.recent_observations if "land-report" not in obs.tags
        )
        query = " ".join(["movement decision", field_text, "recovery residual weather", flags]).strip()
        try:
            return list(self.retriever.search(query or "grazing movement decision", farm_id=context.farm.id, limit=3))  # type: ignore[attr-defined]
        except Exception:
            logger.warning("Knowledge search failed during decision assembly.", exc_info=True)
            return []

    def _last_grazed(self, context: DecisionContext, now: datetime) -> dict[str, datetime | None]:
        last: dict[str, datetime | None] = {unit.id: None for unit in context.land_units}
        for decision in context.history:
            if decision.from_land_unit_id in last and decision.is_move and decision.status in {
                "sent",
                "active",
                "approved",
                "modified",
                "evaluated",
            }:
                moved_at = decision.created_at
                current = last[decision.from_land_unit_id]
                if current is None or as_utc(moved_at) > as_utc(current):
                    last[decision.from_land_unit_id] = moved_at
        if context.herd is not None:
            for summary in self.store.list_collar_summaries(context.herd.id, limit=30):
                for unit_id in summary.land_unit_fix_counts:
                    if unit_id in last:
                        current = last[unit_id]
                        grazed_at = summary.last_fix_at or summary.window_ends_at
                        if current is None or as_utc(grazed_at) > as_utc(current):
                            last[unit_id] = grazed_at
        if context.current_land_unit_id in last:
            last[context.current_land_unit_id] = now  # type: ignore[index]
        return last

    @staticmethod
    def _field_height(observations: list[Observation], unit_id: str) -> float | None:
        for obs in observations:
            if obs.paddock_id != unit_id or not is_field_observation_source(obs.source):
                continue
            for key in RESIDUAL_KEYS:
                value = obs.metrics.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
        return None

    def compute_signals(self, context: DecisionContext, *, now: datetime | None = None) -> dict[str, object]:
        """Grazing signals for the herd and each land unit. See ``openpasture.calculations``."""

        now = now or self.clock()
        herd = context.herd
        window_days = context.settings.window_hours / 24.0
        areas = {unit.id: (unit.area_hectares if has_real_geometry(unit) else None) for unit in context.land_units}

        forage: dict[str, object] = {}
        recovery: dict[str, object] = {}
        risks_by_unit: dict[str, list[dict[str, str]]] = {}
        for unit in context.land_units:
            report = context.land_reports.get(unit.id)
            imagery = report.ok_section("imagery") if report else None
            ndvi = None
            history: list[tuple[datetime, float]] = []
            if imagery:
                stats = imagery.get("ndvi_stats") if isinstance(imagery.get("ndvi_stats"), Mapping) else {}
                ndvi = stats.get("mean") if isinstance(stats.get("mean"), (int, float)) else None  # type: ignore[union-attr]
                for row in imagery.get("history") or []:  # type: ignore[union-attr]
                    if isinstance(row, Mapping) and isinstance(row.get("ndvi_mean"), (int, float)) and row.get("captured_at"):
                        history.append((datetime.fromisoformat(str(row["captured_at"])), float(row["ndvi_mean"])))
                latest = imagery.get("latest") if isinstance(imagery.get("latest"), Mapping) else {}
                if ndvi is not None and latest.get("captured_at"):  # type: ignore[union-attr]
                    history.append((datetime.fromisoformat(str(latest["captured_at"])), float(ndvi)))  # type: ignore[index]
            forage[unit.id] = calculations.forage_estimate(
                ndvi_mean=ndvi, height_inches=self._field_height(context.recent_observations, unit.id)
            )
            recovery[unit.id] = calculations.recovery_trend(history)
            if report is not None:
                risks_by_unit[unit.id] = calculations.risk_flags(
                    {name: report.ok_section(name) for name in report.sections}
                )

        pressure: dict[str, object] = {}
        behavior: dict[str, object] = {}
        if herd is not None and context.collar_summary is not None:
            pressure = calculations.grazing_pressure(
                context.collar_summary.land_unit_fix_counts,
                herd_count=herd.count,
                window_days=window_days,
                area_hectares=areas,
            )
            since = now - timedelta(hours=context.settings.window_hours)
            behavior = calculations.behavior(
                self.store.list_position_fixes(herd.id, since, now),
                self.store.list_cue_events(herd.id, since, now),
                window_days=window_days,
            )

        feed_budget = None
        herd_units = calculations.animal_units(herd.species, herd.count, herd.animal_units) if herd else None
        current_id = context.current_land_unit_id
        if herd_units and current_id and areas.get(current_id):
            available = (forage.get(current_id) or {}).get("available_kg_dm_per_ha")  # type: ignore[union-attr]
            if isinstance(available, (int, float)):
                feed_budget = calculations.feed_budget_days(
                    available_kg_dm=float(available) * float(areas[current_id] or 0.0),
                    herd_animal_units=herd_units,
                )

        current_risks = risks_by_unit.get(current_id or "") or next(iter(risks_by_unit.values()), [])
        return {
            "as_of": now.isoformat(),
            "herd_animal_units": herd_units,
            "rest_days": calculations.rest_days(self._last_grazed(context, now), now),
            "forage": forage,
            "recovery": recovery,
            "grazing_pressure": pressure,
            "feed_budget_days_current": feed_budget,
            "behavior": behavior,
            "risk_flags": current_risks,
            "risk_flags_by_land_unit": risks_by_unit,
            "assumptions": [
                "Forage from imagery maps NDVI 0.2-0.8 to 0-10 inches; farmer heights win when recorded.",
                "Grazing pressure assumes collared animals move like the rest of the herd.",
                "Feed budget counts 60% of standing forage above a 3 inch residual at 11.8 kg DM per animal unit per day.",
            ],
        }

    # -- deciding and sending --------------------------------------------

    def _send_after(self, farm: Farm, settings: EffectiveDecisionSettings, decided_at: datetime) -> datetime:
        if settings.send_time:
            zone = self._zone(farm)
            local = as_utc(decided_at).astimezone(zone)
            hour, minute = parse_clock_time(settings.send_time)
            candidate = datetime.combine(local.date(), time(hour, minute), tzinfo=zone)
            if candidate <= local:
                candidate += timedelta(days=1)
            return candidate
        return as_utc(decided_at) + timedelta(minutes=settings.hold_minutes)

    def _unit_geometry(self, land_unit_id: str | None) -> dict[str, object] | None:
        if not land_unit_id:
            return None
        unit = self.store.get_land_unit(land_unit_id)
        return dict(unit.geometry.geometry) if unit else None

    def submit(self, decision: GrazingDecision, *, now: datetime | None = None) -> DecisionResult:
        """Record a decision, apply autonomy, and send when allowed."""

        now = now or self.clock()
        farm = self._farm(decision.farm_id)
        if decision.action == "MOVE":
            if not decision.to_land_unit_id and not decision.to_boundary:
                raise ValueError("A MOVE decision needs to_land_unit_id or to_boundary.")
            if decision.to_boundary is None:
                decision.to_boundary = self._unit_geometry(decision.to_land_unit_id)
                if decision.to_boundary is None:
                    raise ValueError(f"Land unit '{decision.to_land_unit_id}' does not exist.")
        else:
            decision.to_land_unit_id = None
            decision.to_boundary = None
        if decision.action == "NEEDS_INFO" and not decision.uncertainty_request:
            raise ValueError("A NEEDS_INFO decision must carry an uncertainty_request.")
        if not decision.reasoning:
            raise ValueError("A decision needs at least one line of reasoning.")

        settings = self.settings_for(decision.farm_id, decision.herd_id)
        decision.autonomy = settings.autonomy
        decision.status = "proposed"
        decision.created_at = now
        decision.updated_at = now
        if decision.action == "MOVE" and settings.autonomy == "apply_unless_stopped":
            decision.send_after = self._send_after(farm, settings, now)
        self.store.create_decision(decision)

        if decision.action != "MOVE":
            return DecisionResult(decision, message="Nothing to send: the herd stays inside its current boundary.")
        if settings.autonomy == "apply":
            return self._send(decision, now=now)
        if settings.autonomy == "apply_unless_stopped":
            return DecisionResult(
                decision,
                message=f"The move goes to the collars at {decision.send_after.isoformat()} unless the farmer stops it.",  # type: ignore[union-attr]
            )
        return DecisionResult(decision, message="Waiting for the farmer to approve, change, or reject the move.")

    def _send(self, decision: GrazingDecision, *, now: datetime) -> DecisionResult:
        boundary = decision.boundary_to_send() or self._unit_geometry(decision.land_unit_to_send())
        if decision.herd_id is None or boundary is None:
            return DecisionResult(decision, message="There is no herd or boundary to send.")
        land_unit_id = decision.land_unit_to_send()
        collar_ids = self.collars.collar_ids_for_herd(decision.farm_id, decision.herd_id)
        if not collar_ids:
            if decision.farmer_response is not None and land_unit_id:
                # The farmer approved a move for a herd without collars: they move
                # the animals by hand, so the farm record follows their word.
                self.store.update_herd_position(decision.herd_id, land_unit_id)
            self.store.update_decision(decision, event="not_sent_no_collars")
            return DecisionResult(
                decision,
                message="This herd has no collars registered, so nothing was sent. The farmer moves the herd.",
            )

        options = decision.boundary_options or {}
        transition = options.get("transition")
        command, activation = self.collars.issue_boundary(
            farm_id=decision.farm_id,
            herd_id=decision.herd_id,
            boundary=boundary,
            decision_id=decision.decision_id,
            land_unit_id=land_unit_id,
            exclusions=[item for item in options.get("exclusions") or [] if isinstance(item, dict)],  # type: ignore[union-attr]
            transition=BoundaryTransition.from_dict(transition if isinstance(transition, Mapping) else None),
            previous_boundary=self._previous_boundary(decision),
            activation_threshold=self.settings_for(decision.farm_id, decision.herd_id).activation_threshold,
        )
        decision.boundary_command_id = command.command_id
        if command.status in {"rejected", "failed"}:
            self.store.update_decision(decision, event="send_failed")
            return DecisionResult(decision, command, activation, message=f"The boundary was not sent: {command.error}")
        decision.send_after = None
        decision.status = "active" if command.status == "active" else "sent"
        self.store.update_decision(decision, event=decision.status)
        if decision.status == "active":
            self._on_active(decision, command)
        message = (
            "The boundary is active: enough collars confirmed it."
            if decision.status == "active"
            else f"Sent. Waiting on {len(activation.unconfirmed_collar_ids)} collar(s) to confirm."
        )
        return DecisionResult(decision, command, activation, message=message)

    def _previous_boundary(self, decision: GrazingDecision) -> dict[str, object] | None:
        active = self.collars.active_command(decision.herd_id) if decision.herd_id else None
        if active is not None:
            return active.boundary
        return self._unit_geometry(decision.from_land_unit_id)

    def _on_active(self, decision: GrazingDecision, command: BoundaryCommand) -> None:
        unit_id = command.land_unit_id or decision.land_unit_to_send()
        unit = self.store.get_land_unit(unit_id) if unit_id else None
        if decision.herd_id and unit is not None and unit.unit_type in DECISION_UNIT_TYPES:
            self.store.update_herd_position(decision.herd_id, unit.id)

    def respond(
        self,
        decision_id: str,
        response: str,
        *,
        note: str | None = None,
        boundary: dict[str, object] | None = None,
        land_unit_id: str | None = None,
        now: datetime | None = None,
    ) -> DecisionResult:
        """Record the farmer's answer. Approve or modify sends; reject stops a pending move."""

        now = now or self.clock()
        decision = self.store.get_decision(decision_id)
        if decision is None:
            raise ValueError(f"Decision '{decision_id}' does not exist.")
        kind = RESPONSE_ALIASES.get(response.strip().lower())
        if kind is None:
            raise ValueError("response must be approve, modify, or reject.")
        if decision.status == "evaluated":
            raise ValueError("This decision has already been evaluated. Submit a new decision instead.")
        if kind == "modified":
            if boundary is None and land_unit_id:
                boundary = self._unit_geometry(land_unit_id)
                if boundary is None:
                    raise ValueError(f"Land unit '{land_unit_id}' does not exist.")
            if boundary is None:
                raise ValueError("A modified decision needs the farmer's boundary or land_unit_id.")

        already_sent = decision.status in {"sent", "active"}
        decision.farmer_response = FarmerResponse(
            at=now, response=kind, note=note, boundary=boundary, land_unit_id=land_unit_id  # type: ignore[arg-type]
        )
        decision.send_after = None

        if kind == "rejected":
            if already_sent:
                self.store.update_decision(decision, event="rejected_after_send")
                return DecisionResult(
                    decision,
                    message="The boundary was already sent. The rejection is recorded; submit a new decision to move the herd back.",
                )
            decision.status = "rejected"
            self.store.update_decision(decision, event="rejected")
            return DecisionResult(decision, message="Rejected. Nothing goes to the collars.")

        if kind == "approved" and (already_sent or not decision.is_move):
            if not already_sent:
                decision.status = "approved"
            self.store.update_decision(decision, event="approved")
            return DecisionResult(decision, message="Approved.")

        decision.status = kind  # type: ignore[assignment]
        self.store.update_decision(decision, event=kind)
        if decision.is_move:
            return self._send(decision, now=now)
        return DecisionResult(decision)

    def handle_acks(self, results: list[tuple[BoundaryCommand, BoundaryActivation]]) -> list[GrazingDecision]:
        """Move decisions to ``active`` when their command is confirmed."""

        updated: list[GrazingDecision] = []
        for command, activation in results:
            if not command.decision_id or not activation.active:
                continue
            decision = self.store.get_decision(command.decision_id)
            if decision is None or decision.status != "sent" or decision.boundary_command_id != command.command_id:
                continue
            decision.status = "active"
            self.store.update_decision(decision, event="active")
            self._on_active(decision, command)
            updated.append(decision)
        return updated

    def process_due(self, farm_id: str | None = None, *, now: datetime | None = None) -> list[DecisionResult]:
        """Send apply_unless_stopped moves whose deadline passed, and refresh sent boundaries."""

        now = now or self.clock()
        farms = [self._farm(farm_id)] if farm_id else self.store.list_farms()
        results: list[DecisionResult] = []
        for farm in farms:
            for herd in self.store.get_herds(farm.id):
                latest = self.store.get_latest_decision(farm.id, herd.id)
                if latest is None:
                    continue
                if (
                    latest.status == "proposed"
                    and latest.autonomy == "apply_unless_stopped"
                    and latest.send_after is not None
                    and as_utc(latest.send_after) <= as_utc(now)
                    and latest.is_move
                ):
                    results.append(self._send(latest, now=now))
                elif latest.status == "sent" and latest.boundary_command_id:
                    command = self.store.get_boundary_command(latest.boundary_command_id)
                    if command is not None:
                        activation = self.collars.refresh(command)
                        refreshed = self.store.get_boundary_command(command.command_id) or command
                        self.handle_acks([(refreshed, activation)])
        return results

    # -- outcomes ---------------------------------------------------------

    def evaluate(
        self,
        decision_id: str,
        *,
        now: datetime | None = None,
        residual_estimate_inches: float | None = None,
        notes: list[str] | None = None,
    ) -> GrazingDecision:
        """Write what happened after the decision back onto the record."""

        now = now or self.clock()
        decision = self.store.get_decision(decision_id)
        if decision is None:
            raise ValueError(f"Decision '{decision_id}' does not exist.")
        outcome_notes = list(notes or [])

        command = self.store.get_boundary_command(decision.boundary_command_id) if decision.boundary_command_id else None
        if command is None and decision.herd_id and not decision.is_move:
            command = self.collars.active_command(decision.herd_id)
        start = decision.created_at
        if command is not None and (command.activated_at or command.sent_at):
            start = command.activated_at or command.sent_at  # type: ignore[assignment]
        # Look at the herd from confirmation to the end of the window (or now, if sooner).
        # Stored fix times are to the second and ``until`` is exclusive, so pad a second.
        end = max(min(as_utc(now), as_utc(decision.window.ends_at)), as_utc(start)) + timedelta(seconds=1)

        held = None
        cue_count = None
        if decision.herd_id:
            fixes = self.store.list_position_fixes(decision.herd_id, start, end)
            cues = self.store.list_cue_events(decision.herd_id, start, end)
            if fixes or cues:
                cue_count = len(cues)
            if fixes and command is not None:
                inside = sum(1 for fix in fixes if point_in_geometry(fix.point, command.boundary))
                share = inside / len(fixes)
                held = share >= HELD_BOUNDARY_SHARE
                outcome_notes.append(f"{share:.0%} of {len(fixes)} collar fixes were inside the boundary.")
            elif command is None and decision.is_move:
                outcome_notes.append("No boundary reached the collars for this decision.")

        grazed_unit = decision.from_land_unit_id
        if residual_estimate_inches is None and grazed_unit:
            recent = [
                obs
                for obs in self.store.get_paddock_observations(grazed_unit, days=30)
                if as_utc(obs.observed_at) >= as_utc(decision.created_at)
            ]
            residual_estimate_inches = self._field_height(recent, grazed_unit)
            if residual_estimate_inches is not None:
                outcome_notes.append(f"Residual from the farmer's field note on {grazed_unit}.")

        if grazed_unit and self.store.get_farm(decision.farm_id) is not None:
            outcome_notes.extend(self._ndvi_change_notes(decision, grazed_unit))

        decision.outcome = DecisionOutcome(
            evaluated_at=now,
            herd_held_boundary=held,
            cue_count=cue_count,
            residual_estimate_inches=residual_estimate_inches,
            notes=outcome_notes,
        )
        decision.status = "evaluated"
        self.store.update_decision(decision, event="evaluated")
        return decision

    def _ndvi_change_notes(self, decision: GrazingDecision, land_unit_id: str) -> list[str]:
        def ndvi(report: LandReport | None) -> float | None:
            imagery = report.ok_section("imagery") if report else None
            stats = imagery.get("ndvi_stats") if imagery and isinstance(imagery.get("ndvi_stats"), Mapping) else None
            mean = stats.get("mean") if stats else None  # type: ignore[union-attr]
            return float(mean) if isinstance(mean, (int, float)) else None

        before = None
        for report_id in decision.inputs.land_report_ids:
            report = self.store.get_land_report(report_id)
            if report is not None and land_unit_id in report.land_unit_ids:
                before = ndvi(report)
                break
        latest_reports = self.store.list_land_reports(decision.farm_id, land_unit_id=land_unit_id, limit=1)
        after = ndvi(latest_reports[0]) if latest_reports else None
        if before is None or after is None or latest_reports[0].report_id in decision.inputs.land_report_ids:
            return []
        return [f"{land_unit_id} NDVI {before:.2f} at decision time, {after:.2f} in the latest imagery."]

    def evaluate_prior(self, farm_id: str, herd_id: str, *, now: datetime | None = None) -> list[GrazingDecision]:
        """Evaluate this herd's earlier decisions whose windows have ended."""

        now = now or self.clock()
        evaluated = []
        for decision in self.store.list_decisions(farm_id, herd_id=herd_id, limit=10):
            if decision.status == "evaluated" or as_utc(decision.window.ends_at) > as_utc(now):
                continue
            evaluated.append(self.evaluate(decision.decision_id, now=now))
        return evaluated

    # -- the cycle --------------------------------------------------------

    def _has_newer_field_notes(self, decision: GrazingDecision) -> bool:
        return any(
            is_field_observation_source(obs.source) and as_utc(obs.observed_at) > as_utc(decision.created_at)
            for obs in self.store.get_recent_observations(decision.farm_id, days=2)
        )

    def run_cycle(
        self,
        farm_id: str,
        herd_id: str | None = None,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> tuple[DecisionResult, DecisionContext | None]:
        """Run the fallback heuristic cycle for one herd.

        If this window already has a decision it is reused, unless ``force`` is
        set or it is still only proposed and the farmer has added field notes
        since, in which case a fresh decision is made.
        """

        now = now or self.clock()
        herd = self.resolve_herd(farm_id, herd_id)
        if herd is not None:
            self.evaluate_prior(farm_id, herd.id, now=now)
            self.process_due(farm_id, now=now)
            existing = self.store.get_latest_decision(farm_id, herd.id)
            if (
                not force
                and existing is not None
                and existing.window.contains(now)
                and existing.status != "evaluated"
                and not (existing.status == "proposed" and self._has_newer_field_notes(existing))
            ):
                return DecisionResult(existing, message="Reusing this window's decision."), None

        context = self.assemble_context(farm_id, herd.id if herd else None, now=now, save_summary=True)
        if (
            herd is not None
            and context.position_source == "collar"
            and context.current_land_unit_id
            and context.current_land_unit_id != herd.current_paddock_id
        ):
            self.store.update_herd_position(herd.id, context.current_land_unit_id)
            herd.current_paddock_id = context.current_land_unit_id

        decision = self.advisor.decide(context)
        if decision.action == "NEEDS_INFO" or decision.confidence == "low":
            decision.uncertainty_request = self.attention_director.next_best_question(farm_id)
        return self.submit(decision, now=now), context

    # -- the brief --------------------------------------------------------

    def build_brief(self, decision: GrazingDecision, context: DecisionContext | None = None) -> DailyBrief:
        """The farmer-readable wrapper around a decision."""

        farm = self._farm(decision.farm_id)
        herd = self.resolve_herd(decision.farm_id, decision.herd_id) if decision.herd_id else None
        target = decision.land_unit_to_send()
        highlights: list[str] = []
        if herd is not None:
            where = decision.from_land_unit_id or herd.current_paddock_id or "an unknown paddock"
            highlights.append(f"{herd.species.title()} herd of {herd.count} is currently in {where}.")
        weather = context.weather_observations if context else [
            obs for obs in self.store.get_recent_observations(farm.id, days=1) if obs.source == "weather"
        ]
        if weather:
            highlights.append(weather[0].content)
        highlights.extend(decision.reasoning[:2])

        if decision.action == "MOVE":
            target_text = target or "the next rested paddock"
            summary = (
                f"Recommendation: MOVE today. The current paddock is showing pressure, and {target_text} "
                "is the best recorded next option."
            )
        elif decision.action == "STAY":
            summary = "Recommendation: STAY today. The latest notes do not show enough pressure to force a move."
        else:
            summary = (
                "Recommendation: NEEDS_INFO. There is not enough recent on-the-ground context to make a "
                "confident move call."
            )
        summary += " " + _status_sentence(decision)
        return DailyBrief(
            id=f"brief_{decision.decision_id}",
            farm_id=decision.farm_id,
            generated_at=self.clock(),
            summary=summary.strip(),
            decision=decision,
            uncertainty_request=decision.uncertainty_request,
            highlights=highlights,
        )


def _status_sentence(decision: GrazingDecision) -> str:
    if decision.action != "MOVE" and not decision.is_move:
        return ""
    if decision.status == "proposed" and decision.autonomy == "apply_unless_stopped" and decision.send_after:
        return f"It goes to the collars at {decision.send_after.isoformat()} unless you stop it."
    if decision.status == "proposed":
        return "It waits for your approval."
    if decision.status == "sent":
        return "The boundary is sent and waiting on collar confirmations."
    if decision.status == "active":
        return "The boundary is active on the collars."
    if decision.status == "rejected":
        return "You rejected this move."
    return ""


def new_decision(
    *,
    farm_id: str,
    herd_id: str | None,
    window: DecisionWindow,
    action: str,
    reasoning: list[str],
    **fields: object,
) -> GrazingDecision:
    """Build a decision with a fresh id; used by the submit tool."""

    return GrazingDecision(
        decision_id=str(fields.pop("decision_id", None) or new_decision_id()),
        farm_id=farm_id,
        herd_id=herd_id,
        window=window,
        action=action,  # type: ignore[arg-type]
        reasoning=reasoning,
        inputs=fields.pop("inputs", None) or DecisionInputs(),  # type: ignore[arg-type]
        **fields,  # type: ignore[arg-type]
    )
