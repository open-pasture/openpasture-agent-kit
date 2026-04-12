"""Runtime initialization and shared state for openPasture."""

from __future__ import annotations

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


def build_session_context() -> str:
    notices = get_runtime_notices()
    farm_id = get_active_farm_id()
    if not farm_id:
        lines = [f"Notice: {notice}" for notice in notices]
        lines.append("No active farm is loaded yet.")
        return "\n".join(lines)

    store = get_store()
    farm = store.get_farm(farm_id)
    if farm is None:
        lines = [f"Notice: {notice}" for notice in notices]
        lines.append("No active farm is loaded yet.")
        return "\n".join(lines)

    paddocks = store.list_paddocks(farm_id)
    herds = store.get_herds(farm_id)
    latest_plan = store.get_latest_plan(farm_id)
    recent_obs = store.get_recent_observations(farm_id, days=3)

    lines = [f"Notice: {notice}" for notice in notices]
    lines.extend(
        [
        f"Active farm: {farm.name}",
        f"Timezone: {farm.timezone}",
        f"Paddocks: {len(paddocks)}",
        f"Herds: {len(herds)}",
        ]
    )
    if herds:
        herd = herds[0]
        lines.append(f"Primary herd: {herd.species} ({herd.count}) in paddock {herd.current_paddock_id or 'unknown'}")
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
    text = f"{get_soul_prompt()}\n\nCurrent context:\n{build_session_context()}"
    payload = _find_payload(args, kwargs)
    if payload is not None:
        _inject_system_text(payload, text)
    return text
