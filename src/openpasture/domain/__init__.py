"""Domain primitives for Openpasture."""

from .activity import Animal, FarmActivityAttachment, FarmActivityEvent, FarmActivityTarget
from .action import FarmerAction
from .collar import (
    BoundaryAck,
    BoundaryActivation,
    BoundaryCommand,
    BoundaryTransition,
    Collar,
    CollarSummary,
    CueEvent,
    PositionFix,
    PositionReport,
    boundary_activation,
)
from .decision import (
    AUTONOMY_MODES,
    Autonomy,
    DailyBrief,
    DecisionAction,
    DecisionInputs,
    DecisionOutcome,
    DecisionWindow,
    FarmerResponse,
    GrazingDecision,
)
from .farm import Farm, Herd, LandUnit, Pasture, Section, WaterSource
from .geo import BoundingBox, GeoFeature, GeoPoint, GeoPolygon
from .knowledge import KnowledgeEntry, KnowledgeType, SourceRecord
from .land import LAND_REPORT_SECTIONS, LandReport, LandReportRequest, LandReportSection
from .observation import (
    Observation,
    ObservationSource,
    ObservationWindow,
    is_field_observation_source,
    normalize_observation_source,
)
from .pipeline import DataPipeline
from .settings import DecisionSettings, EffectiveDecisionSettings, resolve_decision_settings

__all__ = [
    "AUTONOMY_MODES",
    "Animal",
    "Autonomy",
    "BoundaryAck",
    "BoundaryActivation",
    "BoundaryCommand",
    "BoundaryTransition",
    "BoundingBox",
    "Collar",
    "CollarSummary",
    "CueEvent",
    "DataPipeline",
    "DailyBrief",
    "DecisionAction",
    "DecisionInputs",
    "DecisionOutcome",
    "DecisionSettings",
    "DecisionWindow",
    "EffectiveDecisionSettings",
    "FarmActivityAttachment",
    "FarmActivityEvent",
    "FarmActivityTarget",
    "FarmerAction",
    "FarmerResponse",
    "Farm",
    "GeoFeature",
    "GeoPoint",
    "GeoPolygon",
    "GrazingDecision",
    "Herd",
    "LAND_REPORT_SECTIONS",
    "LandReport",
    "LandReportRequest",
    "LandReportSection",
    "LandUnit",
    "KnowledgeEntry",
    "KnowledgeType",
    "Observation",
    "ObservationSource",
    "ObservationWindow",
    "Pasture",
    "PositionFix",
    "PositionReport",
    "Section",
    "SourceRecord",
    "WaterSource",
    "boundary_activation",
    "is_field_observation_source",
    "normalize_observation_source",
    "resolve_decision_settings",
]
