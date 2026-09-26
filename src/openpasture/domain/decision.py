"""The grazing decision record and the morning brief that wraps it.

A ``GrazingDecision`` is the record of one decision for one herd in one
decision window. It grows through its lifecycle: proposed, answered by the
farmer (or by the autonomy setting), sent to the collars, confirmed active, and
finally evaluated. The field names follow ``docs/contracts.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

from .clock import as_utc, iso_or_none, parse_datetime, utc_now

DecisionAction = Literal["MOVE", "STAY", "NEEDS_INFO"]
DecisionConfidence = Literal["high", "medium", "low"]
Autonomy = Literal["propose", "apply_unless_stopped", "apply"]
DecisionStatus = Literal["proposed", "approved", "modified", "rejected", "sent", "active", "evaluated"]
FarmerResponseKind = Literal["approved", "modified", "rejected"]

DECISION_ACTIONS: tuple[str, ...] = ("MOVE", "STAY", "NEEDS_INFO")
DECISION_CONFIDENCE: tuple[str, ...] = ("high", "medium", "low")
AUTONOMY_MODES: tuple[str, ...] = ("propose", "apply_unless_stopped", "apply")
DECISION_STATUSES: tuple[str, ...] = (
    "proposed",
    "approved",
    "modified",
    "rejected",
    "sent",
    "active",
    "evaluated",
)
FARMER_RESPONSES: tuple[str, ...] = ("approved", "modified", "rejected")


@dataclass(slots=True)
class DecisionWindow:
    """The span of time one decision covers. Daily by default."""

    starts_at: datetime
    ends_at: datetime

    def contains(self, moment: datetime) -> bool:
        return as_utc(self.starts_at) <= as_utc(moment) < as_utc(self.ends_at)

    def to_dict(self) -> dict[str, object]:
        return {"starts_at": self.starts_at.isoformat(), "ends_at": self.ends_at.isoformat()}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DecisionWindow":
        starts_at = parse_datetime(data.get("starts_at"))
        ends_at = parse_datetime(data.get("ends_at"))
        if starts_at is None or ends_at is None:
            raise ValueError("Decision window needs starts_at and ends_at.")
        return cls(starts_at=starts_at, ends_at=ends_at)


@dataclass(slots=True)
class DecisionInputs:
    """Everything the decision drew on, by id, so it can be replayed later."""

    land_report_ids: list[str] = field(default_factory=list)
    collar_summary_id: str | None = None
    observation_ids: list[str] = field(default_factory=list)
    knowledge_entry_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "land_report_ids": list(self.land_report_ids),
            "collar_summary_id": self.collar_summary_id,
            "observation_ids": list(self.observation_ids),
            "knowledge_entry_ids": list(self.knowledge_entry_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object] | None) -> "DecisionInputs":
        data = data or {}
        collar_summary_id = data.get("collar_summary_id")
        return cls(
            land_report_ids=[str(item) for item in data.get("land_report_ids") or []],
            collar_summary_id=str(collar_summary_id) if collar_summary_id else None,
            observation_ids=[str(item) for item in data.get("observation_ids") or []],
            knowledge_entry_ids=[str(item) for item in data.get("knowledge_entry_ids") or []],
        )


@dataclass(slots=True)
class FarmerResponse:
    """The farmer's answer to a decision. An override is signal, not an error."""

    at: datetime
    response: FarmerResponseKind
    note: str | None = None
    boundary: dict[str, object] | None = None
    land_unit_id: str | None = None

    def __post_init__(self) -> None:
        if self.response not in FARMER_RESPONSES:
            raise ValueError(f"Unsupported farmer response: {self.response}")

    def to_dict(self) -> dict[str, object]:
        return {
            "at": self.at.isoformat(),
            "response": self.response,
            "note": self.note,
            "boundary": self.boundary,
            "land_unit_id": self.land_unit_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object] | None) -> "FarmerResponse | None":
        if not data:
            return None
        at = parse_datetime(data.get("at")) or utc_now()
        boundary = data.get("boundary")
        note = data.get("note")
        land_unit_id = data.get("land_unit_id")
        return cls(
            at=at,
            response=str(data.get("response")),  # type: ignore[arg-type]
            note=str(note) if note else None,
            boundary=dict(boundary) if isinstance(boundary, Mapping) else None,
            land_unit_id=str(land_unit_id) if land_unit_id else None,
        )


@dataclass(slots=True)
class DecisionOutcome:
    """What happened after the decision, filled in on later cycles."""

    evaluated_at: datetime
    herd_held_boundary: bool | None = None
    cue_count: int | None = None
    residual_estimate_inches: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluated_at": self.evaluated_at.isoformat(),
            "herd_held_boundary": self.herd_held_boundary,
            "cue_count": self.cue_count,
            "residual_estimate_inches": self.residual_estimate_inches,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object] | None) -> "DecisionOutcome | None":
        if not data:
            return None
        held = data.get("herd_held_boundary")
        cue_count = data.get("cue_count")
        residual = data.get("residual_estimate_inches")
        return cls(
            evaluated_at=parse_datetime(data.get("evaluated_at")) or utc_now(),
            herd_held_boundary=bool(held) if held is not None else None,
            cue_count=int(cue_count) if isinstance(cue_count, (int, float)) else None,
            residual_estimate_inches=float(residual) if isinstance(residual, (int, float)) else None,
            notes=[str(item) for item in data.get("notes") or []],
        )


@dataclass(slots=True)
class GrazingDecision:
    """The decision for one herd in one decision window."""

    decision_id: str
    farm_id: str
    herd_id: str | None
    window: DecisionWindow
    action: DecisionAction
    from_land_unit_id: str | None = None
    to_land_unit_id: str | None = None
    # GeoJSON geometry (Polygon or MultiPolygon) the engine proposes for a MOVE.
    to_boundary: dict[str, object] | None = None
    reasoning: list[str] = field(default_factory=list)
    confidence: DecisionConfidence = "medium"
    uncertainty_request: str | None = None
    inputs: DecisionInputs = field(default_factory=DecisionInputs)
    autonomy: Autonomy = "propose"
    status: DecisionStatus = "proposed"
    farmer_response: FarmerResponse | None = None
    boundary_command_id: str | None = None
    outcome: DecisionOutcome | None = None
    # Who produced the decision: "agent" or the fallback "heuristic" advisor.
    decided_by: str = "agent"
    # For apply_unless_stopped: when the move goes out unless the farmer stops it.
    send_after: datetime | None = None
    # How the boundary should be sent: {"exclusions": [...], "transition": {...}}.
    boundary_options: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.action not in DECISION_ACTIONS:
            raise ValueError(f"Unsupported decision action: {self.action}")
        if self.confidence not in DECISION_CONFIDENCE:
            raise ValueError(f"Unsupported decision confidence: {self.confidence}")
        if self.autonomy not in AUTONOMY_MODES:
            raise ValueError(f"Unsupported autonomy mode: {self.autonomy}")
        if self.status not in DECISION_STATUSES:
            raise ValueError(f"Unsupported decision status: {self.status}")

    @property
    def is_move(self) -> bool:
        """True when the decision, as answered by the farmer, moves the herd."""

        if self.farmer_response and self.farmer_response.response == "modified":
            return bool(self.boundary_to_send() or self.land_unit_to_send())
        return self.action == "MOVE"

    def boundary_to_send(self) -> dict[str, object] | None:
        """The farmer's boundary when modified, otherwise the engine's."""

        if self.farmer_response and self.farmer_response.response == "modified" and self.farmer_response.boundary:
            return self.farmer_response.boundary
        return self.to_boundary

    def land_unit_to_send(self) -> str | None:
        if self.farmer_response and self.farmer_response.response == "modified" and self.farmer_response.land_unit_id:
            return self.farmer_response.land_unit_id
        return self.to_land_unit_id

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "farm_id": self.farm_id,
            "herd_id": self.herd_id,
            "window": self.window.to_dict(),
            "action": self.action,
            "from_land_unit_id": self.from_land_unit_id,
            "to_land_unit_id": self.to_land_unit_id,
            "to_boundary": self.to_boundary,
            "reasoning": list(self.reasoning),
            "confidence": self.confidence,
            "uncertainty_request": self.uncertainty_request,
            "inputs": self.inputs.to_dict(),
            "autonomy": self.autonomy,
            "status": self.status,
            "farmer_response": self.farmer_response.to_dict() if self.farmer_response else None,
            "boundary_command_id": self.boundary_command_id,
            "outcome": self.outcome.to_dict() if self.outcome else None,
            "decided_by": self.decided_by,
            "send_after": iso_or_none(self.send_after),
            "boundary_options": dict(self.boundary_options),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "GrazingDecision":
        window = data.get("window")
        herd_id = data.get("herd_id")
        to_boundary = data.get("to_boundary")
        return cls(
            decision_id=str(data["decision_id"]),
            farm_id=str(data["farm_id"]),
            herd_id=str(herd_id) if herd_id else None,
            window=DecisionWindow.from_dict(window if isinstance(window, Mapping) else {}),
            action=str(data["action"]),  # type: ignore[arg-type]
            from_land_unit_id=_optional_text(data.get("from_land_unit_id")),
            to_land_unit_id=_optional_text(data.get("to_land_unit_id")),
            to_boundary=dict(to_boundary) if isinstance(to_boundary, Mapping) else None,
            reasoning=[str(item) for item in data.get("reasoning") or []],
            confidence=str(data.get("confidence") or "medium"),  # type: ignore[arg-type]
            uncertainty_request=_optional_text(data.get("uncertainty_request")),
            inputs=DecisionInputs.from_dict(data.get("inputs") if isinstance(data.get("inputs"), Mapping) else None),
            autonomy=str(data.get("autonomy") or "propose"),  # type: ignore[arg-type]
            status=str(data.get("status") or "proposed"),  # type: ignore[arg-type]
            farmer_response=FarmerResponse.from_dict(
                data.get("farmer_response") if isinstance(data.get("farmer_response"), Mapping) else None
            ),
            boundary_command_id=_optional_text(data.get("boundary_command_id")),
            outcome=DecisionOutcome.from_dict(data.get("outcome") if isinstance(data.get("outcome"), Mapping) else None),
            decided_by=str(data.get("decided_by") or "agent"),
            send_after=parse_datetime(data.get("send_after")),
            boundary_options=dict(data["boundary_options"]) if isinstance(data.get("boundary_options"), Mapping) else {},
            created_at=parse_datetime(data.get("created_at")) or utc_now(),
            updated_at=parse_datetime(data.get("updated_at")) or utc_now(),
        )


@dataclass(slots=True)
class DailyBrief:
    """The farmer-readable wrapper around the latest grazing decision."""

    id: str
    farm_id: str
    generated_at: datetime
    summary: str
    decision: GrazingDecision
    uncertainty_request: str | None = None
    highlights: list[str] = field(default_factory=list)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
