#!/usr/bin/env python3
"""Synchronize immutable Java classpath resources into the Python backend."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

DIRECTORIES = ("fonts", "prompts", "scripts", "skills")
FILES = ("voice-interview-opening.yml",)
CONTRACT_FILES = {
    "migration/samples/http/java-baseline.json": (
        "contracts/java-http-baseline.json"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def expected_files(root: Path) -> dict[Path, Path]:
    source_root = root / "app/src/main/resources"
    target_root = root / "backend/resources"
    mappings: dict[Path, Path] = {}
    for directory in DIRECTORIES:
        for source in sorted((source_root / directory).glob("**/*")):
            if source.is_file():
                relative = source.relative_to(source_root)
                mappings[source] = target_root / relative
    for filename in FILES:
        source = source_root / filename
        mappings[source] = target_root / filename
    for source_name, target_name in CONTRACT_FILES.items():
        mappings[root / source_name] = target_root / target_name
    return mappings


def check(root: Path) -> None:
    mappings = expected_files(root)
    for source, target in mappings.items():
        if not target.exists() or sha256(source) != sha256(target):
            raise SystemExit(
                f"{target.relative_to(root)} is missing or stale; "
                "run ./migration/scripts/sync-java-resources.py"
            )
    target_root = root / "backend/resources"
    expected_targets = set(mappings.values())
    extras = {
        path
        for path in target_root.glob("**/*")
        if path.is_file() and path.name != ".gitkeep" and path not in expected_targets
    }
    if extras:
        names = ", ".join(str(path.relative_to(root)) for path in sorted(extras))
        raise SystemExit(f"Unexpected synchronized backend resources: {names}")


def synchronize(root: Path) -> None:
    for source, target in expected_files(root).items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    gitkeep = root / "backend/resources/.gitkeep"
    if gitkeep.exists():
        gitkeep.unlink()


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check(root)
    else:
        synchronize(root)


if __name__ == "__main__":
    main()
