"""Runtime initialization and shared state for openPasture."""

from __future__ import annotations

import json
import os
from logging import getLogger
from pathlib import Path
from typing import Any, Callable, MutableMapping, TYPE_CHECKING

from openpasture import context as toolkit_context
from openpasture.knowledge.embedder import KnowledgeEmbedder
from openpasture.knowledge.retriever import KnowledgeRetriever
from openpasture.knowledge.seed_loader import load_seed_knowledge
from openpasture.store.knowledge_protocol import KnowledgeStore
from openpasture.store.protocol import FarmStore

if TYPE_CHECKING:
    from openpasture.briefing.scheduler import MorningBriefScheduler

logger = getLogger(__name__)

_ONBOARDING_TOOL_RECIPE = json.dumps(
    {
        "name": "Willow Creek",
        "timezone": "America/Chicago",
        "herd": {"id": "herd_1", "species": "cattle", "count": 28},
        "paddocks": [
            {"id": "paddock_home", "name": "Home", "status": "grazing"},
            {"id": "paddock_north", "name": "North", "status": "resting"},
        ],
        "current_paddock_id": "paddock_home",
    },
    sort_keys=True,
)

_store: FarmStore | None = None
_knowledge_store: KnowledgeStore | None = None
_embedder: KnowledgeEmbedder | None = None
_retriever: KnowledgeRetriever | None = None
_active_farm_id: str | None = None
_seed_loaded = False
_soul_prompt: str | None = None
_brief_scheduler: MorningBriefScheduler | None = None
_runtime_notices: list[str] = []


def reset_runtime() -> None:
    """Reset cached runtime state, primarily for tests."""
    global _store, _knowledge_store, _embedder, _retriever, _active_farm_id, _seed_loaded, _soul_prompt, _brief_scheduler, _runtime_notices
    toolkit_context.reset_default_context()
    if _brief_scheduler is not None:
        _brief_scheduler.shutdown()
    _store = None
    _knowledge_store = None
    _embedder = None
    _retriever = None
    _active_farm_id = None
    _seed_loaded = False
    _soul_prompt = None
    _brief_scheduler = None
    _runtime_notices = []


def _data_dir() -> Path:
    return Path(os.environ.get("OPENPASTURE_DATA_DIR", Path.home() / ".openpasture")).expanduser()


def get_data_dir() -> Path:
    return toolkit_context.get_data_dir()


def get_skills_dir() -> Path:
    return toolkit_context.get_skills_dir()


def get_ingest_queue_path() -> Path:
    return toolkit_context.get_ingest_queue_path()


def get_ingestion_batches_dir() -> Path:
    return toolkit_context.get_ingestion_batches_dir()


def init_store(config: MutableMapping[str, object] | None = None) -> FarmStore:
    """Initialize the configured storage backend."""
    global _store
    if config is not None:
        context = toolkit_context.initialize(config)
        _store = context.get_store()
        return _store
    _store = toolkit_context.get_store()
    return _store


def init_knowledge_store(config: MutableMapping[str, object] | None = None) -> KnowledgeStore:
    """Initialize the configured knowledge backend."""
    del config
    global _knowledge_store
    _knowledge_store = toolkit_context.get_knowledge_store()
    return _knowledge_store


def init_knowledge(config: MutableMapping[str, object] | None = None) -> KnowledgeRetriever:
    """Initialize embedding and retrieval backends."""
    global _embedder, _retriever, _seed_loaded
    toolkit_context.load_seed_knowledge = load_seed_knowledge
    if config is not None:
        toolkit_context.initialize(config)
    _retriever = toolkit_context.get_knowledge()
    _embedder = toolkit_context.get_embedder()
    _seed_loaded = True
    return _retriever


def initialize(
    config: MutableMapping[str, object] | None = None,
    *,
    delivery_handler: Callable[[str], bool] | None = None,
) -> None:
    """Initialize all runtime services used by the plugin."""
    global _store, _knowledge_store, _embedder, _retriever, _brief_scheduler
    toolkit_context.load_seed_knowledge = load_seed_knowledge
    context = toolkit_context.initialize(config, delivery_handler=delivery_handler)
    _store = context.get_store()
    _knowledge_store = context.get_knowledge_store()
    _retriever = context.get_knowledge()
    _embedder = context.get_embedder()
    _brief_scheduler = context.get_brief_scheduler()


def init_brief_scheduler(
    config: MutableMapping[str, object] | None = None,
    *,
    delivery_handler: Callable[[str], bool] | None = None,
) -> MorningBriefScheduler:
    """Initialize recurring morning-brief scheduling."""
    global _brief_scheduler
    if config is not None or delivery_handler is not None:
        context = toolkit_context.initialize(config, delivery_handler=delivery_handler)
        _brief_scheduler = context.get_brief_scheduler()
        return _brief_scheduler
    _brief_scheduler = toolkit_context.get_brief_scheduler()
    return _brief_scheduler


def get_store() -> FarmStore:
    return toolkit_context.get_store()


def get_brief_scheduler() -> MorningBriefScheduler:
    return toolkit_context.get_brief_scheduler()


def refresh_runtime_notices() -> list[str]:
    global _runtime_notices
    _runtime_notices = toolkit_context.refresh_runtime_notices()
    return list(_runtime_notices)


def get_runtime_notices() -> list[str]:
    return toolkit_context.get_runtime_notices()


def get_embedder() -> KnowledgeEmbedder:
    return toolkit_context.get_embedder()


def get_knowledge_store() -> KnowledgeStore:
    return toolkit_context.get_knowledge_store()


def get_knowledge() -> KnowledgeRetriever:
    return toolkit_context.get_knowledge()


def set_active_farm_id(farm_id: str | None) -> None:
    global _active_farm_id
    _active_farm_id = farm_id
    toolkit_context.set_active_farm_id(farm_id)


def get_active_farm_id() -> str | None:
    return toolkit_context.get_active_farm_id()


def schedule_farm_brief(farm_id: str) -> None:
    toolkit_context.schedule_farm_brief(farm_id)


def get_soul_prompt() -> str:
    global _soul_prompt
    if _soul_prompt is None:
        soul_path = Path(__file__).resolve().parents[2] / "SOUL.md"
        _soul_prompt = soul_path.read_text().strip()
    return _soul_prompt


def _list_farms_safe() -> list[Any]:
    return toolkit_context.get_default_context().list_farms_safe()


def _format_farm_inventory(farms: list[Any], *, limit: int = 3) -> str:
    preview = ", ".join(f"{farm.id} ({farm.name})" for farm in farms[:limit])
    if len(farms) > limit:
        preview = f"{preview}, +{len(farms) - limit} more"
    return preview


def _resolve_active_farm_id() -> str | None:
    return toolkit_context.get_default_context().resolve_active_farm_id()


def resolve_farm_id(args: MutableMapping[str, object] | dict[str, object], *, key: str = "farm_id") -> str:
    return toolkit_context.resolve_farm_id(args, key=key)


def _resolve_context_farm() -> Any | None:
    farm_id = _resolve_active_farm_id()
    if farm_id is None:
        return None
    return get_store().get_farm(farm_id)


def _onboarding_gaps(farm_id: str) -> list[str]:
    store = get_store()
    paddocks = store.list_paddocks(farm_id)
    herds = store.get_herds(farm_id)
    gaps: list[str] = []
    if not herds:
        gaps.append("create the first herd")
    if not paddocks:
        gaps.append("add at least one paddock")
    if herds and not all(herd.current_paddock_id for herd in herds):
        gaps.append("set the herd's current paddock before the first brief")
    return gaps


def _build_workflow_context() -> list[str]:
    farm = _resolve_context_farm()
    if farm is None:
        farms = _list_farms_safe()
        if farms:
            return [
                "Workflow mode: daily-operations",
                "Multiple farms are registered for this instance. Pass farm_id explicitly for farm-specific tools until one farm becomes active.",
                f"Known farms: {_format_farm_inventory(farms)}",
            ]
        return [
            "Workflow mode: onboarding",
            "Prefer the setup_initial_farm tool for first-run setup.",
            "Do not call setup_initial_farm with empty args.",
            f"Preferred setup_initial_farm payload shape: {_ONBOARDING_TOOL_RECIPE}",
            "Create exactly one farm by default. Do not add another farm unless the operator explicitly asks for it and passes allow_additional_farm=true.",
            "Keep onboarding flexible for map screenshots, rough boundaries, and landmark clues, but persist structured geometry when possible and store any remaining clues in notes.",
            "After setup, record a field observation from the current paddock before expecting a strong MOVE or STAY brief.",
        ]

    gaps = _onboarding_gaps(farm.id)
    if gaps:
        return [
            "Workflow mode: onboarding",
            "Prefer the setup_initial_farm tool until the farm, first herd, paddocks, and herd position are all set.",
            "Do not call setup_initial_farm with empty args.",
            f"Preferred setup_initial_farm payload shape: {_ONBOARDING_TOOL_RECIPE}",
            "Onboarding remaining: " + "; ".join(gaps),
            "Use setup/admin tools only to finish onboarding or make an intentional farm change.",
            "If the user asks for a first brief right after setup, explain that a fresh field observation improves the recommendation.",
        ]

    return [
        "Workflow mode: daily-operations",
        "Focus on observations, morning briefs, movement decisions, and occasional maintenance for the active farm.",
        "Treat register_farm and setup_initial_farm as rare setup/admin tools, not part of the normal daily loop.",
        "When a farmer wants to connect a web-based data source, use the data-pipeline-setup skill and drive Firecrawl CLI directly, then persist the result with save_data_pipeline.",
    ]


def _build_pre_llm_guardrails() -> list[str]:
    farm = _resolve_context_farm()
    if farm is None:
        if _list_farms_safe():
            return [
                "When multiple farms exist and no active farm is selected, ask or infer the correct farm_id before farm-specific tool calls.",
            ]
        return [
            "If the user's latest message already contains first-run farm details, call setup_initial_farm immediately using those details.",
            "Never probe setup_initial_farm with empty args or {}.",
            f"Preferred setup_initial_farm payload shape: {_ONBOARDING_TOOL_RECIPE}",
        ]

    gaps = _onboarding_gaps(farm.id)
    if gaps:
        return [
            "While onboarding is still incomplete, use setup_initial_farm or the minimum setup/admin tools needed to finish setup.",
            "Never probe setup_initial_farm with empty args or {}.",
        ]

    return [
        "For daily operations, prefer the active farm context and avoid redundant lookup calls when one farm is already active.",
        "When the user wants to connect or test a web-based farm service, use the data-pipeline-setup skill first, operate Firecrawl from the CLI in the same live session, and call save_data_pipeline only after you know what to collect.",
    ]


def _format_known_paddocks(paddocks: list[Any], *, limit: int = 5) -> str:
    preview = ", ".join(f"{paddock.id} ({paddock.name})" for paddock in paddocks[:limit])
    if len(paddocks) > limit:
        preview = f"{preview}, +{len(paddocks) - limit} more"
    return preview


def _list_pipelines_safe(farm_id: str) -> list[Any]:
    try:
        return list(get_store().list_pipelines(farm_id))
    except (AttributeError, NotImplementedError):
        return []


def build_session_context(*, include_workflow_guidance: bool = True) -> str:
    notices = get_runtime_notices()
    lines = [f"Notice: {notice}" for notice in notices]
    if include_workflow_guidance:
        lines.extend(_build_workflow_context())

    farm = _resolve_context_farm()
    if farm is None:
        farms = _list_farms_safe()
        if farms:
            lines.append(f"Known farms: {_format_farm_inventory(farms)}")
        lines.append("No active farm is loaded yet.")
        return "\n".join(lines)

    store = get_store()
    farm_id = farm.id
    paddocks = store.list_paddocks(farm_id)
    herds = store.get_herds(farm_id)
    pipelines = _list_pipelines_safe(farm_id)
    latest_plan = store.get_latest_plan(farm_id)
    recent_obs = store.get_recent_observations(farm_id, days=3)

    lines.extend(
        [
        f"Active farm: {farm.name}",
        f"Active farm id: {farm.id}",
        f"Timezone: {farm.timezone}",
        f"Paddocks: {len(paddocks)}",
        f"Herds: {len(herds)}",
        f"Data pipelines: {len(pipelines)}",
        ]
    )
    if herds:
        herd = herds[0]
        lines.append(f"Primary herd id: {herd.id}")
        lines.append(f"Primary herd: {herd.species} ({herd.count}) in paddock {herd.current_paddock_id or 'unknown'}")
    if paddocks:
        lines.append(f"Known paddocks: {_format_known_paddocks(paddocks)}")
    if latest_plan:
        lines.append(
            f"Latest plan: {latest_plan.action} on {latest_plan.for_date.isoformat()} ({latest_plan.status})"
        )
    if recent_obs:
        lines.append(f"Recent observations available: {len(recent_obs)}")
    return "\n".join(lines)


def _find_payload(args: tuple[object, ...], kwargs: dict[str, object]) -> MutableMapping[str, object] | None:
    for value in args:
        if isinstance(value, MutableMapping):
            return value
    for value in kwargs.values():
        if isinstance(value, MutableMapping):
            return value
    return None


def _inject_system_text(payload: MutableMapping[str, object], text: str) -> None:
    if "system_prompt" in payload and isinstance(payload["system_prompt"], str):
        payload["system_prompt"] = f"{payload['system_prompt']}\n\n{text}".strip()
        return
    if "system" in payload and isinstance(payload["system"], str):
        payload["system"] = f"{payload['system']}\n\n{text}".strip()
        return
    messages = payload.get("messages")
    if isinstance(messages, list):
        messages.insert(0, {"role": "system", "content": text})
        return
    prompts = payload.get("system_prompts")
    if isinstance(prompts, list):
        prompts.append(text)
        return
    payload["openpasture_system_context"] = text


def on_session_start(*args: object, **kwargs: object) -> str:
    """Best-effort hook to inject current farm context."""
    text = build_session_context()
    payload = _find_payload(args, kwargs)
    if payload is not None:
        _inject_system_text(payload, text)
    return text


def pre_llm_call(*args: object, **kwargs: object) -> str:
    """Best-effort hook to inject the agent voice before model calls."""
    guardrails = "\n".join(_build_pre_llm_guardrails())
    text = (
        f"{get_soul_prompt()}\n\n"
        f"Live tool guardrails:\n{guardrails}\n\n"
        f"Current context:\n{build_session_context(include_workflow_guidance=False)}"
    )
    payload = _find_payload(args, kwargs)
    if payload is not None:
        _inject_system_text(payload, text)
    return text
