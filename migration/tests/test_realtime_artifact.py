from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY_ROOT / "migration/scripts/realtime_artifact.py"
SPEC = importlib.util.spec_from_file_location("realtime_artifact", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RealtimeArtifactTest(unittest.TestCase):
    def test_sse_preserves_raw_frames_and_multiline_data(self) -> None:
        raw = b"event: token\r\ndata: first\r\ndata: second\r\n\r\ndata: [DONE]\r\n\r\n"

        record = MODULE.sse_record(
            raw,
            200,
            {"content-type": "text/event-stream"},
        )

        self.assertEqual(2, len(record["frames"]))
        self.assertEqual("token", record["frames"][0]["event"])
        self.assertEqual("first\nsecond", record["frames"][0]["data"])
        self.assertEqual("[DONE]", record["frames"][1]["data"])
        self.assertFalse(record["cancelled"])
        self.assertTrue(record["completed"])

    def test_sse_records_client_cancellation(self) -> None:
        record = MODULE.sse_record(
            b"data: partial\n\n",
            200,
            {"content-type": "text/event-stream"},
            cancelled=True,
            completed=False,
        )

        self.assertTrue(record["cancelled"])
        self.assertFalse(record["completed"])

    def test_websocket_transcript_keeps_order_and_raw_json(self) -> None:
        record = MODULE.transcript_record(
            ['{"type":"audio"}'],
            ['{"type":"subtitle"}', '{"type":"audio_chunk","isLast":false}'],
            1000,
            "normal",
        )

        self.assertEqual(
            ["subtitle", "audio_chunk"],
            [item["json"]["type"] for item in record["received"]],
        )
        self.assertFalse(record["received"][1]["json"]["isLast"])

    def test_comparison_detects_file_header_or_pdf_change(self) -> None:
        left = MODULE.file_record(
            b"pdf",
            200,
            {"content-type": "application/pdf"},
            {"pageCount": 1, "text": "fixed"},
        )
        right = MODULE.file_record(
            b"pdf",
            200,
            {"content-type": "application/pdf"},
            {"pageCount": 2, "text": "fixed"},
        )

        self.assertFalse(MODULE.comparison_report(left, right)["passed"])


if __name__ == "__main__":
    unittest.main()
