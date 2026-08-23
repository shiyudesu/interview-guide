from __future__ import annotations

import os
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class LifecycleScriptsTest(unittest.TestCase):
    def test_shell_entrypoints_are_executable(self) -> None:
        for relative in ("scripts/start.sh", "scripts/stop.sh"):
            with self.subTest(relative=relative):
                mode = (REPOSITORY_ROOT / relative).stat().st_mode
                self.assertTrue(mode & os.X_OK)

    def test_start_scripts_cover_all_host_port_mappings(self) -> None:
        required = {
            "FRONTEND_PORT",
            "SERVER_PORT",
            "POSTGRES_PORT",
            "REDIS_PORT",
            "APP_STORAGE_PORT",
            "APP_STORAGE_CONSOLE_PORT",
        }
        for relative in ("scripts/start.sh", "scripts/start.ps1"):
            with self.subTest(relative=relative):
                content = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                self.assertTrue(all(name in content for name in required))
                self.assertIn("port", content.lower())

    def test_stop_scripts_preserve_volumes(self) -> None:
        for relative in ("scripts/stop.sh", "scripts/stop.ps1"):
            with self.subTest(relative=relative):
                content = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("compose down --remove-orphans", content)
                self.assertNotIn("down -v", content)
                self.assertNotIn("--volumes", content)

    def test_windows_entrypoints_call_matching_powershell_scripts(self) -> None:
        start = (REPOSITORY_ROOT / "start.cmd").read_text(encoding="utf-8")
        stop = (REPOSITORY_ROOT / "stop.cmd").read_text(encoding="utf-8")

        self.assertIn("scripts\\start.ps1", start)
        self.assertIn("scripts\\stop.ps1", stop)

    def test_default_frontend_port_is_vite_conventional_port(self) -> None:
        compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        example = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
        bash = (REPOSITORY_ROOT / "scripts/start.sh").read_text(encoding="utf-8")
        powershell = (REPOSITORY_ROOT / "scripts/start.ps1").read_text(encoding="utf-8")

        self.assertIn('${FRONTEND_PORT:-5173}:80', compose)
        self.assertIn("FRONTEND_PORT=5173", example)
        self.assertIn("configured_port FRONTEND_PORT 5173", bash)
        self.assertIn('Get-ConfiguredPort "FRONTEND_PORT" 5173', powershell)

    def test_dockerhub_registry_override_covers_runtime_and_build_images(self) -> None:
        variable = "INTERVIEW_GUIDE_DOCKERHUB_REGISTRY"
        for relative in ("docker-compose.yml", "docker-compose.dev.yml"):
            with self.subTest(relative=relative):
                content = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(f"${{{variable}:-docker.io}}", content)

        for relative in ("backend/Dockerfile", "frontend/Dockerfile"):
            with self.subTest(relative=relative):
                content = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(f"ARG {variable}=docker.io", content)
                from_lines = [
                    line for line in content.splitlines() if line.startswith("FROM ")
                ]
                self.assertTrue(from_lines)
                self.assertTrue(
                    all(f"${{{variable}}}/library/" in line for line in from_lines)
                )

        backend = (REPOSITORY_ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("# syntax=docker/dockerfile", backend)

        for relative in ("scripts/start.sh", "scripts/start.ps1"):
            with self.subTest(relative=relative):
                content = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(variable, content)
                self.assertIn("registry", content.lower())


if __name__ == "__main__":
    unittest.main()
