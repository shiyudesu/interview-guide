from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPOSITORY_ROOT / "migration/scripts/generate_manifests.py"
SPEC = importlib.util.spec_from_file_location("generate_manifests", GENERATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {GENERATOR_PATH}")
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class GenerateManifestsTest(unittest.TestCase):
    def test_api_inventory_preserves_known_frontend_only_endpoint(self) -> None:
        manifest = GENERATOR.build_api_manifest(REPOSITORY_ROOT)

        frontend_only_paths = {
            item["canonicalPath"] for item in manifest["unmatched"]["frontendOnly"]
        }
        self.assertEqual({"/api/resumes/statistics"}, frontend_only_paths)
        self.assertEqual(0, manifest["summary"]["backendOnlyCount"])
        self.assertGreaterEqual(manifest["summary"]["backendEndpointCount"], 80)
        self.assertEqual(manifest["summary"]["webSocketEndpointCount"], 1)
        self.assertGreaterEqual(manifest["summary"]["sseEndpointCount"], 2)

    def test_database_and_redis_inventories_capture_required_baselines(self) -> None:
        database = GENERATOR.extract_database(REPOSITORY_ROOT)
        redis = GENERATOR.extract_redis(REPOSITORY_ROOT)

        self.assertEqual(
            {"hstore", "uuid-ossp", "vector"},
            {item["name"] for item in database["extensions"]},
        )
        vector_store = next(
            item for item in database["tables"] if item["name"] == "vector_store"
        )
        embedding = next(
            item for item in vector_store["columns"] if item["name"] == "embedding"
        )
        self.assertIn("vector(1024)", embedding["definition"])
        self.assertEqual(redis["summary"]["streamCount"], 5)

    def test_resource_inventory_records_prompts_and_disabled_tests(self) -> None:
        resources = GENERATOR.extract_resources(REPOSITORY_ROOT)

        self.assertEqual(
            17, resources["summary"]["resourceCountsByCategory"]["prompt"]
        )
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
                "known-issues.json": GENERATOR.extract_known_issues(REPOSITORY_ROOT),
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
