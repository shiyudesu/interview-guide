from __future__ import annotations

from interview_guide.modules.llm_provider.service import (
    abbreviate,
    connectivity_test_urls,
    looks_like_chat_model,
    mask_api_key,
)


def test_api_key_mask_matches_java() -> None:
    assert mask_api_key(None) == "***"
    assert mask_api_key("") == "***"
    assert mask_api_key("123456") == "***"
    assert mask_api_key("1234567") == "123***567"


def test_provider_connectivity_urls_match_java_order() -> None:
    assert connectivity_test_urls("https://example.test/v1/") == [
        "https://example.test/v1/chat/completions"
    ]
    assert connectivity_test_urls("https://example.test") == [
        "https://example.test/chat/completions",
        "https://example.test/v1/chat/completions",
    ]
    assert abbreviate("  error\nbody  ") == "error body"


def test_embedding_named_qwen_model_is_not_treated_as_chat() -> None:
    assert not looks_like_chat_model("qwen3.7-text-embedding")
    assert looks_like_chat_model("qwen3.5-plus")
