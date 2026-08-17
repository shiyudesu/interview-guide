from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "migration/scripts/rest_performance_compare.py"
SPEC = importlib.util.spec_from_file_location("rest_performance_compare", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def target(p95: float, p99: float, throughput: float) -> dict[str, object]:
    return {
        "errorCount": 0,
        "latency": {"p95Ms": p95, "p99Ms": p99},
        "response": '{"code": 200}',
        "responseVariants": 1,
        "throughputMedianRps": throughput,
    }


class RestPerformanceCompareTest(unittest.TestCase):
    def test_comparison_enforces_latency_and_throughput(self) -> None:
        passing = MODULE.compare_scenario(
            target(100, 120, 1000),
            target(105, 130, 950),
        )
        failing = MODULE.compare_scenario(
            target(100, 120, 1000),
            target(111, 139, 899),
        )
        self.assertTrue(passing["passed"])
        self.assertFalse(failing["passed"])

    def test_summary_reports_errors_and_response_variants(self) -> None:
        summary = MODULE.summarize(
            [
                {
                    "results": [
                        {"body": "first", "elapsedMs": 10},
                        {"body": "second", "elapsedMs": 20},
                        {"elapsedMs": 30, "error": "failure"},
                    ],
                    "throughputRps": 100,
                    "wallMs": 30,
                }
            ]
        )
        self.assertEqual(1, summary["errorCount"])
        self.assertEqual(2, summary["responseVariants"])


if __name__ == "__main__":
    unittest.main()
