#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
ENVIRONMENT_VARIABLE = re.compile(
    r"\b(?:ACME|AI|APP|COMPOSE|CORS|DEV|FRONTEND|INTERVIEW_GUIDE|LOG|OTEL|"
    r"POSTGRES|PROVIDER|PUBLIC|REAL_BACKEND|REDIS|RUN_REAL_BACKEND|SERVER|TEST|"
    r"TLS|TZ|VITE)_[A-Z0-9_]+\b"
)
BUILTIN_ENVIRONMENT_VARIABLES = {"COMPOSE_PROFILES"}
IGNORED_PARTS = {".git", ".venv", "node_modules"}
PROJECT_DOCUMENTS = (
    "README.md",
    "AGENTS.md",
    "backend/README.md",
    "frontend/README.md",
)


def markdown_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.md")
        if not any(part in IGNORED_PARTS for part in path.parts)
    ]


def broken_links(root: Path) -> list[str]:
    errors: list[str] = []
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK.findall(text):
            target = raw_target.split("#", 1)[0]
            if (
                not target
                or "://" in target
                or target.startswith(("mailto:", "data:"))
            ):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{path.relative_to(root)}: missing link target {target}")
    return errors


def trailing_whitespace(root: Path) -> list[str]:
    errors: list[str] = []
    for path in markdown_files(root):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if line.endswith((" ", "\t")):
                errors.append(f"{path.relative_to(root)}:{line_number}: trailing whitespace")
    return errors


def documented_environment_variables(root: Path) -> set[str]:
    paths = [root / value for value in PROJECT_DOCUMENTS]
    paths.extend(sorted((root / "docs").glob("*.md")))
    paths.extend(sorted((root / "tools").glob("**/*.md")))
    paths.append(root / ".env.example")
    paths.append(root / ".env.http.example")
    paths.append(root / ".env.campus.example")
    paths.append(root / "deploy/.env.example")
    values: set[str] = set()
    for path in paths:
        if path.is_file():
            values.update(ENVIRONMENT_VARIABLE.findall(path.read_text(encoding="utf-8")))
    return values


def source_environment_variables(root: Path) -> set[str]:
    paths = (
        root / "backend/src/interview_guide/common/config/settings.py",
        root / "docker-compose.yml",
        root / "docker-compose.dev.yml",
        root / "docker-compose.test.yml",
        root / ".env.http.example",
        root / ".env.campus.example",
        root / "deploy/compose.yml",
        root / "deploy/.env.example",
        root / "frontend/vite.config.ts",
        root / "frontend/src/api/request.ts",
        root / ".github/workflows/ci.yml",
        root / ".github/workflows/real-model.yml",
    )
    values = set(BUILTIN_ENVIRONMENT_VARIABLES)
    for path in paths:
        values.update(ENVIRONMENT_VARIABLE.findall(path.read_text(encoding="utf-8")))
    return values


def unknown_environment_variables(root: Path) -> list[str]:
    documented = documented_environment_variables(root)
    source = source_environment_variables(root)
    return [f"unknown documented environment variable: {value}" for value in sorted(documented - source)]


def check(root: Path) -> list[str]:
    return [
        *broken_links(root),
        *trailing_whitespace(root),
        *unknown_environment_variables(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> None:
    errors = check(parse_args().root.resolve())
    if errors:
        raise SystemExit("\n".join(errors))
    print("documentation checks passed")


if __name__ == "__main__":
    main()
