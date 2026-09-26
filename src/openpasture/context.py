"""Runtime-agnostic Openpasture agent kit context.

The context is the reusable kernel that connectors, CLIs, tests, and hosted
wrappers can share. It owns storage, knowledge retrieval, the land and collar
connectors, the decision engine, data directories, and optional scheduling
without knowing which agent runtime is driving it.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import timedelta
from logging import getLogger
from pathlib import Path
from typing import Callable, Iterator, MutableMapping, TYPE_CHECKING

from openpasture.knowledge.embedder import KnowledgeEmbedder
from openpasture.knowledge.retriever import KnowledgeRetriever
from openpasture.knowledge.seed_loader import load_seed_knowledge
from openpasture.store.convex import ConvexStore
from openpasture.store.knowledge_protocol import KnowledgeStore
from openpasture.store.protocol import FarmStore
from openpasture.store.sqlite import SQLiteStore
from openpasture.store.sqlite_knowledge import SQLiteKnowledgeStore

if TYPE_CHECKING:
    from openpasture.briefing.engine import DecisionEngine
    from openpasture.briefing.scheduler import DecisionScheduler
    from openpasture.collars import CollarGateway, CollarService
    from openpasture.land import LandReportService, LandSource

logger = getLogger(__name__)


@dataclass
class OpenPastureConfig:
    """Configuration for one openPasture toolkit context."""

    data_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("OPENPASTURE_DATA_DIR", Path.home() / ".openpasture")
        ).expanduser()
    )
    skills_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "OPENPASTURE_SKILLS_DIR",
                Path(__file__).resolve().parents[2] / "skills",
            )
        ).expanduser()
    )
    seed_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2] / "seed")
    store_backend: str = field(default_factory=lambda: os.environ.get("OPENPASTURE_STORE", "sqlite"))
    brief_time: str = field(default_factory=lambda: os.environ.get("OPENPASTURE_BRIEF_TIME", "06:00"))
    convex_url: str = field(default_factory=lambda: os.environ.get("OPENPASTURE_CONVEX_URL", ""))
    convex_key: str | None = field(default_factory=lambda: os.environ.get("OPENPASTURE_CONVEX_KEY"))
    load_seed_mode: str | None = field(default_factory=lambda: os.environ.get("OPENPASTURE_LOAD_SEED"))
    land_source: str = field(default_factory=lambda: os.environ.get("OPENPASTURE_LAND_SOURCE", "auto"))
    land_report_max_age_hours: float = field(
        default_factory=lambda: float(os.environ.get("OPENPASTURE_LAND_REPORT_MAX_AGE_HOURS", "6"))
    )
    collar_gateway: str = field(default_factory=lambda: os.environ.get("OPENPASTURE_COLLAR_GATEWAY", "simulated"))
    boundary_activation_threshold: float = field(
        default_factory=lambda: float(os.environ.get("OPENPASTURE_BOUNDARY_ACTIVATION_THRESHOLD", "1.0"))
    )
    collar_fix_retention_days: int = field(
        default_factory=lambda: int(os.environ.get("OPENPASTURE_COLLAR_FIX_RETENTION_DAYS", "30"))
    )

    @classmethod
    def from_mapping(cls, config: MutableMapping[str, object] | None = None) -> "OpenPastureConfig":
        base = cls()
        if not config:
            return base
        if isinstance(config.get("data_dir"), (str, Path)):
            base.data_dir = Path(config["data_dir"]).expanduser()
        if isinstance(config.get("skills_dir"), (str, Path)):
            base.skills_dir = Path(config["skills_dir"]).expanduser()
        if isinstance(config.get("seed_dir"), (str, Path)):
            base.seed_dir = Path(config["seed_dir"]).expanduser()
        if isinstance(config.get("store"), str):
            base.store_backend = str(config["store"])
        if isinstance(config.get("store_backend"), str):
            base.store_backend = str(config["store_backend"])
        if isinstance(config.get("brief_time"), str):
            base.brief_time = str(config["brief_time"])
        if isinstance(config.get("convex_url"), str):
            base.convex_url = str(config["convex_url"])
        if isinstance(config.get("convex_key"), str):
            base.convex_key = str(config["convex_key"])
        if isinstance(config.get("load_seed_mode"), str):
            base.load_seed_mode = str(config["load_seed_mode"])
        if isinstance(config.get("land_source"), str):
            base.land_source = str(config["land_source"])
        if isinstance(config.get("collar_gateway"), str):
            base.collar_gateway = str(config["collar_gateway"])
        if isinstance(config.get("boundary_activation_threshold"), (int, float)):
            base.boundary_activation_threshold = float(config["boundary_activation_threshold"])
        return base


class OpenPastureContext:
    """Holds openPasture services for one agent, CLI, or automation process."""

    def __init__(
        self,
        config: OpenPastureConfig | MutableMapping[str, object] | None = None,
        *,
        delivery_handler: Callable[[str], bool] | None = None,
        land_source: LandSource | None = None,
        collar_gateway: CollarGateway | None = None,
    ) -> None:
        self.config = config if isinstance(config, OpenPastureConfig) else OpenPastureConfig.from_mapping(config)
        self.delivery_handler = delivery_handler
        self._land_source = land_source
        self._collar_gateway = collar_gateway
        self._land_service: LandReportService | None = None
        self._collar_service: CollarService | None = None
        self._store: FarmStore | None = None
        self._knowledge_store: KnowledgeStore | None = None
        self._embedder: KnowledgeEmbedder | None = None
        self._retriever: KnowledgeRetriever | None = None
        self._brief_scheduler: DecisionScheduler | None = None
        self._seed_loaded = False
        self.active_farm_id: str | None = None
        self.runtime_notices: list[str] = []

    @property
    def data_dir(self) -> Path:
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        return self.config.data_dir

    @property
    def skills_dir(self) -> Path:
        if env_skills_dir := os.environ.get("OPENPASTURE_SKILLS_DIR"):
            self.config.skills_dir = Path(env_skills_dir).expanduser()
        self.config.skills_dir.mkdir(parents=True, exist_ok=True)
        return self.config.skills_dir

    @property
    def seed_dir(self) -> Path:
        return self.config.seed_dir

    @property
    def ingest_queue_path(self) -> Path:
        return self.data_dir / "ingest-queue.json"

    @property
    def ingestion_batches_dir(self) -> Path:
        path = self.data_dir / "knowledge-batches"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def initialize(self, *, delivery_handler: Callable[[str], bool] | None = None) -> None:
        """Initialize stores, knowledge, and optional scheduling."""

        if delivery_handler is not None:
            self.delivery_handler = delivery_handler
        self.refresh_runtime_notices()
        self.get_store()
        self.get_knowledge_store()
        self.get_knowledge()
        self.get_brief_scheduler()

    def shutdown(self) -> None:
        if self._brief_scheduler is not None:
            self._brief_scheduler.shutdown()
        self._brief_scheduler = None

    def get_store(self) -> FarmStore:
        if self._store is not None:
            return self._store

        backend = self.config.store_backend.lower()
        if backend == "sqlite":
            store = SQLiteStore(self.config.data_dir)
            store.bootstrap()
            self._store = store
            return store

        if backend == "convex":
            if not self.config.convex_url.strip():
                raise ValueError("OPENPASTURE_STORE=convex requires OPENPASTURE_CONVEX_URL to be set.")
            if not self.config.convex_key:
                raise ValueError("OPENPASTURE_STORE=convex requires OPENPASTURE_CONVEX_KEY to be set.")
            self._store = ConvexStore(
                deployment_url=self.config.convex_url,
                deploy_key=self.config.convex_key,
            )
            return self._store

        raise ValueError(f"Unsupported OPENPASTURE_STORE backend '{backend}'.")

    def get_knowledge_store(self) -> KnowledgeStore:
        if self._knowledge_store is not None:
            return self._knowledge_store
        store = SQLiteKnowledgeStore(self.data_dir)
        store.bootstrap()
        self._knowledge_store = store
        return store

    def get_knowledge(self) -> KnowledgeRetriever:
        if self._retriever is not None:
            return self._retriever

        persist_dir = self.data_dir / "chroma"
        self._embedder = KnowledgeEmbedder(persist_dir=persist_dir)
        knowledge_store = self.get_knowledge_store()
        self._retriever = KnowledgeRetriever(persist_dir=persist_dir, store=knowledge_store)

        force_skip_seed = self.config.load_seed_mode == "0"
        force_reload_seed = self.config.load_seed_mode == "1"
        should_auto_load_seed = not force_skip_seed and knowledge_store.count() == 0
        if force_reload_seed or (should_auto_load_seed and not self._seed_loaded):
            loaded_entries = load_seed_knowledge(knowledge_store, self._embedder)
            self._seed_loaded = True
            if loaded_entries:
                reason = "forced reload" if force_reload_seed else "first-run bootstrap"
                logger.info("Loaded %s seed knowledge entries during %s.", len(loaded_entries), reason)
        return self._retriever

    def get_embedder(self) -> KnowledgeEmbedder:
        if self._embedder is None:
            self.get_knowledge()
        if self._embedder is None:
            raise RuntimeError("Knowledge embedder is not initialized.")
        return self._embedder

    def get_land_source(self) -> LandSource:
        if self._land_source is None:
            from openpasture.land import land_source_from_env

            self._land_source = land_source_from_env(self.config.land_source)
        return self._land_source

    def set_land_source(self, source: LandSource) -> None:
        self._land_source = source
        self._land_service = None

    def get_land_service(self) -> LandReportService:
        if self._land_service is None:
            from openpasture.land import LandReportService

            self._land_service = LandReportService(
                self.get_store(),
                self.get_land_source(),
                max_age=timedelta(hours=self.config.land_report_max_age_hours),
            )
        return self._land_service

    def get_collar_gateway(self) -> CollarGateway:
        if self._collar_gateway is None:
            from openpasture.collars import collar_gateway_from_env

            self._collar_gateway = collar_gateway_from_env(self.config.collar_gateway)
        return self._collar_gateway

    def set_collar_gateway(self, gateway: CollarGateway) -> None:
        self._collar_gateway = gateway
        self._collar_service = None

    def get_collar_service(self) -> CollarService:
        if self._collar_service is None:
            from openpasture.collars import CollarService

            self._collar_service = CollarService(
                self.get_store(),
                self.get_collar_gateway(),
                activation_threshold=self.config.boundary_activation_threshold,
                retention_days=self.config.collar_fix_retention_days,
            )
        return self._collar_service

    def get_decision_engine(self) -> DecisionEngine:
        """A decision engine bound to this context's store and connectors."""

        from openpasture.briefing.engine import DecisionEngine

        try:
            retriever = self.get_knowledge()
        except Exception:
            logger.warning("Knowledge retrieval is unavailable; deciding without it.", exc_info=True)
            retriever = None
        return DecisionEngine(
            self.get_store(),
            land=self.get_land_service(),
            collars=self.get_collar_service(),
            retriever=retriever,
            default_window_start_time=self.config.brief_time or "06:00",
            default_activation_threshold=self.config.boundary_activation_threshold,
        )

    def get_decision_scheduler(self) -> DecisionScheduler:
        return self.get_brief_scheduler()

    def get_brief_scheduler(self) -> DecisionScheduler:
        from openpasture.briefing.scheduler import DecisionScheduler, parse_brief_time

        hour, minute = parse_brief_time(self.config.brief_time)
        if self._brief_scheduler is None:
            self._brief_scheduler = DecisionScheduler(
                store=self.get_store(),
                engine_factory=self.get_decision_engine,
                deliver_fn=self.delivery_handler,
                default_hour=hour,
                default_minute=minute,
            )
        elif self.delivery_handler is not None:
            self._brief_scheduler.set_delivery_handler(self.delivery_handler)

        try:
            farms = self.get_store().list_farms()
        except (AttributeError, NotImplementedError):
            logger.info("Skipping brief scheduler bootstrap for the active store backend.")
            return self._brief_scheduler

        for farm in farms:
            self._brief_scheduler.schedule(farm.id, farm.timezone)
        return self._brief_scheduler

    def refresh_runtime_notices(self) -> list[str]:
        notices: list[str] = []
        if not os.environ.get("FIRECRAWL_API_KEY", "").strip():
            notices.append("Knowledge ingestion from web sources is unavailable until FIRECRAWL_API_KEY is set.")
            if self.config.land_source.strip().lower() == "auto":
                notices.append(
                    "Alexandria land reports are unavailable until FIRECRAWL_API_KEY is set; "
                    "weather comes from Open-Meteo and imagery is unavailable."
                )
        if self.config.collar_gateway.strip().lower() == "simulated":
            notices.append("Collars are simulated (OPENPASTURE_COLLAR_GATEWAY=simulated); boundaries do not reach real collars.")
        self.runtime_notices = notices
        return list(notices)

    def get_runtime_notices(self) -> list[str]:
        if not self.runtime_notices:
            self.refresh_runtime_notices()
        return list(self.runtime_notices)

    def set_active_farm_id(self, farm_id: str | None) -> None:
        self.active_farm_id = farm_id

    def get_active_farm_id(self) -> str | None:
        return self.active_farm_id

    def schedule_farm_brief(self, farm_id: str) -> None:
        farm = self.get_store().get_farm(farm_id)
        if farm is None:
            return
        self.get_brief_scheduler().schedule(farm.id, farm.timezone)

    def list_farms_safe(self) -> list[object]:
        try:
            return list(self.get_store().list_farms())
        except (AttributeError, NotImplementedError):
            return []

    def resolve_active_farm_id(self) -> str | None:
        farm_id = self.get_active_farm_id()
        if farm_id and self.get_store().get_farm(farm_id) is not None:
            return farm_id
        farms = self.list_farms_safe()
        if len(farms) == 1:
            self.set_active_farm_id(farms[0].id)
            return farms[0].id
        return None

    def resolve_farm_id(
        self,
        args: MutableMapping[str, object] | dict[str, object],
        *,
        key: str = "farm_id",
    ) -> str:
        explicit_farm_id = args.get(key)
        if isinstance(explicit_farm_id, str) and explicit_farm_id.strip():
            farm_id = explicit_farm_id.strip()
            self.set_active_farm_id(farm_id)
            return farm_id

        if active_farm_id := self.resolve_active_farm_id():
            return active_farm_id

        farms = self.list_farms_safe()
        if not farms:
            raise ValueError("No farm is loaded yet. Register a farm first or pass 'farm_id' explicitly.")
        raise ValueError(
            "Multiple farms are registered for this instance. Pass 'farm_id' explicitly for farm-specific tools."
        )


_default_context: OpenPastureContext | None = None
_bound_context: ContextVar[OpenPastureContext | None] = ContextVar(
    "openpasture_bound_context",
    default=None,
)


@contextmanager
def bind_context(context: OpenPastureContext) -> Iterator[OpenPastureContext]:
    """Bind an OpenPasture context to the current request/task."""

    token = _bound_context.set(context)
    try:
        yield context
    finally:
        _bound_context.reset(token)


def get_default_context() -> OpenPastureContext:
    global _default_context
    if context := _bound_context.get():
        return context
    if _default_context is None:
        _default_context = OpenPastureContext()
    return _default_context


def set_default_context(context: OpenPastureContext | None) -> None:
    global _default_context
    if _default_context is not None and _default_context is not context:
        _default_context.shutdown()
    _default_context = context


def reset_default_context() -> None:
    set_default_context(None)
    _bound_context.set(None)


def initialize(
    config: MutableMapping[str, object] | None = None,
    *,
    delivery_handler: Callable[[str], bool] | None = None,
) -> OpenPastureContext:
    context = OpenPastureContext(config, delivery_handler=delivery_handler)
    context.initialize()
    set_default_context(context)
    return context


def get_data_dir() -> Path:
    return get_default_context().data_dir


def get_skills_dir() -> Path:
    return get_default_context().skills_dir


def get_ingest_queue_path() -> Path:
    return get_default_context().ingest_queue_path


def get_ingestion_batches_dir() -> Path:
    return get_default_context().ingestion_batches_dir


def get_store() -> FarmStore:
    return get_default_context().get_store()


def get_knowledge_store() -> KnowledgeStore:
    return get_default_context().get_knowledge_store()


def get_knowledge() -> KnowledgeRetriever:
    return get_default_context().get_knowledge()


def get_embedder() -> KnowledgeEmbedder:
    return get_default_context().get_embedder()


def get_brief_scheduler() -> DecisionScheduler:
    return get_default_context().get_brief_scheduler()


def get_decision_scheduler() -> DecisionScheduler:
    return get_default_context().get_decision_scheduler()


def get_land_service() -> LandReportService:
    return get_default_context().get_land_service()


def get_collar_service() -> CollarService:
    return get_default_context().get_collar_service()


def get_decision_engine() -> DecisionEngine:
    return get_default_context().get_decision_engine()


def get_runtime_notices() -> list[str]:
    return get_default_context().get_runtime_notices()


def refresh_runtime_notices() -> list[str]:
    return get_default_context().refresh_runtime_notices()


def set_active_farm_id(farm_id: str | None) -> None:
    get_default_context().set_active_farm_id(farm_id)


def get_active_farm_id() -> str | None:
    return get_default_context().get_active_farm_id()


def resolve_farm_id(args: MutableMapping[str, object] | dict[str, object], *, key: str = "farm_id") -> str:
    return get_default_context().resolve_farm_id(args, key=key)


def schedule_farm_brief(farm_id: str) -> None:
    get_default_context().schedule_farm_brief(farm_id)
