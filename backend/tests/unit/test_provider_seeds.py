from __future__ import annotations

from interview_guide.common.ai.providers import static_provider_seeds


def test_only_dashscope_is_seeded_without_credentials() -> None:
    seeds = static_provider_seeds()

    assert len(seeds) == 1
    assert seeds[0].provider_id == "dashscope"
    assert seeds[0].base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert seeds[0].model == "qwen3.7-max"
    assert seeds[0].embedding_model == "qwen3.7-text-embedding"
    assert seeds[0].embedding_dimensions == 1024
    assert seeds[0].supports_embedding is True
