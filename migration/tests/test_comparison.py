from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPARISON_PATH = REPOSITORY_ROOT / "migration/scripts/comparison.py"
SPEC = importlib.util.spec_from_file_location("comparison", COMPARISON_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {COMPARISON_PATH}")
COMPARISON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARISON)


def snapshot() -> dict:
    return {
        "cases": [
            {
                "id": "health",
                "request": {
                    "body": None,
                    "headers": {},
                    "method": "GET",
                    "path": "/health",
                },
                "response": {
                    "body": '{"code":200,"message":"success","data":{"status":"UP"}}',
                    "headers": {"content-type": ["application/json"]},
                    "status": 200,
                },
            }
        ],
        "schemaVersion": 1,
    }


SCHEMA = """\
CREATE TABLE public.example (
    id bigint NOT NULL
);

CREATE INDEX idx_example_id ON public.example USING btree (id);
"""


class ComparisonTest(unittest.TestCase):
    def test_self_comparison_has_zero_differences(self) -> None:
        report = COMPARISON.compare_snapshots(
            snapshot(), snapshot(), SCHEMA, SCHEMA
        )

        self.assertTrue(report["passed"])
        self.assertEqual(0, report["summary"]["httpDifferenceCount"])
        self.assertTrue(report["summary"]["schemaEqual"])

    def test_response_field_change_fails_comparison(self) -> None:
        changed = copy.deepcopy(snapshot())
        changed["cases"][0]["response"]["body"] = (
            '{"code":200,"message":"success","data":{"status":"DOWN"}}'
        )

        report = COMPARISON.compare_snapshots(
            snapshot(), changed, SCHEMA, SCHEMA
        )

        self.assertFalse(report["passed"])
        self.assertEqual("body", report["differences"]["http"][0]["kind"])

    def test_database_index_change_fails_comparison(self) -> None:
        changed_schema = SCHEMA.replace("idx_example_id", "idx_example_id_changed")

        report = COMPARISON.compare_snapshots(
            snapshot(), snapshot(), SCHEMA, changed_schema
        )

        self.assertFalse(report["passed"])
        self.assertFalse(report["summary"]["schemaEqual"])
        self.assertIn(
            "idx_example_id_changed",
            report["differences"]["databaseSchema"],
        )


if __name__ == "__main__":
    unittest.main()
