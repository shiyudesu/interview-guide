from __future__ import annotations

from pathlib import Path

from alembic.config import Config

from alembic import command


def main() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    command.upgrade(Config(backend_root / "alembic.ini"), "head")
