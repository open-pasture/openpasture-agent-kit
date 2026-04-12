"""Runtime initialization and shared state for openPasture."""

from __future__ import annotations

import json
import os
from logging import getLogger
from pathlib import Path
from typing import Any, Callable, MutableMapping, TYPE_CHECKING

from openpasture.knowledge.embedder import KnowledgeEmbedder
from openpasture.knowledge.retriever import KnowledgeRetriever
from openpasture.knowledge.seed_loader import load_seed_knowledge
from openpasture.store.convex import ConvexStore
from openpasture.store.knowledge_protocol import KnowledgeStore
from openpasture.store.protocol import FarmStore
from openpasture.store.sqlite import SQLiteStore
from openpasture.store.sqlite_knowledge import SQLiteKnowledgeStore

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
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_ingest_queue_path() -> Path:
    return get_data_dir() / "ingest-queue.json"


def get_ingestion_batches_dir() -> Path:
    batches_dir = get_data_dir() / "knowledge-batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    return batches_dir


def init_store(config: MutableMapping[str, object] | None = None) -> FarmStore:
    """Initialize the configured storage backend."""
    global _store
    if _store is not None:
        return _store

    backend = str(os.environ.get("OPENPASTURE_STORE", "sqlite")).lower()
    if config and isinstance(config.get("store"), str):
        backend = str(config["store"]).lower()

    if backend == "sqlite":
        store = SQLiteStore(_data_dir())
        store.bootstrap()
        _store = store
        return _store

    if backend == "convex":
        deployment_url = os.environ.get("OPENPASTURE_CONVEX_URL", "")
        deploy_key = os.environ.get("OPENPASTURE_CONVEX_KEY")
        if not deployment_url.strip():
            raise ValueError(
                "OPENPASTURE_STORE=convex requires OPENPASTURE_CONVEX_URL to be set."
            )
        if not deploy_key:
            raise ValueError(
                "OPENPASTURE_STORE=convex requires OPENPASTURE_CONVEX_KEY to be set."
            )
        _store = ConvexStore(deployment_url=deployment_url, deploy_key=deploy_key)
        return _store

    raise ValueError(f"Unsupported OPENPASTURE_STORE backend '{backend}'.")


def init_knowledge_store(config: MutableMapping[str, object] | None = None) -> KnowledgeStore:
    """Initialize the configured knowledge backend."""
    del config
    global _knowledge_store
    if _knowledge_store is not None:
        return _knowledge_store

    knowledge_store = SQLiteKnowledgeStore(get_data_dir())
    knowledge_store.bootstrap()
    _knowledge_store = knowledge_store
    return _knowledge_store


def init_knowledge(config: MutableMapping[str, object] | None = None) -> KnowledgeRetriever:
    """Initialize embedding and retrieval backends."""
    global _embedder, _retriever, _seed_loaded
    if _retriever is not None:
        return _retriever

    persist_dir = get_data_dir() / "chroma"
    _embedder = KnowledgeEmbedder(persist_dir=persist_dir)
    knowledge_store = get_knowledge_store()
    _retriever = KnowledgeRetriever(persist_dir=persist_dir, store=knowledge_store)

    seed_mode = os.environ.get("OPENPASTURE_LOAD_SEED")
    force_skip_seed = seed_mode == "0"
    force_reload_seed = seed_mode == "1"
    should_auto_load_seed = not force_skip_seed and knowledge_store.count() == 0

    if _embedder is not None and (force_reload_seed or (should_auto_load_seed and not _seed_loaded)):
        loaded_entries = load_seed_knowledge(knowledge_store, _embedder)
        _seed_loaded = True
        if loaded_entries:
            reason = "forced reload" if force_reload_seed else "first-run bootstrap"
            logger.info("Loaded %s seed knowledge entries during %s.", len(loaded_entries), reason)
    return _retriever


def initialize(
    config: MutableMapping[str, object] | None = None,
    *,
    delivery_handler: Callable[[str], bool] | None = None,
) -> None:
    """Initialize all runtime services used by the plugin."""
    refresh_runtime_notices()
    init_store(config)
    init_knowledge_store(config)
    init_knowledge(config)
    init_brief_scheduler(config, delivery_handler=delivery_handler)


def init_brief_scheduler(
    config: MutableMapping[str, object] | None = None,
    *,
    delivery_handler: Callable[[str], bool] | None = None,
) -> MorningBriefScheduler:
    """Initialize recurring morning-brief scheduling."""

    del config
    global _brief_scheduler
    from openpasture.briefing.scheduler import MorningBriefScheduler, parse_brief_time

    hour, minute = parse_brief_time(os.environ.get("OPENPASTURE_BRIEF_TIME", "06:00"))
    if _brief_scheduler is None:
        _brief_scheduler = MorningBriefScheduler(
            store=get_store(),
            deliver_fn=delivery_handler,
            default_hour=hour,
            default_minute=minute,
        )
    elif delivery_handler is not None:
        _brief_scheduler.set_delivery_handler(delivery_handler)

    try:
        farms = get_store().list_farms()
    except (AttributeError, NotImplementedError):
        logger.info("Skipping brief scheduler bootstrap for the active store backend.")
        return _brief_scheduler

    for farm in farms:
        _brief_scheduler.schedule(farm.id, farm.timezone)
    return _brief_scheduler


def get_store() -> FarmStore:
    if _store is None:
        return init_store()
    return _store


def get_brief_scheduler() -> MorningBriefScheduler:
    if _brief_scheduler is None:
        return init_brief_scheduler()
    return _brief_scheduler


def refresh_runtime_notices() -> list[str]:
    global _runtime_notices
    notices: list[str] = []
    if not os.environ.get("FIRECRAWL_API_KEY", "").strip():
        notices.append("Knowledge ingestion from web sources is unavailable until FIRECRAWL_API_KEY is set.")
    _runtime_notices = notices
    return list(_runtime_notices)


def get_runtime_notices() -> list[str]:
    if not _runtime_notices:
        refresh_runtime_notices()
    return list(_runtime_notices)


def get_embedder() -> KnowledgeEmbedder:
    if _embedder is None:
        init_knowledge()
    if _embedder is None:
        raise RuntimeError("Knowledge embedder is not initialized.")
    return _embedder


def get_knowledge_store() -> KnowledgeStore:
    if _knowledge_store is None:
        return init_knowledge_store()
    return _knowledge_store


def get_knowledge() -> KnowledgeRetriever:
    if _retriever is None:
        return init_knowledge()
    return _retriever


def set_active_farm_id(farm_id: str | None) -> None:
    global _active_farm_id
    _active_farm_id = farm_id


def get_active_farm_id() -> str | None:
    return _active_farm_id


def schedule_farm_brief(farm_id: str) -> None:
    farm = get_store().get_farm(farm_id)
    if farm is None:
        return
    get_brief_scheduler().schedule(farm.id, farm.timezone)


def get_soul_prompt() -> str:
    global _soul_prompt
    if _soul_prompt is None:
        soul_path = Path(__file__).resolve().parents[2] / "SOUL.md"
        _soul_prompt = soul_path.read_text().strip()
    return _soul_prompt


def _list_farms_safe() -> list[Any]:
    try:
        return list(get_store().list_farms())
    except (AttributeError, NotImplementedError):
        return []


def _format_farm_inventory(farms: list[Any], *, limit: int = 3) -> str:
    preview = ", ".join(f"{farm.id} ({farm.name})" for farm in farms[:limit])
    if len(farms) > limit:
        preview = f"{preview}, +{len(farms) - limit} more"
    return preview


def _resolve_active_farm_id() -> str | None:
    farm_id = get_active_farm_id()
    if farm_id and get_store().get_farm(farm_id) is not None:
        return farm_id
    farms = _list_farms_safe()
    if len(farms) == 1:
        set_active_farm_id(farms[0].id)
        return farms[0].id
    return None


def resolve_farm_id(args: MutableMapping[str, object] | dict[str, object], *, key: str = "farm_id") -> str:
    explicit_farm_id = args.get(key)
    if isinstance(explicit_farm_id, str) and explicit_farm_id.strip():
        farm_id = explicit_farm_id.strip()
        set_active_farm_id(farm_id)
        return farm_id

    if active_farm_id := _resolve_active_farm_id():
        return active_farm_id

    farms = _list_farms_safe()
    if not farms:
        raise ValueError("No farm is loaded yet. Register a farm first or pass 'farm_id' explicitly.")
    raise ValueError(
        "Multiple farms are registered for this instance. Pass 'farm_id' explicitly for farm-specific tools."
    )


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
    ]


def _format_known_paddocks(paddocks: list[Any], *, limit: int = 5) -> str:
    preview = ", ".join(f"{paddock.id} ({paddock.name})" for paddock in paddocks[:limit])
    if len(paddocks) > limit:
        preview = f"{preview}, +{len(paddocks) - limit} more"
    return preview


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
    latest_plan = store.get_latest_plan(farm_id)
    recent_obs = store.get_recent_observations(farm_id, days=3)

    lines.extend(
        [
        f"Active farm: {farm.name}",
        f"Active farm id: {farm.id}",
        f"Timezone: {farm.timezone}",
        f"Paddocks: {len(paddocks)}",
        f"Herds: {len(herds)}",
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
