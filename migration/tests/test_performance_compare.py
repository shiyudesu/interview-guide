from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "migration/scripts/performance_compare.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("performance_compare", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PerformanceCompareTest(unittest.TestCase):
    def test_qwen37_max_cost_uses_versioned_official_price(self) -> None:
        cost = MODULE.estimated_cost(
            "qwen3.7-max",
            {"inputTokens": 1_000_000, "outputTokens": 1_000_000},
        )
        self.assertEqual(6.601, cost["estimated"])
        self.assertEqual(
            "https://www.alibabacloud.com/help/en/model-studio/qwen3-7-max",
            cost["pricing"]["source"],
        )

    def test_summary_uses_median_p95_and_p99(self) -> None:
        samples = [
            {"elapsedMs": value, "model": "fixed", "response": {}} for value in (10, 20, 30, 40, 50)
        ]
        summary = MODULE.summary(samples)
        self.assertEqual(30, summary["medianMs"])
        self.assertEqual(50, summary["p95Ms"])
        self.assertEqual(50, summary["p99Ms"])

    def test_value_summary_records_application_overhead_distribution(self) -> None:
        summary = MODULE.value_summary([20.0, 25.0, 30.0, 35.0, 40.0])
        self.assertEqual(30, summary["medianMs"])
        self.assertEqual(40, summary["p95Ms"])
        self.assertEqual([20.0, 25.0, 30.0, 35.0, 40.0], summary["samplesMs"])

    def test_proxy_capture_separates_alternating_targets(self) -> None:
        events = []
        for index in range(4):
            correlation_id = f"request-{index}"
            events.extend(
                [
                    {
                        "body": {
                            "json": {
                                "max_tokens": 1,
                                "messages": [{"content": "Reply with OK only.", "role": "user"}],
                                "model": "qwen3.7-max",
                            }
                        },
                        "correlationId": correlation_id,
                        "kind": "http-request",
                    },
                    {
                        "body": {
                            "json": {
                                "usage": {
                                    "completion_tokens": 1,
                                    "prompt_tokens": 6,
                                }
                            }
                        },
                        "correlationId": correlation_id,
                        "durationMs": 10 + index,
                        "kind": "http-response",
                        "status": 200,
                    },
                ]
            )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proxy.jsonl"
            path.write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            capture = MODULE.proxy_capture(path, 0, 4)

        self.assertTrue(capture["requestsIdentical"])
        self.assertEqual(12, capture["targets"]["java"]["usage"]["inputTokens"])
        self.assertEqual(
            [10.0, 12.0],
            capture["targets"]["java"]["providerNetwork"]["samplesMs"],
        )
        self.assertGreater(
            capture["targets"]["python"]["cost"]["estimated"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
