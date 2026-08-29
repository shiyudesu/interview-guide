from __future__ import annotations

import unittest

from tools.scripts.detect_ci_changes import ChangeAreas, classify_paths


class DetectCiChangesTest(unittest.TestCase):
    def test_documentation_only_skips_heavy_jobs(self) -> None:
        areas = classify_paths(["README.md", "docs/OPERATIONS.md"])

        self.assertTrue(areas.docs)
        self.assertFalse(areas.backend)
        self.assertFalse(areas.frontend)
        self.assertFalse(areas.model_proxy)
        self.assertFalse(areas.manifests)
        self.assertFalse(areas.deployment)
        self.assertFalse(areas.production)

    def test_backend_source_runs_backend_manifests_and_production(self) -> None:
        areas = classify_paths(["backend/src/interview_guide/main.py"])

        self.assertTrue(areas.backend)
        self.assertTrue(areas.manifests)
        self.assertTrue(areas.production)
        self.assertFalse(areas.frontend)

    def test_backend_tests_skip_production_integration(self) -> None:
        areas = classify_paths(["backend/tests/unit/test_models.py"])

        self.assertTrue(areas.backend)
        self.assertTrue(areas.manifests)
        self.assertFalse(areas.production)

    def test_backend_integration_tests_run_production_integration(self) -> None:
        areas = classify_paths(["backend/tests/integration/test_s3_integration.py"])

        self.assertTrue(areas.backend)
        self.assertTrue(areas.manifests)
        self.assertTrue(areas.production)

    def test_runtime_markdown_fixture_is_not_documentation(self) -> None:
        areas = classify_paths(
            ["backend/tests/fixtures/knowledge-base/fixed-knowledge-base.md"]
        )

        self.assertFalse(areas.docs)
        self.assertTrue(areas.backend)
        self.assertTrue(areas.manifests)
        self.assertTrue(areas.production)

    def test_skill_markdown_runs_backend_validation(self) -> None:
        areas = classify_paths(["backend/resources/skills/python-backend/SKILL.md"])

        self.assertFalse(areas.docs)
        self.assertTrue(areas.backend)
        self.assertTrue(areas.manifests)
        self.assertTrue(areas.production)

    def test_frontend_source_runs_frontend_manifests_and_production(self) -> None:
        areas = classify_paths(["frontend/src/pages/InterviewPage.tsx"])

        self.assertTrue(areas.frontend)
        self.assertTrue(areas.manifests)
        self.assertTrue(areas.production)
        self.assertFalse(areas.backend)

    def test_model_proxy_only_runs_proxy(self) -> None:
        areas = classify_paths(["tools/model-proxy/src/model_proxy/app.py"])

        self.assertTrue(areas.model_proxy)
        self.assertFalse(areas.backend)
        self.assertFalse(areas.production)

    def test_deployment_change_runs_full_runtime_validation(self) -> None:
        areas = classify_paths(["docker-compose.yml"])

        self.assertTrue(areas.deployment)
        self.assertTrue(areas.production)

        for path in (
            ".env.campus.example",
            ".env.http.example",
            "docker-compose.test.yml",
            "deploy/compose.yml",
            "deploy/update.sh",
        ):
            with self.subTest(path=path):
                areas = classify_paths([path])
                self.assertTrue(areas.deployment)
                self.assertTrue(areas.production)
                self.assertTrue(areas.manifests)

    def test_startup_script_change_runs_deployment_validation(self) -> None:
        for path in (
            "scripts/start.sh",
            "scripts/start-campus.sh",
            "scripts/start-http.sh",
            "scripts/start.ps1",
            "scripts/stop.sh",
            "scripts/stop-campus.sh",
            "scripts/stop-http.sh",
            "scripts/stop.ps1",
            "start.cmd",
            "stop.cmd",
        ):
            with self.subTest(path=path):
                areas = classify_paths([path])
                self.assertTrue(areas.deployment)
                self.assertTrue(areas.production)

    def test_ci_control_change_forces_all_jobs(self) -> None:
        self.assertEqual(
            ChangeAreas.all(),
            classify_paths(["tools/scripts/detect_ci_changes.py"]),
        )

    def test_any_workflow_change_forces_all_jobs(self) -> None:
        self.assertEqual(
            ChangeAreas.all(),
            classify_paths([".github/workflows/real-model.yml"]),
        )
