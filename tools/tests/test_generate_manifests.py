from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPOSITORY_ROOT / "tools/scripts/generate_manifests.py"
SPEC = importlib.util.spec_from_file_location("generate_manifests", GENERATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {GENERATOR_PATH}")
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class GenerateManifestsTest(unittest.TestCase):
    def test_api_inventory_rejects_frontend_only_contracts(self) -> None:
        manifest = GENERATOR.build_api_manifest(REPOSITORY_ROOT)

        self.assertEqual([], manifest["unmatched"]["frontendOnly"])
        self.assertEqual(0, manifest["summary"]["frontendOnlyCount"])
        backend_only_paths = {item["path"] for item in manifest["unmatched"]["backendOnly"]}
        self.assertEqual(
            {
                "/api/auth/login",
                "/api/auth/logout",
                "/api/auth/me",
                "/api/auth/password/change",
                "/api/auth/register",
                "/api/auth/sessions/revoke",
                "/api/interview-schedule/{schedule_id}/status",
                "/api/interview/sessions/{session_id}/report",
                "/health",
                "/info",
                "/metrics",
            },
            backend_only_paths,
        )
        self.assertGreaterEqual(manifest["summary"]["backendEndpointCount"], 80)
        self.assertEqual(manifest["summary"]["webSocketEndpointCount"], 1)
        self.assertGreaterEqual(manifest["summary"]["sseEndpointCount"], 2)

    def test_api_inventory_matches_http_method_as_part_of_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = root / "backend/src/interview_guide/example"
            frontend = root / "frontend/src/api"
            backend.mkdir(parents=True)
            frontend.mkdir(parents=True)
            (backend / "api.py").write_text(
                'router = APIRouter(prefix="/api/example")\n'
                '@router.get("")\n'
                'async def get_example():\n'
                '    return {}\n',
                encoding="utf-8",
            )
            (frontend / "example.ts").write_text(
                "request.post('/api/example');\n",
                encoding="utf-8",
            )

            manifest = GENERATOR.build_api_manifest(root)

        self.assertEqual(1, manifest["summary"]["frontendOnlyCount"])
        self.assertEqual("POST", manifest["unmatched"]["frontendOnly"][0]["httpMethod"])

    def test_database_and_redis_inventories_capture_required_baselines(self) -> None:
        database = GENERATOR.extract_database(REPOSITORY_ROOT)
        redis = GENERATOR.extract_redis(REPOSITORY_ROOT)

        self.assertEqual(
            {"hstore", "uuid-ossp", "vector"},
            {item["name"] for item in database["extensions"]},
        )
        vector_store = next(item for item in database["tables"] if item["name"] == "vector_store")
        embedding = next(item for item in vector_store["columns"] if item["name"] == "embedding")
        self.assertIn("vector(1024)", embedding["definition"])
        self.assertIn(
            "voice_model_config",
            {item["name"] for item in database["tables"]},
        )
        self.assertEqual(redis["summary"]["streamCount"], 4)

    def test_resource_inventory_records_prompts_and_disabled_tests(self) -> None:
        resources = GENERATOR.extract_resources(REPOSITORY_ROOT)

        self.assertEqual(16, resources["summary"]["resourceCountsByCategory"]["prompt"])
        self.assertGreaterEqual(resources["summary"]["disabledTestMarkerCount"], 1)

    def test_generation_is_deterministic(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_dir,
            tempfile.TemporaryDirectory() as second_dir,
        ):
            manifests = {
                "api.json": GENERATOR.build_api_manifest(REPOSITORY_ROOT),
                "configuration.json": GENERATOR.extract_configuration(REPOSITORY_ROOT),
                "database.json": GENERATOR.extract_database(REPOSITORY_ROOT),
                "redis.json": GENERATOR.extract_redis(REPOSITORY_ROOT),
                "resources.json": GENERATOR.extract_resources(REPOSITORY_ROOT),
            }
            for directory in (Path(first_dir), Path(second_dir)):
                for name, value in manifests.items():
                    GENERATOR.write_json(directory, name, value)
            first = {
                path.name: json.loads(path.read_text(encoding="utf-8"))
                for path in Path(first_dir).glob("*.json")
            }
            second = {
                path.name: json.loads(path.read_text(encoding="utf-8"))
                for path in Path(second_dir).glob("*.json")
            }
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
