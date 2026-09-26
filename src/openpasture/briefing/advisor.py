"""The fallback heuristic advisor.

When no agent brain is available, this produces a ``GrazingDecision`` from the
assembled decision context. It reads field notes first, because the farmer's
eyes are the best signal, then uses collar and land signals to pick a target and
explain the call. It is conservative: without a fresh field note it asks for one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from openpasture.domain import DecisionInputs, GrazingDecision, LandUnit
from openpasture.domain.observation import is_field_observation_source

if TYPE_CHECKING:
    from openpasture.briefing.engine import DecisionContext

MOVE_SIGNALS = ("short", "overgraz", "bare", "mud", "trampled", "tight", "hungry", "pug")
STAY_SIGNALS = ("plenty", "good residual", "abundant", "fresh", "ready", "rested")
READY_STATUSES = {"resting", "ready"}


def new_decision_id() -> str:
    return f"gd_{uuid4().hex[:20]}"


class HeuristicAdvisor:
    """Keyword-and-signal advisor used by ``run_decision_cycle``."""

    name = "heuristic"

    def choose_target(self, context: "DecisionContext") -> LandUnit | None:
        """Prefer a resting or ready unit with the most rest; else the first candidate."""

        candidates = context.candidates
        if not candidates:
            return None
        rest = context.signals.get("rest_days", {}) if isinstance(context.signals, dict) else {}
        ready = [unit for unit in candidates if unit.status.lower() in READY_STATUSES]
        if ready:
            # Never-grazed units have no rest record and sort as fully rested.
            return sorted(
                ready,
                key=lambda unit: -(rest.get(unit.id) if rest.get(unit.id) is not None else 10**6),  # type: ignore[operator]
            )[0]
        return candidates[0]

    def decide(self, context: "DecisionContext") -> GrazingDecision:
        herd = context.herd
        current_id = context.current_land_unit_id
        inferred_position = context.position_source == "observation"
        target = self.choose_target(context)

        observations = [obs for obs in context.recent_observations if "land-report" not in obs.tags]
        field_observations = [obs for obs in observations if is_field_observation_source(obs.source)]
        current_text = " ".join(
            obs.content.lower() for obs in observations if obs.paddock_id in {None, current_id}
        )
        wants_move = any(signal in current_text for signal in MOVE_SIGNALS)
        wants_stay = any(signal in current_text for signal in STAY_SIGNALS)

        action = "NEEDS_INFO"
        confidence = "low"
        reasoning: list[str] = []

        if not field_observations:
            reasoning.append("There is no recent field observation from the current paddock.")
        elif inferred_position and current_id:
            reasoning.append("I inferred the herd's current paddock from the most recent herd-linked field observation.")
            if wants_move and target is not None:
                action, confidence = "MOVE", "medium"
                reasoning.append("That observation suggests forage pressure or ground stress in the current paddock.")
                reasoning.append(f"{target.name} is available as the next likely move option.")
            elif wants_stay:
                action, confidence = "STAY", "medium"
                reasoning.append("That observation does not show enough pressure to force a move today.")
        elif wants_move:
            if target is not None:
                action, confidence = "MOVE", "medium"
                reasoning.append("Recent observations suggest forage pressure or ground stress in the current paddock.")
                reasoning.append(f"{target.name} is available as the next likely move option.")
            else:
                reasoning.append("Current paddock looks stressed, but there is no alternate paddock recorded yet.")
        elif wants_stay or context.position_source in {"farm_record", "collar"}:
            action, confidence = "STAY", "medium"
            reasoning.append("Recent observations do not show urgent signs that animals need to move today.")
            reasoning.append("The current paddock still appears workable based on the last field notes.")

        reasoning.extend(self._signal_notes(context, target if action == "MOVE" else None))
        reasoning.extend(entry.content for entry in context.relevant_knowledge[:2])

        to_boundary = target.geometry.geometry if target is not None and action == "MOVE" else None
        return GrazingDecision(
            decision_id=new_decision_id(),
            farm_id=context.farm.id,
            herd_id=herd.id if herd else None,
            window=context.window,
            action=action,  # type: ignore[arg-type]
            from_land_unit_id=current_id,
            to_land_unit_id=target.id if target is not None and action == "MOVE" else None,
            to_boundary=dict(to_boundary) if to_boundary else None,
            reasoning=reasoning[:6] or ["More on-the-ground context is needed before making a confident move call."],
            confidence=confidence,  # type: ignore[arg-type]
            inputs=DecisionInputs(
                land_report_ids=[report.report_id for report in context.land_reports.values()],
                collar_summary_id=context.collar_summary.summary_id if context.collar_summary else None,
                observation_ids=[obs.id for obs in field_observations[:10]],
                knowledge_entry_ids=[entry.id for entry in context.relevant_knowledge],
            ),
            decided_by=self.name,
        )

    def _signal_notes(self, context: "DecisionContext", target: LandUnit | None) -> list[str]:
        """One or two plain lines from collar and land signals."""

        notes: list[str] = []
        summary = context.collar_summary
        if summary is not None and summary.fix_count and context.current_land_unit_id:
            notes.append(
                f"Collars place the herd in {context.current_land_unit_id} "
                f"({summary.land_unit_fix_counts.get(context.current_land_unit_id, 0)} of {summary.fix_count} recent fixes)."
            )
        signals = context.signals if isinstance(context.signals, dict) else {}
        if target is not None:
            rest = (signals.get("rest_days") or {}).get(target.id)
            forage = (signals.get("forage") or {}).get(target.id) or {}
            if rest is not None:
                notes.append(f"{target.name} has rested {rest:.0f} days.")
            elif forage.get("height_inches") is not None:
                notes.append(f"Imagery puts {target.name} at roughly {forage['height_inches']} inches.")
        for flag in (signals.get("risk_flags") or [])[:1]:
            if flag.get("level") == "high":
                notes.append(flag["reason"])
        return notes
