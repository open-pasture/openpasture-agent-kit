"""Morning brief assembly logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from logging import getLogger

from openpasture.briefing.attention_director import AttentionDirector
from openpasture.domain import DailyBrief, Farm, Herd, KnowledgeEntry, MovementDecision, Observation, Paddock
from openpasture.domain.observation import is_field_observation_source
from openpasture.ingestion.weather import WeatherObservationPipeline
from openpasture.knowledge.retriever import KnowledgeRetriever
from openpasture.context import get_knowledge, get_store
from openpasture.store.protocol import FarmStore

logger = getLogger(__name__)


@dataclass(frozen=True)
class MorningBriefContext:
    """Structured farm context an agent can reason over before recommending action."""

    farm: Farm
    herds: list[Herd]
    paddocks: list[Paddock]
    recent_observations: list[Observation]
    weather_observations: list[Observation]
    relevant_knowledge: list[KnowledgeEntry]


class MorningBriefAssembler:
    """Builds a daily brief from current farm context and relevant knowledge."""

    def __init__(
        self,
        store: FarmStore | None = None,
        retriever: KnowledgeRetriever | None = None,
        attention_director: AttentionDirector | None = None,
    ):
        self.store = store or get_store()
        self.retriever = retriever or get_knowledge()
        self.attention_director = attention_director or AttentionDirector(self.store)

    def _choose_target_paddock(self, paddocks: list[Paddock], current_paddock_id: str | None) -> Paddock | None:
        candidates = [paddock for paddock in paddocks if paddock.id != current_paddock_id]
        if not candidates:
            return None
        for paddock in candidates:
            if paddock.status.lower() in {"resting", "ready"}:
                return paddock
        return candidates[0]

    def _infer_current_paddock_id(
        self,
        observations,
        herd_id: str | None,
        current_paddock_id: str | None,
    ) -> tuple[str | None, bool]:
        if current_paddock_id:
            return current_paddock_id, False

        for observation in observations:
            if observation.paddock_id is None:
                continue
            if herd_id and observation.herd_id == herd_id:
                return observation.paddock_id, True

        for observation in observations:
            if observation.paddock_id is not None:
                return observation.paddock_id, True

        return None, False

    def _collect_weather(self, farm_id: str) -> list[Observation]:
        weather_pipeline = WeatherObservationPipeline(self.store)
        try:
            weather_observations = weather_pipeline.collect(farm_id)
        except Exception:
            logger.warning("Weather pipeline raised unexpectedly for farm '%s'. Continuing without weather.", farm_id)
            return []
        for observation in weather_observations:
            self.store.record_observation(observation)
        return weather_observations

    def assemble_context(self, farm_id: str) -> MorningBriefContext:
        """Gather farm state and retrieved knowledge without making a recommendation."""

        farm = self.store.get_farm(farm_id)
        if farm is None:
            raise ValueError(f"Farm '{farm_id}' does not exist.")

        weather_observations = self._collect_weather(farm_id)
        recent_observations = self.store.get_recent_observations(farm_id, days=7)
        knowledge_query = " ".join(
            [
                "movement decision",
                " ".join(obs.content.lower() for obs in recent_observations),
                "recovery residual weather",
            ]
        ).strip()
        relevant_knowledge = self.retriever.search(
            knowledge_query or "grazing movement decision",
            farm_id=farm_id,
            limit=3,
        )
        return MorningBriefContext(
            farm=farm,
            herds=self.store.get_herds(farm_id),
            paddocks=self.store.list_paddocks(farm_id),
            recent_observations=recent_observations,
            weather_observations=weather_observations,
            relevant_knowledge=relevant_knowledge,
        )

    def _build_decision(
        self,
        context: MorningBriefContext,
        herd_id: str | None,
        current_paddock_id: str | None,
    ) -> MovementDecision:
        farm_id = context.farm.id
        paddocks = context.paddocks
        observations = context.recent_observations
        effective_paddock_id, inferred_position = self._infer_current_paddock_id(
            observations=observations,
            herd_id=herd_id,
            current_paddock_id=current_paddock_id,
        )
        target_paddock = self._choose_target_paddock(paddocks, effective_paddock_id)

        field_observations = [obs for obs in observations if is_field_observation_source(obs.source)]
        current_text = " ".join(
            obs.content.lower()
            for obs in observations
            if obs.paddock_id in {None, effective_paddock_id}
        )
        move_signals = ("short", "overgraz", "bare", "mud", "trampled", "tight", "hungry", "pug")
        stay_signals = ("plenty", "good residual", "abundant", "fresh", "ready", "rested")

        action = "NEEDS_INFO"
        confidence = "low"
        reasoning: list[str] = []

        if not field_observations:
            reasoning.append("There is no recent field observation from the current paddock.")
        elif inferred_position and effective_paddock_id:
            reasoning.append("I inferred the herd's current paddock from the most recent herd-linked field observation.")
            if any(signal in current_text for signal in move_signals) and target_paddock is not None:
                action = "MOVE"
                confidence = "medium"
                reasoning.append("That observation suggests forage pressure or ground stress in the current paddock.")
                reasoning.append(f"{target_paddock.name} is available as the next likely move option.")
            elif any(signal in current_text for signal in stay_signals):
                action = "STAY"
                confidence = "medium"
                reasoning.append("That observation does not show enough pressure to force a move today.")
        elif any(signal in current_text for signal in move_signals):
            if target_paddock is not None:
                action = "MOVE"
                confidence = "medium"
                reasoning.append("Recent observations suggest forage pressure or ground stress in the current paddock.")
                reasoning.append(f"{target_paddock.name} is available as the next likely move option.")
            else:
                reasoning.append("Current paddock looks stressed, but there is no alternate paddock recorded yet.")
        elif any(signal in current_text for signal in stay_signals) or current_paddock_id:
            action = "STAY"
            confidence = "medium"
            reasoning.append("Recent observations do not show urgent signs that animals need to move today.")
            reasoning.append("The current paddock still appears workable based on the last field notes.")

        knowledge_entries = context.relevant_knowledge
        reasoning.extend(entry.content for entry in knowledge_entries[:2])

        return MovementDecision(
            id=f"plan_{farm_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            farm_id=farm_id,
            herd_id=herd_id,
            for_date=date.today(),
            action=action,
            reasoning=reasoning[:5] or ["More on-the-ground context is needed before making a confident move call."],
            confidence=confidence,
            source_paddock_id=effective_paddock_id,
            target_paddock_id=target_paddock.id if target_paddock and action == "MOVE" else None,
            knowledge_entry_ids=[entry.id for entry in knowledge_entries],
            status="pending",
            farmer_feedback=None,
            created_at=datetime.utcnow(),
        )

    def assemble(self, farm_id: str, for_date: date | None = None) -> DailyBrief:
        context = self.assemble_context(farm_id)
        herds = context.herds
        current_herd = herds[0] if herds else None
        current_paddock_id = current_herd.current_paddock_id if current_herd else None

        decision = self._build_decision(
            context=context,
            herd_id=current_herd.id if current_herd else None,
            current_paddock_id=current_paddock_id,
        )
        if for_date is not None:
            decision.for_date = for_date

        uncertainty_request = None
        if decision.action == "NEEDS_INFO" or decision.confidence == "low":
            uncertainty_request = self.attention_director.next_best_question(farm_id)

        highlights = []
        if current_herd:
            highlights.append(
                f"{current_herd.species.title()} herd of {current_herd.count} is currently in {decision.source_paddock_id or current_paddock_id or 'an unknown paddock'}."
            )
        if context.weather_observations:
            highlights.append(context.weather_observations[0].content)
        highlights.extend(decision.reasoning[:2])

        if decision.action == "MOVE":
            target_text = decision.target_paddock_id or "the next rested paddock"
            summary = (
                f"Recommendation: MOVE today. The current paddock is showing pressure, and {target_text} is the best recorded next option."
            )
        elif decision.action == "STAY":
            summary = "Recommendation: STAY today. The latest notes do not show enough pressure to force a move."
        else:
            summary = "Recommendation: NEEDS_INFO. There is not enough recent on-the-ground context to make a confident move call."

        return DailyBrief(
            id=f"brief_{farm_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            farm_id=farm_id,
            generated_at=datetime.utcnow(),
            summary=summary,
            recommendation=decision,
            uncertainty_request=uncertainty_request,
            highlights=highlights,
        )
