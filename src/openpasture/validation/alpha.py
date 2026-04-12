"""Reusable alpha validation harness for openPasture maintainers."""

from __future__ import annotations

import argparse
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import tomllib

REQUIRED_SQLITE_FILES = ("farm.db", "knowledge.db")


@dataclass(frozen=True)
class AlphaValidationConfig:
    tested_hermes_version: str
    tested_hermes_commit: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_validation_config(pyproject_path: Path | None = None) -> AlphaValidationConfig:
    root = pyproject_path or (repo_root() / "pyproject.toml")
    payload = tomllib.loads(root.read_text())
    config = payload["tool"]["openpasture"]["alpha_validation"]
    return AlphaValidationConfig(
        tested_hermes_version=str(config["tested_hermes_version"]),
        tested_hermes_commit=str(config["tested_hermes_commit"]),
    )


def run_command(command: list[str], *, cwd: Path | None = None) -> None:
    print(f"$ {shlex.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def run_automated_suite() -> None:
    config = load_validation_config()
    print(
        "Running OSS alpha validation against Hermes "
        f"{config.tested_hermes_version} ({config.tested_hermes_commit[:12]}).",
        flush=True,
    )
    run_command([sys.executable, "-m", "pytest", "-m", "alpha"], cwd=repo_root())


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker CLI is not installed or not on PATH.")
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Docker is installed but the daemon is not reachable.") from exc


def run_docker_check(*, image_name: str = "openpasture-alpha-validation") -> None:
    require_docker()
    root = repo_root()
    run_command(["docker", "build", "-t", image_name, "."], cwd=root)
    smoke_code = (
        "from openpasture.runtime import initialize, get_knowledge_store; "
        "initialize(); "
        "count = get_knowledge_store().count(); "
        "print(f'knowledge_count={count}'); "
        "assert count > 0"
    )
    run_command(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            "OPENPASTURE_STORE=sqlite",
            "-e",
            "OPENPASTURE_DATA_DIR=/tmp/openpasture-docker-smoke",
            image_name,
            "python",
            "-c",
            smoke_code,
        ],
        cwd=root,
    )


def validate_sqlite_data_dir(data_dir: Path) -> None:
    if not data_dir.exists():
        raise FileNotFoundError(f"SQLite data directory does not exist: {data_dir}")
    for name in REQUIRED_SQLITE_FILES:
        db_path = data_dir / name
        if not db_path.exists():
            raise FileNotFoundError(f"Required SQLite file is missing: {db_path}")
        with sqlite3.connect(db_path) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed for {db_path}")


def backup_and_restore_sqlite_data_dir(data_dir: Path, work_dir: Path) -> tuple[Path, Path]:
    validate_sqlite_data_dir(data_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    archive_path = work_dir / "openpasture-sqlite-backup.tar.gz"
    restored_dir = work_dir / "restored"

    with tarfile.open(archive_path, "w:gz") as archive:
        for name in REQUIRED_SQLITE_FILES:
            archive.add(data_dir / name, arcname=name)

    if restored_dir.exists():
        shutil.rmtree(restored_dir)
    restored_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(restored_dir)

    validate_sqlite_data_dir(restored_dir)
    return archive_path, restored_dir


def run_sqlite_backup_restore_check(data_dir: Path, work_dir: Path | None = None) -> None:
    if work_dir is not None:
        archive_path, restored_dir = backup_and_restore_sqlite_data_dir(data_dir, work_dir)
        print(f"Created backup archive: {archive_path}", flush=True)
        print(f"Verified restored SQLite copy: {restored_dir}", flush=True)
        return

    with TemporaryDirectory(prefix="openpasture-alpha-backup-") as temp_dir:
        archive_path, restored_dir = backup_and_restore_sqlite_data_dir(data_dir, Path(temp_dir))
        print(f"Created backup archive: {archive_path}", flush=True)
        print(f"Verified restored SQLite copy: {restored_dir}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run reusable openPasture alpha validation checks.")
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("automated", help="Run the marked OSS alpha pytest suite.")

    docker_parser = subparsers.add_parser("docker", help="Build and boot-check the Docker image.")
    docker_parser.add_argument(
        "--image-name",
        default="openpasture-alpha-validation",
        help="Docker image tag to build and run.",
    )

    backup_parser = subparsers.add_parser(
        "sqlite-backup-restore",
        help="Back up and restore-check one OPENPASTURE_DATA_DIR.",
    )
    backup_parser.add_argument("--data-dir", required=True, help="Path to the SQLite data directory.")
    backup_parser.add_argument(
        "--work-dir",
        help="Optional directory for the generated archive and restored copy.",
    )

    subparsers.add_parser("show-target", help="Print the pinned Hermes compatibility target.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "automated"

    try:
        if command == "automated":
            run_automated_suite()
            return 0
        if command == "docker":
            run_docker_check(image_name=args.image_name)
            return 0
        if command == "sqlite-backup-restore":
            work_dir = Path(args.work_dir).expanduser() if args.work_dir else None
            run_sqlite_backup_restore_check(Path(args.data_dir).expanduser(), work_dir)
            return 0
        if command == "show-target":
            config = load_validation_config()
            print(f"Hermes {config.tested_hermes_version} @ {config.tested_hermes_commit}", flush=True)
            return 0
    except (RuntimeError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
