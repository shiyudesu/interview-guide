#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, fields
from pathlib import Path

ZERO_SHA = "0" * 40
FULL_RUN_PATHS = {
    ".github/workflows/ci.yml",
    "tools/scripts/detect_ci_changes.py",
    "tools/tests/test_detect_ci_changes.py",
}


@dataclass(frozen=True)
class ChangeAreas:
    docs: bool = False
    backend: bool = False
    frontend: bool = False
    model_proxy: bool = False
    manifests: bool = False
    deployment: bool = False
    production: bool = False
    full: bool = False

    @classmethod
    def all(cls) -> ChangeAreas:
        return cls(**{field.name: True for field in fields(cls)})

    def github_output(self) -> str:
        return "\n".join(
            f"{field.name}={'true' if getattr(self, field.name) else 'false'}"
            for field in fields(self)
        )


def is_document(path: str) -> bool:
    runtime_markdown = path.startswith(
        (
            "backend/resources/",
            "backend/tests/fixtures/",
        )
    )
    return (path.endswith(".md") and not runtime_markdown) or path == "LICENSE"


def starts_with_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return path.startswith(prefixes)


def classify_paths(paths: Iterable[str], *, force_full: bool = False) -> ChangeAreas:
    normalized = {path.strip().removeprefix("./") for path in paths if path.strip()}
    if (
        force_full
        or not normalized
        or normalized.intersection(FULL_RUN_PATHS)
        or any(path.startswith(".github/workflows/") for path in normalized)
    ):
        return ChangeAreas.all()

    docs = any(is_document(path) for path in normalized)
    backend = any(
        (
            (path.startswith("backend/") and not is_document(path))
            or path.startswith("docker/postgres/")
        )
        for path in normalized
    )
    frontend = any(
        path.startswith("frontend/") and not is_document(path) for path in normalized
    )
    model_proxy = any(
        path.startswith("tools/model-proxy/") and not is_document(path)
        for path in normalized
    )
    manifests = any(
        path in {
            ".env.example",
            ".env.http.example",
            "docker-compose.dev.yml",
            "docker-compose.test.yml",
            "docker-compose.yml",
            "tools/scripts/check-manifests.sh",
            "tools/scripts/generate-manifests.sh",
            "tools/scripts/generate_manifests.py",
            "tools/tests/test_generate_manifests.py",
        }
        or starts_with_any(
            path,
            (
                "tools/manifests/",
                "backend/src/",
                "backend/alembic/",
                "backend/resources/",
                "backend/tests/",
                "deploy/",
                "frontend/src/",
                "frontend/e2e/",
            ),
        )
        for path in normalized
    )
    deployment = any(
        path in {
            ".env.example",
            ".env.http.example",
            "backend/Dockerfile",
            "backend/pyproject.toml",
            "backend/uv.lock",
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "docker-compose.test.yml",
            "frontend/Dockerfile",
            "frontend/nginx.conf",
            "frontend/package.json",
            "frontend/pnpm-lock.yaml",
            "scripts/start.ps1",
            "scripts/start-http.sh",
            "scripts/start.sh",
            "scripts/stop.ps1",
            "scripts/stop-http.sh",
            "scripts/stop.sh",
            "start.cmd",
            "stop.cmd",
        }
        or path.startswith("docker/")
        or path.startswith("deploy/")
        or path.startswith(".github/workflows/")
        for path in normalized
    )
    production = deployment or any(
        starts_with_any(
            path,
            (
                "backend/src/",
                "backend/alembic/",
                "backend/resources/",
                "backend/tests/fixtures/",
                "backend/tests/integration/",
                "frontend/src/",
                "frontend/e2e/",
            ),
        )
        for path in normalized
    )
    return ChangeAreas(
        docs=docs,
        backend=backend,
        frontend=frontend,
        model_proxy=model_proxy,
        manifests=manifests,
        deployment=deployment,
        production=production,
    )


def git_changed_paths(
    repository: Path,
    *,
    event_name: str,
    before: str | None,
    sha: str,
    base_ref: str | None,
) -> tuple[list[str], bool]:
    if event_name == "workflow_dispatch":
        return [], True
    if event_name == "pull_request":
        if not base_ref:
            return [], True
        subprocess.run(
            ["git", "fetch", "--quiet", "origin", base_ref],
            cwd=repository,
            check=True,
        )
        base = subprocess.run(
            ["git", "merge-base", f"origin/{base_ref}", sha],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        revision_range = f"{base}..{sha}"
    elif before and before != ZERO_SHA:
        revision_range = f"{before}..{sha}"
    else:
        return [], True
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRD", revision_range],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines(), False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--before")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--base-ref")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths, force_full = git_changed_paths(
        args.repository.resolve(),
        event_name=args.event_name,
        before=args.before,
        sha=args.sha,
        base_ref=args.base_ref,
    )
    print(classify_paths(paths, force_full=force_full).github_output())


if __name__ == "__main__":
    main()
