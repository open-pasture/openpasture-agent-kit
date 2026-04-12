"""Runtime initialization and shared state for openPasture."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, MutableMapping

from openpasture.knowledge.embedder import KnowledgeEmbedder
from openpasture.knowledge.retriever import KnowledgeRetriever
from openpasture.knowledge.seed_loader import load_seed_knowledge
from openpasture.store.convex import ConvexStore
from openpasture.store.protocol import FarmStore
from openpasture.store.sqlite import SQLiteStore

_store: FarmStore | None = None
_embedder: KnowledgeEmbedder | None = None
_retriever: KnowledgeRetriever | None = None
_active_farm_id: str | None = None
_seed_loaded = False
_soul_prompt: str | None = None


def reset_runtime() -> None:
    """Reset cached runtime state, primarily for tests."""
    global _store, _embedder, _retriever, _active_farm_id, _seed_loaded, _soul_prompt
    _store = None
    _embedder = None
    _retriever = None
    _active_farm_id = None
    _seed_loaded = False
    _soul_prompt = None


def _data_dir() -> Path:
    return Path(os.environ.get("OPENPASTURE_DATA_DIR", Path.home() / ".openpasture")).expanduser()


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
        _store = ConvexStore(deployment_url=deployment_url, deploy_key=deploy_key)
        return _store

    raise ValueError(f"Unsupported OPENPASTURE_STORE backend '{backend}'.")


def init_knowledge(config: MutableMapping[str, object] | None = None) -> KnowledgeRetriever:
    """Initialize embedding and retrieval backends."""
    global _embedder, _retriever, _seed_loaded
    if _retriever is not None:
        return _retriever

    persist_dir = _data_dir() / "chroma"
    _embedder = KnowledgeEmbedder(persist_dir=persist_dir)
    _retriever = KnowledgeRetriever(persist_dir=persist_dir, store=get_store())

    should_load_seed = os.environ.get("OPENPASTURE_LOAD_SEED", "1") != "0"
    if should_load_seed and not _seed_loaded:
        load_seed_knowledge(get_store(), _embedder)
        _seed_loaded = True
    return _retriever


def initialize(config: MutableMapping[str, object] | None = None) -> None:
    """Initialize all runtime services used by the plugin."""
    init_store(config)
    init_knowledge(config)


def get_store() -> FarmStore:
    if _store is None:
        return init_store()
    return _store


def get_embedder() -> KnowledgeEmbedder:
    if _embedder is None:
        init_knowledge()
    if _embedder is None:
        raise RuntimeError("Knowledge embedder is not initialized.")
    return _embedder


def get_knowledge() -> KnowledgeRetriever:
    if _retriever is None:
        return init_knowledge()
    return _retriever


def set_active_farm_id(farm_id: str | None) -> None:
    global _active_farm_id
    _active_farm_id = farm_id


def get_active_farm_id() -> str | None:
    return _active_farm_id


def get_soul_prompt() -> str:
    global _soul_prompt
    if _soul_prompt is None:
        soul_path = Path(__file__).resolve().parents[2] / "SOUL.md"
        _soul_prompt = soul_path.read_text().strip()
    return _soul_prompt


def build_session_context() -> str:
    farm_id = get_active_farm_id()
    if not farm_id:
        return "No active farm is loaded yet."

    store = get_store()
    farm = store.get_farm(farm_id)
    if farm is None:
        return "No active farm is loaded yet."

    paddocks = store.list_paddocks(farm_id)
    herds = store.get_herds(farm_id)
    latest_plan = store.get_latest_plan(farm_id)
    recent_obs = store.get_recent_observations(farm_id, days=3)

    lines = [
        f"Active farm: {farm.name}",
        f"Timezone: {farm.timezone}",
        f"Paddocks: {len(paddocks)}",
        f"Herds: {len(herds)}",
    ]
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
