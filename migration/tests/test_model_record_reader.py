from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS / "model_record_reader.py"
SPEC = importlib.util.spec_from_file_location("model_record_reader", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ModelRecordReaderTest(unittest.TestCase):
    def test_ignores_only_incomplete_trailing_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text('{"kind":"complete"}\n{"kind":"partial', encoding="utf-8")

            self.assertEqual(
                [{"kind": "complete"}],
                MODULE.read_jsonl_records(path),
            )

    def test_rejects_malformed_completed_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text('{"kind":}\n', encoding="utf-8")

            with self.assertRaises(ValueError):
                MODULE.read_jsonl_records(path)

    def test_preserves_unicode_line_separator_inside_json_string(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text('{"text":"before\u0085after"}\n', encoding="utf-8")

            self.assertEqual(
                [{"text": "before\u0085after"}],
                MODULE.read_jsonl_records(path),
            )


if __name__ == "__main__":
    unittest.main()
