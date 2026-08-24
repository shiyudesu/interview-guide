from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class LifecycleScriptsTest(unittest.TestCase):
    def test_shell_entrypoints_are_executable(self) -> None:
        for relative in (
            "scripts/start.sh",
            "scripts/stop.sh",
            "scripts/start-http.sh",
            "scripts/stop-http.sh",
            "deploy/install.sh",
            "deploy/lib.sh",
            "deploy/refresh.sh",
            "deploy/rollback.sh",
            "deploy/status.sh",
            "deploy/stop.sh",
            "deploy/update.sh",
        ):
            with self.subTest(relative=relative):
                mode = (REPOSITORY_ROOT / relative).stat().st_mode
                self.assertTrue(mode & os.X_OK)

    def test_start_scripts_check_the_only_production_host_port(self) -> None:
        for relative in (
            "scripts/start.sh",
            "scripts/start.ps1",
            "scripts/start-http.sh",
        ):
            with self.subTest(relative=relative):
                content = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("FRONTEND_PORT", content)
                self.assertIn("port", content.lower())

        compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertEqual(compose.count("    ports:\n"), 1)
        self.assertIn("FRONTEND_BIND_ADDRESS", compose)
        for internal_port in (
            "${SERVER_PORT:-8080}:8080",
            "${POSTGRES_PORT:-5432}:5432",
            "${REDIS_PORT:-6379}:6379",
            "${APP_STORAGE_PORT:-9000}:9000",
        ):
            self.assertNotIn(internal_port, compose)

    def test_stop_scripts_preserve_volumes(self) -> None:
        for relative in (
            "scripts/stop.sh",
            "scripts/stop.ps1",
            "scripts/stop-http.sh",
            "deploy/stop.sh",
        ):
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

    def test_compose_uses_project_scoped_names_and_native_architecture(self) -> None:
        for relative in (
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "backend/Dockerfile",
            "frontend/Dockerfile",
        ):
            with self.subTest(relative=relative):
                content = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn("container_name:", content)
                self.assertNotIn("platform: linux/amd64", content)
                self.assertNotIn("FROM --platform=linux/amd64", content)

    def test_production_secrets_are_generated_and_not_defaulted(self) -> None:
        compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        example = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("POSTGRES_PASSWORD=\n", example)
        self.assertIn("APP_STORAGE_SECRET_KEY=\n", example)
        self.assertIn("POSTGRES_PASSWORD:?set POSTGRES_PASSWORD", compose)
        self.assertIn("APP_STORAGE_SECRET_KEY:?set APP_STORAGE_SECRET_KEY", compose)

    def test_test_overlay_is_the_only_internal_host_port_escape_hatch(self) -> None:
        overlay = (REPOSITORY_ROOT / "docker-compose.test.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('"127.0.0.1:${SERVER_PORT:-8080}:8080"', overlay)
        self.assertIn('"127.0.0.1:${POSTGRES_PORT:-5432}:5432"', overlay)
        self.assertIn('"127.0.0.1:${REDIS_PORT:-6379}:6379"', overlay)
        self.assertIn('"127.0.0.1:${APP_STORAGE_PORT:-9000}:9000"', overlay)

    def test_frontend_is_the_single_origin_for_http_and_websocket_traffic(self) -> None:
        nginx = (REPOSITORY_ROOT / "frontend/nginx.conf").read_text(encoding="utf-8")
        vite = (REPOSITORY_ROOT / "frontend/vite.config.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("server_name _;", nginx)
        self.assertIn("location /api/", nginx)
        self.assertIn("location /ws/", nginx)
        self.assertIn("location /docs", nginx)
        self.assertIn("location = /openapi.json", nginx)
        self.assertIn("proxy_set_header Host $http_host;", nginx)
        self.assertIn("$http_x_forwarded_proto", nginx)
        self.assertIn("'/ws':", vite)
        self.assertIn("ws: true", vite)

    def test_ghcr_deployment_uses_images_without_source_builds(self) -> None:
        compose = (REPOSITORY_ROOT / "deploy/compose.yml").read_text(encoding="utf-8")
        workflow = (
            REPOSITORY_ROOT / ".github/workflows/publish-ghcr.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("build:", compose)
        self.assertNotIn("container_name:", compose)
        self.assertEqual(compose.count("    ports:\n"), 1)
        self.assertIn("interview-guide-backend", compose)
        self.assertIn("interview-guide-frontend", compose)
        self.assertIn("workflow_run:", workflow)
        self.assertIn("packages: write", workflow)
        self.assertIn("linux/amd64,linux/arm64", workflow)
        self.assertIn("interview-guide-deploy:main", workflow)

    def test_active_pull_uses_immutable_revision_tags_and_preserves_volumes(self) -> None:
        refresh = (REPOSITORY_ROOT / "deploy/refresh.sh").read_text(encoding="utf-8")
        update = (REPOSITORY_ROOT / "deploy/update.sh").read_text(encoding="utf-8")
        self.assertIn('candidate_tag="sha-${revision}"', refresh)
        self.assertIn("org.opencontainers.image.revision", refresh)
        self.assertIn("compose pull", update)
        self.assertIn("compose up -d --wait", update)
        self.assertNotIn("down -v", refresh + update)
        self.assertNotIn("--volumes", refresh + update)

    def test_deployment_root_rejects_unsafe_systemd_paths(self) -> None:
        lib = REPOSITORY_ROOT / "deploy/lib.sh"
        for path in ("relative/path", "/", "/opt/interview guide", "/opt/../tmp"):
            with self.subTest(path=path):
                result = subprocess.run(
                    [
                        "bash",
                        "-c",
                        'source "$1"; deploy_validate_root "$2"',
                        "bash",
                        str(lib),
                        path,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)

        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; deploy_validate_root "$2"',
                "bash",
                str(lib),
                "/opt/interview-guide_1.0",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_deployment_installer_requires_systemd_and_repairs_empty_channel(self) -> None:
        install = (REPOSITORY_ROOT / "deploy/install.sh").read_text(encoding="utf-8")
        stop = (REPOSITORY_ROOT / "deploy/stop.sh").read_text(encoding="utf-8")
        self.assertIn("command -v systemctl", install)
        self.assertGreaterEqual(install.count("INTERVIEW_GUIDE_UPDATE_CHANNEL"), 2)
        self.assertIn("interview-guide-update.timer", stop)

    def test_dockerhub_registry_override_covers_runtime_and_build_images(self) -> None:
        variable = "INTERVIEW_GUIDE_DOCKERHUB_REGISTRY"
        for relative in (
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "deploy/compose.yml",
        ):
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
