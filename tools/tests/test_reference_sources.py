from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.scripts.reference_sources import (
    CategoryConfig,
    collect_github_json,
    collect_github_markdown,
    collect_mianshiya,
    deduplicate_candidates,
    extract_markdown_candidates,
    match_category,
    validate_configuration,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class ReferenceSourcesTest(unittest.TestCase):
    def test_repository_configuration_is_valid(self) -> None:
        self.assertEqual([], validate_configuration(REPOSITORY_ROOT))

    def test_extract_markdown_candidates_ignores_answer_bullets(self) -> None:
        markdown = """
## How does the event loop work?
- Explain the difference between microtasks and tasks.
- Promise callbacks use the microtask queue.
<summary>为什么 Redis Cluster 使用槽位？</summary>
*Q: What is an incident command system?*
A:
* Can we automatically restart every unhealthy service?
"""

        self.assertEqual(
            [
                "How does the event loop work?",
                "Explain the difference between microtasks and tasks.",
                "为什么 Redis Cluster 使用槽位？",
                "What is an incident command system?",
            ],
            extract_markdown_candidates(markdown),
        )

    def test_mianshiya_collection_preserves_source_and_difficulty(self) -> None:
        source = {
            "id": "mianshiya",
            "endpoint": "https://example.test/search",
            "resultUrlTemplate": "https://example.test/question/{id}",
            "license": "external-terms",
            "usage": "link-only",
        }
        categories = (
            CategoryConfig(
                key="REDIS",
                queries=("Redis 分布式锁",),
                keywords=("redis",),
            ),
        )

        def fake_fetch(
            url: str,
            payload: object,
            timeout: float,
        ) -> dict[str, object]:
            self.assertEqual("https://example.test/search", url)
            self.assertEqual({"searchText": "Redis 分布式锁"}, payload)
            self.assertEqual(3.0, timeout)
            return {
                "code": 0,
                "data": {
                    "records": [
                        {
                            "id": "42",
                            "title": "Redis 中如何实现分布式锁？",
                            "difficulty": 3,
                            "tagList": ["Redis", "后端"],
                        }
                    ]
                },
            }

        candidates = collect_mianshiya(
            source,
            "java-backend",
            categories,
            timeout=3.0,
            json_fetcher=fake_fetch,
        )

        self.assertEqual("mid", candidates[0]["difficulty"])
        self.assertEqual("REDIS", candidates[0]["categoryKey"])
        self.assertEqual("42", candidates[0]["sources"][0]["externalId"])
        self.assertEqual(["Redis 分布式锁"], candidates[0]["queries"])

    def test_github_collection_reads_only_configured_markdown(self) -> None:
        archive_buffer = io.BytesIO()
        with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
            for name, content in (
                (
                    "sample-main/questions/javascript.md",
                    "## What is a JavaScript closure?\n- It captures lexical state.\n",
                ),
                ("sample-main/docs/ignored.md", "## What is JavaScript?\n"),
            ):
                encoded = content.encode()
                member = tarfile.TarInfo(name)
                member.size = len(encoded)
                archive.addfile(member, io.BytesIO(encoded))
        source = {
            "id": "frontend-source",
            "repository": "example/sample",
            "revision": "main",
            "includePrefixes": ["questions"],
            "license": "MIT",
            "usage": "adapt-with-attribution",
            "skills": ["frontend"],
        }
        taxonomy = {
            "frontend": (
                CategoryConfig(
                    key="JAVASCRIPT",
                    queries=("JavaScript",),
                    keywords=("javascript", "closure"),
                ),
            )
        }

        candidates = collect_github_markdown(
            source,
            taxonomy,
            {"frontend"},
            bytes_fetcher=lambda _url, _timeout: archive_buffer.getvalue(),
        )

        self.assertEqual(1, len(candidates))
        self.assertEqual("What is a JavaScript closure?", candidates[0]["title"])
        self.assertIn("questions/javascript.md", candidates[0]["sources"][0]["url"])

    def test_github_collection_can_fetch_explicit_files(self) -> None:
        source = {
            "id": "frontend-source",
            "repository": "example/sample",
            "revision": "main",
            "files": ["questions/javascript.md"],
            "includePrefixes": [],
            "license": "MIT",
            "usage": "adapt-with-attribution",
            "skills": ["frontend"],
        }
        taxonomy = {
            "frontend": (
                CategoryConfig(
                    key="JAVASCRIPT",
                    queries=("JavaScript",),
                    keywords=("javascript",),
                ),
            )
        }
        requested_urls: list[str] = []

        def fake_fetch(url: str, _timeout: float) -> bytes:
            requested_urls.append(url)
            return b"## What is JavaScript?\n"

        candidates = collect_github_markdown(
            source,
            taxonomy,
            {"frontend"},
            bytes_fetcher=fake_fetch,
        )

        self.assertEqual(1, len(candidates))
        self.assertEqual(
            ["https://raw.githubusercontent.com/example/sample/main/questions/javascript.md"],
            requested_urls,
        )

    def test_github_json_collection_uses_configured_fields(self) -> None:
        source = {
            "id": "data-source",
            "repository": "example/data",
            "revision": "a" * 40,
            "files": ["questions.json"],
            "questionField": "question",
            "difficultyField": "difficulty",
            "externalIdField": "id",
            "tagFields": ["topic"],
            "license": "MIT",
            "usage": "adapt-with-attribution",
            "skills": ["data-engineering"],
        }
        taxonomy = {
            "data-engineering": (
                CategoryConfig(
                    key="STREAM_PROCESSING",
                    queries=("Kafka",),
                    keywords=("kafka", "streaming"),
                ),
            )
        }
        payload = json.dumps(
            [
                {
                    "id": 7,
                    "question": "How does Kafka streaming recover after a failure?",
                    "difficulty": "medium",
                    "topic": "Streaming",
                }
            ]
        ).encode()

        candidates = collect_github_json(
            source,
            taxonomy,
            {"data-engineering"},
            bytes_fetcher=lambda _url, _timeout: payload,
        )

        self.assertEqual(1, len(candidates))
        self.assertEqual("STREAM_PROCESSING", candidates[0]["categoryKey"])
        self.assertEqual("mid", candidates[0]["difficulty"])
        self.assertEqual("7", candidates[0]["sources"][0]["externalId"])

    def test_deduplicate_candidates_merges_provenance(self) -> None:
        common = {
            "categoryKey": "JAVA",
            "difficulty": None,
            "queries": [],
            "skillId": "java-backend",
            "tags": [],
            "title": "volatile 能保证原子性吗？",
        }
        candidates = deduplicate_candidates(
            [
                {
                    **common,
                    "sources": [{"sourceId": "one", "url": "https://one.test"}],
                },
                {
                    **common,
                    "difficulty": "mid",
                    "queries": ["Java volatile"],
                    "sources": [{"sourceId": "two", "url": "https://two.test"}],
                },
            ]
        )

        self.assertEqual(1, len(candidates))
        self.assertEqual("mid", candidates[0]["difficulty"])
        self.assertEqual(["Java volatile"], candidates[0]["queries"])
        self.assertEqual(2, len(candidates[0]["sources"]))

    def test_ascii_keyword_matching_does_not_match_inside_another_word(self) -> None:
        categories = (
            CategoryConfig("DISTRIBUTED", ("CAP",), ("cap",)),
            CategoryConfig("SECURITY", ("Linux security",), ("linux capabilities",)),
        )

        matched = match_category("What are the Linux Capabilities?", categories)

        self.assertIsNotNone(matched)
        self.assertEqual("SECURITY", matched.key if matched is not None else None)

    def test_invalid_configuration_reports_unknown_category(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tools/reference_sources").mkdir(parents=True)
            (root / "backend/resources/skills/demo").mkdir(parents=True)
            (root / "backend/resources/skills/demo/skill.meta.yml").write_text(
                "categories:\n  - key: KNOWN\n",
                encoding="utf-8",
            )
            (root / "tools/reference_sources/catalog.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "sources": [
                            {
                                "id": "docs",
                                "displayName": "Docs",
                                "kind": "documentation",
                                "homepage": "https://example.test",
                                "license": "MIT",
                                "licenseUrl": "https://example.test/license",
                                "usage": "verify-only",
                                "enabled": True,
                                "skills": ["demo"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "tools/reference_sources/taxonomy.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "skills": {
                            "demo": {
                                "categories": [
                                    {
                                        "key": "UNKNOWN",
                                        "queries": ["query"],
                                        "keywords": ["keyword"],
                                    }
                                ]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "tools/reference_sources/provenance.json").write_text(
                json.dumps({"schemaVersion": 1, "references": []}),
                encoding="utf-8",
            )

            errors = validate_configuration(root)

        self.assertTrue(any("UNKNOWN" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
