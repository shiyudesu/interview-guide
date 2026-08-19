from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.scripts.check_docs import broken_links, trailing_whitespace


class CheckDocsTest(unittest.TestCase):
    def test_reports_missing_relative_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("[missing](docs/missing.md)\n", encoding="utf-8")

            self.assertEqual(
                ["README.md: missing link target docs/missing.md"],
                broken_links(root),
            )

    def test_ignores_external_and_anchor_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text(
                "[external](https://example.com)\n[anchor](#section)\n",
                encoding="utf-8",
            )

            self.assertEqual([], broken_links(root))

    def test_reports_markdown_trailing_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("value  \n", encoding="utf-8")

            self.assertEqual(
                ["README.md:1: trailing whitespace"],
                trailing_whitespace(root),
            )


if __name__ == "__main__":
    unittest.main()
