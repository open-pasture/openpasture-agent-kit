"""SQLite backend for self-hosted openPasture deployments."""

from __future__ import annotations

from pathlib import Path


class SQLiteStore:
    """Placeholder SQLite-backed implementation of the FarmStore protocol."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def bootstrap(self) -> None:
        """Prepare local storage files for a self-hosted install."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        raise NotImplementedError("SQLiteStore.bootstrap is not implemented yet.")
